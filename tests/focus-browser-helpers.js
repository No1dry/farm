import {expect} from '@playwright/test';

export async function ready(page,{dataset='real'}={}){
 await page.goto('/');
 await expect(page.locator('#loading')).toHaveClass(/hide/,{timeout:120000});
 await expect(page.locator('#loading')).toHaveCSS('opacity','0');
 await page.waitForFunction(()=>window.farmTwin?.state.entities.length>0);
 // Legacy ledger tests explicitly opt into source data; the application itself opens demo/full.
 if(await page.evaluate(()=>window.farmTwin.state.dataset)!==dataset){
  const toggle=page.locator('#dataset-'+dataset),drawer=page.locator('[data-panel="left"]');
  const needsDrawer=!(await toggle.isVisible());
  if(needsDrawer)await drawer.click();
  await toggle.click();await page.waitForFunction(dataset=>window.farmTwin.state.dataset===dataset&&window.farmTwin.state.entities.length>0,dataset);
  if(needsDrawer)await drawer.click();
 }
}
export async function catalog(page){
 if(await page.locator('#search').isVisible())return;
 await page.locator('.scene-tag').click();await expect(page.locator('#search')).toBeVisible();
}
export async function chooseEntity(page,query){
 await catalog(page);await page.locator('#search').fill(query);await page.locator('#entity-list [data-entity]').first().click();
 await expect(page.locator('.modal-backdrop')).toHaveCount(0);
}
export async function chooseAsset(page,id){
 await catalog(page);await page.locator(`[data-asset="${id}"]`).click();
 await page.waitForFunction(id=>window.farmTwin.scene.activeAsset===id&&!window.farmTwin.scene.flight,id);
}
export async function chooseDataset(page,id){
 await catalog(page);await page.locator(`.modal-backdrop [data-dataset="${id}"]`).click();
 await page.waitForFunction(id=>window.farmTwin.state.dataset===id&&window.farmTwin.state.entities.length>0&&window.farmTwin.state.entities.every(e=>e.dataset===id),id);
}
export function gate(){let release;const promise=new Promise(resolve=>release=resolve);return{promise,release};}
