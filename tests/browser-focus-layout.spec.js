import {test, expect} from '@playwright/test';
import {readFile, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

test('restored dashboard retains the original frame, panel grouping and stylesheet', async ({page}) => {
 const baseline=JSON.parse(await readFile('deliverables/verification/focus-restore/original-layout.json','utf8'));
 const css=await readFile('src/focus/style.css');
 expect(createHash('sha256').update(css).digest('hex')).toBe(baseline.styleSHA256);
 await page.goto('/');
 await expect(page.locator('.screen-header')).toBeVisible({timeout:10000});
 await expect(page.locator('#loading')).toHaveClass(/hide/,{timeout:120000});
 await expect(page.locator('#loading')).toHaveCSS('opacity','0');
 expect(await page.locator('.left-side .panel-head h2').allTextContents()).toEqual(['全域空间与本体','地块档案','全域数据档案']);
 expect(await page.locator('.right-side .panel-head h2').allTextContents()).toEqual(['环境与水情','对象关系与预警','现场影像资料']);
 expect(await page.locator('.bottom-nav .view-tab').allTextContents()).toEqual(['片区总览','农田近景','沟渠细节','水塘岸线']);
 const current=await page.evaluate(selectors=>Object.fromEntries(selectors.map(selector=>{
  const node=document.querySelector(selector),rect=node.getBoundingClientRect();
  return [selector,{x:rect.x,y:rect.y,width:rect.width,height:rect.height,display:getComputedStyle(node).display}];
 })),Object.keys(baseline.layout));
 for(const [selector,expected]of Object.entries(baseline.layout)){
  expect(current[selector].display,selector).toBe(expected.display);
  for(const axis of ['x','y','width','height'])expect(Math.abs(current[selector][axis]-expected[axis]),`${selector} ${axis}`).toBeLessThanOrEqual(1);
 }
 await writeFile('deliverables/verification/focus-restore/layout-comparison.json',JSON.stringify({timestamp:new Date().toISOString(),baseline:baseline.layout,current,styleSHA256:baseline.styleSHA256},null,2));
 await page.screenshot({path:'deliverables/verification/focus-restore/restored-desktop.png'});
});

test('original photo viewer, four camera controls and narrow-screen panel drawers remain usable',async({page})=>{
 await page.goto('/');await expect(page.locator('#loading')).toHaveClass(/hide/,{timeout:120000});await expect(page.locator('#loading')).toHaveCSS('opacity','0');
 const before=await page.locator('#photo-image').getAttribute('src');
 await page.locator('#photo-next').click();expect(await page.locator('#photo-image').getAttribute('src')).not.toBe(before);
 await page.locator('#open-photo').click();await expect(page.locator('.photo-large')).toBeVisible();
 await page.keyboard.press('Escape');await expect(page.locator('.modal-backdrop')).toHaveCount(0);
 for(const view of ['field','channel','pond','overview']){
  await page.locator(`[data-view="${view}"]`).click();
  await expect(page.locator(`[data-view="${view}"]`)).toHaveAttribute('aria-pressed','true');
 }
 await page.setViewportSize({width:760,height:850});
 await page.locator('[data-panel="left"]').click();await expect(page.locator('.left-side')).toHaveClass(/visible/);
 await page.locator('[data-panel="right"]').click();await expect(page.locator('.right-side')).toHaveClass(/visible/);
 await expect(page.locator('.left-side')).not.toHaveClass(/visible/);
 await page.waitForFunction(()=>!window.farmTwin.scene.flight);
 await page.screenshot({path:'deliverables/verification/focus-restore/restored-drawer-760.png'});
});
