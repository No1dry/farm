import test from 'node:test';
import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
import {writeFile} from 'node:fs/promises';

async function harness(run,{setup,ready}={}){
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--enable-webgl','--ignore-gpu-blocklist']});
 try{const page=await browser.newPage({viewport:{width:1600,height:1000}});if(setup)await setup(page);await page.goto(process.env.FARM_TEST_BASE_URL||'http://127.0.0.1:5174');await page.waitForFunction(ready||(()=>window.farmTwin?.state.selected),undefined,{timeout:120000});await run(page);}finally{await browser.close();}
}
test('dataset switch releases the send button while the old assistant request remains pending',()=>harness(async page=>{
 let release;const pending=new Promise(r=>release=r);await page.route('**/api/assistant',async route=>{await pending;await route.fulfill({json:{status:'not_found',answer:'old dataset reply',actions:[]}});});
 await page.locator('#assistant-toggle').click();await page.locator('#chat-input').fill('query');await page.locator('#send').click();await page.waitForFunction(()=>document.querySelector('#send').disabled);
 await page.locator('.scene-tag').click();await page.locator('.modal-backdrop [data-dataset="real"]').click();await page.waitForFunction(()=>window.farmTwin.state.dataset==='real');
 const disabled=await page.locator('#send').isDisabled();release();assert.equal(disabled,false);
}),{timeout:150000});
test('manual camera navigation during assistant entity hydration prevents a late focus action',()=>harness(async page=>{
 const id=await page.evaluate(()=>window.farmTwin.state.selected.id);let release,started;const pending=new Promise(r=>release=r),hydrating=new Promise(r=>started=r);
 await page.route('**/api/assistant',route=>route.fulfill({json:{status:'unconfigured',answer:'database result',entity:{id},actions:[{type:'focus_entity',entity_id:id}]}}));
 await page.route(`**/api/entities/${id}?*`,async route=>{const response=await route.fetch();started();await pending;await route.fulfill({response});});
 await page.locator('#assistant-toggle').click();await page.locator('#chat-input').fill('query');await page.locator('#send').click();await hydrating;
 const navigation=await page.evaluate(()=>{window.farmTwin.scene.controls.dispatchEvent({type:'start'});return window.farmTwin.scene.navigationVersion;});release();
 await page.waitForFunction(()=>!document.querySelector('#send').disabled);assert.equal(await page.evaluate(()=>window.farmTwin.scene.navigationVersion),navigation);
}),{timeout:150000});
test('asset selection clears the displayed business context immediately',()=>harness(async page=>{
 await page.locator('.scene-tag').click();await page.locator('[data-asset="full"]').click();assert.equal(await page.evaluate(()=>window.farmTwin.state.selected),null);assert.equal(await page.locator('#context').textContent(),'当前未选中对象');
}),{timeout:150000});
test('real ledger search preserves source-asset navigation and the unconfirmed area unit',()=>harness(async page=>{
 await page.locator('#dataset-real').click();await page.waitForFunction(()=>window.farmTwin.state.dataset==='real'&&window.farmTwin.state.entities.length);await page.locator('.scene-tag').click();await page.locator('#search').fill('L19');await page.locator('.modal-backdrop [data-entity]').first().click();
 await page.waitForFunction(()=>window.farmTwin.state.selected?.code==='L19'&&window.farmTwin.scene.activeAsset==='detail-miaoxia');assert.match(await page.locator('#selection').textContent(),/原表单位未注/);
}),{timeout:150000});
test('late local authentication cannot replace an object selected during initialization',async()=>{
 let release;const pending=new Promise(resolve=>release=resolve);
 await harness(async page=>{
  await page.waitForFunction(()=>!window.farmTwin.scene.flight);await page.waitForTimeout(150);const marker=page.locator('[data-scene-entity][data-kind="pond"]:visible').first(),id=await marker.getAttribute('data-scene-entity');await marker.click();await page.waitForFunction(id=>window.farmTwin.state.selected?.id===id,id);release();await page.waitForFunction(()=>window.farmTwin.state.canSave);await page.waitForTimeout(350);assert.equal(await page.evaluate(()=>window.farmTwin.state.selected?.id),id);
 },{setup:page=>page.route('**/api/auth/local-session',async route=>{await pending;await route.fulfill({json:{actor:{role:'operator'}}});}),ready:()=>window.farmTwin?.state.entities.length});
},{timeout:150000});
test('selecting an unbound object cancels a pending asset navigation',()=>harness(async page=>{
 let release,started;const pending=new Promise(resolve=>release=resolve),loading=new Promise(resolve=>started=resolve);
 const url=await page.evaluate(()=>window.farmTwin.scene.assets.find(a=>a.id==='detail-miaoxia').url);await page.route('**'+url+'*',async route=>{started();await pending;await route.continue();});
 await page.locator('.scene-tag').click();await page.locator('[data-asset="detail-miaoxia"]').click();await loading;await page.evaluate(()=>window.farmTwin.selectSpatial('L18',{navigate:false}));release();await page.waitForFunction(()=>window.farmTwin.scene.pending.size===0);assert.equal(await page.evaluate(()=>window.farmTwin.scene.activeAsset),'full');assert.equal(await page.evaluate(()=>window.farmTwin.state.selected),null);
}),{timeout:150000});
test('database text in the original details modal is rendered as text rather than markup',()=>harness(async page=>{
 const id=await page.evaluate(()=>window.farmTwin.state.selected.id);await page.route(`**/api/entities/${id}?*`,async route=>{const response=await route.fetch(),entity=await response.json();entity.region='<em data-untrusted>untrusted</em>';await route.fulfill({json:entity});});
 await page.evaluate(id=>window.farmTwin.selectEntity(id,{navigate:false}),id);await page.locator('#profile-details').click();assert.equal(await page.locator('#dialog-title [data-untrusted]').count(),0);assert.match(await page.locator('#dialog-title').textContent(),/<em data-untrusted>/);
}),{timeout:150000});
test('fullscreen catalog and original photo modal remain inside the visible fullscreen layer',()=>harness(async page=>{
 await page.locator('#fullscreen').click();await page.waitForFunction(()=>document.fullscreenElement);await page.locator('.scene-tag').click();
 const visible=await page.evaluate(()=>{const search=document.querySelector('#search'),rect=search.getBoundingClientRect();return document.fullscreenElement.contains(search)&&document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2)===search;});assert.equal(visible,true);
 await page.locator('#search').fill('L18');await page.locator('.modal-close').click();await page.locator('#open-photo').click();assert.equal(await page.evaluate(()=>document.fullscreenElement.contains(document.querySelector('.photo-large'))),true);await page.locator('.modal-close').click();await page.locator('#fullscreen').click();
}),{timeout:150000});
test('a demo not-found reply offers an explicit switch to real L18 instead of fabricating a binding',()=>harness(async page=>{
 await page.route('**/api/assistant',route=>route.fulfill({json:{status:'not_found',answer:'演示中没有该实体',actions:[]}}));
 await page.locator('#assistant-toggle').click();await page.locator('#chat-input').fill('进入庙下刘L18');await page.locator('#send').click();await page.locator('[data-search-real]').click();await page.waitForFunction(()=>window.farmTwin.state.dataset==='real');assert.equal(await page.locator('#search').inputValue(),'L18');await page.locator('.modal-backdrop [data-entity]').first().click();await page.waitForFunction(()=>window.farmTwin.state.selected?.code==='L18');assert.equal(await page.evaluate(()=>window.farmTwin.state.selected.dataset),'real');
}),{timeout:150000});
test('late relation graphs cannot restore demo lines after a real-data switch',()=>harness(async page=>{
 const device=await page.evaluate(()=>window.farmTwin.state.entities.find(e=>e.kind==='device'&&e.scene_anchor)?.id);let release,started;const pending=new Promise(resolve=>release=resolve),loading=new Promise(resolve=>started=resolve);
 await page.route(`**/api/relations/${device}?*`,async route=>{const response=await route.fetch();started();await pending;await route.fulfill({response});});
 await page.evaluate(id=>window.farmTwin.selectEntity(id,{navigate:false}),device);await loading;await page.locator('#dataset-real').click();await page.waitForFunction(()=>window.farmTwin.state.dataset==='real'&&window.farmTwin.state.entities.length);release();await page.waitForTimeout(250);
 assert.equal(await page.evaluate(()=>window.farmTwin.state.relations),null);assert.equal(await page.evaluate(()=>window.farmTwin.scene.relationshipLines.children.length),0);
}),{timeout:150000});

