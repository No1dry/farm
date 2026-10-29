"""Compare GLB material factors against real Blender shader factor snapshots."""
import json,re,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def normalized(name):return re.sub(r'\.\d+$','',name).removesuffix(' LOD')
def require(condition,detail):
    if not condition:raise AssertionError(detail)
def capture_blender_materials():
    import bpy
    expected={}
    for material in bpy.data.materials:
        if not material.use_nodes:continue
        bs=material.node_tree.nodes.get('Principled BSDF')
        if not bs:continue
        socket=bs.inputs['Base Color']
        if not socket.links:expected[material.name]=list(socket.default_value);continue
        node=socket.links[0].from_node
        if node.type=='MIX' and node.data_type=='RGBA' and node.blend_type=='MULTIPLY' and not node.inputs[7].links:expected[material.name]=list(node.inputs[7].default_value)
    (ROOT/'deliverables/blender/material-export-expectations.json').write_text(json.dumps({'source':'Blender actual shader sockets','materials':expected},indent=2),encoding='utf8')
    return expected
def verify(expectations=None,manifest=None):
    if expectations is None:expectations=json.loads((ROOT/'deliverables/blender/material-export-expectations.json').read_text(encoding='utf8'))['materials']
    expected={normalized(k):v for k,v in expectations.items()};report=[]
    if manifest is None:manifest=json.loads((ROOT/'public/models/manifest.json').read_text(encoding='utf8'))
    paths=sorted({ROOT/'public'/a[key].lstrip('/') for a in manifest['assets'] for key in ('url','lod_url') if a.get(key)})
    require(len(paths)==7,'Expected six main assets plus full-area LOD')
    for path in paths:
        raw=path.read_bytes();size=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+size]);checked=[]
        skipped=[]
        for material in doc['materials']:
            require(material.get('name'),(path.name,'unnamed delivered material'))
            name=normalized(material['name']);pbr=material.get('pbrMetallicRoughness',{})
            if name not in expected:
                require('CC0 photographic broadleaf sprays' in name,(path.name,name,'uncovered material'))
                require(pbr.get('baseColorTexture') and material.get('alphaMode')=='MASK',(path.name,name,'Direct leaves must retain texture and MASK'))
                skipped.append({'name':material['name'],'reason':'Direct photographic RGBA leaf texture; no multiplier in Blender shader.'});continue
            wanted=expected[name];actual=pbr.get('baseColorFactor',[1,1,1,1]);error=max(abs(a-b) for a,b in zip(actual,wanted))
            require(error<.0001,(path.name,material['name'],'PBR factor mismatch',wanted,actual))
            checked.append(material['name'])
        require(checked,(path,'no expected material checked'))
        report.append({'path':path.name,'verified_material_factors':len(checked),'direct_texture_materials':skipped})
    result={'passed':True,'assets':report,'comparison':'Exported baseColorFactor equals the Blender BSDF or RGBA Multiply constant; absent glTF factor means white and fails when tint is expected.'}
    (ROOT/'deliverables/blender/material-export-verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2));return result
if __name__=='__main__':verify()
