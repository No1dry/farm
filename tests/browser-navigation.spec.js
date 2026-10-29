import {test,expect} from '@playwright/test';
import {ready,catalog,chooseEntity,chooseAsset,gate} from './focus-browser-helpers.js';

test('an explicit area change remains authoritative when an earlier entity lookup finishes later',async({page,request})=>{
 await ready(page);const items=(await (await request.get('/api/entities?dataset=real')).json()).items,parcel=items.find(e=>e.code==='L18'&&e.area.value!=null),entered=gate(),delayed=gate();
 await page.route(`**/api/entities/${parcel.id}?dataset=real`,async route=>{entered.release();await delayed.promise;await route.continue();});
 try{await chooseEntity(page,'L18');await entered.promise;await chooseAsset(page,'full');delayed.release();await page.waitForFunction(()=>window.farmTwin.scene.pending.size===0);
  await expect.poll(()=>page.evaluate(()=>({asset:window.farmTwin.scene.activeAsset,selected:window.farmTwin.scene.selectedID}))).toEqual({asset:'full',selected:null});
 }finally{delayed.release();}
});
async function delayedParcel(page){
 await ready(page);const entered=gate(),delayed=gate();await page.route('**/models/detail-abcdef.glb*',async route=>{entered.release();await delayed.promise;await route.continue();});
 await chooseEntity(page,'F5-1');await entered.promise;return delayed;
}
test('changing area cancels an older parcel GLB load and local-coordinate flight',async({page})=>{
 const delayed=await delayedParcel(page);
 try{await chooseAsset(page,'full');const target=await page.evaluate(()=>window.farmTwin.scene.controls.target.toArray().map(v=>+v.toFixed(6)));delayed.release();await page.waitForFunction(()=>window.farmTwin.scene.pending.size===0);
  await expect.poll(()=>page.evaluate(()=>({asset:window.farmTwin.scene.activeAsset,selected:window.farmTwin.scene.selectedID,target:window.farmTwin.scene.controls.target.toArray().map(v=>+v.toFixed(6)),flight:!!window.farmTwin.scene.flight}))).toEqual({asset:'full',selected:null,target,flight:false});
 }finally{delayed.release();}
});
test('an older assistant reply cannot replace a newer user-selected parcel',async({page,request})=>{
 await ready(page);const items=(await (await request.get('/api/entities?dataset=real')).json()).items,old=items.find(e=>e.code==='L18'&&e.area.value!=null),next=items.find(e=>e.code==='L19'&&e.area.value!=null),entered=gate(),delayed=gate();
 await page.route('**/api/assistant',async route=>{entered.release();await delayed.promise;await route.fulfill({json:{status:'ok',answer:'回归延迟回答：L18资料',entity:old,evidence:old.sources,gaps:[],actions:[{type:'focus_entity',entity_id:old.id}],model:{configured:true}}});});
 try{await chooseEntity(page,'L18');await expect(page.locator('#selection')).toContainText('L18');await page.locator('#assistant-toggle').click();await page.locator('#chat-input').fill('介绍 L18');await page.locator('#send').click();await entered.promise;await chooseEntity(page,'L19');await page.waitForFunction(id=>window.farmTwin.state.selected?.id===id,next.id);delayed.release();await expect(page.locator('#messages .answer')).toContainText('回归延迟回答');await expect(page.locator('#send')).toBeEnabled();expect(await page.evaluate(()=>window.farmTwin.state.selected?.id)).toBe(next.id);await expect(page.locator('#context')).toContainText('L19');}finally{delayed.release();}
});
test('selecting a full-area object cancels an older pending drawing selection',async({page})=>{
 const delayed=await delayedParcel(page);
 try{await chooseEntity(page,'SAT-FIELD-001');await page.waitForFunction(()=>window.farmTwin.scene.selectedID==='SAT-FIELD-001'&&!window.farmTwin.scene.flight);delayed.release();await page.waitForFunction(()=>window.farmTwin.scene.pending.size===0);
  await expect.poll(()=>page.evaluate(()=>({asset:window.farmTwin.scene.activeAsset,selected:window.farmTwin.scene.selectedID}))).toEqual({asset:'full',selected:'SAT-FIELD-001'});
 }finally{delayed.release();}
});
