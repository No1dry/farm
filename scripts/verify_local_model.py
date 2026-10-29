"""Run real inference and the real assistant path; save receipts without credentials."""
import json
from pathlib import Path
import sys
import time
import argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi.testclient import TestClient
from backend.config import load_settings
from backend.app import create_app
from backend.store import Store

root=Path(__file__).resolve().parents[1]
args=argparse.ArgumentParser();args.add_argument('--scenario',choices=['historical','ready'],default='historical');args=args.parse_args()
settings=load_settings();store=Store(settings['db_path'])
kb=root/'data/knowledge/curated.json'
if kb.exists():store.import_knowledge(json.loads(kb.read_text(encoding='utf8'))['entries'])
headers={'Authorization':'Bearer '+settings['model_api_key']}
started=time.monotonic()
raw=httpx.post(settings['model_base_url']+'/chat/completions',headers=headers,timeout=120,json={
    'model':settings['model_name'],'messages':[{'role':'system','content':'你是中文助手。只返回JSON，回答字段是answer。'},
    {'role':'user','content':'某水塘没有今天的溶解氧观测，能否确定当前缺氧？请简短说明判断边界。'}],
    'temperature':0.2,'max_tokens':300,'response_format':{'type':'json_object'},'chat_template_kwargs':{'enable_thinking':False}})
raw.raise_for_status();model=raw.json()
client=TestClient(create_app(store=store,settings=settings))
pond=next(e for e in store.list_entities('demo')['items'] if (e['code']=='DEMO-CHECK-POND' if args.scenario=='ready' else e['business_alerts']))
original_post=httpx.Client.post
def capture_model(self,url,*args,**kwargs):
    response=original_post(self,url,*args,**kwargs)
    if str(url).startswith(settings['model_base_url']):
        (root/'runtime/model-last-response.json').write_text(json.dumps(response.json(),ensure_ascii=False,indent=2),encoding='utf8')
        (root/'runtime/model-last-request.json').write_text(json.dumps(kwargs.get('json'),ensure_ascii=False,indent=2),encoding='utf8')
    return response
httpx.Client.post=capture_model
question='依据这口独立合成塘已有观测、鱼种阶段、设备关系和适用公开资料，给出针对性的现场核查方案，含优先级、条件、设备核查和复测记录。不可将单次读数判为正常或缺氧，不给操作指令或阈值。' if args.scenario=='ready' else '分析这口演示水塘的缺氧预警，依据历史观测和检索资料给出现场核查方案。不要给设备操作指令。'
reply=client.post('/api/assistant',json={'message':question,
    'dataset':'demo','selected_entity_id':pond['id']}).json()
httpx.Client.post=original_post
result={'model':settings['model_name'],'base_url':settings['model_base_url'],'actual_inference':True,
    'smoke':{'response':model['choices'][0]['message']['content'],'usage':model.get('usage'),'elapsed_seconds':round(time.monotonic()-started,3),'accepted_as_advice':False,'note':'原始模型诊断输出，未受应用证据校验；可能包含无依据阈值，不能作为建议。'},
    'assistant':reply}
(root/('docs/audit/local-model-verification'+('-ready' if args.scenario=='ready' else '')+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'smoke':result['smoke'],'assistant_status':reply['status'],'model':reply['model'],'answer':reply['answer']},ensure_ascii=False))
if reply['status']!='ok':raise SystemExit('Actual model response needs review; see verification artifact')
