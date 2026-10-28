import fs from 'node:fs/promises';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
import {buildFarm} from '../src/scene.js';
import {prepareExport} from '../src/export.js';
import {SOURCE,boundary,parcels,lake,area,world} from '../src/data.js';
// Node's Blob has arrayBuffer; Three.js expects the browser FileReader adapter.
globalThis.FileReader=class{readAsArrayBuffer(blob){blob.arrayBuffer().then(data=>{this.result=data;this.onloadend?.();}).catch(e=>this.onerror?.(e));}readAsDataURL(blob){blob.arrayBuffer().then(data=>{this.result=`data:${blob.type};base64,${Buffer.from(data).toString('base64')}`;this.onloadend?.();});}};
const {farm}=buildFarm();farm.updateMatrixWorld(true);
const data=await new GLTFExporter().parseAsync(prepareExport(farm),{binary:true,onlyVisible:true});
await fs.mkdir('public/models',{recursive:true});
await fs.writeFile('public/models/tongtiehai-farm-v01.glb',Buffer.from(data));
await fs.writeFile('public/models/parcels.local.json',JSON.stringify({metadata:SOURCE,boundary,lake,parcels:parcels.map(p=>({...p,areaApproxM2:Math.round(area(p.points)),coordinatesLocalM:p.points.map(world)}))},null,2));
const buffer=Buffer.from(data);
if(buffer.toString('ascii',0,4)!=='glTF'||buffer.readUInt32LE(4)!==2||buffer.readUInt32LE(8)!==buffer.length)throw Error('Invalid GLB header');
const jsonLength=buffer.readUInt32LE(12);const json=JSON.parse(buffer.toString('utf8',20,20+jsonLength));
for(const p of parcels){if(!json.nodes.some(n=>n.name===p.id))throw Error('Missing parcel '+p.id);}
if(!json.nodes.some(n=>n.name==='L-001'))throw Error('Missing lake');
console.log(JSON.stringify({file:'public/models/tongtiehai-farm-v01.glb',bytes:buffer.length,meshCount:json.meshes.length,parcelCount:parcels.length,lakeCount:1,requiredExtensions:json.extensionsRequired||[],header:'valid glTF 2.0',allParcelIds:'present'},null,2));
