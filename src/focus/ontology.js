import * as THREE from 'three';
import {escapeHTML as esc} from './twin-adapter.js';
import {sceneAnchorFor,layoutMarkers,kindLabels} from './ontology-contracts.js';
import './ontology.css';

const shortName=e=>(e.name||e.code||'对象').replace(/\s*·\s*演示$/,'');
const predicateName=iri=>({monitors:'监测',serves:'服务',managedBy:'管理',partOf:'属于',locatedIn:'位于'}[iri?.split('/').at(-1)]||iri?.split('/').at(-1)||'关联');
const glyph=kind=>({field:'▱',pond:'≈',lake:'≈',settlement:'⌂',woodland:'♧',road:'╱',channel:'≋',bare:'◇',device:'◎',alert:'⚠'}[kind]||'◇');

export function mountOntologyDashboard({adapter,database,toast}){
 const state=database.state,$=selector=>document.querySelector(selector);let selected=null,graph=null,markers=[],lastAsset=null,lastList='',lastFrame=0;
 const layer=document.createElement('div');layer.className='ontology-markers';layer.setAttribute('aria-label','空间本体对象与演示监测标记');$('#twin').appendChild(layer);
 const lines=new THREE.Group();lines.name='OntologyRelationships';adapter.scene.add(lines);adapter.relationshipLines=lines;
 const stats=$('.scope-stats').querySelectorAll('strong');stats[0].id='scope-entity-count';stats[1].id='scope-device-count';
 $('.unit-list').id='visible-entities';$('.unit-list').onclick=event=>{const item=event.target.closest('[data-entity]');if(item)database.selectEntity(item.dataset.entity);};
 $('.header-title p').textContent='红线全域 · 卫星轮廓与本体业务';
 $('.units-panel .panel-head h2').textContent='全域空间与本体';$('.archive-panel .panel-head h2').textContent='全域数据档案';$('.engineering-panel .panel-head h2').textContent='对象关系与预警';$('.engineering-panel .panel-head small').textContent='ONTOLOGY';
 const head=$('.engineering-panel .panel-head').outerHTML;$('.engineering-panel').innerHTML=head+'<div id="scene-relations" class="ontology-relations"><p class="ontology-empty">选择图中实体查看本体关系。</p></div>';
 $('.archive-foot').innerHTML='<span class="ontology-snapshot-note" id="dataset-caption">加载全域本体</span><span class="ontology-datasets"><button id="dataset-real" type="button">资料</button><button id="dataset-demo" type="button">演示</button></span>';
 for(const dataset of ['real','demo'])$('#dataset-'+dataset).onclick=()=>database.changeDataset(dataset);
 function sceneEntities(){return state.entities.filter(e=>sceneAnchorFor(e,adapter.objects,adapter.activeAsset));}
 function setData(){
  const summary=state.summary?.scene||{},demo=state.dataset==='demo';$('#scope-entity-count').innerHTML=esc(summary.principal_count??'—')+'<i>个</i>';$('#scope-device-count').innerHTML=esc(summary.device_count??'—')+'<i>个</i>';
  const captions=$('.scope-stats').querySelectorAll('.scope-stat>span');captions[0].textContent='全域空间对象';captions[1].textContent=demo?'演示设备实体':'登记设备实体';
  $('#dataset-caption').textContent=demo?'演示业务 · 卫星轮廓':'资料记录 · 未现场核验';for(const dataset of ['real','demo'])$('#dataset-'+dataset).setAttribute('aria-pressed',String(state.dataset===dataset));
  const archive=$('.document-area').children;archive[0].querySelector('strong').innerHTML=esc(summary.principal_count??'—')+'<i>个</i>';archive[0].querySelector('span').textContent='本场景空间身份';
  const relations=new Set(sceneEntities().flatMap(e=>(e.relations||[]).map(r=>r.id)));archive[1].querySelector('strong').innerHTML=esc(relations.size)+'<i>条</i>';archive[1].querySelector('span').textContent='数据库本体关系';
  $('.bottom-status .status-left').innerHTML='<i></i>'+esc(demo?'全域样例业务 · 观测为固定快照 / 非现场实况':'来源档案 · 卫星概略 / 样例外观 · 业务缺失保持空值');
  rebuild();renderList(sceneEntities().filter(e=>e.kind!=='device').slice(0,4));if(!selected)renderReadings(null);
 }
 function rebuild(){
  layer.replaceChildren();markers=[];lastAsset=adapter.activeAsset;
  for(const entity of sceneEntities()){
   const anchor=sceneAnchorFor(entity,adapter.objects,adapter.activeAsset);if(!anchor)continue;
   add(entity,entity.kind,anchor,null);
   const alert=(entity.business_alerts||[]).find(a=>a.condition_historically_met);if(alert)add(entity,'alert',anchor,alert);
  }
 }
 function add(entity,kind,anchor,alert){
  const button=document.createElement('button');button.className='ontology-marker';button.dataset.sceneEntity=entity.id;button.dataset.kind=kind;button.dataset.dataset=entity.dataset;if(alert)button.dataset.alertId=alert.id;
  button.innerHTML=`<span class="ontology-symbol">${glyph(kind)}</span><span>${esc(alert?'样例条件 · '+shortName(entity):shortName(entity))}<small>${esc(alert?'固定快照 / 非生产预警':(entity.class_iris?.[0]?.split('/').at(-1)||kindLabels[kind]||kind)+' · '+(entity.dataset==='demo'?'演示':'资料'))}</small></span>`;
  button.title=(alert?alert.title+'；':'')+entity.id+'；'+(entity.dataset==='demo'?'合成演示，非现场事实':'可追溯来源对象');button.onclick=()=>database.selectEntity(entity.id,{navigate:kind==='device'});layer.appendChild(button);
  const point=new THREE.Vector3(...anchor.position);point.y+=kind==='device'?3:kind==='alert'?12:0;
  markers.push({id:entity.id+(alert?':alert':''),entity,kind,button,point});
 }
 function renderList(entities){
  const principals=[...new Map(entities.filter(e=>e.kind!=='device').map(e=>[e.id,e])).values()];if(selected&&!principals.some(e=>e.id===selected.id))principals.unshift(selected);for(const candidate of sceneEntities().filter(e=>e.kind!=='device')){if(principals.length>=4)break;if(!principals.some(e=>e.id===candidate.id))principals.push(candidate);}const items=principals.slice(0,4),key=state.dataset+items.map(e=>e.id).join(',');if(key===lastList)return;lastList=key;
  $('#visible-entities').innerHTML=items.map(e=>`<button class="unit-item ${selected?.id===e.id?'active':''}" data-entity="${esc(e.id)}"><svg viewBox="0 0 38 32"><path d="m3 12 18-8 14 8-18 8-14-8Zm0 4 14 8 18-8M3 21l14 8 18-8"/></svg><div class="unit-info"><strong>${esc(shortName(e))}</strong><small>${esc(kindLabels[e.kind]||e.kind)} · 全域${esc(state.summary?.scene?.counts?.[e.kind]||0)} · ${e.dataset==='demo'?'演示':'资料'}</small></div><span class="unit-id">${glyph(e.kind)}</span></button>`).join('')||'<p class="ontology-empty">正在读取当前数据集…</p>';
 }
 function select(entity){
  selected=entity;lastList='';const demo=entity.dataset==='demo',klass=entity.class_iris?.[0]?.split('/').at(-1)||entity.kind;
  const source=demo?'全域样例配置 v1':entity.sources?.some(s=>s.file?.endsWith('.xls'))?'原始面积台账':'卫星/图纸来源表示';
  const modelArea=entity.scenario_properties?.model_area_m2,detailLabel=entity.area?.value!=null?'台账面积':Number.isFinite(modelArea)?'模型估算面积':entity.kind==='device'?'设备状态':'用途 / 作物',detailValue=entity.area?.value!=null?database.areaText(entity):Number.isFinite(modelArea)?Math.round(modelArea).toLocaleString()+' m²（演示）':entity.kind==='device'?(demo?'样例登记 / 未接入':'登记状态待核'):entity.species||entity.scenario_properties?.usage||'待核查';
  $('#selection').dataset.entityId=entity.id;$('#selection').innerHTML=`<div class="selected-kicker"><span class="ontology-uuid-inline" title="UUID ${esc(entity.id)}">UUID ${esc(entity.id)}</span><span class="pill" id="profile-details" role="button" tabindex="0">${demo?'演示数据':'来源资料'}</span></div><h3 class="selected-title">${esc(shortName(entity))}</h3><div class="property"><span>本体分类</span><b>${esc(klass)}</b></div><div class="property"><span>来源</span><b class="ontology-source-value" title="${esc(entity.sources?.map(s=>s.file||s.id).join('；'))}">${esc(source)}</b></div><div class="property"><span>${detailLabel}</span><b class="ontology-source-value" title="${esc(detailValue)}">${esc(detailValue)}</b></div><button class="focus-action" id="focus-selected">◎ 定位此本体对象</button>`;
  $('#focus-selected').onclick=()=>database.selectEntity(entity.id);$('#profile-details').onclick=database.openDetails;$('#profile-details').onkeydown=e=>{if(e.key==='Enter')database.openDetails();};renderReadings(entity);setRelations(null);renderList(sceneEntities());
 }
 function renderReadings(entity){
  const observations=entity?.observations||[],demo=entity?.dataset==='demo',quality=new Set((entity?.quality_alerts||[]).map(a=>a.code));$('.monitor-status strong').textContent=quality.has('stale_observation')?(demo?'演示快照 · 已过期':'观测已过期'):quality.has('unit_conflict')?'观测单位待核':quality.has('future_observation')||quality.has('invalid_observation_time')?'观测时间待核':demo?'演示观测快照':observations.length?'来源观测记录':'等待设备接入';
  $('.monitor-status small').textContent=observations[0]?.observed_at?(demo?'非实时 · ':'记录 · ')+observations[0].observed_at.replace('T',' ').slice(0,16)+'Z':'暂无已登记观测';
  const boxes=$('.monitor-readings').children;for(let i=0;i<boxes.length;i++){const obs=observations[i];boxes[i].querySelector('span').textContent=obs?(obs.label||obs.metric).replace('（演示）',''):['水情 / 土壤','环境观测','设备采样','来源时间'][i];boxes[i].querySelector('b').textContent=obs?String(obs.value):'—';boxes[i].querySelector('i').textContent=obs?.unit||'';}
 }
 function setRelations(value){
  graph=value;for(const child of [...lines.children]){lines.remove(child);child.geometry?.dispose();child.material?.dispose();}
  if(!selected){$('#scene-relations').innerHTML='<p class="ontology-empty">点击图中实体、设备或预警标记。</p>';return;}
  if(value?.error){$('#scene-relations').innerHTML='<p class="ontology-empty">本体关系查询暂不可用，请重新选择重试。</p>';return;}
  const edges=value?.edges||[],entities=new Map(state.entities.map(e=>[e.id,e])),html=[];
  for(const edge of edges){const subject=entities.get(edge.subject_id),target=entities.get(edge.target_id),other=edge.subject_id===selected.id?target:subject;
   html.push(`<button class="ontology-relation" data-relation-id="${esc(edge.id||edge.assertion_id||edge.subject_id+'-'+edge.target_id)}" data-related-entity="${esc(other?.id||'')}"><strong>${esc(subject?shortName(subject):edge.subject_id)}</strong> → ${esc(predicateName(edge.predicate_iri))} → <strong>${esc(target?shortName(target):edge.target_id)}</strong>${selected.dataset==='demo'?' · 演示':''}</button>`);
   const a=subject&&sceneAnchorFor(subject,adapter.objects,adapter.activeAsset),b=target&&sceneAnchorFor(target,adapter.objects,adapter.activeAsset);if(a&&b){const p=new THREE.Vector3(...a.position).add(new THREE.Vector3(0,12,0)),q=new THREE.Vector3(...b.position).add(new THREE.Vector3(0,12,0)),mid=p.clone().lerp(q,.5);mid.y+=14;const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([p,mid,q]),new THREE.LineDashedMaterial({color:0xb4efcf,transparent:true,opacity:.85,dashSize:5,gapSize:3,depthTest:false}));line.computeLineDistances();line.userData.relationId=edge.id;lines.add(line);}
  }
  const alert=(selected.business_alerts||[]).find(a=>a.condition_historically_met);if(alert)html.push(`<p class="ontology-alert-note">⚠ ${esc(alert.title)} · ${alert.status==='stale'?'已过期':'演示条件满足'}<br>仅合成规则，不是现场处置指令。</p>`);
  $('#scene-relations').innerHTML=html.join('')||'<p class="ontology-empty">'+(value?'没有已登记关系；不按同名推断。':'正在查询本体关系…')+'</p>';
  $('#scene-relations').onclick=event=>{const button=event.target.closest('[data-related-entity]');if(button?.dataset.relatedEntity)database.selectEntity(button.dataset.relatedEntity,{navigate:false});};
 }
 function clear(){selected=null;graph=null;lastList='';$('#selection').dataset.entityId='';$('#selection').innerHTML='<div class="selected-kicker"><span>全域本体</span><span class="pill">待选择</span></div><h3 class="selected-title">点击图中对象</h3><div class="property"><span>身份 / 类型</span><b>数据库查询</b></div><div class="property"><span>数据性质</span><b>'+ (state.dataset==='demo'?'独立合成演示':'来源资料')+'</b></div><div class="property"><span>设备与关系</span><b>点击图标查看</b></div>';renderReadings(null);setRelations(null);setData();}
 function update(now){
  if(now-lastFrame<90)return;lastFrame=now;if(lastAsset!==adapter.activeAsset){rebuild();setRelations(graph);lastList='';}
  const width=adapter.renderer.domElement.clientWidth,height=adapter.renderer.domElement.clientHeight,candidates=[];
  for(const marker of markers){marker.button.hidden=true;const p=marker.point.clone().project(adapter.camera);if(p.z<=-1||p.z>=1||Math.abs(p.x)>1||Math.abs(p.y)>1)continue;marker.button.dataset.active=String(marker.entity.id===selected?.id);candidates.push({...marker,x:(p.x*.5+.5)*width,y:(-.5*p.y+.5)*height,selected:marker.entity.id===selected?.id});}
  const distance=adapter.camera.position.distanceTo(adapter.controls.target),max=width<560?6:distance>700?14:18,placed=layoutMarkers(candidates,{width,height,max});
  for(const item of placed){item.button.hidden=false;item.button.style.left=item.x+'px';item.button.style.top=item.y+'px';}
  renderList(placed.map(p=>p.entity));
 }
 clear();return{setData,select,setRelations,clear,update,layer};
}
