import {test,expect} from '@playwright/test';

async function fullReady(page){
 await page.goto('/');
 await expect(page.locator('#loading')).toHaveClass(/hide/,{timeout:120000});
 await expect(page.locator('#loading')).toHaveCSS('opacity','0');
 await page.waitForFunction(()=>window.farmTwin?.state.entities.length>0);
}

test('first opening presents the whole satellite region and explicitly marked ontology scenario',async({page})=>{
 await fullReady(page);
 const state=await page.evaluate(()=>({asset:window.farmTwin.scene.activeAsset,dataset:window.farmTwin.state.dataset,entities:window.farmTwin.state.entities}));
 expect(state.asset).toBe('full');
 expect(state.dataset).toBe('demo');
 expect(state.entities.filter(e=>e.spatial_ids?.some(id=>id.startsWith('SAT-'))).length).toBeGreaterThanOrEqual(121);
 await expect(page.locator('.status-left')).toContainText(/演示|样例/);
 const labels=page.locator('[data-scene-entity]:visible');
 expect(await labels.count()).toBeGreaterThanOrEqual(3);
 await expect(page.locator('.scope-stats')).not.toContainText('样板');
});

test('an on-map ontology label opens its persisted UUID, sources and relations',async({page,request})=>{
 await fullReady(page);
 await page.waitForFunction(()=>!window.farmTwin.scene.flight);
 const label=page.locator('[data-scene-entity]:visible').first();
 const id=await label.getAttribute('data-scene-entity');
 expect(id).toMatch(/^[0-9a-f-]{36}$/i);
 const response=await request.get(`/api/entities/${id}?dataset=demo`);expect(response.ok()).toBe(true);
 const entity=await response.json();
 await label.click();
 await expect(page.locator('#selection')).toHaveAttribute('data-entity-id',id);
 await expect(page.locator('#selection')).toContainText('演示');
 await expect(page.locator('#selection')).toContainText(id);
 expect(await page.evaluate(()=>window.farmTwin.state.selected.id)).toBe(entity.id);
 await expect(page.locator('#scene-relations')).toBeVisible();
});

test('whole-region sample placement never writes its species, sensors or observations into real records',async({page,request})=>{
 await fullReady(page);
 const demo=(await (await request.get('/api/entities?dataset=demo&limit=1000')).json()).items;
 const real=(await (await request.get('/api/entities?dataset=real&limit=1000')).json()).items;
 const realBySpatial=new Map(real.flatMap(e=>(e.spatial_ids||[]).map(sid=>[sid,e])));
 const placed=demo.filter(e=>e.spatial_ids?.some(sid=>sid.startsWith('SAT-')));
 expect(placed.length).toBeGreaterThanOrEqual(121);
 for(const entity of placed){
  expect(entity.dataset).toBe('demo');
  const counterpart=realBySpatial.get(entity.spatial_ids.find(sid=>sid.startsWith('SAT-')));
  expect(counterpart).toBeTruthy();expect(counterpart.id).not.toBe(entity.id);
  expect(counterpart.dataset).toBe('real');expect(counterpart.observations||[]).toHaveLength(0);
  expect(counterpart.devices||[]).toHaveLength(0);expect(counterpart.species||null).toBeNull();
 }
 await page.locator('#dataset-real').click();
 await page.waitForFunction(()=>window.farmTwin.state.dataset==='real'&&window.farmTwin.state.entities.length>0&&window.farmTwin.state.entities.every(e=>e.dataset==='real'));
 await expect(page.locator('[data-scene-entity][data-dataset="demo"]')).toHaveCount(0);
 await page.locator('#dataset-demo').click();
 await page.waitForFunction(()=>window.farmTwin.state.dataset==='demo'&&window.farmTwin.state.entities.length>0&&window.farmTwin.state.entities.every(e=>e.dataset==='demo'));
 await expect.poll(()=>page.locator('[data-scene-entity][data-dataset="demo"]:visible').count()).toBeGreaterThan(0);
});

test('clicking a device on the map queries its own ontology identity and connected object',async({page,request})=>{
 await fullReady(page);await page.waitForFunction(()=>!window.farmTwin.scene.flight);
 const label=page.locator('[data-scene-entity][data-kind="device"]:visible').first();
 await expect(label).toBeVisible();const id=await label.getAttribute('data-scene-entity');
 const entity=await (await request.get(`/api/entities/${id}?dataset=demo`)).json();
 expect(entity.kind).toBe('device');expect(entity.scene_anchor.role).toBe('device');
 await label.click();await expect(page.locator('#selection')).toHaveAttribute('data-entity-id',id);
 await expect(page.locator('#selection')).toContainText('设备');await expect(page.locator('#selection')).toContainText(id);
 await expect.poll(()=>page.locator('#scene-relations [data-relation-id]').count()).toBeGreaterThan(0);
 await expect.poll(()=>page.evaluate(()=>window.farmTwin.scene.relationshipLines.children.length)).toBeGreaterThan(0);
 expect(await page.evaluate(()=>window.farmTwin.scene.activeAsset)).toBe('full');
 await expect(page.locator('.monitor-status')).toContainText(/演示|合成/);
});

