"""Take a consistent final snapshot and verify every restored application table.

Never overwrites the active database or an existing backup. Source checks refer
to the original user-input manifest, not generated asset counts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_fingerprints(path):
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Snapshot failed SQLite integrity check')
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        result = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            rows = [json.dumps(tuple(row), ensure_ascii=False, separators=(',', ':'),
                               default=lambda value: {'blob_hex': value.hex()})
                    for row in db.execute('SELECT * FROM ' + quoted)]
            result[table] = {'count': len(rows), 'sha256': hashlib.sha256(
                '\n'.join(sorted(rows)).encode('utf8')).hexdigest()}
        return result, db.execute('PRAGMA user_version').fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='runtime/farm.sqlite3')
    args = parser.parse_args()
    source = (ROOT / args.db).resolve()
    if not source.is_file():
        raise FileNotFoundError('Active database does not exist')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = ROOT / 'runtime/backups' / f'farm-v06-{stamp}.sqlite3'
    restored = ROOT / 'runtime/backups' / f'farm-v06-restored-{stamp}.sqlite3'
    if backup.exists() or restored.exists():
        raise FileExistsError('Snapshot destinations must be new paths')
    backup.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as db:
        with sqlite3.connect(backup) as target:
            db.backup(target)
    subprocess.run([sys.executable, str(ROOT / 'scripts/db_restore.py'), str(backup), str(restored)],
                   check=True, capture_output=True, text=True)
    tables, version = table_fingerprints(backup)
    restored_tables, restored_version = table_fingerprints(restored)
    if tables != restored_tables or version != restored_version:
        raise RuntimeError('Restored schema or application table contents differ')
    sources = json.loads((ROOT / 'data/audit/source-manifest.json').read_text(encoding='utf8'))['sources']
    items = [{'path': item['path'], 'unchanged': digest(ROOT / item['path']) == item['sha256']}
             for item in sources]
    if not all(item['unchanged'] for item in items):
        raise RuntimeError('Original user inputs changed')
    output = ROOT / 'deliverables/verification'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'original-source-integrity.json').write_text(json.dumps({
        'captured_at': datetime.now(timezone.utc).isoformat(), 'original_sources': len(items),
        'all_unchanged': True, 'items': items}, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    report = {'captured_at': datetime.now(timezone.utc).isoformat(),
              'backup': backup.relative_to(ROOT).as_posix(), 'restored': restored.relative_to(ROOT).as_posix(),
              'backup_sha256': digest(backup), 'integrity': 'ok', 'schema_version': version,
              'all_application_tables_equal': True, 'tables': tables,
              'original_source_files_unchanged': len(items),
              'note': 'Consistent V0.6 snapshot; compared all application table contents after restore to a new path. Secrets excluded.'}
    (output / 'final-backup.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'verified': True, 'tables': len(tables), 'original_sources': len(items),
                      'backup': report['backup']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
