export function escapeHTML(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
export function evidenceLabel(record){return record.dataset==='demo'?'演示数据 · 不代表现场':record.verification==='unconfirmed'?'待确认':'资料记录 · 查看来源';}
export function uniqueBindings(entities){const candidates=new Map();for(const e of entities)for(const id of e.spatial_ids||[]){if(!candidates.has(id))candidates.set(id,new Set());candidates.get(id).add(e.id);}return new Map([...candidates].filter(([,ids])=>ids.size===1).map(([id,ids])=>[id,[...ids][0]]));}
export function evidenceURL(value){try{if(!/^https?:\/\//i.test(value))return null;const url=new URL(value);return ['https:','http:'].includes(url.protocol)?url.href:null;}catch{return null;}}
export function preferredRepresentation(entity,objects){const ranking={unregistered_drawing_detail:0,unregistered_drawing_geometry:1,drawing_anchor:2,approximate_satellite:3};return (entity.spatial_ids||[]).filter(id=>objects.has(id)).sort((a,b)=>(ranking[objects.get(a).precision]??4)-(ranking[objects.get(b).precision]??4))[0]||null;}
export function validatedFocus(action,objects){
 if(action?.type!=='focus_entity'||typeof action.entity_id!=='string')return null;
 return preferredRepresentation({spatial_ids:[...objects].filter(([,obj])=>obj.entity_uuid===action.entity_id).map(([id])=>id)},objects);
}