test('a failed relation lookup is visibly unavailable rather than claiming there are no relations',()=>harness(async page=>{
 const id=await page.evaluate(()=>window.farmTwin.state.selected.id);await page.route(`**/api/relations/${id}?*`,route=>route.fulfill({status:503,json:{detail:'Unavailable'}}));await page.evaluate(id=>window.farmTwin.selectEntity(id,{navigate:false}),id);await page.waitForFunction(()=>document.querySelector('#scene-relations').textContent.includes('暂不可用'),undefined,{timeout:4000});assert.match(await page.locator('#scene-relations').textContent(),/暂不可用/);
}),{timeout:150000});

test('a selected pond shows its incoming sensor relation in subject-predicate-object order',()=>harness(async page=>{
 const pair=await page.evaluate(()=>{const entities=window.farmTwin.state.entities,device=entities.find(e=>e.kind==='device'&&e.scene_anchor?.spatial_id==='SAT-POND-001'&&e.relations.some(r=>r.predicate_iri.endsWith('/monitors'))),edge=device.relations.find(r=>r.predicate_iri.endsWith('/monitors')),pond=entities.find(e=>e.id===edge.target_id);return{device,edge,pond};});
 await page.evaluate(id=>window.farmTwin.selectEntity(id,{navigate:false}),pair.pond.id);const row=page.locator(`[data-relation-id="${pair.edge.id}"]`);await row.waitFor({state:'visible'});const text=await row.textContent(),short=name=>name.replace(/\s*·\s*演示$/,'');assert.equal(text,`${short(pair.device.name)} → 监测 → ${short(pair.pond.name)} · 演示`);assert.equal(await row.getAttribute('data-related-entity'),pair.device.id);
 await page.waitForFunction(()=>getComputedStyle(document.querySelector('#loading')).opacity==='0'&&!window.farmTwin.scene.flight);await page.screenshot({path:'deliverables/verification/ontology-incoming-relation.png'});await writeFile('deliverables/verification/ontology-incoming-relation.json',JSON.stringify({selected_id:pair.pond.id,subject_id:pair.edge.subject_id,predicate_iri:pair.edge.predicate_iri,target_id:pair.edge.target_id,dom_text:text},null,2));await row.click();await page.waitForFunction(id=>window.farmTwin.state.selected?.id===id,pair.device.id);
}),{timeout:150000});
