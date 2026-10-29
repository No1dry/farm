"""Produce an actual test/import/backup/semantic receipt from the current deployment."""
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import load_settings,ROOT
from backend.importer import initialize
from backend.store import Store
from backend.semantics import validate_graph,data_graph

settings=load_settings();store=Store(settings['db_path']);stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
temporary=ROOT.parent/'.tools'/('pytest-backend-receipt-'+stamp)
command=[sys.executable,'-m','pytest','tests/test_backend.py','-q','--basetemp',str(temporary)]
tests=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf8')
print(tests.stdout)
if tests.returncode:raise SystemExit('Backend tests failed; no successful verification receipt written')
matched=re.search(r'(\d+) passed',tests.stdout)
if not matched:raise SystemExit('Could not read test count')

def identity_snapshot(db):
    return {r['id']:(r['revision'],r['content_digest']) for r in db.execute('SELECT id,revision,content_digest FROM entities')}

with store.connection() as db:before=identity_snapshot(db)
initialize(store.path)
with store.connection() as db:
    after=identity_snapshot(db)
    if before!=after:raise SystemExit('Repeat import changed identity/revision; inspect before accepting deployment')
    integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
    version=db.execute('PRAGMA user_version').fetchone()[0]
    retired=db.execute("SELECT COUNT(*) FROM entities WHERE json_extract(payload,'$.state')='retired'").fetchone()[0]
    plans=db.execute('SELECT COUNT(*) FROM plans').fetchone()[0]
    knowledge=db.execute('SELECT COUNT(*) FROM knowledge_entries').fetchone()[0]
backup=ROOT/'runtime/backups'/('farm-verified-'+stamp+'.sqlite3')
restored=ROOT/'runtime/backups'/('farm-restored-'+stamp+'.sqlite3')
store.backup(backup)
subprocess.run([sys.executable,'scripts/db_restore.py',str(backup),str(restored)],cwd=ROOT,check=True,capture_output=True)
restored_store=Store(restored)
with restored_store.connection() as db:
    if identity_snapshot(db)!=after:raise SystemExit('Backup restore identity mismatch')
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Restored integrity failure')
manifest=json.loads((ROOT/'public/models/manifest.json').read_text(encoding='utf8'))
real=store.list_entities('real',limit=10000)['items'];ledger=[e for e in real if e['area']['value'] is not None]
binding_ids={sid for e in real for sid in e['spatial_ids']}
if binding_ids!={o['spatial_id'] for o in manifest['objects']}:raise SystemExit('Active spatial bindings differ from current manifest')
if len(ledger)!=100 or not all(e['spatial_ids'] for e in ledger):raise SystemExit('Not all 100 ledger identities have reviewed representations')
initial=ROOT/'runtime/backups/farm-20261029-final.sqlite3'
initial_ledger_match=None
if initial.exists():
    with sqlite3.connect(initial.as_uri()+'?mode=ro',uri=True) as db:
        old={r[0] for r in db.execute("SELECT id FROM entities WHERE dataset='real' AND json_extract(payload,'$.area_original') IS NOT NULL")}
    initial_ledger_match=old=={e['id'] for e in ledger}
    if not initial_ledger_match:raise SystemExit('Original ledger identity set changed')
semantic={d:validate_graph(data_graph(store,d)) for d in ('real','demo')}
model_receipts={}
for name in ('local-model-verification.json','local-model-verification-ready.json'):
    receipt=json.loads((ROOT/'docs/audit'/name).read_text(encoding='utf8'))
    model_receipts[name]={'status':receipt['assistant']['status'],'model':receipt['assistant']['model'],
        'evidence_ids':[e['id'] for e in receipt['assistant']['evidence']],
        'sections':len(receipt['assistant']['analysis_sections']),'production_plan_accepted':receipt['assistant']['production_plan_accepted']}
report={'verified_at':datetime.now(timezone.utc).isoformat(),'python_tests':{'command':command,'passed':int(matched[1]),'failed':0,
    'warnings':['Starlette TestClient httpx deprecation']},'database':{'schema_version':version,'integrity':integrity,
    'counts':{d:store.summary(d)['entity_count'] for d in ('real','demo')},'ledger_count':len(ledger),
    'bound_ledger_count':sum(bool(e['spatial_ids']) for e in ledger),'spatial_representations':len(binding_ids),
    'retired_identities':retired,'public_references':knowledge,'saved_drafts':plans,
    'original_ledger_uuid_set_unchanged':initial_ledger_match,'repeat_import_uuid_revision_unchanged':before==after},
    'backup_restore':{'backup':backup.relative_to(ROOT).as_posix(),'restored':restored.relative_to(ROOT).as_posix(),
        'integrity':'ok','identical_resource_ids_and_revisions':True,'schema_version':version},
    'semantic_validation':semantic,'actual_model_inference':model_receipts,
    'limitations':['No production equipment connected','No full upstream multi-store runtime exercised',
        'No field-approved agronomic thresholds or biological outcome verification','Arbitrary model prose is not proof of fact',
        'Source drawings use paper coordinates and are not georeferenced','Operator sessions and bearer roles are not a complete account platform']}
(ROOT/'docs/audit/backend-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(report['database'],ensure_ascii=False))
