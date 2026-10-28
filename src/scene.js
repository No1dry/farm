import * as THREE from 'three';
import { boundary,lake,parcels,roads,greenAreas,settlements,world,center,area,SOURCE } from './data.js';

const color={ground:0x83936b,base:0x56664e,bank:0xa4a17a,pond:0x417f78,lake:0x3c7772,field:[0x8d9e4d,0xa9ae5d,0x78914d,0xb2ae65,0x97a761,0x647f45],tree:0x3e6547,trunk:0x776047,roadEdge:0x747b60,road:0xc7c4a5,forest:0x56764c};
const mat=(c,extras={})=>new THREE.MeshStandardMaterial({color:c,roughness:.88,...extras});
function shapeOf(points){return new THREE.Shape(points.map(p=>{const [x,z]=world(p);return new THREE.Vector2(x,-z);}));}
export function polygon(points,height=1,y=0,material=mat(color.ground)){
 const geo=new THREE.ExtrudeGeometry(shapeOf(points),{depth:height,bevelEnabled:false,curveSegments:1});
 const mesh=new THREE.Mesh(geo,material);mesh.rotation.x=-Math.PI/2;mesh.position.y=y;mesh.receiveShadow=true;return mesh;
}
function outline(points,y,c,closed=true){const pts=points.map(p=>{const[x,z]=world(p);return new THREE.Vector3(x,y,z);});if(closed)pts.push(pts[0]);return new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),new THREE.LineBasicMaterial({color:c,transparent:true,opacity:.65}));}
function inset(points,f){const c=center(points);return points.map(p=>[c[0]+(p[0]-c[0])*f,c[1]+(p[1]-c[1])*f]);}
function inside(x,y,poly){let c=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if(((a[1]>y)!==(b[1]>y))&&(x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]))c=!c;}return c;}
let seed=592;function random(){seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;}
function ribbon(points,width,y,material){const curve=new THREE.CatmullRomCurve3(points.map(p=>{const[x,z]=world(p);return new THREE.Vector3(x,y,z);}));const pts=curve.getPoints(points.length*12);const vertices=[],indices=[];pts.forEach((p,i)=>{const prev=pts[Math.max(0,i-1)],next=pts[Math.min(pts.length-1,i+1)];const n=new THREE.Vector3(next.z-prev.z,0,-(next.x-prev.x)).normalize().multiplyScalar(width/2);vertices.push(p.x+n.x,y,p.z+n.z,p.x-n.x,y,p.z-n.z);if(i<pts.length-1){const j=i*2;indices.push(j,j+1,j+2,j+1,j+3,j+2);}});const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.setIndex(indices);geo.computeVertexNormals();const m=new THREE.Mesh(geo,material);m.receiveShadow=true;return m;}
function cropRows(record,index){const pts=inset(record.points,.88);const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);const vertices=[];for(let y=Math.min(...ys);y<Math.max(...ys);y+=2.3){const ints=[];for(let i=0;i<pts.length;i++){const a=pts[i],b=pts[(i+1)%pts.length];if((a[1]<=y&&b[1]>y)||(b[1]<=y&&a[1]>y))ints.push(a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]));}ints.sort((a,b)=>a-b);for(let j=0;j<ints.length-1;j+=2){const [x1,z1]=world([ints[j],y]),[x2,z2]=world([ints[j+1],y]);vertices.push(x1,2.5,z1,x2,2.5,z2);}}
 const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));return new THREE.LineSegments(geo,new THREE.LineBasicMaterial({color:index%3===0?0xd4c77a:0x506c37,transparent:true,opacity:.55}));}
