import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
// 展平植被实例，导出不依赖 EXT_mesh_gpu_instancing 的通用 GLB。
export function prepareExport(farm){
 const root=farm.clone(true);root.traverse(o=>o.visible=true);root.getObjectByName('buildings').visible=false;
 const instances=[];root.traverse(o=>{if(o.isInstancedMesh)instances.push(o);if(o.isLine){const old=o.material;o.material=new THREE.MeshBasicMaterial({color:old.color,transparent:old.transparent,opacity:old.opacity});}});
 for(const obj of instances){const geometries=[],matrix=new THREE.Matrix4(),c=new THREE.Color();for(let i=0;i<obj.count;i++){obj.getMatrixAt(i,matrix);const g=(obj.geometry.type==='IcosahedronGeometry'?new THREE.IcosahedronGeometry(1,0):obj.geometry.clone()).applyMatrix4(matrix);if(obj.instanceColor){obj.getColorAt(i,c);const values=new Float32Array(g.getAttribute('position').count*3);for(let k=0;k<values.length;k+=3){values[k]=c.r;values[k+1]=c.g;values[k+2]=c.b;}g.setAttribute('color',new THREE.BufferAttribute(values,3));}geometries.push(g);}const material=obj.material.clone();if(obj.instanceColor){material.vertexColors=true;material.color.set(0xffffff);}const mesh=new THREE.Mesh(mergeGeometries(geometries),material);mesh.name=obj.name;mesh.userData=obj.userData;mesh.position.copy(obj.position);mesh.quaternion.copy(obj.quaternion);mesh.scale.copy(obj.scale);obj.parent.add(mesh);obj.parent.remove(obj);geometries.forEach(g=>g.dispose());}
 root.updateMatrixWorld(true);return root;
}
