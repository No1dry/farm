import {test,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
import {ready,chooseEntity,chooseAsset,chooseDataset} from './focus-browser-helpers.js';

test('Blender assets, persisted parcel and actual model focus run inside the restored dashboard',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));await ready(page);
 expect(await page.evaluate(()=>window.farmTwin.scene.objects.size)).toBeGreaterThan(100);
 await chooseEntity(page,'L18');await expect(page.locator('#selection')).toContainText('L18');await expect(page.locator('#selection')).toContainText('单位未注');
 expect(await page.evaluate(()=>window.farmTwin.state.canSave)).toBe(true);const id=await page.evaluate(()=>window.farmTwin.state.selected.id);
 await page.locator('#assistant-toggle').click();await page.locator('#chat-input').fill('进入庙下刘片区的 L18 田块，介绍一下这块田');await page.locator('#send').click();
 await expect(page.locator('#messages .answer')).toContainText('模型回答',{timeout:120000});await page.waitForFunction(()=>!document.querySelector('#send').disabled&&!window.farmTwin.scene.flight);
 expect(await page.evaluate(()=>window.farmTwin.state.lastReply.entity.id)).toBe(id);expect(await page.evaluate(()=>window.farmTwin.state.lastReply.model.actual_inference)).toBe(true);expect(await page.evaluate(()=>window.farmTwin.state.lastReply.model.usage.completion_tokens)).toBeGreaterThan(0);
 expect(await page.evaluate(()=>window.farmTwin.scene.activeAsset)).toBe('detail-miaoxia');await page.screenshot({path:'deliverables/verification/parcel-assistant.png'});
 await page.locator('#assistant-close').click();await chooseAsset(page,'full');await page.waitForFunction(()=>window.farmTwin.metrics().samples>=120);
 const metrics=await page.evaluate(()=>window.farmTwin.metrics());expect(metrics.triangles).toBeGreaterThan(0);
 await writeFile('deliverables/verification/browser-performance.json',JSON.stringify({timestamp:new Date().toISOString(),browser:await page.evaluate(()=>navigator.userAgent),metrics,errors},null,2));await page.screenshot({path:'deliverables/verification/full-area.png'});
 await chooseDataset(page,'demo');expect(await page.evaluate(()=>window.farmTwin.state.selected)).toBeNull();expect(await page.evaluate(()=>window.farmTwin.state.entities.every(e=>e.dataset==='demo'))).toBe(true);expect(errors).toEqual([]);
});

test('small viewport keeps the added assistant reachable without replacing panel drawers',async({page})=>{
 await page.setViewportSize({width:760,height:850});await ready(page);await page.locator('#assistant-toggle').click();await expect(page.locator('#chat-input')).toBeVisible();await expect(page.locator('#send')).toBeVisible();await page.screenshot({path:'deliverables/verification/narrow-layout.png'});
});

test('historical demo warning queries evidence and saves only an explicit draft',async({page,request})=>{
 await ready(page);await chooseDataset(page,'demo');const entities=(await (await request.get('/api/entities?dataset=demo')).json()).items;const pond=entities.find(e=>e.kind==='pond'&&e.code?.startsWith('DEMO-POND-')&&e.observations?.some(o=>o.id==='demo-oxygen-20260115'));expect(pond).toBeTruthy();
 await page.locator('#search').fill(pond.code);
 await page.locator(`#entity-list [data-entity="${pond.id}"]`).click();await page.waitForFunction(id=>window.farmTwin.state.selected?.id===id,pond.id);
 await page.locator('#assistant-toggle').click();await page.locator('#chat-input').fill('分析当前水塘的缺氧预警，核查观测时间、设备及知识依据，给出适合已有证据的处置核查方案');await page.locator('#send').click();
 await expect(page.locator('#messages .answer')).toContainText('模型回答',{timeout:120000});await expect(page.locator('#messages .answer')).toContainText('过期');await expect(page.locator('#messages .answer')).toContainText('未执行');
 const before=(await (await request.get('/api/plans?dataset=demo')).json()).items.length;await page.locator('[data-save-plan]').click();await expect(page.locator('[data-save-plan]')).toContainText('已保存');
 const plans=(await (await request.get('/api/plans?dataset=demo')).json()).items;expect(plans.length).toBe(before+1);expect(plans[0].entity_id).toBe(pond.id);expect(plans[0].device_control).toBe(false);await page.screenshot({path:'deliverables/verification/demo-warning-inspection.png'});
});

test('raycasting an actual Blender parcel loads its persisted identity',async({page})=>{
 await ready(page);await chooseEntity(page,'L18');await expect(page.locator('#selection')).toContainText('L18');await page.waitForFunction(()=>!window.farmTwin.scene.flight);
 await page.evaluate(async()=>{const s=window.farmTwin.scene,v=await s.focusSpatial('DETAIL-L19');s.camera.position.copy(v.position);s.controls.target.copy(v.target);s.controls.update();s.camera.updateMatrixWorld(true);await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
 expect(await page.evaluate(()=>window.farmTwin.state.selected?.code)).toBe('L18');
 const hit=await page.evaluate(()=>{const s=window.farmTwin.scene,selection=s.selections.get('DETAIL-L19'),point=selection.point.clone().project(s.camera);return{x:(point.x+1)*innerWidth/2,y:(1-point.y)*innerHeight/2,id:s.objects.get('DETAIL-L19').entity_uuid};});
 expect(hit.x).toBeGreaterThan(303);expect(hit.x).toBeLessThan(1297);await page.mouse.click(hit.x,hit.y);await expect(page.locator('#selection')).toContainText('L19');expect(await page.evaluate(()=>window.farmTwin.state.selected?.id)).toBe(hit.id);
});