export function buildFarm(){
 seed=592;
 const farm=new THREE.Group();farm.name='Tongtiehai_Farm_Local_Approximation';farm.userData={coordinateSystem:SOURCE.crs,source:'User supplied satellite screenshot and planning photograph',scaleBasis:SOURCE.basis,accuracy:'Illustrative manual tracing. Not surveyed.',terrain:'Flat schematic; no measured elevations',unit:'metre_approximate'};
 const groups={};for(const key of ['base','field','pond','lake','road','vegetation','buildings','boundary']){groups[key]=new THREE.Group();groups[key].name=key;farm.add(groups[key]);}
 const base=polygon(boundary,25,-25,[mat(color.ground),mat(color.base)]);base.name='Project_extent_schematic';base.userData={kind:'projectBoundary',source:'Screenshot red line'};groups.base.add(base);
 const selectables=[];const objects=new Map();
 const waterMat=mat(color.pond,{roughness:.3,metalness:.13});
 parcels.forEach((p,i)=>{let mesh;
  if(p.kind==='pond'){
   const bankShape=shapeOf(p.points);bankShape.holes.push(new THREE.Path(inset(p.points,.91).map(p=>{const[x,z]=world(p);return new THREE.Vector2(x,-z);})));const bank=new THREE.Mesh(new THREE.ExtrudeGeometry(bankShape,{depth:1.8,bevelEnabled:false}),mat(color.bank));bank.rotation.x=-Math.PI/2;bank.name=`${p.id}_embankment`;groups.pond.add(bank);
   mesh=polygon(inset(p.points,.91),.3,.5,waterMat);groups.pond.add(mesh);
   groups.pond.add(outline(inset(p.points,.9),1.2,0x83b4a1));
   const c=center(p.points),[cx,cz]=world(c);const ripples=[];
   for(let j=0;j<3;j++){let x=c[0]-5+j*3,y=c[1]-5+j*5;if(!inside(x,y,p.points))continue;const[xw,zw]=world([x,y]);ripples.push(xw-5,1.25,zw,xw+5,1.25,zw);}
   const rg=new THREE.BufferGeometry();rg.setAttribute('position',new THREE.Float32BufferAttribute(ripples,3));groups.pond.add(new THREE.LineSegments(rg,new THREE.LineBasicMaterial({color:0x9dc5ae,transparent:true,opacity:.32})));
  }else{
   groups.field.add(polygon(p.points,1.4,0,mat(color.bank)));
   mesh=polygon(inset(p.points,.94),1.6,.1,mat(color.field[i%color.field.length]));groups.field.add(mesh);groups.field.add(cropRows(p,i));
  }
  mesh.name=p.id;mesh.userData={...p,areaApproxM2:Math.round(area(p.points))};selectables.push(mesh);objects.set(p.id,mesh);
 });
 const lm=polygon(lake,.4,.2,mat(color.lake,{roughness:.28,metalness:.18}));lm.name='L-001';lm.userData={id:'L-001',name:'铜铁海',kind:'lake',points:lake,source:'卫星截图人工描绘',verification:'待现场校核',deviceIds:[],depth:null};groups.lake.add(lm,outline(lake,1.3,0xa8b69a));selectables.push(lm);objects.set(lm.name,lm);
 greenAreas.forEach(p=>groups.vegetation.add(polygon(p,.5,.1,mat(color.forest))));
 const trees=[];
 for(const p of greenAreas){const xs=p.map(a=>a[0]),ys=p.map(a=>a[1]);for(let i=0;i<550;i++){const x=Math.min(...xs)+random()*(Math.max(...xs)-Math.min(...xs));const y=Math.min(...ys)+random()*(Math.max(...ys)-Math.min(...ys));if(inside(x,y,p)&&inside(x,y,boundary)&&!inside(x,y,lake))trees.push({p:[x,y],h:8+random()*12,r:4+random()*5});}}
 roads.forEach((points,i)=>{groups.road.add(ribbon(points,i<2?16:10,2.1,mat(color.roadEdge)),ribbon(points,i<2?10:6,2.3,mat(color.road)));});
 // 道旁植被是表现细节，不是实际树木清查点。
 for(const r of roads.slice(0,2)){for(let i=0;i<r.length-1;i++){const a=r[i],b=r[i+1],len=Math.hypot(b[0]-a[0],b[1]-a[1]);for(let d=10;d<len;d+=10){const t=d/len,p=[a[0]+(b[0]-a[0])*t+6,a[1]+(b[1]-a[1])*t+4];if(inside(...p,boundary)&&!inside(...p,lake)&&!parcels.some(k=>inside(...p,k.points)))trees.push({p,h:9+random()*7,r:4+random()*3});}}}
 const trunk=new THREE.InstancedMesh(new THREE.CylinderGeometry(.9,1.1,1,5),mat(color.trunk),trees.length);
 const canopy=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,1),mat(color.tree),trees.length);const dummy=new THREE.Object3D();const tc=new THREE.Color();
 trees.forEach((t,i)=>{const[x,z]=world(t.p);dummy.position.set(x,t.h*.23,z);dummy.scale.set(1,t.h*.45,1);dummy.updateMatrix();trunk.setMatrixAt(i,dummy.matrix);dummy.position.set(x,t.h*.7,z);dummy.scale.set(t.r,t.h*.55,t.r);dummy.rotation.set(random(),random(),random());dummy.updateMatrix();canopy.setMatrixAt(i,dummy.matrix);tc.setHSL(.28+random()*.05,.19+random()*.15,.23+random()*.1);canopy.setColorAt(i,tc);});trunk.name='Illustrative_tree_trunks';canopy.name='Illustrative_tree_canopies';canopy.castShadow=true;groups.vegetation.add(trunk,canopy);
 const bm=mat(0xc9c5ae),roof=mat(0x65736b);
 settlements.forEach((c,j)=>{for(let i=0;i<14;i++){const p=[c[0]+(random()-.5)*22,c[1]+(random()-.5)*20];if(!inside(...p,boundary)||inside(...p,lake))continue;const[x,z]=world(p),w=7+random()*8,d=7+random()*8,h=5+random()*7;const b=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),bm);b.position.set(x,h/2,z);b.rotation.y=j*.7;b.castShadow=true;const r=new THREE.Mesh(new THREE.BoxGeometry(w+1,1.4,d+1),roof);r.position.set(x,h+.5,z);r.rotation.y=b.rotation.y;groups.buildings.add(b,r);}});groups.buildings.userData={status:'Illustrative context buildings, footprints and heights unverified'};groups.buildings.visible=false;
 const borderPts=[...boundary,boundary[0]].map(p=>{const[x,z]=world(p);return new THREE.Vector3(x,4,z);});const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(borderPts),new THREE.LineDashedMaterial({color:0xe2dd95,dashSize:13,gapSize:8,transparent:true,opacity:.9}));line.computeLineDistances();groups.boundary.add(line);
 return {farm,groups,selectables,objects};
}
export {outline,inside};
