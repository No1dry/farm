import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {RGBELoader} from 'three/addons/loaders/RGBELoader.js';
import {validatedFocus,uniqueBindings} from './contracts.js';

// The browser never creates the farm geometry. All subject meshes come from Blender.
export class TwinScene {
 constructor(element,onSelect,onStatus){
  this.element=element;this.onSelect=onSelect;this.onStatus=onStatus;this.objects=new Map();this.roots=new Map();this.pending=new Map();this.frameTimes=[];this.layerStates=new Map();
  this.renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});this.assetLoadTimes=new Map();const gl=this.renderer.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');this.hardware={gpu:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):null,logicalProcessors:navigator.hardwareConcurrency,deviceMemoryGiB:navigator.deviceMemory};
  this.renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));this.renderer.outputColorSpace=THREE.SRGBColorSpace;this.renderer.toneMapping=THREE.ACESFilmicToneMapping;
  this.renderer.toneMappingExposure=.95;this.waterNormals=new Set();element.append(this.renderer.domElement);
  this.scene=new THREE.Scene();this.scene.background=new THREE.Color('#a9bfc3');
  this.camera=new THREE.PerspectiveCamera(45,1,1,18000);
  this.controls=new OrbitControls(this.camera,this.renderer.domElement);this.controls.enableDamping=true;this.controls.dampingFactor=.07;this.controls.minDistance=12;this.controls.maxDistance=9000;this.controls.maxPolarAngle=Math.PI*.49;
  this.controls.addEventListener('start',()=>{this.cancelNavigation();});
  this.scene.add(new THREE.HemisphereLight(0xe0f3ff,0x6d674b,1.2));
  const sun=new THREE.DirectionalLight(0xffedcf,2.6);sun.position.set(-1200,2200,900);this.scene.add(sun);
  this.raycaster=new THREE.Raycaster();this.pointer=new THREE.Vector2();
  this.renderer.domElement.addEventListener('pointerdown',e=>{this.down=[e.clientX,e.clientY];});
  this.renderer.domElement.addEventListener('pointerup',e=>{
   if(!this.down||Math.hypot(e.clientX-this.down[0],e.clientY-this.down[1])>5)return;
   const rect=element.getBoundingClientRect();this.pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);this.raycaster.setFromCamera(this.pointer,this.camera);
   const root=this.activeRoot();if(!root)return;
   for(const hit of this.raycaster.intersectObject(root,true)){
    let o=hit.object;let visible=true;for(let p=o;p;p=p.parent)if(!p.visible)visible=false;if(!visible)continue;
    while(o&&!o.userData.spatial_id)o=o.parent;
    if(o&&this.objects.has(o.userData.spatial_id)){this.select(o.userData.spatial_id,false);onSelect(this.objects.get(o.userData.spatial_id));break;}
   }
  });
  this.observer=new ResizeObserver(()=>{const w=element.clientWidth,h=element.clientHeight;this.renderer.setSize(w,h);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();});this.observer.observe(element);
  this.renderer.setAnimationLoop(now=>{
   if(this.lastFrame){this.frameTimes.push(now-this.lastFrame);if(this.frameTimes.length>300)this.frameTimes.shift();}this.lastFrame=now;
   if(this.flight){const f=this.flight;let t=Math.min(1,(now-f.start)/1500);t=t*t*(3-2*t);this.camera.position.lerpVectors(f.from,f.to,t);this.controls.target.lerpVectors(f.targetFrom,f.targetTo,t);if(t>=1)this.flight=null;}
   if(!matchMedia('(prefers-reduced-motion: reduce)').matches)for(const texture of this.waterNormals){texture.offset.x=(now*.000004)%1;texture.offset.y=(now*.000002)%1;}
   this.controls.update();const near=Math.max(.1,Math.min(20,this.camera.position.distanceTo(this.controls.target)*.002));if(Math.abs(this.camera.near-near)>.05){this.camera.near=near;this.camera.updateProjectionMatrix();}this.renderer.render(this.scene,this.camera);this.updateLabel();
   if(now-(this.lastLODCheck||0)>700&&!this.flight&&!this.lodPending){this.lastLODCheck=now;this.checkLOD();}
  });
 }
 async init(){
  const start=performance.now();const r=await fetch('/models/manifest.json',{cache:'no-store'});if(!r.ok)throw Error('模型清单未生成');this.manifest=await r.json();
  for(const obj of this.manifest.objects||[])this.objects.set(obj.spatial_id,obj);
  this.assets=this.manifest.assets||[{id:'full',url:'/models/full-area.glb',scope:'full',label:'规划全域'}];
  await this.showAsset(this.assets[0].id);this.loadMs=performance.now()-start;
  new RGBELoader().load('/focus/textures/daylight-sky.hdr',texture=>{texture.mapping=THREE.EquirectangularReflectionMapping;this.scene.environment=texture;this.scene.environmentIntensity=.45;},undefined,()=>{});
  return this.manifest;
 }
 activeRoot(){return this.roots.get(this.activeKey||this.activeAsset);}
 async loadAsset(id,level='detail'){
  const key=level==='overview'?`${id}:lod`:id;
  if(this.roots.has(key))return this.roots.get(key);
  if(this.pending.has(key))return this.pending.get(key);
  const asset=this.assets.find(a=>a.id===id);if(!asset)throw Error('未找到对应模型分片');
  const baseURL=level==='overview'&&asset.lod_url?asset.lod_url:asset.url,hash=level==='overview'?asset.lod_sha256:asset.sha256;
  const promise=new GLTFLoader().loadAsync(baseURL+(hash?`?v=${encodeURIComponent(hash)}`:'')).then(gltf=>{const root=gltf.scene;root.visible=false;root.traverse(mesh=>{if(!mesh.isMesh)return;for(const material of [].concat(mesh.material)){if(/Water surface/i.test(material.name)){material.roughness=.22;material.envMapIntensity=1.1;if(material.normalMap){material.normalMap.wrapS=material.normalMap.wrapT=THREE.RepeatWrapping;this.waterNormals.add(material.normalMap);}}}});this.scene.add(root);this.roots.set(key,root);return root;});
  const loadStarted=performance.now();this.pending.set(key,promise);try{const loaded=await promise;this.assetLoadTimes.set(key,performance.now()-loadStarted);return loaded;}finally{this.pending.delete(key);}
 }
 async showAsset(id,{keepSelection=false}={}){
  if(!keepSelection){this.selectSeq=(this.selectSeq||0)+1;this.flight=null;}
  const seq=this.assetSeq=(this.assetSeq||0)+1;const asset=this.assets.find(a=>a.id===id),level=asset?.lod_url?'overview':'detail';const root=await this.loadAsset(id,level);if(seq!==this.assetSeq)return;
  this.activeAsset=id;this.activeKey=level==='overview'?`${id}:lod`:id;this.lod=level;for(const [key,r]of this.roots)r.visible=key===this.activeKey;this.applyLayers();this.clearHighlight();
  const box=new THREE.Box3();root.updateMatrixWorld(true);root.traverse(mesh=>{if(mesh.isMesh&&!['satellite','drawing_reference'].includes(mesh.userData.layer))box.expandByObject(mesh);});if(box.isEmpty())box.setFromObject(root);const center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());const d=Math.max(size.x,size.y,size.z,50);
  this.assetSpan=d;const position=new THREE.Vector3(center.x+d*.42,center.y+d*.65,center.z+d*.65);
  if(!this.hasView){this.camera.position.copy(position);this.controls.target.copy(center);this.hasView=true;}else this.fly(center,position);
  this.onStatus(this.assets.find(a=>a.id===id));
 }
 async setLOD(level){
  const asset=this.assets.find(a=>a.id===this.activeAsset);if(!asset?.lod_url||this.lod===level)return;
  const seq=this.assetSeq;this.lodPending=true;
  try{await this.loadAsset(asset.id,level);if(seq!==this.assetSeq)return;const selected=this.selectedID;this.clearHighlight();this.activeKey=level==='overview'?`${asset.id}:lod`:asset.id;this.lod=level;for(const [key,root]of this.roots)root.visible=key===this.activeKey;this.applyLayers();if(selected)await this.select(selected,false);}finally{this.lodPending=false;}
 }
 checkLOD(){const ratio=this.camera.position.distanceTo(this.controls.target)/(this.assetSpan||1);if(this.lod==='overview'&&ratio<.65)this.setLOD('detail').catch(()=>{});else if(this.lod==='detail'&&ratio>1.05)this.setLOD('overview').catch(()=>{});}
 fly(target,position){
  if(matchMedia('(prefers-reduced-motion: reduce)').matches){this.camera.position.copy(position);this.controls.target.copy(target);return;}
  if(this.camera.position.length()<1){this.camera.position.copy(position);this.controls.target.copy(target);return;}
  this.flight={start:performance.now(),from:this.camera.position.clone(),to:position,targetFrom:this.controls.target.clone(),targetTo:target};
 }
 clearHighlight(){for(const [material,color,intensity]of this.previous||[]){material.emissive.copy(color);material.emissiveIntensity=intensity;}this.previous=[];this.selectedID=null;if(this.label)this.label.hidden=true;}
 async select(id,fly=true){
  const obj=this.objects.get(id);if(!obj)return false;const seq=this.selectSeq=(this.selectSeq||0)+1;this.assetSeq=(this.assetSeq||0)+1;this.flight=null;
  if(obj.asset_id&&obj.asset_id!==this.activeAsset)await this.showAsset(obj.asset_id,{keepSelection:true});if(seq!==this.selectSeq||(obj.asset_id&&obj.asset_id!==this.activeAsset))return false;
  this.clearHighlight();this.selectedID=id;const box=new THREE.Box3();const root=this.activeRoot();
  root?.traverse(mesh=>{let owner=mesh;while(owner&&!owner.userData.spatial_id)owner=owner.parent;
   if(owner?.userData.spatial_id!==id||!mesh.isMesh)return;
   box.expandByObject(mesh);if(!mesh.userData.uniqueMaterial){mesh.material=Array.isArray(mesh.material)?mesh.material.map(m=>m.clone()):mesh.material.clone();mesh.userData.uniqueMaterial=true;}
   for(const m of [].concat(mesh.material))if(m.emissive){this.previous.push([m,m.emissive.clone(),m.emissiveIntensity]);m.emissive.set('#e2ba59');m.emissiveIntensity=.12;}
  });
  this.labelPosition=box.isEmpty()?new THREE.Vector3(...(obj.center||[0,0,0])):box.getCenter(new THREE.Vector3());
  if(!this.label){this.label=document.createElement('div');this.label.className='scene-label';this.element.append(this.label);}this.label.textContent=`${obj.name||id}${obj.precision==='drawing_anchor'?' · 图纸标号锚点，边界未确认':''}${this.alertEntities?.has(obj.entity_uuid)?' · 有预警记录':''}`;
  if(fly){const center=this.labelPosition;const size=box.getSize(new THREE.Vector3());const d=Math.max(size.x,size.z,50);this.fly(center,center.clone().add(new THREE.Vector3(d*.7,d*.95,d*1.2)));}
  return true;
 }
 cancelNavigation(){this.selectSeq=(this.selectSeq||0)+1;this.assetSeq=(this.assetSeq||0)+1;this.flight=null;}
 updateLabel(){if(!this.label||!this.selectedID)return;const p=this.labelPosition.clone().project(this.camera);const obj=this.objects.get(this.selectedID);this.label.hidden=p.z>1||p.z< -1||this.layerStates.get('labels')===false||this.layerStates.get(obj?.kind)===false;this.label.style.left=`${(p.x+1)*this.element.clientWidth/2}px`;this.label.style.top=`${(1-p.y)*this.element.clientHeight/2}px`;}
 bindEntities(items){const bindings=uniqueBindings(items);for(const [id,o]of this.objects)o.entity_uuid=bindings.get(id)||null;this.alertEntities=new Set(items.filter(e=>e.business_alerts?.length).map(e=>e.id));}
 async action(action){const id=validatedFocus(action,this.objects);return id?this.select(id):false;}
 layer(kind,visible){this.layerStates.set(kind,visible);this.applyLayers();}
 applyLayers(){for(const root of this.roots.values())root.traverse(o=>{const kind=o.userData.layer||o.userData.kind;if(this.layerStates.has(kind))o.visible=this.layerStates.get(kind);if(o.name==='WholeRedlineTerrain')o.visible=this.layerStates.get('satellite')===false;});}
 metrics(){const values=[...this.frameTimes].sort((a,b)=>a-b);return{viewport:[this.element.clientWidth,this.element.clientHeight],pixelRatio:this.renderer.getPixelRatio(),asset:this.activeAsset,lod:this.lod,loadedAssets:this.roots.size,loadMs:this.loadMs,assetLoadMs:this.assetLoadTimes.get(this.activeKey),hardware:this.hardware,samples:values.length,medianFrameMs:values[Math.floor(values.length*.5)],p95FrameMs:values[Math.floor(values.length*.95)],drawCalls:this.renderer.info.render.calls,triangles:this.renderer.info.render.triangles,geometries:this.renderer.info.memory.geometries,textures:this.renderer.info.memory.textures};}
}
