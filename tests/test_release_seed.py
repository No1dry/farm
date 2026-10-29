"""Public release bootstrap must preserve identities without copying user history."""
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / 'data/seed/farm-v0.6.0.sqlite3'
MANIFEST = ROOT / 'data/seed/manifest.json'


def api():
    assert importlib.util.find_spec('scripts.release_data_seed'), 'Public, identity-preserving seed bootstrap is missing'
    return importlib.import_module('scripts.release_data_seed')


def connect(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def identities(path):
    with connect(path) as db:
        return db.execute('SELECT id,dataset,canonical_key,content_digest,revision FROM entities ORDER BY id').fetchall()


def test_fresh_install_preserves_all_published_ledger_ids_and_repeat_init(tmp_path):
    module = api()
    assert SEED.is_file() and MANIFEST.is_file()
    from scripts.db_init import initialize_database
    target = tmp_path / 'fresh.sqlite3'
    store, bootstrapped = initialize_database(target)
    assert bootstrapped is True
    published = json.loads(MANIFEST.read_text(encoding='utf8'))
    with store.connection() as db:
        ledger = sorted(r[0] for r in db.execute("SELECT id FROM entities WHERE dataset='real' AND canonical_key LIKE 'xls:%'"))
    assert len(ledger) == 100
    assert ledger == published['ledger_uuids']
    assert identities(target) == identities(SEED)
    before = identities(target)
    _, bootstrapped = initialize_database(target)
    assert bootstrapped is False and identities(target) == before
    assert module.bootstrap_database(target, SEED, MANIFEST) is False


def test_public_seed_has_only_current_business_data_and_no_history():
    module = api()
    report = module.validate_seed(SEED, MANIFEST)
    assert report['counts']['entities'] == 473
    with connect(SEED) as db:
        for table in ('plans', 'audit_log', 'import_previews'):
            assert db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] == 0
        versions = db.execute('SELECT COUNT(*) FROM entity_versions').fetchone()[0]
        assert versions == 473
        assert db.execute('SELECT COUNT(*) FROM entity_versions v JOIN entities e ON v.entity_id=e.id WHERE v.revision<>e.revision OR v.payload<>e.payload').fetchone()[0] == 0
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        assert not tables & {'users', 'sessions', 'credentials', 'messages', 'conversations'}


def test_seed_builder_excludes_history_bytes_without_modifying_source(tmp_path):
    module = api()
    dirty = tmp_path / 'source.sqlite3'
    with connect(SEED) as source, sqlite3.connect(dirty) as target:
        source.backup(target)
    sentinel = 'PRIVATE_HISTORY_MUST_NEVER_BE_RELEASED_948310'
    with sqlite3.connect(dirty) as db:
        identifier, revision, payload = db.execute('SELECT id,revision,payload FROM entities ORDER BY id LIMIT 1').fetchone()
        db.execute('INSERT INTO plans VALUES (?,?,?,?,?)', ('p', 'real', identifier, json.dumps({'private_text': sentinel}), '2026-10-29'))
        db.execute('INSERT INTO audit_log VALUES (?,?,?,?,?)', ('a', '2026-10-29', 'assistant.test', 'real', json.dumps({'private_text': sentinel})))
        db.execute('INSERT INTO import_previews VALUES (?,?,?,?,?,?,?,?,?)', ('i', 'real', sentinel, 'hash', '{}', 'operator', '2026-10-29', 'pending', None))
        db.execute('INSERT INTO entity_versions VALUES (?,?,?,?)', (identifier, 0, json.dumps({'private_text': sentinel}), '2026-10-28'))
    before = hashlib.sha256(dirty.read_bytes()).hexdigest()
    out, meta = tmp_path / 'public.sqlite3', tmp_path / 'manifest.json'
    module.build_seed(dirty, out, meta)
    assert hashlib.sha256(dirty.read_bytes()).hexdigest() == before
    assert sentinel.encode() not in out.read_bytes()
    assert identities(out) == identities(SEED)
    with connect(out) as db:
        assert db.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM plans').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM import_previews').fetchone()[0] == 0
    with pytest.raises(FileExistsError):
        module.build_seed(dirty, out, meta)


def test_corrupt_or_unexpected_seed_is_rejected_before_destination_creation(tmp_path):
    module = api()
    corrupt = tmp_path / 'corrupt.sqlite3'
    corrupt.write_bytes(SEED.read_bytes() + b'changed')
    target = tmp_path / 'target.sqlite3'
    with pytest.raises(ValueError, match='hash'):
        module.bootstrap_database(target, corrupt, MANIFEST)
    assert not target.exists()
    dirty = tmp_path / 'extra.sqlite3'
    with connect(SEED) as source, sqlite3.connect(dirty) as db:
        source.backup(db)
        db.execute('CREATE TABLE credentials(secret TEXT)')
        db.execute("INSERT INTO credentials VALUES ('not-a-real-secret')")
    with pytest.raises(ValueError, match='table'):
        module.build_seed(dirty, tmp_path / 'rejected.sqlite3', tmp_path / 'rejected.json')
    assert not (tmp_path / 'rejected.sqlite3').exists()


def test_existing_database_is_never_replaced_even_if_seed_unavailable(tmp_path):
    module = api()
    target = tmp_path / 'already-exists.sqlite3'
    original = b'owned by another installation'
    target.write_bytes(original)
    assert module.bootstrap_database(target, tmp_path / 'missing.sqlite3', tmp_path / 'missing.json') is False
    assert target.read_bytes() == original


def test_seed_builder_rejects_private_cached_column_content(tmp_path):
    module = api()
    dirty = tmp_path / 'private-column.sqlite3'
    with connect(SEED) as source, sqlite3.connect(dirty) as target:
        source.backup(target)
        target.execute("UPDATE entities SET name='PRIVATE_CACHED_CONTENT' WHERE id=(SELECT id FROM entities LIMIT 1)")
    output = tmp_path / 'rejected.sqlite3'
    with pytest.raises(ValueError, match='cached columns'):
        module.build_seed(dirty, output, tmp_path / 'rejected.json')
    assert not output.exists()
