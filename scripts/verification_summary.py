"""Summarize existing final receipts; fail if current deployment differs."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables/verification'


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8-sig'))


def main():
    raw = (ROOT / 'public/models/manifest.json').read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    manifest = json.loads(raw)
    served = urllib.request.urlopen('http://127.0.0.1:5173/models/manifest.json').read()
    if hashlib.sha256(served).hexdigest() != sha:
        raise RuntimeError('Production manifest differs from current source')
    browser = read('browser-tests.json')['stats']
    if browser['unexpected'] or browser['flaky'] or browser['skipped'] or browser['expected'] != 23:
        raise RuntimeError('Final browser suite is incomplete or not passing')
    suites = list(ET.parse(OUT / 'backend-junit.xml').getroot().iter('testsuite'))
    backend_count = sum(int(s.attrib['tests']) for s in suites)
    if backend_count != 81 or any(int(s.attrib[k]) for s in suites for k in ('errors', 'failures', 'skipped')):
        raise RuntimeError('Final backend suite is incomplete or not passing')
    node_log = (OUT / 'v06-node-tests.log').read_text(encoding='utf-8-sig')
    if not re.search(r'# pass 33\s', node_log) or not re.search(r'# fail 0\s', node_log):
        raise RuntimeError('Final JavaScript suite is incomplete or not passing')
    review = read('full-region/review.json')
    if review['manifestSHA256'] != sha or review['errors'] or len(review['records']) != 16:
        raise RuntimeError('Final visual/performance evidence is incomplete or stale')
    db = read('v06-database-import.json')
    if db['manifest']['sha256'] != sha:
        raise RuntimeError('Database import refers to an older manifest')
    backup = read('final-backup.json')
    if not backup['all_application_tables_equal'] or backup['original_source_files_unchanged'] != 12:
        raise RuntimeError('Final backup/source verification failed')
    result = {'verified_at': datetime.now(timezone.utc).isoformat(), 'version': '0.6.0',
              'production_url': 'http://127.0.0.1:5173', 'production_manifest_matches': True,
              'manifest_sha256': sha, 'model_revision': manifest['model_revision'],
              'tests': {'browser': 23, 'backend': 81, 'javascript_and_browser_adapter': 33, 'failed': 0},
              'browser_views': 16, 'village_views': 9,
              'p95_frame_ms_range': [round(fn(x['frameWindow']['p95'] for x in review['records']), 2) for fn in (min, max)],
              'original_source_files_unchanged': 12, 'restored_tables_equal': len(backup['tables']),
              'backup': backup['backup'], 'backup_sha256': backup['backup_sha256'],
              'limits': ['Simplified full-region reconstruction with explicit replaceable samples, not a survey or photorealistic replica',
                         'Five drawing coordinate systems remain independently unregistered',
                         'No real telemetry or equipment control connected; synthetic business data stays isolated',
                         'Performance measured on the documented local RTX 5070 Ti desktop only']}
    (OUT / 'v06-summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
