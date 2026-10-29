"""Canonicalize unsupported legacy multiply nodes, re-export same geometry.
Run with the delivered Blend open; no geometry/identity/anchor regeneration.
"""
import bpy,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import blender_build as A
import blender_full_region as F
import blender_volume as V
from blender_material_verify import verify
A.MANIFEST=json.loads((ROOT/'public/models/manifest.json').read_text(encoding='utf8'));F.A=A;F.P=json.loads((ROOT/'data/model/full-region-parameters.json').read_text(encoding='utf8'));V.API=A
full=next(c for c in bpy.data.collections if c.get('asset_id')=='full');scene=next(s for s in bpy.data.scenes if s.get('asset_id')=='full');bpy.context.window.scene=scene
converted=0
for material in bpy.data.materials:
    if not material.use_nodes:continue
    nodes=material.node_tree.nodes;links=material.node_tree.links
    for old in list(nodes):
        if old.type!='MIX_RGB' or old.blend_type!='MULTIPLY':continue
        assert abs(old.inputs[0].default_value-1)<.0001,'Unsupported non-unit factor requires a separate bake'
        new=nodes.new('ShaderNodeMix');new.data_type='RGBA';new.blend_type='MULTIPLY';new.inputs[0].default_value=1;new.inputs[6].default_value=old.inputs[1].default_value;new.inputs[7].default_value=old.inputs[2].default_value
        for old_index,new_index in [(1,6),(2,7)]:
            for link in list(old.inputs[old_index].links):links.new(link.from_socket,new.inputs[new_index])
        for link in list(old.outputs[0].links):links.new(new.outputs[2],link.to_socket)
        nodes.remove(old);converted+=1
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
try:verify(expected)
except AssertionError as error:print('EXPECTED_PRE_REPAIR_EXPORT_FAILURE',str(error),flush=True)
else:print('CURRENT_FACTORS_PASS; REEXPORTING_WITH_ACTIVE_SCENE_SCOPE',flush=True)
F.export_full(full,'full-area.glb');F.export_full(full,'full-area-lod.glb',lod=True)
for collection in [c for c in bpy.data.collections if c.get('asset_id') and c.get('asset_id')!='full']:
    layer=scene.view_layers[0].layer_collection.children[collection.name];previous=layer.exclude;layer.exclude=False;A.export_collection(collection,collection['asset_id']+'.glb');layer.exclude=previous
for asset in A.MANIFEST['assets']:
    for key,prefix in [('url',''),('lod_url','lod_')]:
        if key in asset:
            path=ROOT/'public'/asset[key].lstrip('/');asset[prefix+'bytes']=path.stat().st_size;asset[prefix+'sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
A.MANIFEST['material_export_revision']='v06-canonical-rgba-multiply'
views=next(a for a in A.MANIFEST['assets'] if a['id']=='full')['camera_views'];views['overview']={'position':[460,2472.5,1760],'target':[0,0,154.455]};views['focus']=views['overview'];V.set_camera(scene,views['overview'])
(ROOT/'public/models/manifest.json').write_text(json.dumps(A.MANIFEST,ensure_ascii=False,indent=2),encoding='utf8')
block=bpy.data.texts['spatial-manifest.json'];block.clear();block.write(json.dumps(A.MANIFEST,ensure_ascii=False,indent=2))
for filename in ('blender_build.py','blender_drawings.py','blender_traces.py','blender_volume.py','blender_full_region.py'):
    block=bpy.data.texts[filename];block.clear();block.write((ROOT/'scripts'/filename).read_text(encoding='utf8'))
bpy.context.preferences.filepaths.save_version=0;bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'deliverables/blender/farm-full.blend'))
verify(expected)
print('MATERIAL_REPAIR_COMPLETE',converted,flush=True)
