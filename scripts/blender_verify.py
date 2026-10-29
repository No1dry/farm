"""Verify the deliverable contract, without importing Blender or project JS."""
import json
import math
import pathlib
import struct

ROOT = pathlib.Path(__file__).resolve().parents[1]

def read_glb(path):
    data = path.read_bytes()
    magic, version, length = struct.unpack_from('<4sII', data)
    assert (magic, version, length) == (b'glTF', 2, len(data)), path
    size, kind = struct.unpack_from('<I4s', data, 12)
    assert kind == b'JSON'
    return json.loads(data[20:20 + size])

def verify():
    manifest_path = ROOT / 'public/models/manifest.json'
    assert manifest_path.exists(), 'Missing full-area manifest; Blender build has not run.'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert len(manifest['objects']) >= 80, 'Full-area coverage requires more than the old four-object focus sample.'
    ids = [obj['spatial_id'] for obj in manifest['objects']]
    assert len(ids) == len(set(ids)), 'Duplicate spatial IDs'
    full = [obj for obj in manifest['objects'] if obj['asset_id'] == 'full']
    assert {'field', 'pond', 'lake', 'road', 'woodland', 'settlement'}.issubset({obj['kind'] for obj in full})
    assert min(obj['center'][0] for obj in full) < -800
    assert max(obj['center'][0] for obj in full) > 800
    assert min(obj['center'][2] for obj in full) < -900
    assert max(obj['center'][2] for obj in full) > 900
    glbs = {}
    for asset in manifest['assets']:
        glb = read_glb(ROOT / 'public' / asset['url'].lstrip('/'))
        assert glb.get('meshes') and glb.get('materials')
        assert glb.get('images'), 'PBR materials must embed their texture images.'
        glbs[asset['id']] = glb
    for obj in manifest['objects']:
        assert len(obj['center']) == 3 and all(math.isfinite(v) for v in obj['center'])
        assert obj['entity_uuid'] is None, 'Business mapping belongs to database, not inferred from satellite geometry.'
        assert obj['precision'] in ('approximate_satellite', 'unregistered_drawing_detail','drawing_anchor','unregistered_drawing_geometry')
        assert obj['source']
        if obj['model_area_m2'] is None:
            assert obj.get('coordinate_system')=='PDF_PAGE_LOCAL'
        else:
            assert obj['model_area_m2']>=0
        assert any(n.get('extras', {}).get('spatial_id') == obj['spatial_id'] for n in glbs[obj['asset_id']]['nodes']), obj['spatial_id']
    blend = ROOT / 'deliverables/blender/farm-full.blend'
    assert blend.exists() and blend.stat().st_size > 1000000
    from PIL import Image, ImageStat
    review = Image.open(ROOT / 'deliverables/blender/full-area-review.png').convert('RGB')
    assert max(ImageStat.Stat(review).stddev) > 15, 'Blender review is empty or camera clipped the landscape.'
    report = {'verified': True, 'objects': len(ids), 'assets': len(glbs), 'full_area_objects': len(full), 'checks': ['GLB header', 'embedded textures', 'spatial IDs', 'separate detail asset', 'whole-redline extent', 'finite Y-up centers', 'no inferred business UUIDs', 'editable Blender source']}
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    verify()
