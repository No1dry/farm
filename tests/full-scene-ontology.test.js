import test from 'node:test';
import assert from 'node:assert/strict';
import {sceneAnchorFor,layoutMarkers} from '../src/focus/ontology-contracts.js';

const objects=new Map([['SAT-POND-001',{spatial_id:'SAT-POND-001',asset_id:'full',center:[100,0,200]}]]);
test('demo devices locate by explicit scenario anchor without claiming the parent business identity',()=>{
 const entity={id:'device',dataset:'demo',data_nature:'synthetic',scenario:{id:'case'},spatial_ids:[],scene_anchor:{scenario_id:'case',spatial_id:'SAT-POND-001',offset:[3,0,-4],role:'device'}};
 assert.deepEqual(sceneAnchorFor(entity,objects,'full').position,[103,0,196]);assert.deepEqual(entity.spatial_ids,[]);
 assert.equal(sceneAnchorFor({...entity,dataset:'real'},objects,'full'),null);
 assert.equal(sceneAnchorFor({...entity,state:'retired'},objects,'full'),null);
 assert.equal(sceneAnchorFor({...entity,scene_anchor:{...entity.scene_anchor,scenario_id:'other'}},objects,'full'),null);
});
test('real labels require an explicit current-asset spatial identity',()=>{
 assert.equal(sceneAnchorFor({dataset:'real',spatial_ids:[]},objects,'full'),null);
 assert.deepEqual(sceneAnchorFor({dataset:'real',spatial_ids:['SAT-POND-001']},objects,'full').position,[100,0,200]);
 assert.equal(sceneAnchorFor({dataset:'real',spatial_ids:['SAT-POND-001']},objects,'detail'),null);
});
test('marker placement keeps selected labels and avoids overlapping side panels or labels',()=>{
 const points=[{id:'selected',x:800,y:400,selected:true,kind:'pond'},{id:'overlap',x:804,y:402,kind:'field'},{id:'village',x:1050,y:500,kind:'settlement'},{id:'behind-panel',x:100,y:500,kind:'device'}];
 const result=layoutMarkers(points,{width:1600,height:1000,max:12});assert.deepEqual(result.map(p=>p.id),['selected','village']);
});
