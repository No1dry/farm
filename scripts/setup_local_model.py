"""Download pinned official assets, verify SHA-256, then extract safely. No paid service."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT.parent/'.tools'


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while data:=stream.read(8*1024*1024):h.update(data)
    return h.hexdigest()


def download(spec,root=TOOLS):
    root=Path(root).resolve();target=(root/spec['relative_path']).resolve()
    if not target.is_relative_to(root):raise ValueError('Download target escaped tool directory')
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and target.stat().st_size==spec['bytes'] and file_sha(target)==spec['sha256']:
        return target
    parts=root/('download-parts-'+target.name);parts.mkdir(exist_ok=True)
    step=spec.get('chunk_bytes',1024*1024);size=spec['bytes'];total=(size+step-1)//step
    def chunk(i):
        start=i*step;end=min(size-1,start+step-1);part=parts/str(i)
        if part.exists() and part.stat().st_size==end-start+1:return
        for attempt in range(5):
            try:
                request=urllib.request.Request(spec['url'],headers={'Range':f'bytes={start}-{end}','User-Agent':'FarmTwin-LocalDeployment/1'})
                with urllib.request.urlopen(request,timeout=120) as response:
                    if response.status!=206:raise ValueError('Server did not honor range request')
                    data=response.read()
                if len(data)!=end-start+1:raise ValueError('Incomplete range response')
                part.write_bytes(data);return
            except Exception:
                if attempt==4:raise
                time.sleep(1+attempt)
    with ThreadPoolExecutor(max_workers=spec.get('workers',8)) as pool:
        completed=0
        for task in as_completed([pool.submit(chunk,i) for i in range(total)]):
            task.result();completed+=1
            if completed%16==0 or completed==total:print(target.name,completed,'/',total,flush=True)
    temporary=target.with_suffix(target.suffix+'.download')
    with temporary.open('wb') as stream:
        for i in range(total):stream.write((parts/str(i)).read_bytes())
    if file_sha(temporary)!=spec['sha256']:raise ValueError('SHA-256 mismatch; asset was not installed')
    temporary.replace(target)
    return target


def extract_verified(path,destination):
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            target=(destination/member.filename).resolve()
            if not target.is_relative_to(destination):raise ValueError('Unsafe archive path')
            if member.is_dir():target.mkdir(parents=True,exist_ok=True);continue
            data=archive.read(member)
            # Running Windows executables/DLLs are locked; identical verified files need no write.
            if target.exists() and file_sha(target)==hashlib.sha256(data).hexdigest():continue
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)


def setup():
    manifest=json.loads((ROOT/'backend/local-model-manifest.json').read_text(encoding='utf8'))
    for key in ('model','runtime'):
        spec=manifest[key];path=download(spec)
        if key=='runtime':
            destination=(TOOLS/spec['extract_directory']).resolve();destination.mkdir(exist_ok=True)
            extract_verified(path,destination)
        else:destination=path.parent
        license_path=destination/'LICENSE'
        if not license_path.exists() or file_sha(license_path)!=spec['license_sha256']:
            license_data=urllib.request.urlopen(spec['license_url'],timeout=30).read()
            if hashlib.sha256(license_data).hexdigest()!=spec['license_sha256']:raise ValueError('License SHA-256 mismatch')
            license_path.write_bytes(license_data)
    (ROOT/'docs/audit/local-model-assets.json').write_text(json.dumps({**manifest,'verified_sha256':True},indent=2)+'\n',encoding='utf8')
    print('Official model and runtime verified; licenses retained.')


if __name__=='__main__':setup()
