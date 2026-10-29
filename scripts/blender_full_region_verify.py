"""Independent V0.6 exported-byte checks; these do not replace visual review."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from blender_traces import FEATURES,ROADS,CHANNELS

def read_glb(path):
    raw=path.read_bytes();magic,version,length=struct.unpack_from('<III',raw)
    assert magic==0x46546c67 and version==2 and length==len(raw)
    size,kind=struct.unpack_from('<II',raw,12);assert kind==0x4e4f534a
    return json.loads(raw[20:20+size]),raw

def main():
    manifest=json.loads((ROOT/'public/models/manifest.json').read_text(encoding='utf8'));layout=json.loads((ROOT/'data/demo/full-area-device-layout.json').read_text(encoding='utf8'))
    expected={x['spatial_id'] for x in FEATURES}|{f'SAT-ROAD-{i+1:03d}' for i in range(len(ROADS))}|{f'SAT-CHANNEL-{i+1:03d}' for i in range(len(CHANNELS))}
    objects={x['spatial_id']:x for x in manifest['objects']};assert {s for s,o in objects.items() if o['asset_id']=='full'}==expected
    assert manifest['default_asset_id']=='full' and len(manifest['objects'])==284
    report={'model_revision':manifest['model_revision'],'source_owners':len(expected),'assets':[]}
    for filename in ('full-area.glb','full-area-lod.glb'):
        doc,raw=read_glb(ROOT/'public/models'/filename);nodes=doc.get('nodes',[])
        exported={n.get('extras',{}).get('spatial_id') for n in nodes if n.get('extras',{}).get('spatial_id')};assert expected==exported,{'missing':expected-exported,'cross_asset_leak':exported-expected}
        devices={n.get('extras',{}).get('scene_device_key'):n for n in nodes if n.get('extras',{}).get('scene_device_key')}
        assert len(devices)==len(layout['devices'])==49
        for row in layout['devices']:
            extra=devices[row['key']]['extras'];assert extra['scene_scenario_id']==layout['scenario_id'];assert extra['data_nature']=='synthetic';assert extra['spatial_id']==row['parent_spatial_id']
            center=objects[row['parent_spatial_id']]['center'];position=[center[i]+row['offset'][i] for i in range(3)]
            assert max(abs(a-b) for a,b in zip(position,extra['base_position_three']))<.0002,(row['key'],position,extra['base_position_three'])
        instancing=[n['extensions']['EXT_mesh_gpu_instancing'] for n in nodes if n.get('extensions',{}).get('EXT_mesh_gpu_instancing')]
        assert instancing,'Tree GPU instancing missing'
        instance_count=sum(doc['accessors'][i['attributes']['TRANSLATION']]['count'] for i in instancing)
        assert instance_count>1000
        leaves=[m for m in doc['materials'] if 'photographic broadleaf' in m.get('name','')];assert leaves and all(m.get('alphaMode')=='MASK' for m in leaves)
        assert all('uri' not in image for image in doc.get('images',[])),'External image dependency'
        forbidden=[m.get('name') for m in doc['materials'] if any(t in m.get('name','').lower() for t in ('satellite','source-projected','drawing reference'))];assert not forbidden,forbidden
        assert not any(n.get('extras',{}).get('reference_only') or n.get('extras',{}).get('layer') in ('satellite','drawing_reference') for n in nodes)
        report['assets'].append({'file':filename,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'nodes':len(nodes),'meshes':len(doc['meshes']),'gpu_instance_batches':len(instancing),'gpu_component_instances':instance_count,'device_nodes':len(devices),'leaf_alpha_mask':True,'embedded_images':len(doc.get('images',[]))})
    assert manifest['full_region_appearance_statistics']['observed_roof_candidates']==192
    report['passed']=True;report['limits']='Checks identity, self-containment and instance/material contracts; appearance is separately reviewed in actual rendered images.'
    (ROOT/'deliverables/blender/full-region-export-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
