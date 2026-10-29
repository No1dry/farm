"""Independent structural/source validation of the drawing audit artifact."""
from pathlib import Path
import json,hashlib,math
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]

def main():
    data=json.loads((ROOT/'data/spatial/drawing-entities.json').read_text(encoding='utf8'))
    ledger=json.loads((ROOT/'data/audit/entities.json').read_text(encoding='utf8'))['records']
    drawings={d['asset_id']:d for d in data['drawings']}
    assert len(drawings)==5
    for d in drawings.values():
        assert hashlib.sha256((ROOT/d['source_file']).read_bytes()).hexdigest()==d['source_hash']
        assert (ROOT/d['image_path']).is_file()
        assert d['coordinate_units']=='pt' and d['crs'] is None
    records=data['records'];ids=[r['representation_id'] for r in records]
    assert len(ids)==len(set(ids)),'Duplicate representation ID'
    polygons=[(r['asset_id'],json.dumps(r['geometry'],sort_keys=True)) for r in records if r['geometry']['type']=='Polygon']
    assert len(polygons)==len(set(polygons)),'Two features reuse exactly the same polygon'
    truefields=[r for r in records if r['kind']=='field' and r['link_verified']]
    assert len(truefields)==100
    assert {r['source_key'] for r in truefields}=={r['source_key'] for r in ledger}
    assert len({r['source_key'] for r in truefields})==100
    assert all(r['geometry']['type']=='Polygon' for r in truefields)
    source_vectors={}
    for index,d in enumerate(data['drawings'],1):
        path=ROOT/f'tmp/audit/drawing-geometry/pdf-{index:02}-vectors.json'
        if path.exists():source_vectors[d['asset_id']]={v['op_index']:v for v in json.loads(path.read_text(encoding='utf8'))['paths']}
    for r in truefields:
        if r['asset_id'] in source_vectors:
            original=source_vectors[r['asset_id']][r['source_evidence'][0]['vector_content_operation']]['points'][:]
            if original[0]!=original[-1]:original.append(original[0])
            assert original==r['geometry']['coordinates'][0],'Field geometry differs from cited source path'
    for r in records:
        assert r['source_evidence'] and r['source_bbox_pt']
        assert r['model_area_m2'] is None and r['crs'] is None and r['elevation_datum'] is None
        d=drawings[r['asset_id']];w,h=d['page_size_pt']
        assert r['source_hash']==d['source_hash']
        g=r['geometry'];t=g['type'];c=g['coordinates']
        if t=='Polygon':
            assert len(c)==1 and len(c[0])>=4 and c[0][0]==c[0][-1]
            pts=c[0]
        elif t=='LineString':assert len(c)>=2;pts=c
        else:assert t=='Point' and r['boundary_status']=='boundary_unknown';pts=[c]
        assert all(len(p)==2 and all(math.isfinite(v) for v in p) and 0<=p[0]<=w and 0<=p[1]<=h for p in pts)
    e3=[r for r in records if r['kind']=='field' and r['original_code']=='E3']
    assert len(e3)==2 and len({r['source_key'] for r in e3})==2
    unresolved=next(r for r in e3 if not r['link_verified'])
    assert unresolved['identity_match_status']=='ambiguous_repeated_code' and unresolved['area_original'] is None
    assert all(r['area_unit'] is None for r in truefields)
    result={'status':'pass','drawings':len(drawings),'verified_ledger_field_polygons':len(truefields),'representation_count':len(records),'by_kind':dict(Counter(r['kind'] for r in records)),'by_geometry':dict(Counter(r['geometry']['type'] for r in records)),'source_hashes_verified':5,'e3_ambiguity_separated':True,'metric_area_or_crs_fabricated':False}
    (ROOT/'data/spatial/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
