"""Build/validate a public seed without copying operational history.

Only current entity identities are read from the readonly source; supporting
business tables are rebuilt by the public importer. This is not a backup tool.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.importer import initialize
from backend.store import Store, digest

SEED = ROOT / 'data/seed/farm-v0.6.0.sqlite3'
MANIFEST = ROOT / 'data/seed/manifest.json'
VERSION = 'v0.6.0'
TABLES = {
    'source_systems': ('id', 'dataset', 'source_key'),
    'entities': ('id', 'dataset', 'source_id', 'canonical_key', 'code', 'name', 'region', 'kind', 'payload', 'content_digest', 'revision', 'updated_at'),
    'entity_versions': ('entity_id', 'revision', 'payload', 'recorded_at'),
    'sources': ('id', 'dataset', 'payload'),
    'entity_sources': ('entity_id', 'source_id'),
    'spatial_bindings': ('dataset', 'spatial_id', 'entity_id', 'payload'),
    'relations': ('id', 'dataset', 'subject_id', 'predicate_iri', 'target_id', 'payload'),
    'plans': ('id', 'dataset', 'entity_id', 'payload', 'created_at'),
    'audit_log': ('id', 'created_at', 'tool', 'dataset', 'payload'),
    'schema_migrations': ('version', 'applied_at', 'description'),
    'knowledge_entries': ('id', 'version', 'payload', 'content_digest'),
    'import_previews': ('id', 'dataset', 'payload', 'content_digest', 'baseline', 'actor_id', 'created_at', 'state', 'receipt'),
}
EXCLUDED = ('plans', 'audit_log', 'import_previews')
SOURCE_SYSTEMS = {
    ('real', 'workbook-area-register'), ('real', 'blender-manifest'),
    ('demo', 'upstream-semantic-fixtures'), ('demo', 'farm-synthetic-scenarios'),
    ('demo', 'full-area-synthetic-scenario'),
}


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def readonly(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def check_schema(db):
    actual = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    if actual != set(TABLES):
        raise ValueError('Unreviewed database table set: ' + repr(sorted(actual ^ set(TABLES))))
    for table, columns in TABLES.items():
        if tuple(row[1] for row in db.execute(f'PRAGMA table_info("{table}")')) != columns:
            raise ValueError('Unreviewed columns in table ' + table)
    if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('view','trigger')").fetchone():
        raise ValueError('Unreviewed database views or triggers')
    if db.execute('PRAGMA user_version').fetchone()[0] != 2:
        raise ValueError('Release seed requires reviewed schema version 2')


def current_entities(db):
    rows = db.execute("SELECT * FROM entities WHERE coalesce(json_extract(payload,'$.state'),'') != 'retired' ORDER BY id").fetchall()
    for row in rows:
        UUID(row['id'])
        UUID(row['source_id'])
        payload = json.loads(row['payload'])
        if digest(payload) != row['content_digest'] or payload.get('resource_id') != row['id']:
            raise ValueError('Entity payload/digest/identity mismatch: ' + row['id'])
        # An idempotent refresh would otherwise retain private cached columns.
        code = str(payload.get('original_code') or payload.get('record_id') or payload['source_key'])
        contract = payload['source_key_contract']
        expected = (code, payload.get('name') or code, payload.get('region') or '未归属',
                    payload.get('kind', 'field'), contract['source_id'], contract['canonical_key'])
        actual = tuple(row[key] for key in ('code', 'name', 'region', 'kind', 'source_id', 'canonical_key'))
        if actual != expected:
            raise ValueError('Entity cached columns differ from public payload: ' + row['id'])
        if not isinstance(row['revision'], int) or row['revision'] < 1:
            raise ValueError('Invalid entity revision')
        timestamp = datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            raise ValueError('Entity update time must contain a timezone')
    return rows


def identity_rows(rows):
    return [[row['id'], row['dataset'], row['source_id'], row['canonical_key'], row['content_digest'], row['revision']] for row in rows]


def inspect_seed(path):
    with closing(readonly(path)) as db:
        check_schema(db)
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Seed database integrity check failed')
        counts = {table: db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] for table in TABLES}
        if any(counts[table] for table in EXCLUDED):
            raise ValueError('Operational history is forbidden in the public seed')
        rows = current_entities(db)
        if len(rows) != counts['entities']:
            raise ValueError('Retired entity history is forbidden in the public seed')
        if counts['entity_versions'] != len(rows) or db.execute('''SELECT 1 FROM entity_versions v
                JOIN entities e ON e.id=v.entity_id WHERE v.revision!=e.revision OR v.payload!=e.payload''').fetchone():
            raise ValueError('Only the current entity version may be released')
        systems = {(row['dataset'], row['source_key']) for row in db.execute('SELECT * FROM source_systems')}
        if systems != SOURCE_SYSTEMS:
            raise ValueError('Unreviewed business source systems')
        dataset_counts = dict(db.execute('SELECT dataset,count(*) FROM entities GROUP BY dataset').fetchall())
        ledger = sorted(row['id'] for row in rows if row['dataset'] == 'real' and row['canonical_key'].startswith('xls:'))
        if dataset_counts != {'real': 284, 'demo': 189} or len(ledger) != 100:
            raise ValueError('Unexpected v0.6.0 entity or ledger counts')
        return {'counts': counts, 'dataset_counts': dataset_counts, 'ledger_uuids': ledger,
                'identity_sha256': digest(identity_rows(rows))}


def validate_seed(seed_path=SEED, manifest_path=MANIFEST):
    seed_path, manifest_path = Path(seed_path), Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('release') != VERSION or manifest.get('schema_version') != 2:
        raise ValueError('Unexpected release seed manifest version')
    if sha256(seed_path) != manifest.get('sha256'):
        raise ValueError('Release seed hash does not match manifest')
    report = inspect_seed(seed_path)
    for key in ('counts', 'dataset_counts', 'ledger_uuids', 'identity_sha256'):
        if report[key] != manifest.get(key):
            raise ValueError('Release seed manifest mismatch: ' + key)
    return report


def public_sources(root, db):
    names = {
        'data/audit/entities.json', 'public/models/manifest.json', 'data/knowledge/curated.json',
        'data/demo/oxygen-scenario.json', 'data/demo/inspection-ready-scenario.json',
        'data/demo/full-area-scenario.json', 'data/demo/full-area-device-layout.json',
        'deliverables/liangzihu-samples/source-manifest.json',
    }
    audit = json.loads((root / 'data/audit/entities.json').read_text(encoding='utf-8-sig'))
    names.add(audit['source']['path'])
    model = json.loads((root / 'public/models/manifest.json').read_text(encoding='utf-8-sig'))
    for obj in model['objects']:
        names.update(e['source_file'] for e in obj.get('source_evidence', []) if e.get('source_file'))
    for row in db.execute('SELECT payload FROM sources'):
        name = json.loads(row[0]).get('file')
        if name:
            names.add(name)
    result = []
    for name in sorted(names):
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError('Public provenance file is missing or outside repository: ' + name)
        result.append({'path': path.relative_to(root).as_posix(), 'sha256': sha256(path)})
    return result


def build_seed(source_path, seed_path=SEED, manifest_path=MANIFEST, root=ROOT):
    """Publish reviewed identities into a clean new database; refuse overwrite."""
    source_path, seed_path, manifest_path, root = map(Path, (source_path, seed_path, manifest_path, root))
    if seed_path.exists() or manifest_path.exists():
        raise FileExistsError('Seed and manifest output paths must both be new')
    if source_path.resolve() in (seed_path.resolve(), manifest_path.resolve()):
        raise ValueError('Source database cannot be an output')
    # This readonly transaction gives a consistent view of a WAL-mode live source.
    # No plans, audit records, previews, or historical payloads are ever read.
    with closing(readonly(source_path)) as source:
        source.execute('BEGIN')
        check_schema(source)
        original = current_entities(source)
        systems = source.execute('SELECT * FROM source_systems ORDER BY id').fetchall()
        for row in systems:
            UUID(row['id'])
        if {(row['dataset'], row['source_key']) for row in systems} != SOURCE_SYSTEMS:
            raise ValueError('Unreviewed business source systems')
        expected = identity_rows(original)
    with tempfile.TemporaryDirectory(prefix='farm-public-seed-') as temp:
        temporary = Path(temp) / 'seed.sqlite3'
        store = Store(temporary)
        with store.connection() as db:
            for table, rows in (('source_systems', systems), ('entities', original)):
                placeholders = ','.join('?' for _ in TABLES[table])
                db.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', [tuple(row) for row in rows])
        # Reconstruct all associations exclusively from the checked-in sources.
        store = initialize(temporary, root=root)
        with store.connection() as db:
            if identity_rows(current_entities(db)) != expected:
                raise ValueError('Current entities differ from public import sources; publication rejected')
            for table in EXCLUDED:
                db.execute(f'DELETE FROM "{table}"')
            db.execute('DELETE FROM entity_versions')
            db.execute('INSERT INTO entity_versions SELECT id,revision,payload,updated_at FROM entities')
            provenance = public_sources(root, db)
        with closing(sqlite3.connect(temporary)) as db:
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            db.execute('PRAGMA journal_mode=DELETE')
            db.execute('VACUUM')
        report = inspect_seed(temporary)
        manifest = {
            'release': VERSION, 'schema_version': 2, 'seed': seed_path.name,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'sha256': sha256(temporary), 'bytes': temporary.stat().st_size, **report,
            'provenance': {
                'method': 'Read-only current identity extraction; supporting tables rebuilt from public source files',
                'source_scope': 'Current reviewed business entities and source-system UUIDs only; no operational history read',
                'source_files': provenance,
            },
            'included': ['current entity identities and payloads', 'one current entity version', 'source systems',
                         'current source evidence', 'entity-source links', 'spatial bindings', 'ontology relations',
                         'curated knowledge', 'schema migration metadata'],
            'excluded': ['retired entities', 'historical entity revisions', 'assistant conversations', 'saved plans',
                         'tool audit records', 'import previews', 'authentication', 'sessions', 'credentials', 'secrets'],
            'data_notice': 'Real means source-derived and unverified on site. Demo remains isolated synthetic data. No live telemetry is claimed.',
        }
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with seed_path.open('xb') as target, temporary.open('rb') as source:
            shutil.copyfileobj(source, target)
        with manifest_path.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    return manifest


def bootstrap_database(target, seed_path=SEED, manifest_path=MANIFEST):
    """Initialize a nonexistent target only. Existing installations always win."""
    target, seed_path = Path(target), Path(seed_path)
    if target.exists():
        return False
    validate_seed(seed_path, manifest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open('xb') as output, seed_path.open('rb') as source:
            shutil.copyfileobj(source, output)
    except FileExistsError:
        return False
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Readonly source DB; omit to validate the shipped seed')
    parser.add_argument('--seed', type=Path, default=SEED)
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    args = parser.parse_args()
    report = build_seed(args.source, args.seed, args.manifest) if args.source else validate_seed(args.seed, args.manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2))
