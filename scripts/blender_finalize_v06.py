"""Synchronize delivery metadata; no geometry, source ID or GLB mutations."""
import bpy,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'public/models/manifest.json';manifest=json.loads(p.read_text(encoding='utf8'))
next(a for a in manifest['assets'] if a['id']=='full')['lod_policy']='Same source owners, all building bodies, equipment and GPU-instanced tree crowns; leaf-card density halved, fine window frames and grass microdetail omitted.'
p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
text=bpy.data.texts['spatial-manifest.json'];text.clear();text.write(json.dumps(manifest,ensure_ascii=False,indent=2))
for filename in ('blender_build.py','blender_drawings.py','blender_traces.py','blender_volume.py','blender_full_region.py'):
    text=bpy.data.texts[filename];text.clear();text.write((root/'scripts'/filename).read_text(encoding='utf8'))
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(root/'deliverables/blender/farm-full.blend'))
print('V06_METADATA_SYNCHRONIZED_NO_GLB_CHANGE')
