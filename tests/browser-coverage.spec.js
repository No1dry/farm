import {test,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
import {ready,chooseAsset} from './focus-browser-helpers.js';

test('all 100 ledger parcels retain source polygons and persisted IDs across five loaded Blender areas',async({page,request})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));const entities=(await (await request.get('/api/entities?dataset=real')).json()).items;
 const ledger=entities.filter(e=>e.source_key?.canonical_key?.startsWith('xls:'));expect(ledger.length).toBe(100);await ready(page);
 const drawings=await page.evaluate(()=>window.farmTwin.scene.assets.filter(a=>a.source_type==='drawing'));expect(drawings.length).toBe(5);const covered=new Set(),performance=[];
 for(const asset of drawings){
  await chooseAsset(page,asset.id);
  const result=await page.evaluate(()=>{const s=window.farmTwin.scene,nodes=[];s.activeRoot().traverse(n=>{if(n.userData.spatial_id&&n.isMesh)nodes.push(n.userData.spatial_id);});return{objects:[...s.objects.values()].filter(o=>o.asset_id===s.activeAsset),nodes,metrics:window.farmTwin.metrics()};});
  const nodeIds=new Set(result.nodes);
  for(const parcel of ledger)for(const obj of result.objects.filter(o=>parcel.spatial_ids.includes(o.spatial_id))){expect(obj.entity_uuid).toBe(parcel.id);expect(nodeIds.has(obj.spatial_id)).toBe(true);expect(obj.geometry.type).toBe('Polygon');expect(obj.model_area_m2).toBeNull();covered.add(parcel.id);}
  expect(result.metrics.triangles).toBeGreaterThan(0);performance.push(result.metrics);
  const sample=result.objects.find(o=>ledger.some(e=>e.id===o.entity_uuid));expect(sample).toBeTruthy();
  // Position the real camera without populating the profile; the mouse ray must do that.
  await page.evaluate(async id=>{const s=window.farmTwin.scene,v=await s.focusSpatial(id);s.camera.position.copy(v.position);s.controls.target.copy(v.target);s.controls.update();s.camera.updateMatrixWorld(true);await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));},sample.spatial_id);
  expect(await page.evaluate(()=>window.farmTwin.state.selected)).toBeNull();
  // A road can legitimately cross the projected parcel centre. Use the real
  // hover ray to find an exposed field surface, and exclude overlaid DOM labels.
  let pixel=null;
  const offsets=[0,-60,60,-120,120,-180,180];
  for(const dy of offsets){
   for(const dx of offsets){
    const candidate={x:800+dx,y:500+dy};
    if(!await page.evaluate(({x,y})=>document.elementFromPoint(x,y)===window.farmTwin.scene.renderer.domElement,candidate))continue;
    await page.mouse.move(candidate.x,candidate.y);
    const hover=await page.locator('#hover-tip').evaluate(el=>getComputedStyle(el).display==='none'?'':el.textContent);
    if(hover===`${sample.name||sample.spatial_id} / 来源表示`){pixel=candidate;break;}
   }
   if(pixel)break;
  }
  expect(pixel,`Visible canvas surface for ${asset.id}/${sample.spatial_id}`).toBeTruthy();
  await page.evaluate(()=>{const canvas=window.farmTwin.scene.renderer.domElement;window.__coveragePointer=null;canvas.addEventListener('pointerup',e=>{window.__coveragePointer=e.isTrusted&&e.target===canvas;},{once:true});});
  await page.mouse.click(pixel.x,pixel.y);expect(await page.evaluate(()=>window.__coveragePointer)).toBe(true);
  await expect(page.locator('#selection')).toHaveAttribute('data-entity-id',sample.entity_uuid);
  await expect(page.locator('#selection')).toContainText(ledger.find(e=>e.id===sample.entity_uuid).code);await page.screenshot({path:`deliverables/verification/${asset.id}.png`});
 }
 expect(covered.size).toBe(100);expect(errors).toEqual([]);
 await writeFile('deliverables/verification/drawing-browser-coverage.json',JSON.stringify({timestamp:new Date().toISOString(),ledgerCount:ledger.length,covered:covered.size,assets:drawings.map(a=>a.id),performance,errors},null,2));
});

test('whole-area distance LOD retains selectable identities and actual volume',async({page})=>{
 await ready(page);await chooseAsset(page,'full');await page.waitForFunction(()=>window.farmTwin.scene.lod==='overview');
 const low=await page.evaluate(()=>{const s=window.farmTwin.scene,ids=[];s.activeRoot().traverse(n=>{if(n.userData.spatial_id)ids.push(n.userData.spatial_id);});return{ids:[...new Set(ids)].sort(),metrics:window.farmTwin.metrics()};});
 await page.evaluate(()=>{const s=window.farmTwin.scene,b=s.assets.find(a=>a.id==='full').bounds,span=Math.max(b.max[0]-b.min[0],b.max[2]-b.min[2]);s.camera.position.copy(s.controls.target).add(s.camera.position.clone().set(0,span*.4,span*.2));s.controls.update();});
 await page.waitForFunction(()=>window.farmTwin.scene.lod==='detail'&&!window.farmTwin.scene.lodPending,null,{timeout:60000});
 const high=await page.evaluate(()=>{const s=window.farmTwin.scene,ids=[];s.activeRoot().traverse(n=>{if(n.userData.spatial_id)ids.push(n.userData.spatial_id);});return{ids:[...new Set(ids)].sort(),metrics:window.farmTwin.metrics()};});
 expect(high.ids).toEqual(low.ids);expect(high.metrics.triangles).toBeGreaterThan(low.metrics.triangles);
 await page.evaluate(()=>{const s=window.farmTwin.scene,b=s.assets.find(a=>a.id==='full').bounds,span=Math.max(b.max[0]-b.min[0],b.max[2]-b.min[2]);s.camera.position.copy(s.controls.target).add(s.camera.position.clone().set(0,span*1.5,span));s.controls.update();});await page.waitForFunction(()=>window.farmTwin.scene.lod==='overview'&&!window.farmTwin.scene.lodPending);
 await writeFile('deliverables/verification/lod-browser-performance.json',JSON.stringify({timestamp:new Date().toISOString(),overview:low.metrics,detail:high.metrics,identicalIdentityCount:high.ids.length},null,2));
});

test('a repeated drawing code requires an explicit choice without changing the current parcel',async({page})=>{
 await ready(page);const original=await page.evaluate(()=>window.farmTwin.state.selected?.id);
 await page.locator('#assistant-toggle').click();await page.locator('#chat-input').fill('进入 E3 田块');await page.locator('#send').click();await expect(page.locator('#messages .answer')).toContainText('歧义');
 const reply=await page.evaluate(()=>window.farmTwin.state.lastReply);expect(reply.status).toBe('needs_clarification');expect(reply.candidates.length).toBeGreaterThan(1);expect(reply.actions).toEqual([]);expect(new Set(reply.candidates.map(e=>e.id)).size).toBe(reply.candidates.length);
 expect(await page.evaluate(()=>window.farmTwin.state.selected?.id)).toBe(original);const ledger=reply.candidates.find(e=>e.source_key.canonical_key.startsWith('xls:'));expect(ledger).toBeTruthy();
 await page.locator(`[data-candidate="${ledger.id}"]`).click();await page.waitForFunction(id=>window.farmTwin.state.selected?.id===id,ledger.id);await expect(page.locator('#selection')).toContainText('E3');
});
