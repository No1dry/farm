"""Build reproducible release archives from an explicit public-file allowlist.

Large current GLBs and the final Blend are distributed as Release assets.
The complete archive contains the same source tree plus these assets, never
runtime databases, credentials, downloaded tools, dependencies or working Blends.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CORE_DIRS = ('backend', 'data', 'docs', 'licenses', 'public', 'scripts', 'src', 'tests',
             '参考图', '现场竣工图pdf版本', 'deliverables/blender',
             'deliverables/verification', 'deliverables/focus-v02', 'deliverables/liangzihu-samples')
CORE_FILES = ('.gitignore', '.gitattributes', '.env.example', 'index.html', 'overview-v01.html',
              'package.json', 'package-lock.json', 'requirements.txt', 'requirements-audit.txt',
              'vite.config.js', 'playwright.config.js', 'pytest.ini', 'THIRD_PARTY_NOTICES.md',
              '梁湖情田块面积汇总202607.xls')


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def safe_public(path):
    relative = path.relative_to(ROOT)
    if path.is_symlink() or any(part in ('__pycache__', 'node_modules', 'runtime', '.git', '.venv')
                                or part.startswith(('.pytest', '.farm-release-', '.release-asset-backups'))
                                for part in relative.parts):
        return False
    if path.name.startswith('.env') and path.name != '.env.example':
        return False
    return path.suffix.lower() not in ('.pyc', '.blend1', '.blend2')


def core_paths():
    paths = {ROOT / name for name in CORE_FILES if (ROOT / name).is_file()}
    paths.update(ROOT.glob('README*.md'))
    for directory in CORE_DIRS:
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file())
    return sorted(p for p in paths if safe_public(p) and p.suffix != '.blend'
                  and (p.suffix != '.glb' or p.name == 'tongtiehai-farm-v01.glb'))


def archive(path, files):
    temporary = path.with_suffix('.zip.partial')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as bundle:
        for source in sorted(files):
            relative = source.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(2026, 10, 29, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            with source.open('rb') as incoming, bundle.open(info, 'w', force_zip64=True) as target:
                shutil.copyfileobj(incoming, target, 1024 * 1024)
    temporary.replace(path)
    return {'name': path.name, 'bytes': path.stat().st_size, 'sha256': digest(path),
            'files': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                       'sha256': digest(p)} for p in sorted(files)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='v0.6.0')
    parser.add_argument('--output', type=Path, default=ROOT.parent / '.publish/artifacts/v0.6.0')
    parser.add_argument('--stage-source', type=Path)
    parser.add_argument('--assets-only', action='store_true')
    args = parser.parse_args()
    if args.version != 'v' + json.loads((ROOT / 'package.json').read_text(encoding='utf8'))['version']:
        raise ValueError('Release tag must match package.json version')
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Archive output must be outside the project tree')
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / 'public/models/manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    models = {manifest_path}
    for asset in manifest['assets']:
        for url_key, hash_key in (('url', 'sha256'), ('lod_url', 'lod_sha256')):
            if not asset.get(url_key):
                continue
            path = ROOT / 'public' / asset[url_key].lstrip('/')
            if path.parent != ROOT / 'public/models' or digest(path) != asset[hash_key]:
                raise ValueError('Current model is outside scope or has wrong digest')
            models.add(path)
    blender = {p for p in (ROOT / 'deliverables/blender').rglob('*') if p.is_file()
               and safe_public(p) and (p.suffix != '.blend' or p.name == 'farm-full.blend')}
    if not (ROOT / 'deliverables/blender/farm-full.blend').is_file():
        raise FileNotFoundError('Final editable Blend missing')
    release_assets = []
    for key, files in (('models', models), ('blender', blender)):
        result = archive(output / f'farm-{args.version}-{key}.zip', files)
        result.update(id=key, url=f'https://github.com/No1dry/farm/releases/download/{args.version}/{result["name"]}')
        release_assets.append(result)
        print(json.dumps({k: result[k] for k in ('id', 'name', 'bytes', 'sha256')}, ensure_ascii=False), flush=True)
    catalog = ROOT / 'data/releases' / (args.version + '-assets.json')
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(json.dumps({'schema_version': 'farm-release-assets/1', 'version': args.version,
        'repository': 'No1dry/farm', 'assets': release_assets}, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    if args.assets_only:
        return
    core = core_paths()
    oversized = [str(p.relative_to(ROOT)) for p in core if p.stat().st_size >= 100 * 1024 * 1024]
    if oversized:
        raise ValueError('Oversized Git files: ' + ', '.join(oversized))
    if args.stage_source:
        staging = args.stage_source.resolve()
        if staging == ROOT or ROOT in staging.parents or not (staging / '.git').is_dir():
            raise ValueError('Source staging must be a separate Git checkout')
        for path in core:
            target = staging / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    complete = archive(output / f'farm-{args.version}-complete.zip', set(core) | models | blender)
    assets = release_assets + [complete]
    (output / 'SHA256SUMS.txt').write_text(''.join(f'{a["sha256"]}  {a["name"]}\n' for a in assets), encoding='utf8')
    (output / 'publication-inventory.json').write_text(json.dumps({'version': args.version,
        'source_file_count': len(core), 'source_bytes': sum(p.stat().st_size for p in core),
        'source_files': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in core],
        'excluded': ['runtime', 'credentials', 'node_modules', '.tools', 'dist', 'tmp', 'working Blend previews'],
        'assets': [{k: a[k] for k in ('name', 'bytes', 'sha256')} for a in assets]}, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'source_files': len(core), 'complete': {k: complete[k] for k in ('name','bytes','sha256')}}, indent=2), flush=True)


if __name__ == '__main__':
    main()
