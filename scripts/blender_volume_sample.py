"""First visual review: audited Miaoxialiu channel, independent of production exports."""
import sys,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import bpy
import blender_build as a
import blender_drawings as d
import blender_volume as v
from shapely.geometry import Polygon,LineString
from shapely.ops import unary_union
a.reset_scene();v.materials(a);v.install(a)
data=json.loads((ROOT/'data/spatial/drawing-entities.json').read_text(encoding='utf8'))
drawing=data['drawings'][0];w,h=d.drawing_dimensions(drawing)
a.CURRENT_ASSET='detail-miaoxia';a.ACTIVE_COLLECTION=a.new_collection('SAMPLE · source-positioned Miaoxialiu relief')
rows=[r for r in data['records'] if r['asset_id']==a.CURRENT_ASSET]
shapes=[];holes=[];allpolys=[]
for r in rows:
 g=r['geometry'];typ=g['type'];xy=lambda p:(p[0]-w/2,h/2-p[1])
 if typ=='Polygon':
  rings=[[xy(p) for p in ring] for ring in d.polygon_rings(g)];p=Polygon(rings[0],rings[1:]).buffer(0);shapes.append(p);allpolys.append(p)
  if r['kind'] in ('pond','lake'):holes.append(p)
 elif typ=='LineString':
  p=LineString([xy(p) for p in g['coordinates']]).buffer(3.7);shapes.append(p)
  if r['kind']=='channel':holes.append(p)
v.CUTS=unary_union(holes)
outer=unary_union(shapes).buffer(24).buffer(-9)
v.terrain('MiaoxialiuExcavatedTerrain',outer,unary_union(allpolys+holes))
channel_points=None
for r in rows:
 if r['geometry']['type']=='Point':continue
 obj,points=d.make_record(a,r,drawing,w,h);sid=obj['spatial_id'];kind=obj['kind']
 if kind=='field':v.field(sid,points,detail=True)
 elif kind=='pond':v.water(sid,points,detail=True)
 elif kind=='road':v.road(sid,points,3.3)
 elif kind=='channel':v.channel(sid,points,6.4,1.2,1.8,True);channel_points=points
a.lights_and_camera();scene=bpy.context.scene
for obj in scene.objects:
 if obj.type=='MESH' and '__ChannelCrest' in obj.name:
  assert all(p.normal.z>0 for p in obj.data.polygons),('Crest winding',obj.name)
view=v.camera_view(channel_points,'channel');v.render_pair(scene,view,'correction-channel-sample')
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(a.SOURCE_OUT/'correction-channel-sample.blend'))
print('SAMPLE_COMPLETE',view)
