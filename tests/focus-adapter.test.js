import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import * as THREE from 'three';
import {FocusAdapter,uniqueSpatialBindings} from '../src/focus/twin-adapter.js';

test('original focus stylesheet stays byte-identical and entry uses focus',async()=>{
 assert.equal(createHash('sha256').update(await readFile('src/focus/style.css')).digest('hex'),'874531436ffa156b232ca89766c1acfdd1f715ef22b4b2eba473cb5702a7c1cd');
 assert.match(await readFile('index.html','utf8'),/src\/focus\/main\.js/);
 assert.doesNotMatch(await readFile('src/focus/main.js','utf8'),/buildFocus\(|loadMaterials\(/);
});
test('ambiguous spatial identities never become selectable business bindings',()=>{
 assert.deepEqual([...uniqueSpatialBindings([{id:'a',spatial_ids:['x','y']},{id:'b',spatial_ids:['x']}])],[['y','a']]);
});
test('late detail loading cannot replace a newer overview navigation',async()=>{
 let release;const delayed=new Promise(resolve=>release=resolve);
 const loader={loadAsync:async url=>{if(url==='detail')await delayed;return{scene:new THREE.Group()};}};
 const adapter=new FocusAdapter({scene:new THREE.Scene(),loader});
 adapter.assets=[{id:'detail',url:'detail'},{id:'full',url:'full'}];adapter.objects.set('field',{spatial_id:'field',asset_id:'detail'});
 const old=adapter.focusSpatial('field');await adapter.showAsset('full');release();
 assert.equal(await old,null);assert.equal(adapter.activeAsset,'full');assert.equal(adapter.selectedID,null);
});
test('explicit cancellation prevents a late asset commit',async()=>{
 let release;const adapter=new FocusAdapter({scene:new THREE.Scene(),loader:{loadAsync:()=>new Promise(resolve=>release=()=>resolve({scene:new THREE.Group()}))}});
 adapter.assets=[{id:'detail',url:'detail'}];const pending=adapter.showAsset('detail');adapter.cancelNavigation();release();
 assert.equal(await pending,null);assert.equal(adapter.activeAsset,null);
});
test('LOD swaps preserve identity and selection without moving the camera',async()=>{
 const loader={loadAsync:async()=>{const root=new THREE.Group();const mesh=new THREE.Mesh(new THREE.BoxGeometry(10,1,10),new THREE.MeshStandardMaterial());mesh.userData.spatial_id='field';root.add(mesh);return{scene:root};}};
 const adapter=new FocusAdapter({scene:new THREE.Scene(),loader});adapter.assets=[{id:'full',url:'full',lod_url:'full-low'}];adapter.objects.set('field',{spatial_id:'field',asset_id:'full'});
 await adapter.showAsset('full');adapter.select('field');const token=adapter.navigationVersion;
 await adapter.setLOD('detail');assert.equal(adapter.selectedID,'field');assert.equal(adapter.activeAsset,'full');assert.equal(adapter.navigationVersion,token);assert.equal(adapter.lod,'detail');
});
test('hidden reference meshes do not enter the selectable business mesh index',async()=>{
 const root=new THREE.Group(),reference=new THREE.Group();reference.position.x=5000;reference.userData.layer='drawing_reference';reference.userData.spatial_id='ref';reference.add(new THREE.Mesh(new THREE.BoxGeometry(),new THREE.MeshStandardMaterial()));root.add(reference);
 const adapter=new FocusAdapter({scene:new THREE.Scene(),loader:{loadAsync:async()=>({scene:root})}});adapter.assets=[{id:'full',url:'full'}];adapter.objects.set('ref',{spatial_id:'ref',asset_id:'full'});await adapter.showAsset('full');assert.equal(adapter.selectables.length,0);assert.equal(adapter.cameraView('overview').target.x,0);
});
test('selection preserves shader materials used by reflection surfaces',async()=>{
 const root=new THREE.Group(),material=new THREE.ShaderMaterial(),mesh=new THREE.Mesh(new THREE.PlaneGeometry(),material);mesh.userData.spatial_id='water';root.add(mesh);
 const adapter=new FocusAdapter({scene:new THREE.Scene(),loader:{loadAsync:async()=>({scene:root})}});adapter.assets=[{id:'detail',url:'detail'}];adapter.objects.set('water',{spatial_id:'water',asset_id:'detail'});await adapter.showAsset('detail');adapter.select('water');assert.equal(mesh.material,material);
});
test('many water meshes sharing a Blender material retain its authored color across asset and LOD loads',async()=>{
 const material=new THREE.MeshStandardMaterial({color:new THREE.Color(.025,.085,.065)}),original=material.color.clone();material.name='V06 natural green freshwater photographic ripples';
 const loader={loadAsync:async()=>{const root=new THREE.Group();for(let i=0;i<40;i++){const mesh=new THREE.Mesh(new THREE.PlaneGeometry(),material);mesh.userData={spatial_id:'pond',water_surface:true};root.add(mesh);}return{scene:root};}};
 const adapter=new FocusAdapter({scene:new THREE.Scene(),loader});adapter.assets=[{id:'full',url:'full',lod_url:'lod'}];adapter.objects.set('pond',{spatial_id:'pond',asset_id:'full'});
 await adapter.showAsset('full');assert.deepEqual(material.color.toArray(),original.toArray(),'Loading shared meshes must not repeatedly darken the source material');
 await adapter.setLOD('detail');assert.deepEqual(material.color.toArray(),original.toArray());
});
test('camera presets without a selected object stay in the current region asset',async()=>{
 const adapter=new FocusAdapter({scene:new THREE.Scene(),loader:{loadAsync:async()=>({scene:new THREE.Group()})}});adapter.defaultAsset='detail';adapter.assets=[{id:'full',url:'full',camera_views:{field:{position:[10,3,10],target:[2,0,3]},pond:{position:[20,3,20],target:[4,0,5]}}},{id:'detail',url:'detail'}];await adapter.showAsset('full');
 for(const name of ['field','pond']){const view=await adapter.view(name);assert.equal(adapter.activeAsset,'full');assert.deepEqual(view.target.toArray(),adapter.assets[0].camera_views[name].target);}
});
test('unverified source anchors start hidden and appear only on selection or explicit layer enable',async()=>{
 const root=new THREE.Group();for(const id of ['annotation','confirmed']){const mesh=new THREE.Mesh(new THREE.BoxGeometry(),new THREE.MeshStandardMaterial());mesh.userData.spatial_id=id;root.add(mesh);}
 const adapter=new FocusAdapter({scene:new THREE.Scene(),loader:{loadAsync:async()=>({scene:root})}});adapter.assets=[{id:'detail',url:'detail'}];adapter.objects.set('annotation',{spatial_id:'annotation',asset_id:'detail',kind:'facility',identity_scope:'drawing_annotation_not_verified_unique_asset',geometry_role:'source_label_anchor'});adapter.objects.set('confirmed',{spatial_id:'confirmed',asset_id:'detail',kind:'facility',identity_scope:'verified_site_asset'});await adapter.showAsset('detail');
 assert.deepEqual(adapter.selectables.map(m=>m.userData.spatial_id),['confirmed']);assert.equal(adapter.select('annotation'),true);assert.equal(adapter.selectables.length,2);adapter.clearHighlight();assert.equal(adapter.selectables.length,1);adapter.groups.facilities.visible=true;assert.equal(adapter.selectables.length,2);
});
test('initial default camera uses focus while explicit overview uses the whole-region preset',async()=>{
 const prior=globalThis.fetch;globalThis.fetch=async()=>({ok:true,json:async()=>({default_asset_id:'detail',assets:[{id:'detail',url:'detail',camera_views:{focus:{position:[10,5,10],target:[1,0,1]},overview:{position:[100,50,100],target:[10,0,10]}}}],objects:[]})});
 try{const adapter=new FocusAdapter({scene:new THREE.Scene(),loader:{loadAsync:async()=>({scene:new THREE.Group()})}}),initial=await adapter.init();assert.deepEqual(initial.target.toArray(),[1,0,1]);assert.deepEqual((await adapter.view('overview')).target.toArray(),[10,0,10]);}finally{globalThis.fetch=prior;}
});

test('sample device meshes resolve to their own UUID and disappear in real data mode',async()=>{
 const root=new THREE.Group(),deviceRoot=new THREE.Group(),mesh=new THREE.Mesh(new THREE.BoxGeometry(),new THREE.MeshStandardMaterial());deviceRoot.userData={spatial_id:'SAT-POND-001',scene_device_key:'SAT-POND-001:sensor',scene_scenario_id:'demo',data_nature:'synthetic'};deviceRoot.add(mesh);root.add(deviceRoot);
 const adapter=new FocusAdapter({scene:new THREE.Scene(),loader:{loadAsync:async()=>({scene:root})}});adapter.assets=[{id:'full',url:'full'}];adapter.objects.set('SAT-POND-001',{spatial_id:'SAT-POND-001',asset_id:'full',center:[0,0,0]});
 const parent={id:'demo-parent',dataset:'demo',spatial_ids:['SAT-POND-001']},device={id:'demo-device',state:'active',dataset:'demo',data_nature:'synthetic',kind:'device',spatial_ids:[],scenario:{id:'demo'},scenario_properties:{device_key:'SAT-POND-001:sensor'},scene_anchor:{scenario_id:'demo',spatial_id:'SAT-POND-001',asset_id:'full',offset:[0,0,0],role:'device'}};
 adapter.bindEntities([parent,device]);await adapter.showAsset('full');assert.equal(adapter.entityForMesh?.(mesh)?.id,'demo-device');assert.ok(adapter.selectables.includes(mesh));
 adapter.bindEntities([{id:'real-parent',dataset:'real',spatial_ids:['SAT-POND-001']}]);assert.equal(deviceRoot.visible,false);assert.equal(adapter.entityForMesh?.(mesh),null);assert.equal(adapter.selectables.includes(mesh),false);
 adapter.bindEntities([parent,device,{...device,id:'ambiguous-device'}]);assert.equal(adapter.entityForMesh?.(mesh),null);
 assert.equal(deviceRoot.visible,false);assert.equal(adapter.selectables.includes(mesh),false);
 for(const candidate of [null,{...device,state:'retired'},{...device,scenario:null},{...device,scenario:{id:'other'},scene_anchor:{...device.scene_anchor,scenario_id:'other'}}]){
  adapter.bindEntities(candidate?[parent,candidate]:[parent]);assert.equal(deviceRoot.visible,false);assert.equal(adapter.selectables.includes(mesh),false);assert.equal(adapter.entityForMesh(mesh),null);
 }
 delete deviceRoot.userData.scene_scenario_id;adapter.bindEntities([parent,device]);assert.equal(deviceRoot.visible,false);assert.equal(adapter.entityForMesh(mesh),null);
 deviceRoot.userData.scene_scenario_id='demo';adapter.bindEntities([parent,device]);assert.equal(deviceRoot.visible,true);assert.equal(adapter.entityForMesh(mesh).id,device.id);
});
