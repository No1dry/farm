import bpy,sys,pathlib,json
p=pathlib.Path.cwd();sys.path.insert(0,str(p/'scripts'));import blender_volume as v;import blender_build as a
v.API=a;m=json.load(open(p/'public/models/manifest.json',encoding='utf8'));scene=next(s for s in bpy.data.scenes if s.get('asset_id')=='detail-miaoxia');a.SOURCE_OUT=p/'deliverables/blender'
for kind,sid in [('field','DETAIL-L19'),('pond','DETAIL-QING17')]:
 o=next(o for o in m['objects'] if o['spatial_id']==sid);pp=[(p[0]-1683.71997/2,1190.52002/2-p[1]) for p in o['geometry']['coordinates'][0]];view=v.camera_view(pp,kind);v.render_pair(scene,view,'correction-'+kind)
