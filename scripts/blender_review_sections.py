"""Independent low-angle inspection of the saved Blend; never modifies assets."""
import bpy,json,math,pathlib,sys
from mathutils import Vector
from shapely.geometry import Polygon,Point

ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import blender_build as api
import blender_volume as volume
volume.API=api
manifest=json.loads((ROOT/'public/models/manifest.json').read_text(encoding='utf8'))

def camera_at_shore(points):
    poly=Polygon(points).buffer(0);c=poly.representative_point()
    # Inspect from inside the basin toward shore so the slope faces the camera.
    edge=poly.exterior.interpolate(poly.exterior.project(c))
    dx,dy=c.x-edge.x,c.y-edge.y;length=math.hypot(dx,dy);dx/=length;dy/=length
    return {'position':[edge.x+dx*11,2.4,-edge.y-dy*11],
            'target':[edge.x-dx*5,-.2,-edge.y+dy*5]}

def render(scene,view,name,clay=False,dry=False):
    volume.set_camera(scene,view);volume.lighting(scene)
    scene.render.resolution_x=1600;scene.render.resolution_y=1000
    hidden=[];swapped=[]
    if dry:
        for obj in scene.objects:
            if obj.get('water_surface'):hidden.append((obj,obj.hide_render));obj.hide_render=True
    world=scene.world;bg=world.node_tree.nodes['Background'];links=world.node_tree.links
    original_links=[(l.from_socket,l.to_socket) for l in bg.inputs[0].links]
    original_strength=bg.inputs[1].default_value
    sun=bpy.data.objects['AfternoonSun'];sun_rotation=sun.rotation_euler.copy();sun_energy=sun.data.energy
    if clay:
        material=api.pbr('Independent neutral clay inspection',(.48,.48,.48),roughness=1)
        for obj in scene.objects:
            if obj.type=='MESH':
                for slot in obj.material_slots:swapped.append((slot,slot.material));slot.material=material
        for link in list(bg.inputs[0].links):links.remove(link)
        bg.inputs[0].default_value=(.27,.30,.34,1);bg.inputs[1].default_value=.3
        sun.rotation_euler=(math.radians(57),math.radians(-20),math.radians(-35));sun.data.energy=3.5
    scene.render.filepath=str(api.SOURCE_OUT/(name+'.png'));bpy.ops.render.render(write_still=True,scene=scene.name)
    for slot,material in swapped:slot.material=material
    for obj,hide in hidden:obj.hide_render=hide
    for a,b in original_links:links.new(a,b)
    bg.inputs[1].default_value=original_strength;sun.rotation_euler=sun_rotation;sun.data.energy=sun_energy

detail=next(s for s in bpy.data.scenes if s.get('asset_id')=='detail-miaoxia')
view={'position':[139,2.3,169],'target':[121,-.2,181]}
render(detail,view,'pond-section-material')
render(detail,view,'pond-section-clay',clay=True,dry=True)
full=next(s for s in bpy.data.scenes if s.get('asset_id')=='full')
for sid in ['SAT-POND-001','SAT-POND-012','SAT-POND-025','SAT-POND-034']:
    obj=next(o for o in manifest['objects'] if o['spatial_id']==sid)
    points=[(p[0],-p[1]) for p in obj['geometry']['coordinates']]
    render(full,camera_at_shore(points),'full-inspection-'+sid)
obj=next(o for o in manifest['objects'] if o['spatial_id']=='SAT-CHANNEL-005')
points=[(p[0],-p[1]) for p in obj['geometry']['coordinates']]
render(full,volume.camera_view(points,'channel'),'full-inspection-SAT-CHANNEL-005')
obj=next(o for o in manifest['objects'] if o['spatial_id']=='SAT-CHANNEL-001')
points=[(p[0],-p[1]) for p in obj['geometry']['coordinates']]
render(full,volume.camera_view(points,'channel'),'full-edge-channel-001-after')
print('Saved supplemental section inspections; GLB, manifest and Blend were not modified.')
