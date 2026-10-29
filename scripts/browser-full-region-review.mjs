// Actual full-region browser review: editable model identity, spatial ontology,
// and all village close-ups. Images are evidence, never model textures.
import {chromium} from '@playwright/test';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

const dir='deliverables/verification/full-region';await mkdir(dir,{recursive:true});
const raw=await readFile('public/models/manifest.json'),manifest=JSON.parse(raw);
const hash=value=>createHash('sha256').update(value).digest('hex');
const manifestSHA256=hash(raw),records=[],errors=[];
const browser=await chromium.launch({headless:true,channel:'chrome',args:['--enable-webgl','--ignore-gpu-blocklist']});
const page=await browser.newPage({viewport:{width:1600,height:1000}});
page.on('pageerror',error=>errors.push(error.message));
try{
 await page.goto(process.env.FARM_REVIEW_BASE_URL||'http://127.0.0.1:5173');
 const served=await (await page.request.get(new URL('/models/manifest.json',page.url()).href)).body();
 if(hash(served)!==manifestSHA256)throw Error('Rebuild: served manifest differs from source.');
 await page.waitForFunction(()=>window.farmTwin?.state.entities.length>0&&getComputedStyle(document.querySelector('#loading')).opacity==='0',null,{timeout:120000});
 if(await page.evaluate(()=>window.farmTwin.scene.activeAsset!=='full'))throw Error('Default page is still a partial scene.');

 async function capture(name){
  await page.waitForFunction(()=>!window.farmTwin.scene.flight&&!window.farmTwin.scene.pending.size&&!window.farmTwin.scene.lodPending,null,{timeout:120000});
  const timing=await page.evaluate(()=>new Promise(resolve=>{let previous;const times=[];function frame(now){if(previous!==undefined)times.push(now-previous);previous=now;if(times.length<120)requestAnimationFrame(frame);else{times.sort((a,b)=>a-b);resolve({samples:120,median:times[60],p95:times[114]});}}requestAnimationFrame(frame);}));
  const record=await page.evaluate(()=>{const {state,scene:s}=window.farmTwin;const references=[];s.activeRoot().traverse(n=>{if(!n.isMesh||!['satellite','drawing_reference','reference_image'].includes(n.userData.layer))return;for(let p=n;p;p=p.parent)if(!p.visible)return;references.push(n.name);});return{dataset:state.dataset,asset:s.activeAsset,lod:s.lod,selected:state.selected?.id,selectedSpatial:s.selectedID,camera:s.camera.position.toArray(),target:s.controls.target.toArray(),labels:[...document.querySelectorAll('[data-scene-entity]')].filter(n=>n.getBoundingClientRect().width&&getComputedStyle(n).visibility!=='hidden').map(n=>({id:n.dataset.sceneEntity,kind:n.dataset.kind,text:n.textContent})),profile:document.querySelector('#selection').textContent,relations:document.querySelector('#scene-relations')?.textContent,metrics:window.farmTwin.metrics(),visibleReferences:references};});
  record.frameWindow=timing;record.file=`${dir}/${name}.png`;await page.screenshot({path:record.file});records.push(record);
  console.log(JSON.stringify({name,asset:record.asset,labels:record.labels.length,triangles:record.metrics.triangles,p95:timing.p95}));
 }
 await capture('whole-region-default');
 const fullObjects=manifest.objects.filter(o=>o.asset_id==='full');
 const villages=fullObjects.filter(o=>o.kind==='settlement');
 if(villages.length!==9)throw Error(`Expected all 9 satellite village coverages; got ${villages.length}`);
 for(const object of villages){
  await page.evaluate(id=>window.farmTwin.selectSpatial(id),object.spatial_id);
  await capture(object.spatial_id.toLowerCase());
 }
 for(const kind of ['lake','pond','field','channel']){
  const object=fullObjects.find(o=>o.kind===kind);if(!object)throw Error(`Missing ${kind}`);
  await page.evaluate(id=>window.farmTwin.selectSpatial(id),object.spatial_id);
  await capture(`whole-region-${kind}`);
 }
 await page.locator('[data-view="overview"]').click();await capture('whole-region-return');
 await page.locator('#dataset-real').click();
 await page.waitForFunction(()=>window.farmTwin.state.dataset==='real'&&window.farmTwin.state.entities.length>0&&window.farmTwin.state.entities.every(e=>e.dataset==='real'));
 await capture('whole-region-source-data');
 if(hash(await readFile('public/models/manifest.json'))!==manifestSHA256)throw Error('Models changed during review.');
 await writeFile(`${dir}/review.json`,JSON.stringify({captured_at:new Date().toISOString(),manifestSHA256,records,errors},null,2));
 if(errors.length)throw Error(errors.join('\n'));
}finally{await browser.close();}
