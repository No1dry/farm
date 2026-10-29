"""Back up the current SQLite file before opening it with the versioned migrator."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.store import Store

parser=argparse.ArgumentParser();parser.add_argument('--db',default='runtime/farm.sqlite3');args=parser.parse_args()
path=Path(args.db)
if path.exists():
    backup=path.parent/'backups'/('pre-migration-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite3')
    backup.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path) as source,sqlite3.connect(backup) as destination:source.backup(destination)
    print('Backup:',backup)
store=Store(path)
with store.connection() as db:print('Schema version:',db.execute('PRAGMA user_version').fetchone()[0])
