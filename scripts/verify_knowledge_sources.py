"""Verify the exact public reference URLs, recording hashes without copying articles."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
path = ROOT/'data/knowledge/curated.json'
payload = json.loads(path.read_text(encoding='utf-8'))

def inspect(entry):
    request = Request(entry['url'], headers={'User-Agent':'FarmTwinSourceAudit/1.0'})
    with urlopen(request, timeout=45) as response:
        body = response.read()
        if response.status != 200 or not body:
            raise ValueError('Reference unavailable: '+entry['id'])
        return {**entry, 'retrieved_at':datetime.now(timezone.utc).isoformat(),
                'source_sha256':hashlib.sha256(body).hexdigest(),
                'source_bytes':len(body), 'retrieved_url':response.url}

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(inspect, payload['entries']))
    payload['entries'] = entries
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'verified_urls':len(entries), 'ids':[e['id'] for e in entries]}))
