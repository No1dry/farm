import {api,post,escapeHTML as esc,safeURL} from './twin-adapter.js';
import './assistant.css';

const areaText=e=>e?.area?.value==null?'待补充':`${e.area.value}（${e.area.unit||'原表单位未注'}）`;
const pretty=value=>typeof value==='object'?JSON.stringify(value,null,2):String(value??'未记录');
const facts=items=>items.map(([k,v])=>`<div class="property"><span>${esc(k)}</span><b>${esc(v??'待确认')}</b></div>`).join('');

export function mountAssistant({adapter,modal,closeModal,toast,onEntity,onClear,onView,onCancel,onData=()=>{},onRelations=()=>{}}){
 const state={dataset:'demo',entities:[],summary:null,relations:null,selected:null,lastReply:null,history:[],canSave:false,selectionVersion:0,chatVersion:0,dataVersion:0};
 document.querySelector('#twin').insertAdjacentHTML('beforeend',`<button id="assistant-toggle" class="focus-assistant-toggle">✧ 农业助手</button><section id="assistant" class="focus-assistant" aria-label="农业助手" hidden><div class="fa-heading"><div><strong>农业助手</strong><small id="model-status">连接数据库…</small></div><button id="assistant-close" aria-label="关闭助手">×</button></div><p id="context">当前未选中对象</p><div id="messages" aria-live="polite"><p>可查询台账、定位对象并核查预警；建议需人工复核。</p></div><form id="chat-form"><textarea id="chat-input" rows="2" maxlength="4000" required aria-label="对话内容" placeholder="例如：进入庙下刘的 L18，介绍资料依据"></textarea><button id="send" type="submit">发送 ↑</button></form><button id="catalog-from-assistant" type="button">查询全部对象与片区</button><small class="fa-note">本系统没有设备控制接口。公开资料不等于现场事实。</small></section>`);
 const $=s=>document.querySelector(s);
 function openAssistant(){$('#assistant').hidden=false;$('#chat-input').focus();}
 $('#assistant-toggle').onclick=openAssistant;$('#assistant-close').onclick=()=>$('#assistant').hidden=true;
 function cancelPending(){state.selectionVersion++;adapter.cancelNavigation();onCancel();}
 function sourceCards(sources){return (sources||[]).length?`<details><summary>来源与证据（${sources.length}）</summary>${sources.map(source=>{const url=safeURL(source.url);const file=source.file&&(/^(参考图|现场竣工图pdf版本)\//.test(source.file)||source.file==='梁湖情田块面积汇总202607.xls');return`<article><b>${esc(source.title||source.file||source.id)}</b>${source.summary?`<p>${esc(source.summary)}</p>`:''}${url?`<p><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">发布机构原文 ↗</a></p>`:''}${file?`<p><a href="/api/sources/${encodeURIComponent(source.id)}/file?dataset=${encodeURIComponent(source.dataset||state.dataset)}" target="_blank" rel="noopener">原始资料 ↗</a></p>`:''}<details><summary>证据位置与版本</summary><pre>${esc(pretty(source))}</pre></details></article>`;}).join('')}</details>`:'<p>暂无可追溯来源。</p>';}
 async function loadData(){
  const version=++state.dataVersion,dataset=state.dataset;
  try{const [page,health,summary]=await Promise.all([api(`/entities?dataset=${dataset}&limit=1000`),api('/health'),api(`/summary?dataset=${dataset}`)]);if(version!==state.dataVersion||dataset!==state.dataset)return false;
   state.entities=page.items;state.summary=summary;adapter.bindEntities(state.entities);onData();$('#model-status').textContent=health.model.configured?`本地/服务端模型 · ${health.model.model}`:'模型未配置 · 仍可查询数据库';return true;
  }catch(error){if(version===state.dataVersion){state.entities=[];state.summary=null;adapter.bindEntities([]);onData();$('#model-status').textContent='数据库未连接';toast('数据库不可用：'+error.message);}return false;}
 }
 function preferred(entity){if(entity.scene_anchor&&adapter.canLocateEntity(entity))return entity.scene_anchor.spatial_id;return(entity.spatial_ids||[]).filter(id=>adapter.objects.has(id)).sort((a,b)=>{const aa=adapter.objects.get(a),bb=adapter.objects.get(b);return (aa.asset_id===adapter.activeAsset?-1:0)-(bb.asset_id===adapter.activeAsset?-1:0);})[0]||null;}
 async function selectEntity(id,{navigate=true,preserveNavigation=false}={}){
  const version=++state.selectionVersion,dataset=state.dataset;if(!preserveNavigation){adapter.cancelNavigation();onCancel();}const navigation=adapter.navigationVersion;
  try{const entity=await api(`/entities/${encodeURIComponent(id)}?dataset=${dataset}`);if(version!==state.selectionVersion||dataset!==state.dataset)return null;
   state.selected=entity;state.relations=null;const spatial=preferred(entity);onEntity(entity,spatial);$('#context').textContent=`当前：${entity.region} · ${entity.code||entity.name} · ${dataset==='demo'?'合成演示':'资料记录'}`;
   api(`/relations/${encodeURIComponent(entity.id)}?dataset=${dataset}&depth=1`).then(graph=>{if(version===state.selectionVersion&&dataset===state.dataset){state.relations=graph;onRelations(graph);}}).catch(()=>{if(version===state.selectionVersion&&dataset===state.dataset)onRelations({error:'unavailable',edges:[],nodes:[]});});
   if(navigate&&navigation===adapter.navigationVersion){if(spatial){const view=await adapter.focusEntity(entity);if(version===state.selectionVersion&&dataset===state.dataset&&view&&adapter.isCurrent(view.token))onView(view);}else{adapter.clearHighlight();toast('该档案未关联空间表示，不跳转到同名对象。');}}
   return entity;
  }catch(error){if(version===state.selectionVersion)toast(error.message);return null;}
 }
 async function selectSpatial(id,options={}){
  id=adapter.toSpatial(id);const identifier=adapter.bindings?.get(id);
  if(!identifier){cancelPending();state.selected=null;$('#context').textContent='空间对象尚未关联当前数据集';onClear(adapter.objects.get(id));if(options.navigate!==false){const view=await adapter.focusSpatial(id);if(view)onView(view);}return null;}
  return selectEntity(identifier,options);
 }
 async function changeDataset(dataset){
  if(!['real','demo'].includes(dataset))return;cancelPending();state.chatVersion++;state.dataset=dataset;state.entities=[];state.summary=null;state.relations=null;state.selected=null;state.lastReply=null;state.history=[];adapter.bindEntities([]);adapter.clearHighlight();onClear();onData();$('#context').textContent='当前未选中对象';$('#messages').textContent='已切换数据集，对话上下文已清空。';$('#send').disabled=false;return loadData();
 }
 function openCatalog(){
  const dialog=modal('资料查询与片区切换','原面板保持重点单元；完整台账与空间资料在此检索。',`<div class="source-info"><p>模型片区：${adapter.assets.map(a=>`<button class="text-button" data-asset="${esc(a.id)}">${esc(a.label||a.name||a.id)}</button>　`).join('')}</p><p><button class="text-button" data-dataset="real">资料数据</button>　<button class="text-button" data-dataset="demo">隔离演示</button><span id="catalog-dataset">　当前：${state.dataset==='demo'?'合成演示':'资料数据'}</span></p><p><label>编号 / 片区 / 名称　<input id="search" aria-label="搜索地块" size="28" placeholder="例如 L18、庙下流、E3"></label></p><p id="catalog-count"></p><div id="entity-list"></div></div>`);
  const render=()=>{if(!dialog.isConnected)return;const query=dialog.querySelector('#search').value.trim().toLowerCase();const matches=state.entities.filter(e=>[e.code,e.name,e.region,e.scenario_properties?.original_geometry_name,...(e.aliases||[])].join(' ').toLowerCase().includes(query));dialog.querySelector('#catalog-count').textContent=`${state.dataset==='demo'?'合成演示':'资料记录'}：匹配 ${matches.length} 条，显示前 60 条。记录数不代表已核验现场资产数。`;
   dialog.querySelector('#entity-list').innerHTML=matches.slice(0,60).map(e=>`<p><button class="text-button" data-entity="${esc(e.id)}">${esc(e.region)} · ${esc(e.code||e.name)} · ${esc(e.name)}　${esc(areaText(e))}</button></p>`).join('')||'<p>没有匹配对象。</p>';};
  dialog.querySelector('#search').oninput=render;render();dialog.onclick=event=>{
   if(event.target===dialog){closeModal();return;}const asset=event.target.closest('[data-asset]');if(asset){cancelPending();state.selected=null;$('#context').textContent='当前未选中对象';onClear();closeModal();adapter.showAsset(asset.dataset.asset).then(view=>{if(view)onView(view);}).catch(e=>toast(e.message));return;}
   const choice=event.target.closest('[data-entity]');if(choice){closeModal();selectEntity(choice.dataset.entity);return;}
   const dataset=event.target.closest('[data-dataset]');if(dataset){const loading=changeDataset(dataset.dataset.dataset);dialog.querySelector('#catalog-dataset').textContent='　当前：'+(state.dataset==='demo'?'合成演示':'资料数据');dialog.querySelector('#entity-list').replaceChildren();dialog.querySelector('#catalog-count').textContent='正在加载当前数据集…';loading.then(()=>{if(dialog.isConnected)render();});}
  };return dialog;
 }
 $('#catalog-from-assistant').onclick=openCatalog;
 function openDetails(){
  const entity=state.selected;if(!entity){openCatalog();return;}
  const dialog=modal(`${entity.region} · ${entity.code||entity.name}`,entity.dataset==='demo'?'独立合成演示，不代表现场':'来源资料，未经现场核验',`<div class="source-info">${facts([['稳定身份',entity.id],['台账面积',areaText(entity)],['种植/养殖',entity.species||'未确认'],['数据性质',entity.data_nature],['空间关联',(entity.spatial_ids||[]).join('、')||'未关联']])}<p>模型面积、台账面积与图纸面积分别保存；纸页坐标不能当实地米制。</p><details><summary>空间表示及精度</summary><pre>${esc(pretty(entity.representations))}</pre></details><details><summary>观测与设备</summary><pre>${esc(pretty({observations:entity.observations,devices:entity.devices,alerts:entity.alerts}))}</pre></details><details open><summary>本体关系</summary><div id="profile-relations">正在查询…</div></details>${sourceCards(entity.sources)}<p><button class="text-button" id="ask-current">请助手核查此对象</button></p></div>`);
  api(`/relations/${encodeURIComponent(entity.id)}?dataset=${entity.dataset}&depth=1`).then(graph=>{if(dialog.isConnected)dialog.querySelector('#profile-relations').innerHTML=graph.edges.length?`<pre>${esc(pretty(graph))}</pre>`:'<p>尚无已登记关系，不按同名推断设备。</p>';}).catch(error=>{if(dialog.isConnected)dialog.querySelector('#profile-relations').textContent=error.message;});
  dialog.querySelector('#ask-current').onclick=()=>{closeModal();openAssistant();$('#chat-input').value='核查当前对象的资料、预警和可用依据，指出缺失与不确定性。';};
 }
 function append(role,html){const node=document.createElement('div');node.className='fa-message '+role;node.innerHTML=html;$('#messages').appendChild(node);$('#messages').scrollTop=$('#messages').scrollHeight;return node;}
 function renderReply(reply,dataset){
  const status={ok:'模型回答 · 需人工复核',unconfigured:'模型未配置 · 数据库查询',unavailable:'模型不可用 · 保留数据库证据',invalid_response:'模型输出未通过校验',needs_clarification:'目标有歧义，请选择',not_found:'未找到明确目标'}[reply.status]||reply.status;
  let html=`<small>${esc(status)}</small><p>${esc(reply.answer)}</p>`;
  if(reply.status==='not_found'&&dataset==='demo')html+='<p>当前为独立演示业务，真实田块需在资料数据中查询。</p><button data-search-real>到真实资料查找</button>';
  for(const candidate of reply.candidates||[])html+=`<button data-candidate="${esc(candidate.id)}">${esc(candidate.region)} · ${esc(candidate.code||candidate.name)}</button>`;
  if(reply.gaps?.length)html+=`<details open><summary>判断边界</summary><ul>${reply.gaps.map(g=>`<li>${esc(g)}</li>`).join('')}</ul></details>`;
  if(reply.analysis_sections)html+=`<details open><summary>数据库事实与核查建议</summary>${reply.analysis_sections.map(s=>`<article><b>${esc(s.title)}</b><p>${esc(s.content)}</p></article>`).join('')}</details>`;
  html+=sourceCards(reply.evidence||[]);
  if(reply.saved_plans?.length)html+=`<details><summary>历史草稿（非执行记录）</summary>${reply.saved_plans.map(p=>`<b>${esc(p.title)}</b><p>${esc(p.content)}</p>`).join('')}</details>`;
  const plan=reply.suggested_plan;if(plan)html+=`<details open><summary>${reply.analysis_kind==='model_assisted_evidence_review'?'模型核查草稿':'规则核查清单'} · 未执行</summary><b>${esc(plan.title)}</b><p>${esc(plan.content)}</p><p>${esc((plan.conditions||[]).join('；'))}</p><ul>${[...new Set([...(reply.gaps||[]),...(plan.gaps||[])])].map(g=>`<li>${esc(g)}</li>`).join('')}</ul></details>${state.canSave?'<button data-save-plan>保存此方案记录</button>':'<p>当前只读，保存需要本地操作员身份。</p>'}`;
  const node=append('answer',html);node.onclick=async event=>{const choice=event.target.closest('[data-candidate]');if(choice){await selectEntity(choice.dataset.candidate);return;}const save=event.target.closest('[data-save-plan]');if(save){save.disabled=true;try{if(dataset!==state.dataset||!reply.entity)throw Error('当前数据集或对象已变化，请重新核查');const result=await post('/plans',{title:plan.title,entity_id:reply.entity.id,dataset,content:plan.content,evidence_ids:plan.evidence_ids,conditions:plan.conditions||[],gaps:[...new Set([...(reply.gaps||[]),...(plan.gaps||[])])]});save.textContent='已保存 · '+result.id;}catch(error){save.disabled=false;toast(error.message);}}};
 }
 $('#chat-form').onsubmit=async event=>{
  event.preventDefault();const message=$('#chat-input').value.trim();if(!message)return;const version=++state.chatVersion,dataset=state.dataset,selection=state.selectionVersion,navigation=adapter.navigationVersion;
  state.lastQuery=message;append('user',esc(message));$('#chat-input').value='';$('#send').disabled=true;
  try{const reply=await post('/assistant',{message,selected_entity_id:state.selected?.id||null,dataset,history:state.history.slice(-12)});if(version!==state.chatVersion||dataset!==state.dataset)return;
   state.lastReply=reply;renderReply(reply,dataset);state.history.push({role:'user',content:message.slice(0,4000)},{role:'assistant',content:(reply.answer||'').slice(0,4000)});
   if(reply.entity&&selection===state.selectionVersion&&navigation===adapter.navigationVersion){const lookup=selectEntity(reply.entity.id,{navigate:false}),ownSelection=state.selectionVersion,ownNavigation=adapter.navigationVersion;const entity=await lookup;if(!entity||version!==state.chatVersion||dataset!==state.dataset||ownSelection!==state.selectionVersion||ownNavigation!==adapter.navigationVersion)return;
    for(const action of reply.actions||[]){if(action.type!=='focus_entity'||action.entity_id!==entity.id||ownSelection!==state.selectionVersion||!adapter.canLocateEntity(entity))continue;const view=await adapter.focusEntity(entity);if(view&&ownSelection===state.selectionVersion&&adapter.isCurrent(view.token))onView(view);}}
  }catch(error){if(version===state.chatVersion)append('error',esc(error.message));}finally{if(version===state.chatVersion)$('#send').disabled=false;}
 };
 $('#messages').addEventListener('click',async event=>{const button=event.target.closest('[data-search-real]');if(!button)return;const query=(state.lastQuery||'').match(/[A-Z]+\d+(?:-\d+)?/i)?.[0]||'';button.disabled=true;const switching=changeDataset('real'),version=state.dataVersion;await switching;if(state.dataset!=='real'||version!==state.dataVersion)return;const dialog=openCatalog(),search=dialog.querySelector('#search');search.value=query;search.dispatchEvent(new Event('input'));});
 async function initialize(){const dataset=state.dataset,selection=state.selectionVersion,navigation=adapter.navigationVersion,loading=loadData(),dataVersion=state.dataVersion;const[loaded]=await Promise.all([loading,post('/auth/local-session',{}).then(r=>state.canSave=['operator','admin'].includes(r.actor?.role)).catch(()=>state.canSave=false)]);if(!loaded||dataset!==state.dataset||selection!==state.selectionVersion||navigation!==adapter.navigationVersion||dataVersion!==state.dataVersion)return null;const first=state.entities.find(e=>e.scene_anchor?.role==='object'&&e.business_alerts?.length)||state.entities.find(e=>e.spatial_ids?.length);return first?selectEntity(first.id,{navigate:false,preserveNavigation:true}):null;}
 return{state,initialize,selectEntity,selectSpatial,changeDataset,openCatalog,openDetails,openAssistant,cancelPending,areaText};
}
