import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import zipfile

import pytest


@pytest.fixture
def release_tool():
    path = Path(__file__).resolve().parents[1] / 'scripts/fetch_release_assets.py'
    assert path.is_file(), 'Release restoration implementation is missing'
    spec = importlib.util.spec_from_file_location('farm_release_assets', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(value):
    return hashlib.sha256(value).hexdigest()


def package(root, archive_dir, asset_id='models', content=None, members=None):
    content = content or {'public/models/full-area.glb': b'actual-model-bytes'}
    name = f'farm-v0.6.0-{asset_id}.zip'
    archive_dir.mkdir(parents=True, exist_ok=True)
    path = archive_dir / name
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for filename, payload in (members if members is not None else list(content.items())):
            archive.writestr(filename, payload)
    asset = {'id': asset_id, 'name': name,
             'url': f'https://github.com/No1dry/farm/releases/download/v0.6.0/{name}',
             'bytes': path.stat().st_size, 'sha256': sha(path.read_bytes()),
             'files': [{'path': name, 'bytes': len(value), 'sha256': sha(value)} for name, value in content.items()]}
    metadata = root / 'data/releases/v0.6.0-assets.json'
    metadata.parent.mkdir(parents=True, exist_ok=True)
    doc = json.loads(metadata.read_text('utf8')) if metadata.exists() else {
        'schema_version': 'farm-release-assets/1', 'version': 'v0.6.0', 'repository': 'No1dry/farm', 'assets': []}
    doc['assets'] = [item for item in doc['assets'] if item['id'] != asset_id] + [asset]
    metadata.write_text(json.dumps(doc), encoding='utf8')
    return asset, path


def test_offline_restore_is_verified_idempotent_and_verify_only_needs_no_archive(tmp_path, release_tool):
    root = tmp_path / 'project'
    archives = tmp_path / 'archives'
    package(root, archives)
    result = release_tool.restore_assets(root=root, archive_dir=archives)
    target = root / 'public/models/full-area.glb'
    assert target.read_bytes() == b'actual-model-bytes'
    assert result['installed_files'] == 1
    first_mtime = target.stat().st_mtime_ns
    result = release_tool.restore_assets(root=root, archive_dir=tmp_path / 'absent')
    assert result['installed_files'] == 0 and target.stat().st_mtime_ns == first_mtime
    assert release_tool.restore_assets(root=root, verify_only=True)['verified_files'] == 1


def test_changed_local_model_is_preserved_without_replace_and_backed_up_with_replace(tmp_path, release_tool):
    root = tmp_path / 'project'
    archives = tmp_path / 'archives'
    package(root, archives)
    target = root / 'public/models/full-area.glb'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'user-edited-model')
    with pytest.raises(release_tool.AssetError, match='existing|Existing|modified'):
        release_tool.restore_assets(root=root, archive_dir=archives)
    assert target.read_bytes() == b'user-edited-model'
    result = release_tool.restore_assets(root=root, archive_dir=archives, replace=True)
    assert target.read_bytes() == b'actual-model-bytes'
    assert (root / result['backup_directory'] / 'public/models/full-area.glb').read_bytes() == b'user-edited-model'


def test_archive_and_member_hashes_are_checked_before_any_destination_is_written(tmp_path, release_tool):
    root = tmp_path / 'project'
    archives = tmp_path / 'archives'
    _, path = package(root, archives)
    path.write_bytes(path.read_bytes() + b'tampering')
    with pytest.raises(release_tool.AssetError, match='archive|Archive'):
        release_tool.restore_assets(root=root, archive_dir=archives)
    assert not (root / 'public').exists()
    package(root, archives, members=[('public/models/full-area.glb', b'wrong-model-bytes!')])
    with pytest.raises(release_tool.AssetError, match='size|hash'):
        release_tool.restore_assets(root=root, archive_dir=archives)
    assert not (root / 'public').exists()


@pytest.mark.parametrize('bad_name', ['../escape', '/absolute', 'C:/escape', 'public\\models\\evil.glb',
                                      'public/models/a/../../escape', 'public/models/file.glb:stream',
                                      'public/models/CON', 'public/models/ending.'])
def test_unsafe_zip_members_are_rejected_even_when_archive_digest_matches(tmp_path, release_tool, bad_name):
    root = tmp_path / 'project'
    archives = tmp_path / 'archives'
    package(root, archives, members=[('public/models/full-area.glb', b'actual-model-bytes'), (bad_name, b'bad')])
    with pytest.raises(release_tool.AssetError):
        release_tool.restore_assets(root=root, archive_dir=archives)
    assert not (root / 'public').exists()


def test_symlinks_duplicates_extra_and_missing_members_are_rejected(tmp_path, release_tool):
    root = tmp_path / 'project'
    archives = tmp_path / 'archives'
    link = zipfile.ZipInfo('public/models/full-area.glb')
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    for members in [[], [(link, b'actual-model-bytes')],
                    [('public/models/full-area.glb', b'actual-model-bytes')] * 2,
                    [('public/models/full-area.glb', b'actual-model-bytes'), ('public/models/EXTRA.glb', b'extra')]]:
        with pytest.warns(UserWarning) if len(members) == 2 and members[0] == members[1] else _no_warning_context():
            package(root, archives, members=members)
        with pytest.raises(release_tool.AssetError):
            release_tool.restore_assets(root=root, archive_dir=archives)
        assert not (root / 'public').exists()


def _no_warning_context():
    from contextlib import nullcontext
    return nullcontext()


def test_all_selected_packages_validate_before_first_install(tmp_path, release_tool):
    root = tmp_path / 'project'
    archives = tmp_path / 'archives'
    package(root, archives)
    _, bad = package(root, archives, 'blender', {'deliverables/blender/farm-full.blend': b'blend-source'})
    bad.write_bytes(b'not-the-pinned-archive')
    with pytest.raises(release_tool.AssetError):
        release_tool.restore_assets(root=root, archive_dir=archives, include_blender=True)
    assert not (root / 'public').exists() and not (root / 'deliverables').exists()


def test_metadata_cannot_redirect_download_or_write_into_runtime(tmp_path, release_tool):
    root = tmp_path / 'project'
    archives = tmp_path / 'archives'
    package(root, archives)
    metadata = root / 'data/releases/v0.6.0-assets.json'
    doc = json.loads(metadata.read_text('utf8'))
    doc['assets'][0]['url'] = 'https://example.com/untrusted.zip'
    metadata.write_text(json.dumps(doc), encoding='utf8')
    with pytest.raises(release_tool.AssetError):
        release_tool.restore_assets(root=root, archive_dir=archives)
    package(root, archives, content={'runtime/farm.sqlite3': b'forbidden'})
    with pytest.raises(release_tool.AssetError):
        release_tool.restore_assets(root=root, archive_dir=archives)
    assert not (root / 'runtime').exists()


def test_existing_destination_directory_is_never_replaced(tmp_path, release_tool):
    root = tmp_path / 'project'
    archives = tmp_path / 'archives'
    package(root, archives)
    target = root / 'public/models/full-area.glb'
    target.mkdir(parents=True)
    (target / 'keep.txt').write_text('user-folder', encoding='utf8')
    with pytest.raises(release_tool.AssetError):
        release_tool.restore_assets(root=root, archive_dir=archives, replace=True)
    assert (target / 'keep.txt').read_text('utf8') == 'user-folder'
