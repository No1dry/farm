"""Reopen the delivered V0.6 Blend and verify geometry and packaging."""
import bpy,json,sys
from pathlib import Path
from mathutils import Vector
from shapely.geometry import Polygon,LineString,shape
from shapely.ops import transform,unary_union
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from blender_traces import BOUNDARY,CHANNELS,pts
def xy(p):return ((p[0]-1110)*300/101,-(p[1]-740)*300/101)
def native(g):return transform(lambda x,y,z=None:((x*1952/2940-1110)*300/101,-(y*1269/1912-740)*300/101),shape(g))
def main():
    manifest=json.loads((ROOT/'public/models/manifest.json').read_text(encoding='utf8'));assert manifest==json.loads(bpy.data.texts['spatial-manifest.json'].as_string())
    sources=json.loads((ROOT/'data/spatial/full-region-enrichment.json').read_text(encoding='utf8'))
    holes=[native(r['geometry']) for r in sources['records'] if r.get('status')=='image_refined_water_outline'];holes.extend(LineString([xy(p) for p in pts(t)]).buffer(w/2+.3) for _,t,w in CHANNELS)
    expected=Polygon([xy(p) for p in BOUNDARY]).difference(unary_union(holes)).area;terrain=bpy.data.objects['FullAgriculturalContextGround'];actual=sum(p.area for p in terrain.data.polygons);assert abs(actual-expected)<2,(actual,expected)
    water_samples=0
    for obj in bpy.data.objects:
        if obj.type!='MESH' or not obj.get('water_surface') or obj.get('asset_id')!='full' or obj.get('water_kind')=='channel':continue
        for face in obj.data.polygons:
            c=sum((obj.data.vertices[i].co for i in face.vertices),Vector())/len(face.vertices)
            for ground in (terrain,bpy.data.objects['FullExteriorContext']):
                hit,_,_,_=ground.ray_cast(Vector((c.x,c.y,100)),Vector((0,0,-1)));assert not hit,(obj.name,ground.name,'water covered by ground')
            water_samples+=1
    assert water_samples>200
    buildings=[o for o in bpy.data.objects if o.name.endswith('__EditableBuilding')];assert len(buildings)==manifest['full_region_appearance_statistics']['building_instances']
    trees=[o for o in bpy.data.objects if o.get('tree_instance')];assert len(trees)==manifest['full_region_appearance_statistics']['sample_tree_count']*3
    tree_data={o.data.name for o in trees};assert len(tree_data)<=12,'Trees lost linked geometry reuse'
    assert all(min(v.co.z for v in o.data.vertices)<0 for o in trees if o.get('tree_part')=='Trunk')
    crests=[o for o in bpy.data.objects if o.type=='MESH' and '__ChannelCrest' in o.name];assert crests and all(p.normal.z>0 for o in crests for p in o.data.polygons)
    assert all(i.packed_file for i in bpy.data.images if i.type=='IMAGE' and i.size[0]>0),'Image not packed'
    assert len([s for s in bpy.data.scenes if s.get('asset_id')])==6
    for name in ['blender_full_region.py','full-region-parameters.json','full-region-enrichment.json','full-area-device-layout.json']:assert name in bpy.data.texts
    report={'passed':True,'reopened_blend':bpy.data.filepath,'terrain_area_expected':expected,'terrain_area_actual':actual,'unoccluded_water_triangles':water_samples,'editable_buildings':len(buildings),'tree_component_instances':len(trees),'unique_tree_mesh_datablocks':len(tree_data),'channel_crest_faces_up':sum(len(o.data.polygons) for o in crests),'packed_images':sum(bool(i.packed_file) for i in bpy.data.images),'embedded_manifest_exact':True}
    (ROOT/'deliverables/blender/full-region-scene-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('V06_BLEND_REOPEN_VERIFIED '+json.dumps(report))
if __name__=='__main__':main()
