"""Monotonic schema additions; migration never recreates business identities."""
from datetime import datetime,timezone

SCHEMA_VERSION=2


def migrate(db):
    version=db.execute('PRAGMA user_version').fetchone()[0]
    if version>SCHEMA_VERSION:raise ValueError('Unsupported newer database schema')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL,description TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS knowledge_entries(id TEXT PRIMARY KEY,version TEXT NOT NULL,payload TEXT NOT NULL,content_digest TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS import_previews(id TEXT PRIMARY KEY,dataset TEXT NOT NULL,payload TEXT NOT NULL,
        content_digest TEXT NOT NULL,baseline TEXT NOT NULL,actor_id TEXT NOT NULL,created_at TEXT NOT NULL,
        state TEXT NOT NULL,receipt TEXT);
    ''')
    stamp=datetime.now(timezone.utc).isoformat()
    db.execute('INSERT OR IGNORE INTO schema_migrations VALUES (1,?,?)',(stamp,'Initial persisted identity and evidence schema'))
    db.execute('INSERT OR IGNORE INTO schema_migrations VALUES (2,?,?)',(stamp,'Public reference versions and controlled import staging'))
    db.execute('PRAGMA user_version=2')
