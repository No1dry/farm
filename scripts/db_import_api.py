"""Explicit preview/apply client. Administrator bearer token never appears in output."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from backend.config import load_settings

parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['preview','apply']);parser.add_argument('input')
parser.add_argument('--dataset',default='real',choices=['real','demo']);parser.add_argument('--url',default='http://127.0.0.1:8000')
parser.add_argument('--output',default='runtime/import-receipt.json');args=parser.parse_args()
settings=load_settings();data=json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
if args.operation=='preview':
    records=data.get('records',[]) if isinstance(data,dict) else data
    records=[{**r,'source_id':r.get('source_id') or r.get('source_instance'),'kind':r.get('kind') or r.get('entity_type','field')} for r in records]
    body={'dataset':args.dataset,'records':records}
else:
    body={'preview_id':data['id'],'content_digest':data['content_digest']}
response=httpx.post(args.url+'/api/admin/imports/'+args.operation,json=body,
    headers={'Authorization':'Bearer '+settings['admin_token']},timeout=90)
if response.status_code>=400:raise SystemExit(f'Import rejected ({response.status_code}): '+response.text)
path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(response.json(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(f'{args.operation} receipt saved to {path}; no credential was exported')
