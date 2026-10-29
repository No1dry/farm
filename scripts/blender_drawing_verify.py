"""Artifact-level contract for the complete five-PDF build."""
import json
import pathlib
from collections import defaultdict
from blender_verify import read_glb

ROOT=pathlib.Path(__file__).resolve().parents[1]

def verify():
    manifest=json.loads((ROOT/'public/models/manifest.json').read_text(encoding='utf-8'))
    assets=[a for a in manifest['assets'] if a.get('source_type')=='drawing']
    assert len(assets)==5, 'All five PDF drawings must have independent source assets.'
    source=json.loads((ROOT/'data/spatial/drawing-entities.json').read_text(encoding='utf-8'))
    records=source.get('records',[])
    wanted={r['representation_id'] for r in records}
    represented={o.get('source_record_id',o['spatial_id']) for o in manifest['objects'] if o['asset_id'] in {a['id'] for a in assets}}
    assert wanted==represented, {'missing':sorted(wanted-represented),'unexpected':sorted(represented-wanted)}
    for record in records:
        obj=next(o for o in manifest['objects'] if o.get('source_record_id')==record['representation_id'])
        assert obj['geometry']==record['geometry'], ('Stale or changed source geometry',record['representation_id'])
        assert obj['documented_dimensions']==record.get('documented_dimensions')
        assert obj.get('candidate_source_key')==record.get('candidate_source_key')
        assert obj.get('identity_match_status')==record.get('identity_match_status')
        assert obj.get('match_note')==record.get('match_note')
    surfaces=defaultdict(list)
    for obj in manifest['objects']:
        if obj.get('coordinate_system')=='PDF_PAGE_LOCAL' and obj['geometry']['type']=='Polygon':
            surfaces[(obj['asset_id'],obj['kind'],json.dumps(obj['geometry']['coordinates']))].append(obj['spatial_id'])
    assert not [ids for ids in surfaces.values() if len(ids)>1], 'Duplicate coincident source surfaces make physical ownership and picking ambiguous.'
    for asset in assets:
        glb=read_glb(ROOT/'public'/asset['url'].lstrip('/'))
        expected_ids={o['spatial_id'] for o in manifest['objects'] if o['asset_id']==asset['id']}
        actual_ids={n.get('extras',{}).get('spatial_id') for n in glb['nodes'] if n.get('extras',{}).get('spatial_id')}
        assert expected_ids==actual_ids,('Cross-asset selection leaked into export',asset['id'],actual_ids-expected_ids,expected_ids-actual_ids)
        assert not any(n.get('extras',{}).get('layer') in ('drawing_reference','satellite') for n in glb['nodes']), asset['id']
        assert glb.get('images'), 'Photographic PBR texture images must be embedded.'
        assert not any('landscape' in i.get('name','').lower() for i in glb.get('images',[])), 'A PDF screenshot cannot be a primary model texture.'
        assert set(('overview','focus','field','channel','pond')).issubset(asset['camera_views'])
        objects=[o for o in manifest['objects'] if o['asset_id']==asset['id']]
        for obj in objects:
            if obj.get('boundary_status')=='boundary_unknown':
                assert obj['geometry']['type']=='Point', obj['spatial_id']
                assert obj['model_area_m2'] is None, obj['spatial_id']
                parts=[n for n in glb['nodes'] if n.get('extras',{}).get('spatial_id')==obj['spatial_id']]
                assert not any(n.get('extras',{}).get('model_role') in ('field bed','water surface; depth unknown') for n in parts)
            assert obj.get('source_evidence') and obj['coordinate_system']=='PDF_PAGE_LOCAL'
    full=next(a for a in manifest['assets'] if a['id']=='full')
    assert full.get('lod_url'), 'Whole area must supply a separate low-cost LOD.'
    lod=read_glb(ROOT/'public'/full['lod_url'].lstrip('/'))
    lod_ids={n.get('extras',{}).get('spatial_id') for n in lod['nodes'] if 'mesh' in n}
    full_ids={o['spatial_id'] for o in manifest['objects'] if o['asset_id']=='full'}
    assert full_ids.issubset(lod_ids), 'Far view must retain a clickable mesh for every full-area resource.'
    if manifest.get('model_revision')=='v06':
        water_owners={o['spatial_id'] for o in manifest['objects'] if o['asset_id']=='full' and o['kind'] in ('pond','lake')}
        volumes=set()
        for node in lod['nodes']:
            sid=node.get('extras',{}).get('spatial_id')
            if sid not in water_owners or 'mesh' not in node:continue
            for primitive in lod['meshes'][node['mesh']]['primitives']:
                positions=lod['accessors'][primitive['attributes']['POSITION']]
                if positions['max'][1]-positions['min'][1]>2:volumes.add(sid)
        assert volumes==water_owners,('LOD lost volumetric basin/shore',water_owners-volumes)
    else:
        assert any(n.get('extras',{}).get('model_role')=='editable excavated shoreline slope' for n in lod['nodes']), 'LOD must retain shoreline closure rather than exposing terrain holes.'
    from PIL import Image, ImageStat
    for asset in assets:
        review=Image.open(ROOT/'deliverables/blender'/(asset['id']+'-review.png')).convert('RGB')
        assert min(review.size)>=1000 and max(ImageStat.Stat(review).stddev)>12, asset['id']
    print(json.dumps({'verified':True,'drawing_assets':len(assets),'source_representations':len(wanted),'manifest_representations':len(represented),'boundary_unknown':sum(o.get('boundary_status')=='boundary_unknown' for o in manifest['objects'])},ensure_ascii=False,indent=2))

if __name__=='__main__': verify()
