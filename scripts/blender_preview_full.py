"""Inspect the next whole-area material/LOD build while source drawing extraction runs."""
import pathlib
import sys
import bpy
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import blender_build as b
b.OUT=b.ROOT/'tmp/model-next'
b.OUT.mkdir(exist_ok=True)
b.reset_scene(); b.create_materials(); full=b.build_full(); b.lights_and_camera()
b.export_collection(full,'full-area.glb'); b.export_low_cost_lod(full)
bpy.data.objects['SatelliteReference'].hide_render=True
bpy.context.scene.render.filepath=str(b.OUT/'preview.png')
bpy.ops.render.render(write_still=True)
