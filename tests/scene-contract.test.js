import test from 'node:test';
import assert from 'node:assert/strict';
import {validatedFocus, escapeHTML, evidenceLabel, uniqueBindings, evidenceURL, preferredRepresentation} from '../src/twin/contracts.js';

test('scene action only resolves an exact mapped identity and rejects executable payloads',()=>{
 const ids=new Map([['s-1',{spatial_id:'s-1',entity_uuid:'uuid-1'}]]);
 assert.equal(validatedFocus({type:'focus_entity',entity_id:'uuid-1'},ids),'s-1');
 assert.equal(validatedFocus({type:'focus_entity',entity_id:'L18'},ids),null);
 assert.equal(validatedFocus({type:'eval',code:'alert(1)'},ids),null);
 assert.equal(validatedFocus({type:'focus_entity',entity_id:'uuid-2',spatial_id:'s-1'},ids),null);
});
test('untrusted record text is escaped before insertion in cards',()=>{
 assert.equal(escapeHTML('<img src=x onerror="x">'), '&lt;img src=x onerror=&quot;x&quot;&gt;');
});
test('data quality preserves demonstration and missing-source status',()=>{
 assert.match(evidenceLabel({dataset:'demo'}),/演示/);
 assert.match(evidenceLabel({dataset:'real',verification:'unconfirmed'}),/待确认/);
});
test('conflicting spatial identity is rejected rather than taking first or last',()=>{
 const bindings=uniqueBindings([{id:'a',spatial_ids:['s1','s2']},{id:'b',spatial_ids:['s1']}]);
 assert.equal(bindings.has('s1'),false);assert.equal(bindings.get('s2'),'a');
 assert.equal(uniqueBindings([]).size,0);
});
test('source cards never turn executable or protocol-relative data into links',()=>{
 assert.equal(evidenceURL('javascript:alert(1)'),null);
 assert.equal(evidenceURL('//evil.example'),null);
 assert.equal(evidenceURL('file:///C:/secret'),null);
 assert.equal(evidenceURL('https://www.fao.org/4/T0555E/T0555E02.htm'),'https://www.fao.org/4/T0555E/T0555E02.htm');
});
test('parcel location prefers confirmed outline then explicit drawing anchor, never unrelated satellite name',()=>{
 const objects=new Map([['old',{precision:'unregistered_drawing_detail'}],['anchor',{precision:'drawing_anchor'}],['outline',{precision:'unregistered_drawing_geometry'}]]);
 assert.equal(preferredRepresentation({spatial_ids:['anchor','outline']},objects),'outline');
 assert.equal(preferredRepresentation({spatial_ids:['anchor']},objects),'anchor');
 assert.equal(preferredRepresentation({name:'L18',spatial_ids:[]},objects),null);
});