test('a whole-region pond warning reaches the actual model with its ontology and sample evidence',async({page,request})=>{
 await fullReady(page);
 const entities=(await (await request.get('/api/entities?dataset=demo&limit=1000')).json()).items;
 const pond=entities.find(e=>e.kind==='pond'&&e.scenario?.id==='full-area-demo-v1'&&e.business_alerts?.some(a=>a.condition_historically_met));
 expect(pond).toBeTruthy();
 await page.evaluate(id=>window.farmTwin.selectEntity(id),pond.id);
 await expect(page.locator('#selection')).toHaveAttribute('data-entity-id',pond.id);
 await expect(page.locator('#scene-relations')).toContainText(/演示|样例/);
 await page.locator('#assistant-toggle').click();
 await page.locator('#chat-input').fill('分析当前演示水塘的预警，核查本体关联设备、观测与来源，给出有证据的核查处置方案；明确这是样例，不能执行现场设备操作。');
 await page.locator('#send').click();
 await expect(page.locator('#messages .answer')).toContainText('模型回答',{timeout:120000});
 await page.waitForFunction(()=>!document.querySelector('#send').disabled);
 const result=await page.evaluate(()=>window.farmTwin.state.lastReply);
 expect(result.entity.id).toBe(pond.id);expect(result.model.actual_inference).toBe(true);
 expect(result.analysis_sections).toHaveLength(7);expect(result.evidence.length).toBeGreaterThan(0);
 expect(result.production_plan_accepted).toBe(false);
 expect((result.actions||[]).every(action=>action.type==='focus_entity')).toBe(true);
 expect(await page.evaluate(()=>window.farmTwin.scene.activeAsset)).toBe('full');
});

test('a physical Blender device mesh selects the device UUID rather than its parent plot',async({page,request})=>{
 await fullReady(page);
 const entities=(await (await request.get('/api/entities?dataset=demo&limit=1000')).json()).items;
 const device=entities.find(e=>e.kind==='device'&&e.scenario?.id==='full-area-demo-v1'&&e.scenario_properties?.device_key==='SAT-POND-001:sensor');
 expect(device).toBeTruthy();
 await page.evaluate(id=>window.farmTwin.selectEntity(id),device.id);
 await page.waitForFunction(()=>!window.farmTwin.scene.flight&&!window.farmTwin.scene.pending.size&&!window.farmTwin.scene.lodPending&&window.farmTwin.scene.lod==='detail',null,{timeout:120000});
 const placement=await page.evaluate(id=>{
  const s=window.farmTwin.scene,meshes=s.selectables.filter(m=>s.entityForMesh(m)?.id===id);
  if(!meshes.length)throw Error('No active, identity-bound Blender device mesh');
  const mesh=meshes.sort((a,b)=>b.geometry.attributes.position.count-a.geometry.attributes.position.count)[0];
  mesh.geometry.computeBoundingBox();const point=mesh.geometry.boundingBox.getCenter(s.camera.position.clone());mesh.localToWorld(point);
  s.flight=null;s.cancelNavigation();s.controls.target.copy(point);s.camera.position.copy(point).add(s.camera.position.clone().set(-12,9,17));s.controls.update();s.camera.updateMatrixWorld();
  return {point:point.toArray(),mesh:mesh.name,device_key:deviceKey(mesh),mesh_count:meshes.length};
  function deviceKey(node){for(let n=node;n;n=n.parent)if(n.userData.scene_device_key)return n.userData.scene_device_key;}
 },device.id);
 expect(placement.device_key).toBe('SAT-POND-001:sensor');
 const parent=entities.find(e=>e.spatial_ids?.includes('SAT-POND-001'));
 await page.evaluate(id=>window.farmTwin.selectEntity(id,{navigate:false}),parent.id);
 await expect(page.locator('#selection')).toHaveAttribute('data-entity-id',parent.id);
 // Wait for the real render matrix; the click below targets canvas geometry, not a DOM label.
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const pixel=await page.evaluate(point=>{const s=window.farmTwin.scene,p=s.camera.position.clone().fromArray(point).project(s.camera),r=s.renderer.domElement.getBoundingClientRect();return{x:r.left+(p.x+1)*r.width/2,y:r.top+(1-p.y)*r.height/2};},placement.point);
 const canvasTarget=await page.evaluate(({x,y})=>{
  const canvas=window.farmTwin.scene.renderer.domElement;
  window.__physicalDevicePointer=null;
  canvas.addEventListener('pointerup',event=>{window.__physicalDevicePointer={trusted:event.isTrusted,targetCanvas:event.target===canvas};},{once:true});
  return document.elementFromPoint(x,y)===canvas;
 },pixel);
 expect(canvasTarget,'A DOM marker must not substitute for the physical mesh click').toBe(true);
 await page.mouse.click(pixel.x,pixel.y);
 expect(await page.evaluate(()=>window.__physicalDevicePointer)).toEqual({trusted:true,targetCanvas:true});
 await expect(page.locator('#selection')).toHaveAttribute('data-entity-id',device.id);
 await expect(page.locator('#selection')).toContainText(device.id);
 await page.screenshot({path:'deliverables/verification/full-region-device-mesh.png'});
});
