import {chromium} from '@playwright/test';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

const directory='deliverables/verification/model-review';await mkdir(directory,{recursive:true});
const raw=await readFile('public/models/manifest.json'),manifest=JSON.parse(raw),records=[],errors=[],manifestSHA=createHash('sha256').update(raw).digest('hex');
const browser=await chromium.launch({headless:true,channel:'chrome',args:['--enable-webgl','--ignore-gpu-blocklist']});
const page=await browser.newPage({viewport:{width:1600,height:1000}});page.on('pageerror',e=>errors.push(e.message));
await page.goto(process.env.FARM_REVIEW_BASE_URL||'http://127.0.0.1:5173');
const served=await (await page.request.get(new URL('/models/manifest.json',page.url()).href)).body();
if(createHash('sha256').update(served).digest('hex')!==manifestSHA)throw Error('Served model manifest differs from workspace; rebuild before reviewing.');
await page.waitForFunction(()=>window.farmTwin?.state.entities.length>0&&getComputedStyle(document.querySelector('#loading')).opacity==='0');

async function capture(name){
 await page.waitForFunction(()=>!window.farmTwin.scene.flight&&window.farmTwin.scene.pending.size===0&&!window.farmTwin.scene.lodPending);
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))));
 const timing=await page.evaluate(()=>new Promise(resolve=>{const values=[];let previous;function frame(now){if(previous!==undefined)values.push(now-previous);previous=now;if(values.length<120)requestAnimationFrame(frame);else{values.sort((a,b)=>a-b);resolve({samples:values.length,medianFrameMs:values[60],p95FrameMs:values[114]});}}requestAnimationFrame(frame);}));
 const record=await page.evaluate(()=>{const s=window.farmTwin.scene;const refs=[];s.activeRoot().traverse(n=>{if(n.isMesh&&n.visible&&['satellite','drawing_reference','reference_image'].includes(n.userData.layer))refs.push(n.name);});return{asset:s.activeAsset,lod:s.lod,position:s.camera.position.toArray(),target:s.controls.target.toArray(),metrics:window.farmTwin.metrics(),visibleReferences:refs,selected:s.selectedID};});
 record.stableFrameWindow=timing;record.file=`${directory}/${name}.png`;await page.screenshot({path:record.file});records.push(record);console.log(JSON.stringify({file:record.file,asset:record.asset,lod:record.lod,triangles:record.metrics.triangles,p95FrameMs:timing.p95FrameMs}));
}
await capture('default-focus');
for(const view of ['field','channel','pond','overview']){await page.locator(`[data-view="${view}"]`).click();await capture(`miaoxia-${view}`);}
for(const asset of manifest.assets.filter(a=>a.id!=='detail-miaoxia')){
 await page.locator('.scene-tag').click();await page.locator(`[data-asset="${asset.id}"]`).click();
 await page.waitForFunction(id=>window.farmTwin.scene.activeAsset===id,asset.id);
 await capture(`${asset.id}-overview`);
 for(const view of asset.id==='full'?['field','channel','pond']:['field']){await page.locator(`[data-view="${view}"]`).click();await capture(`${asset.id}-${view}`);}
}
if(createHash('sha256').update(await readFile('public/models/manifest.json')).digest('hex')!==manifestSHA)throw Error('Model assets changed during browser review.');
await writeFile(`${directory}/review-views.json`,JSON.stringify({timestamp:new Date().toISOString(),manifestSHA256:manifestSHA,viewport:[1600,1000],records,errors},null,2));
await browser.close();if(errors.length)throw Error(errors.join('\n'));
