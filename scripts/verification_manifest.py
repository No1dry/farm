"""Record which exact deliverables were present at the final verification run."""
from pathlib import Path
import hashlib
import json
import platform
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
paths = [root/name for name in ('package.json','package-lock.json','requirements.txt','requirements-audit.txt',
         'README.md','.env.example','index.html','vite.config.js','playwright.config.js')]
for folder in ('public/models','public/focus','src/focus','src/twin','backend','tests','scripts','deliverables/blender',
               'deliverables/verification','data/audit','data/spatial','data/model','data/demo','data/knowledge','docs','dist'):
    paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and p.name != 'artifact-hashes.json'
                 and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.blend1'))
report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
          'python': platform.python_version(), 'files': []}
for p in sorted(set(paths)):
    report['files'].append({'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size,
                            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
(root/'deliverables/verification/artifact-hashes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Recorded {len(report['files'])} artifact hashes")
