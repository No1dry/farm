export const kindLabels={field:'田块',pond:'水塘',lake:'湖面',settlement:'村落',woodland:'林地',road:'道路',channel:'沟渠',bare:'待用地',device:'设备',organization:'管理组'};
const validVector=value=>Array.isArray(value)&&value.length===3&&value.every(Number.isFinite);
export function sceneAnchorFor(entity,objects,asset){
 if(entity?.state==='retired')return null;
 const anchor=entity?.scene_anchor;
 if(anchor){
  if(entity.dataset!=='demo'||entity.data_nature!=='synthetic'||!entity.scenario?.id||anchor.scenario_id!==entity.scenario.id||!validVector(anchor.offset))return null;
  const object=objects.get(anchor.spatial_id);if(!object||object.asset_id!==asset||!validVector(object.center))return null;
  return{entityId:entity.id,spatialId:anchor.spatial_id,assetId:asset,role:anchor.role,position:object.center.map((n,i)=>n+anchor.offset[i])};
 }
 const spatialId=(entity?.spatial_ids||[]).find(id=>objects.get(id)?.asset_id===asset),object=objects.get(spatialId);
 if(!object||!validVector(object.center))return null;
 return{entityId:entity.id,spatialId,assetId:asset,role:'object',position:[...object.center]};
}
export function layoutMarkers(points,{width,height,max=14}){
 const side=width>1000?315:14,top=width>1000?155:128,bottom=height-108,placed=[];
 const rank={pond:45,lake:44,field:43,settlement:42,woodland:35,channel:34,road:33,bare:30};
 const sorted=[...points].sort((a,b)=>((b.selected?10000:0)+(b.kind==='alert'?300:b.kind==='device'?120:rank[b.kind]||20))-
  ((a.selected?10000:0)+(a.kind==='alert'?300:a.kind==='device'?120:rank[a.kind]||20))||Math.abs(a.x-width/2)-Math.abs(b.x-width/2));
 const used=new Set(),counts=new Map();
 const place=point=>{if(used.has(point.id)||placed.length>=max)return false;const w=point.width||150,h=point.height||44,box={x:point.x-w/2,y:point.y-h-8,w,h};
  if(box.x<side||box.x+w>width-side||box.y<top||box.y+h>bottom)return false;
  if(placed.some(p=>box.x<p.box.x+p.box.w+8&&box.x+w+8>p.box.x&&box.y<p.box.y+p.box.h+7&&box.y+h+7>p.box.y))return false;
  used.add(point.id);counts.set(point.kind,(counts.get(point.kind)||0)+1);placed.push({...point,box});return true;};
 for(const point of sorted.filter(p=>p.selected))place(point);
 for(const kind of ['pond','field','settlement','lake','device','alert','woodland','channel','road','bare']){
  if(counts.has(kind))continue;for(const point of sorted.filter(p=>p.kind===kind))if(place(point))break;
 }
 for(const point of sorted){if((counts.get(point.kind)||0)>=(point.kind==='alert'||point.kind==='device'?3:2))continue;place(point);}
 return placed;
}
