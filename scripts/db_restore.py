"""Restore a verified backup to a NEW destination; never overwrite an active database."""
import argparse
from pathlib import Path
import sqlite3

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('backup');parser.add_argument('destination')
    args=parser.parse_args();source=Path(args.backup).resolve();target=Path(args.destination).resolve()
    if not source.is_file():raise SystemExit('Backup does not exist')
    if target.exists():raise SystemExit('Destination must be new; stop the service and select a new database path')
    target.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Backup failed integrity check')
        if db.execute('PRAGMA user_version').fetchone()[0] not in (1,2):raise SystemExit('Unsupported schema version')
        with sqlite3.connect(target) as restored:
            db.backup(restored)
    print(str(target))
