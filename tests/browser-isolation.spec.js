import {test,expect} from '@playwright/test';
import {ready,catalog,chooseEntity,chooseDataset,gate} from './focus-browser-helpers.js';

async function openRealParcel(page){await ready(page);await chooseEntity(page,'L18');await expect(page.locator('#selection')).toContainText('L18');return page.evaluate(()=>window.farmTwin.state.selected);}
async function expectNoRealContext(page){
 await expect(page.locator('#context')).toHaveText('当前未选中对象');await expect(page.locator('#selection')).not.toContainText('L18');await expect(page.locator('#messages')).not.toContainText('回归延迟回答');
 expect(await page.evaluate(()=>({selected:window.farmTwin.state.selected,history:window.farmTwin.state.history}))).toEqual({selected:null,history:[]});
}
test('a delayed demo load clears real rows and context before the response arrives',async({page})=>{
 const real=await openRealParcel(page),entered=gate(),delayed=gate();await page.route('**/api/entities?dataset=demo*',async route=>{entered.release();await delayed.promise;await route.continue();});
 try{await catalog(page);await page.locator('[data-dataset="demo"]').click();await entered.promise;
  await expect(page.locator('#entity-list [data-entity]')).toHaveCount(0);await expect(page.locator(`#entity-list [data-entity="${real.id}"]`)).toHaveCount(0);await expectNoRealContext(page);expect(await page.evaluate(()=>window.farmTwin.state.entities)).toEqual([]);
  delayed.release();await expect(page.locator('#catalog-dataset')).toContainText('合成演示');expect(await page.evaluate(()=>window.farmTwin.state.entities.every(e=>e.dataset==='demo'))).toBe(true);
 }finally{delayed.release();}
});
test('a failed demo query cannot leave real rows under the demo context',async({page})=>{
 await openRealParcel(page);const entered=gate(),delayed=gate();await page.route('**/api/entities?dataset=demo*',async route=>{entered.release();await delayed.promise;await route.fulfill({status:503,json:{detail:'回归测试：演示查询不可用'}});});
 try{await catalog(page);await page.locator('[data-dataset="demo"]').click();await entered.promise;await expect(page.locator('#entity-list [data-entity]')).toHaveCount(0);delayed.release();await expect(page.locator('#model-status')).toHaveText('数据库未连接');await expect(page.locator('#entity-list [data-entity]')).toHaveCount(0);await expectNoRealContext(page);expect(await page.evaluate(()=>window.farmTwin.state.entities)).toEqual([]);}finally{delayed.release();}
});
const delayedReply=entity=>({status:'ok',answer:'回归延迟回答：资料L18',entity,candidates:[],evidence:entity.sources,gaps:[],actions:[{type:'focus_entity',entity_id:entity.id}],suggested_plan:null,model:{configured:true,provider:'test-boundary'},audit_id:'test-only-response'});
async function recordFocusCalls(page){await page.evaluate(()=>{window.__isolationActions=[];const s=window.farmTwin.scene,focus=s.focusSpatial.bind(s);s.focusSpatial=id=>{window.__isolationActions.push(id);return focus(id);};});}
test('an assistant reply after dataset change cannot restore real context or focus',async({page})=>{
 const entity=await openRealParcel(page);await recordFocusCalls(page);const entered=gate(),delayed=gate();await page.route('**/api/assistant',async route=>{entered.release();await delayed.promise;await route.fulfill({json:delayedReply(entity)});});
 try{await page.locator('#assistant-toggle').click();await page.locator('#chat-input').fill('介绍当前L18');await page.locator('#send').click();await entered.promise;await chooseDataset(page,'demo');delayed.release();await expect(page.locator('#send')).toBeEnabled();await expectNoRealContext(page);expect(await page.evaluate(()=>window.__isolationActions)).toEqual([]);expect(await page.evaluate(()=>window.farmTwin.state.lastReply)).toBeNull();}finally{delayed.release();}
});
test('dataset change during assistant entity lookup suppresses previously received actions',async({page})=>{
 const entity=await openRealParcel(page);await recordFocusCalls(page);const entered=gate(),delayed=gate();await page.route(`**/api/entities/${entity.id}?dataset=real`,async route=>{entered.release();await delayed.promise;await route.fulfill({json:entity});});await page.route('**/api/assistant',route=>route.fulfill({json:delayedReply(entity)}));
 try{await page.locator('#assistant-toggle').click();await page.locator('#chat-input').fill('进入当前L18');await page.locator('#send').click();await entered.promise;await chooseDataset(page,'demo');delayed.release();await expect(page.locator('#send')).toBeEnabled();await expectNoRealContext(page);expect(await page.evaluate(()=>window.__isolationActions)).toEqual([]);}finally{delayed.release();}
});
