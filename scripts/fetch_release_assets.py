"""Restore pinned public GitHub Release assets without replacing local edits.

Uses only Python's standard library. No credentials, runtime database, or
environment secrets are read. All selected archives validate before install.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import urllib.parse
import urllib.request
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
METADATA = 'data/releases/v0.6.0-assets.json'
CHUNK = 1024 * 1024
PREFIXES = {'models': ('public/models/',),
            'blender': ('deliverables/blender/', 'data/model/', 'public/focus/textures/')}


class AssetError(RuntimeError):
    pass


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(CHUNK), b''):
            value.update(block)
    return value.hexdigest()


def safe_relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or value.startswith('/'):
        raise AssetError(f'Unsafe asset path: {value!r}')
    parts = value.split('/')
    for part in parts:
        if (part in ('', '.', '..') or part.endswith(('.', ' ')) or
                any(ord(char) < 32 for char in part) or
                re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', part, re.I)):
            raise AssetError(f'Unsafe asset path: {value!r}')
    return PurePosixPath(value)


def safe_destination(root, relative):
    relative = safe_relative(relative)
    target = root.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(root):
        raise AssetError(f'Destination escapes project: {relative}')
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise AssetError(f'Linked destination is not allowed: {relative}')
    return target


def valid_size_hash(item):
    if (type(item.get('bytes')) is not int or item['bytes'] < 0 or
            not isinstance(item.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
        raise AssetError('Invalid pinned file size or SHA-256')


def load_manifest(root):
    try:
        doc = json.loads((root / METADATA).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise AssetError(f'Cannot read release metadata: {METADATA}') from exc
    if (not isinstance(doc, dict) or doc.get('schema_version') != 'farm-release-assets/1' or doc.get('version') != 'v0.6.0' or
            doc.get('repository') != 'No1dry/farm' or not isinstance(doc.get('assets'), list)):
        raise AssetError('Unsupported release metadata')
    assets = {}
    all_paths = set()
    for asset in doc['assets']:
        if not isinstance(asset, dict) or asset.get('id') not in PREFIXES or asset['id'] in assets:
            raise AssetError('Invalid or duplicate asset ID')
        expected_name = f"farm-{doc['version']}-{asset['id']}.zip"
        if asset.get('name') != expected_name or asset.get('url') != (
                f"https://github.com/No1dry/farm/releases/download/{doc['version']}/{expected_name}"):
            raise AssetError('Asset must use the pinned public GitHub Release URL')
        valid_size_hash(asset)
        if not asset['bytes'] or not isinstance(asset.get('files'), list) or not asset['files']:
            raise AssetError('Asset file whitelist is empty')
        for entry in asset['files']:
            if not isinstance(entry, dict):
                raise AssetError('Invalid file whitelist entry')
            path = str(safe_relative(entry.get('path')))
            if not path.startswith(PREFIXES[asset['id']]):
                raise AssetError(f'Path is outside the permitted asset folders: {path}')
            if path.casefold() in all_paths:
                raise AssetError(f'Duplicate or case-ambiguous whitelist path: {path}')
            all_paths.add(path.casefold())
            valid_size_hash(entry)
        assets[asset['id']] = asset
    if 'models' not in assets:
        raise AssetError('Models asset is missing from release metadata')
    return doc, assets


class PublicReleaseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        host = (parsed.hostname or '').lower()
        if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443) or
                not (host == 'github.com' or host.endswith('.githubusercontent.com'))):
            raise AssetError('Release download redirected outside public GitHub HTTPS hosts')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_archive(asset, destination):
    request = urllib.request.Request(asset['url'], headers={'User-Agent': 'No1dry-farm-release-assets/0.6.0'})
    opener = urllib.request.build_opener(PublicReleaseRedirects())
    try:
        with opener.open(request, timeout=60) as response, destination.open('xb') as output:
            size = 0
            while block := response.read(CHUNK):
                size += len(block)
                if size > asset['bytes']:
                    raise AssetError(f"Downloaded archive exceeds pinned size: {asset['name']}")
                output.write(block)
    except (OSError, ValueError) as exc:
        raise AssetError(f"Release download failed for {asset['name']}: {exc}") from exc


def stage_archive(asset, archive_path, staging):
    if not archive_path.is_file() or archive_path.stat().st_size != asset['bytes'] or digest(archive_path) != asset['sha256']:
        raise AssetError(f"Archive size/hash mismatch: {asset['name']}")
    wanted = {entry['path']: entry for entry in asset['files']}
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            seen = set()
            for info in infos:
                name = str(safe_relative(info.filename))
                mode = info.external_attr >> 16
                if (info.is_dir() or stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or
                        info.flag_bits & 1 or name.casefold() in seen or name not in wanted):
                    raise AssetError(f'Unexpected, duplicate, encrypted or linked ZIP member: {name}')
                seen.add(name.casefold())
                if info.file_size != wanted[name]['bytes']:
                    raise AssetError(f'ZIP member size mismatch: {name}')
            if {info.filename for info in infos} != set(wanted):
                raise AssetError(f"ZIP whitelist mismatch: {asset['name']}")
            for info in infos:
                expected = wanted[info.filename]
                destination = safe_destination(staging, info.filename)
                destination.parent.mkdir(parents=True, exist_ok=True)
                checksum = hashlib.sha256()
                size = 0
                with archive.open(info) as source, destination.open('xb') as target:
                    while block := source.read(CHUNK):
                        size += len(block)
                        if size > expected['bytes']:
                            raise AssetError(f'ZIP member exceeds pinned size: {info.filename}')
                        checksum.update(block)
                        target.write(block)
                if size != expected['bytes'] or checksum.hexdigest() != expected['sha256']:
                    raise AssetError(f'ZIP member size/hash mismatch: {info.filename}')
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        if isinstance(exc, AssetError):
            raise
        raise AssetError(f"Cannot validate archive: {asset['name']}: {exc}") from exc


def existing_state(root, entry):
    target = safe_destination(root, entry['path'])
    if not target.exists():
        return None
    if not target.is_file():
        raise AssetError(f"Existing destination is not a regular file: {entry['path']}")
    return (target.stat().st_size, digest(target))


def restore_assets(root=ROOT, *, include_blender=False, verify_only=False, archive_dir=None, replace=False):
    root = Path(root).resolve()
    if not root.is_dir():
        raise AssetError('Project root does not exist')
    doc, assets = load_manifest(root)
    ids = ['models'] + (['blender'] if include_blender else [])
    if any(asset_id not in assets for asset_id in ids):
        raise AssetError('Requested Blender asset is missing from release metadata')
    selected = [assets[asset_id] for asset_id in ids]
    entries = [entry for asset in selected for entry in asset['files']]
    before = {entry['path']: existing_state(root, entry) for entry in entries}
    pending = [entry for entry in entries if before[entry['path']] != (entry['bytes'], entry['sha256'])]
    if verify_only:
        if pending:
            raise AssetError('Missing or modified release files: ' + ', '.join(entry['path'] for entry in pending))
        return {'version': doc['version'], 'verified_files': len(entries), 'installed_files': 0, 'backup_directory': None}
    changed = [entry for entry in pending if before[entry['path']] is not None]
    if changed and not replace:
        raise AssetError('Existing modified files are protected; use --replace to back up and replace: ' +
                         ', '.join(entry['path'] for entry in changed))
    if not pending:
        return {'version': doc['version'], 'verified_files': len(entries), 'installed_files': 0, 'backup_directory': None}
    backup_relative = None
    with tempfile.TemporaryDirectory(prefix='.farm-release-', dir=root) as temporary:
        temporary = Path(temporary)
        staged = temporary / 'staged'
        staged.mkdir()
        pending_names = {entry['path'] for entry in pending}
        for asset in selected:
            if not any(entry['path'] in pending_names for entry in asset['files']):
                continue
            if archive_dir is not None:
                archive = Path(archive_dir).resolve() / asset['name']
            else:
                archive = temporary / asset['name']
                print(f"Downloading {asset['name']} ...", flush=True)
                download_archive(asset, archive)
            stage_archive(asset, archive, staged)
        # Recheck protected files after network/staging before any install.
        for entry in entries:
            if existing_state(root, entry) != before[entry['path']]:
                raise AssetError(f"Existing file changed during validation: {entry['path']}")
        if changed:
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex[:8]
            backup_relative = f'.release-asset-backups/{stamp}'
            backup = safe_destination(root, backup_relative)
            backup.mkdir(parents=True, exist_ok=False)
            for entry in changed:
                target = safe_destination(backup, entry['path'])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(safe_destination(root, entry['path']), target)
                if (target.stat().st_size, digest(target)) != before[entry['path']]:
                    raise AssetError(f"Backup verification failed: {entry['path']}")
        # Every selected package and member has now passed validation. Newly
        # created paths use an exclusive hard link so a concurrent file is safe.
        for entry in pending:
            source = safe_destination(staged, entry['path'])
            destination = safe_destination(root, entry['path'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            if before[entry['path']] is None:
                os.link(source, destination)
                source.unlink()
            else:
                os.replace(source, destination)
    for entry in entries:
        if existing_state(root, entry) != (entry['bytes'], entry['sha256']):
            raise AssetError(f"Installed file validation failed: {entry['path']}")
    return {'version': doc['version'], 'verified_files': len(entries), 'installed_files': len(pending),
            'backup_directory': backup_relative}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', action='store_true', help='Also restore the editable Blender source package')
    parser.add_argument('--all', action='store_true', help='Restore both models and Blender source packages')
    parser.add_argument('--verify-only', action='store_true', help='Check local pinned files without network or writes')
    parser.add_argument('--archive-dir', type=Path, help='Use downloaded ZIPs from this directory without network')
    parser.add_argument('--replace', action='store_true', help='Back up modified local files before replacing them')
    args = parser.parse_args()
    try:
        result = restore_assets(include_blender=args.blender or args.all, verify_only=args.verify_only,
                                archive_dir=args.archive_dir, replace=args.replace)
    except (AssetError, OSError) as exc:
        parser.exit(1, f'Release assets were not restored successfully: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
