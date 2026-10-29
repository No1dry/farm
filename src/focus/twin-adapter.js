import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {Water} from 'three/addons/objects/Water.js';
import {sceneAnchorFor} from './ontology-contracts.js';

export const legacySpatialIDs={L18:'DETAIL-L18',L19:'DETAIL-L19',L20:'DETAIL-L20',P17:'DETAIL-QING17'};
export function uniqueSpatialBindings(entities){
 const owners=new Map();for(const entity of entities)for(const id of entity.spatial_ids||[]){if(!owners.has(id))owners.set(id,new Set());owners.get(id).add(entity.id);}
 return new Map([...owners].filter(([,ids])=>ids.size===1).map(([id,ids])=>[id,[...ids][0]]));
}
export function escapeHTML(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
export function safeURL(value){try{const url=new URL(value);return ['https:','http:'].includes(url.protocol)?url.href:null;}catch{return null;}}
export async function api(path,options={}){const response=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',...options.headers}});if(!response.ok){let detail;try{detail=(await response.json()).detail;}catch{}throw Error(typeof detail==='string'?detail:`请求失败 (${response.status})`);}return response.json();}
export const post=(path,body)=>api(path,{method:'POST',body:JSON.stringify(body)});
const visible=node=>{for(let parent=node;parent;parent=parent.parent)if(!parent.visible)return false;return true;};
const classified=(node,pattern)=>{for(let parent=node;parent;parent=parent.parent)if(pattern.test([parent.userData.layer,parent.userData.kind,parent.userData.category].filter(Boolean).join(' ')))return true;return false;};

// The original focus page owns the scene, sky, lighting and controls. This adapter only loads Blender subject meshes.
export class FocusAdapter{
 constructor({scene,renderer,loader=new GLTFLoader(),onAsset=()=>{},onProgress=()=>{}}){
  Object.assign(this,{scene,renderer,loader,onAsset,onProgress});this.root=new THREE.Group();this.root.name='BlenderFarmAssets';scene.add(this.root);
  this.objects=new Map();this.roots=new Map();this.pending=new Map();this.selections=new Map();this.selectables=[];this.assets=[];this.activeAsset=null;this.selectedID=null;this.navigationVersion=0;this.previous=[];this.waterNormals=new Set();this.frameTimes=[];this.assetLoadTimes=new Map();
  if(renderer){const gl=renderer.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');this.hardware={gpu:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):null,logicalProcessors:navigator.hardwareConcurrency,deviceMemoryGiB:navigator.deviceMemory};}
  this.reflectiveWater=new Set();this.layerStates={facilities:false,vegetation:true};this.groups={};for(const key of Object.keys(this.layerStates)){const adapter=this;this.groups[key]={get visible(){return adapter.layerStates[key];},set visible(value){adapter.layerStates[key]=value;adapter.applyLayers();adapter.indexSelections();}};}
 }
 async init(){
  const started=performance.now(),response=await fetch('/models/manifest.json',{cache:'no-store'});if(!response.ok)throw Error('Blender 模型清单不可用');this.manifest=await response.json();
  this.assets=this.manifest.assets||[];for(const object of this.manifest.objects||[])this.objects.set(object.spatial_id,{...object,entity_uuid:null});
  this.defaultAsset=this.assets.some(a=>a.id==='full')?'full':this.manifest.default_asset_id||this.manifest.default_asset||this.assets.find(a=>a.default)?.id||'detail-miaoxia';
  const view=await this.showAsset(this.defaultAsset);this.loadMs=performance.now()-started;return view?{...this.cameraView(this.assets.find(a=>a.id===this.defaultAsset)?.camera_views?.focus?'focus':'overview'),token:view.token}:null;
 }
 toSpatial(id){return legacySpatialIDs[id]||id;}
 displayID(id){return Object.keys(legacySpatialIDs).find(key=>legacySpatialIDs[key]===id)||id;}
 activeRoot(){return this.roots.get(this.activeKey||this.activeAsset);}
 cancelNavigation(){this.navigationVersion++;return this.navigationVersion;}
 isCurrent(token){return token===this.navigationVersion;}
 async loadAsset(id,level='detail'){
  const key=level==='overview'?id+':overview':id;
  if(this.roots.has(key))return this.roots.get(key);if(this.pending.has(key))return this.pending.get(key);
  const asset=this.assets.find(a=>a.id===id);if(!asset)throw Error('未找到对应 Blender 分片');
  const url=level==='overview'&&asset.lod_url?asset.lod_url:asset.url,hash=level==='overview'?asset.lod_sha256:asset.sha256;
  const started=performance.now(),promise=this.loader.loadAsync(url+(hash?`?v=${encodeURIComponent(hash)}`:''),event=>this.onProgress(event.loaded,event.total||0)).then(gltf=>{
   const root=gltf.scene;root.visible=false;const water=[];root.traverse(mesh=>{
    if(['drawing_reference','satellite','reference_image'].includes(mesh.userData.layer))mesh.visible=false;
    if(!mesh.isMesh)return;mesh.castShadow=level==='detail'&&!classified(mesh,/vegetation|grass|water/i);mesh.receiveShadow=level==='detail';
    for(const material of [].concat(mesh.material)){for(const key of ['map','normalMap','roughnessMap','metalnessMap','aoMap']){const texture=material[key];if(texture&&this.renderer)texture.anisotropy=Math.min(8,this.renderer.capabilities.getMaxAnisotropy());}if(/water.surface|Water surface/i.test(material.name)||mesh.userData.water_surface){water.push(mesh);material.roughness=.38;material.envMapIntensity=.42;if(material.normalMap){material.normalMap.wrapS=material.normalMap.wrapT=THREE.RepeatWrapping;this.waterNormals.add(material.normalMap);}}}
   });
   // Reuse the exact Blender water geometry for one reflection surface per detailed asset.
   if(this.renderer&&level==='detail'&&water.length){const chosen=water.find(mesh=>{for(let p=mesh;p;p=p.parent)if(p.userData.spatial_id==='DETAIL-QING17')return true;return false;})||water[0];this.addReflection(chosen);}
   this.root.add(root);this.roots.set(key,root);this.assetLoadTimes.set(key,performance.now()-started);return root;
  });this.pending.set(key,promise);try{return await promise;}finally{this.pending.delete(key);}
 }
 async showAsset(id,token=this.cancelNavigation()){
  const asset=this.assets.find(a=>a.id===id),level=id==='full'&&asset?.lod_url?'overview':'detail';const root=await this.loadAsset(id,level);if(!this.isCurrent(token))return null;
  this.clearHighlight();this.activeAsset=id;this.activeKey=level==='overview'?id+':overview':id;this.lod=level;for(const [key,value]of this.roots)value.visible=key===this.activeKey;root.updateMatrixWorld(true);this.applyLayers();this.indexSelections();
  this.onAsset(this.assets.find(a=>a.id===id));return {...this.cameraView('overview'),token};
 }
 indexSelections(){
  this.selections.clear();this.selectables=[];const root=this.activeRoot();if(!root)return;
  root.traverse(mesh=>{
   if(!mesh.isMesh||!visible(mesh))return;let owner=mesh;while(owner&&!owner.userData.spatial_id)owner=owner.parent;const id=owner?.userData.spatial_id;if(!id||!this.objects.has(id))return;
   const object=this.objects.get(id);if(!this.selections.has(id))this.selections.set(id,{record:object,meshes:[],box:new THREE.Box3()});
   const selection=this.selections.get(id);selection.meshes.push(mesh);selection.box.expandByObject(mesh);mesh.userData.focusSpatialId=id;this.selectables.push(mesh);
  });
  for(const [id,value]of [...this.selections]){value.point=value.box.getCenter(new THREE.Vector3());value.center=[value.point.x,value.point.z];value.id=id;const alias=this.displayID(id);if(alias!==id)this.selections.set(alias,value);}
 }
 bindEntities(entities){const bindings=uniqueSpatialBindings(entities);for(const [id,object]of this.objects)object.entity_uuid=bindings.get(id)||null;this.bindings=bindings;this.dataset=entities[0]?.dataset||null;this.entities=entities;this.applyLayers();this.indexSelections();}
 sceneDeviceForNode(node){
  if(this.dataset!=='demo')return null;let owner=node;while(owner&&!owner.userData.scene_device_key)owner=owner.parent;if(!owner||!owner.userData.scene_scenario_id||owner.userData.data_nature!=='synthetic')return null;
  let spatial=owner;while(spatial&&!spatial.userData.spatial_id)spatial=spatial.parent;const spatialId=spatial?.userData.spatial_id,asset=this.objects.get(spatialId)?.asset_id;if(!asset)return null;
  const matches=(this.entities||[]).filter(entity=>entity.dataset==='demo'&&entity.state==='active'&&entity.data_nature==='synthetic'&&entity.kind==='device'&&entity.scenario?.id===owner.userData.scene_scenario_id&&entity.scenario_properties?.device_key===owner.userData.scene_device_key&&entity.scene_anchor?.role==='device'&&sceneAnchorFor(entity,this.objects,asset)?.spatialId===spatialId);return matches.length===1?matches[0]:null;
 }
 entityForMesh(mesh){return visible(mesh)?this.sceneDeviceForNode(mesh):null;}
 clearHighlight(){for(const [material,color,intensity]of this.previous)material.emissive.copy(color),material.emissiveIntensity=intensity;this.previous=[];this.selectedID=null;this.applyLayers();this.indexSelections();}
 select(id){
  this.clearHighlight();const spatial=this.toSpatial(id);this.selectedID=spatial;this.applyLayers();this.indexSelections();const selection=this.selections.get(spatial);if(!selection){this.selectedID=null;return false;}
  for(const mesh of selection.meshes){if(!mesh.userData.focusUniqueMaterial){const copy=material=>material.emissive?material.clone():material;mesh.material=Array.isArray(mesh.material)?mesh.material.map(copy):copy(mesh.material);mesh.userData.focusUniqueMaterial=true;}
   for(const material of [].concat(mesh.material))if(material.emissive){this.previous.push([material,material.emissive.clone(),material.emissiveIntensity]);material.emissive.set('#b0dbbc');material.emissiveIntensity=.1;}}
  return true;
 }
 async focusSpatial(id){
  id=this.toSpatial(id);const object=this.objects.get(id);if(!object)return null;const token=this.cancelNavigation();
  if(object.asset_id!==this.activeAsset&&!await this.showAsset(object.asset_id,token))return null;
  if(!this.isCurrent(token))return null;this.select(id);return {...this.cameraView('selected',id),token};
 }
 canLocateEntity(entity){const asset=entity.scene_anchor?.asset_id||this.objects.get(entity.spatial_ids?.[0])?.asset_id,anchor=sceneAnchorFor(entity,this.objects,asset);return Boolean(anchor&&(anchor.role==='device'||this.bindings?.get(anchor.spatialId)===entity.id));}
 async focusEntity(entity){
  const asset=entity.scene_anchor?.asset_id||this.objects.get(entity.spatial_ids?.find(id=>this.objects.get(id)?.asset_id===this.activeAsset)||entity.spatial_ids?.[0])?.asset_id,anchor=sceneAnchorFor(entity,this.objects,asset);if(!anchor||!this.canLocateEntity(entity))return null;
  if(anchor.role!=='device')return this.focusSpatial(anchor.spatialId);
  const token=this.cancelNavigation();if(asset!==this.activeAsset&&!await this.showAsset(asset,token))return null;if(!this.isCurrent(token))return null;this.select(anchor.spatialId);const target=new THREE.Vector3(...anchor.position).add(new THREE.Vector3(0,4,0));return{target,position:target.clone().add(new THREE.Vector3(-65,48,80)),token,hint:'演示设备位置 · 来源与本体关系见档案，未接入现场'};
 }
 async view(name,id){
  const token=this.cancelNavigation();const spatial=this.toSpatial(id),object=this.objects.get(spatial);
  const wanted=name==='overview'?(this.activeAsset||this.defaultAsset):object?.asset_id||this.activeAsset||this.defaultAsset;
  if(wanted!==this.activeAsset&&!await this.showAsset(wanted,token))return null;if(!this.isCurrent(token))return null;
  if(object)this.select(spatial);return {...this.cameraView(name,spatial),token};
 }
 cameraView(name,id){
  const asset=this.assets.find(a=>a.id===this.activeAsset)||{},presets=asset.camera_views||{},preset=presets[name];
  if(preset&&(preset.position||preset.pos)&&preset.target){const position=new THREE.Vector3(...(preset.position||preset.pos)),target=new THREE.Vector3(...preset.target);
   if(name==='field'&&id&&id!=='DETAIL-L19'){const point=this.selections.get(id)?.point,base=this.selections.get('DETAIL-L19')?.point;if(point&&base){const delta=point.clone().sub(base);position.add(delta);target.add(delta);}}
   return{position,target,hint:preset.hint};}
  const selection=name==='overview'?null:this.selections.get(id),box=selection?.box?.clone()||new THREE.Box3();
  if(box.isEmpty())this.activeRoot()?.traverse(mesh=>{if(mesh.isMesh&&visible(mesh))box.expandByObject(mesh);});
  if(box.isEmpty())box.set(new THREE.Vector3(-50,0,-50),new THREE.Vector3(50,1,50));
  const target=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3()),d=Math.max(size.x,size.z,25);
  return{target,position:target.clone().add(new THREE.Vector3(-d*.55,d*(name==='overview'?.55:.32),d*.85)),hint:'Blender 空间表示 · 高程与实地尺度待核验'};
 }
 applyLayers(){for(const root of this.roots.values())root.traverse(node=>{if(node.userData.scene_device_key){node.visible=Boolean(this.sceneDeviceForNode(node));return;}const kind=node.userData.layer||node.userData.kind||node.userData.category;if(['drawing_reference','satellite','reference_image'].includes(kind)){node.visible=false;return;}let owner=node;while(owner&&!owner.userData.spatial_id)owner=owner.parent;const id=owner?.userData.spatial_id,record=this.objects.get(id);const annotation=record&&(record.geometry_role==='source_label_anchor'||['drawing_annotation_not_verified_unique_asset','unresolved_drawing_label'].includes(record.identity_scope)||record.geometry_type==='Point'||record.geometry?.type==='Point');if(annotation){node.visible=this.layerStates.facilities||this.selectedID===id;return;}if(['vegetation','grass'].includes(kind))node.visible=this.layerStates.vegetation;});}
 async setLOD(level){const asset=this.assets.find(a=>a.id===this.activeAsset);if(!asset?.lod_url||level===this.lod)return;const id=this.activeAsset,token=this.navigationVersion;this.lodPending=true;try{const root=await this.loadAsset(id,level);if(!this.isCurrent(token)||id!==this.activeAsset)return;const selected=this.selectedID;this.clearHighlight();this.activeKey=level==='overview'?id+':overview':id;this.lod=level;for(const[key,value]of this.roots)value.visible=key===this.activeKey;root.updateMatrixWorld(true);this.applyLayers();this.indexSelections();if(selected)this.select(selected);this.onAsset(asset);}finally{this.lodPending=false;}}
 checkLOD(){const asset=this.assets.find(a=>a.id===this.activeAsset);if(!asset?.lod_url||!this.camera||!this.controls||this.flight||this.lodPending)return;const bounds=asset.bounds,box=bounds?new THREE.Box3(new THREE.Vector3(...bounds.min),new THREE.Vector3(...bounds.max)):new THREE.Box3().setFromObject(this.activeRoot());const size=box.getSize(new THREE.Vector3()),span=this.assetSpan=Math.max(size.x,size.z,100),ratio=this.camera.position.distanceTo(this.controls.target)/span;if(this.lod==='overview'&&ratio<.65)this.setLOD('detail').catch(()=>{});else if(this.lod==='detail'&&ratio>1.15)this.setLOD('overview').catch(()=>{});}
 addReflection(mesh){
  if(!mesh.geometry.attributes.normal||!mesh.parent)return;
  const normal=new THREE.Vector3().fromBufferAttribute(mesh.geometry.attributes.normal,0).normalize(),rotation=new THREE.Matrix4().makeRotationFromQuaternion(new THREE.Quaternion().setFromUnitVectors(normal,new THREE.Vector3(0,0,1)));
  const geometry=mesh.geometry.clone().applyMatrix4(rotation);if(!this.waterTexture)this.waterTexture=new THREE.TextureLoader().load('/focus/textures/water-normal.jpg',texture=>{texture.wrapS=texture.wrapT=THREE.RepeatWrapping;});
  const water=new Water(geometry,{textureWidth:512,textureHeight:512,waterNormals:this.waterTexture,sunDirection:new THREE.Vector3(-.65,.52,-.48).normalize(),sunColor:0xc6d7c8,waterColor:0x20564b,distortionScale:.45,fog:true});
  mesh.updateMatrix();water.matrix.copy(mesh.matrix).multiply(rotation.clone().invert());water.matrixAutoUpdate=false;water.userData={...mesh.userData};water.name=mesh.name;mesh.parent.add(water);mesh.parent.remove(mesh);this.reflectiveWater.add(water);
 }
 update(elapsed){const now=performance.now();if(this.lastFrame!=null){this.frameTimes.push(now-this.lastFrame);if(this.frameTimes.length>300)this.frameTimes.shift();}this.lastFrame=now;for(const texture of this.waterNormals){texture.offset.x=(elapsed*.004)%1;texture.offset.y=(elapsed*.002)%1;}for(const water of this.reflectiveWater)water.material.uniforms.time.value=elapsed*.35;if(now-(this.lastLODCheck||0)>700){this.lastLODCheck=now;this.checkLOD();}}
 metrics(){const values=[...this.frameTimes].sort((a,b)=>a-b),renderer=this.renderer;return{viewport:[renderer.domElement.clientWidth,renderer.domElement.clientHeight],pixelRatio:renderer.getPixelRatio(),asset:this.activeAsset,lod:this.lod,loadedAssets:this.roots.size,loadMs:this.loadMs,assetLoadMs:this.assetLoadTimes.get(this.activeKey),hardware:this.hardware,samples:values.length,medianFrameMs:values[Math.floor(values.length*.5)],p95FrameMs:values[Math.floor(values.length*.95)],drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,geometries:renderer.info.memory.geometries,textures:renderer.info.memory.textures};}
 labels(){const ids=new Set(Object.values(legacySpatialIDs));if(this.selectedID)ids.add(this.selectedID);return [...ids].filter(id=>this.selections.has(id)).map(id=>({id:this.displayID(id),spatialId:id,record:this.objects.get(id),position:this.selections.get(id).point.clone().add(new THREE.Vector3(0,4,0))}));}
}
