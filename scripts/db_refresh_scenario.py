"""Refresh only the editable synthetic full-area scenario, retaining real records."""
import argparse
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.importer import ROOT,read_json,file_digest
from backend.scenario import import_full_scene
from backend.store import Store,canonical


def refresh(db_path):
    store=Store(db_path)
    def real_fingerprint():
        with store.connection() as db:
            rows=[dict(r) for r in db.execute("SELECT id,payload,revision FROM entities WHERE dataset='real' ORDER BY id")]
        return hashlib.sha256(canonical(rows).encode()).hexdigest()
    before=real_fingerprint()
    timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=ROOT/'runtime/backups'/('farm-before-scenario-refresh-'+timestamp+'.sqlite3')
    store.backup(backup)
    manifest=ROOT/'public/models/manifest.json'
    recipe=ROOT/'data/demo/full-area-scenario.json'
    layout=ROOT/'data/demo/full-area-device-layout.json'
    result=import_full_scene(store,read_json(manifest),read_json(recipe),file_digest(recipe),dict(read_json(layout),_source_sha256=file_digest(layout)))
    after=real_fingerprint()
    if before!=after:raise RuntimeError('Real record fingerprint changed unexpectedly')
    result.update(timestamp=datetime.now(timezone.utc).isoformat(),backup=str(backup.relative_to(ROOT)),backup_sha256=file_digest(backup),
        real_unchanged=True,real_entity_payload_sha256=after,recipe_sha256=file_digest(recipe),layout_sha256=file_digest(layout),
        scene_summary=store.summary('demo')['scene'])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--db',default=str(ROOT/'runtime/farm.sqlite3'));parser.add_argument('--receipt')
    args=parser.parse_args();result=refresh(Path(args.db));output=json.dumps(result,ensure_ascii=False,indent=2)
    if args.receipt:Path(args.receipt).write_text(output+'\n',encoding='utf8')
    print(output)
