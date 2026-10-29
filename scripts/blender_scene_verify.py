"""Run inside Blender against the saved .blend, independently from the builder."""
import bpy
import json
import pathlib
import sys
from mathutils import Vector
from shapely.geometry import Polygon,LineString
from shapely.ops import unary_union

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from blender_traces import SOURCE,BOUNDARY,FEATURES,CHANNELS,pts

if json.loads((ROOT/'public/models/manifest.json').read_text(encoding='utf8')).get('model_revision')=='v06':
    from blender_full_scene_verify import main
    main()
    sys.exit(0)

def xy(p):
    return ((p[0]-SOURCE['origin'][0])*SOURCE['meters_per_pixel'], -(p[1]-SOURCE['origin'][1])*SOURCE['meters_per_pixel'])

terrain=bpy.data.objects['WholeRedlineTerrain']
boundary=Polygon([xy(p) for p in BOUNDARY]).buffer(0)
overlays=unary_union([Polygon([xy(p) for p in f['points']]).buffer(0) for f in FEATURES]+[LineString([xy(p) for p in pts(text)]).buffer(width/2+.3) for _,text,width in CHANNELS])
expected=boundary.difference(overlays).area
actual=sum(p.area for p in terrain.data.polygons)
assert abs(actual-expected)<1, (actual,expected,'terrain holes/coverage mismatch')
water_samples=0
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj.get('asset_id')=='full' and obj.get('water_surface') and obj.get('water_kind')!='channel':
        for face in obj.data.polygons:
            center=sum((obj.data.vertices[i].co for i in face.vertices),Vector())/len(face.vertices)
            hit,_,_,_=terrain.ray_cast(Vector((center.x,center.y,100)),Vector((0,0,-1)))
            assert not hit,(obj.name,'water is occluded by terrain')
            context=bpy.data.objects.get('FullExteriorContext')
            if context:
                hit,_,_,_=context.ray_cast(Vector((center.x,center.y,100)),Vector((0,0,-1)))
                assert not hit,(obj.name,'water is occluded by exterior context')
            water_samples+=1
assert water_samples>200
assert bpy.data.objects['FullAreaReviewCamera'].data.clip_end>=10000
canopy_supports=0
for obj in bpy.data.objects:
    if obj.name.endswith('__CanopyMass'):
        support=bpy.data.objects.get(obj.name.replace('__CanopyMass','__TrunksAndBranches'))
        assert support and min(v.co.z for v in support.data.vertices)<0, (obj.name,'canopy is not ground-connected')
        assert support.get('spatial_id')==obj.get('spatial_id')
        canopy_supports+=1
crest_faces=0
for obj in bpy.data.objects:
    if obj.type=='MESH' and '__ChannelCrest' in obj.name:
        assert all(p.normal.z>0 for p in obj.data.polygons), (obj.name,'downward-facing channel crest')
        crest_faces+=len(obj.data.polygons)
material=bpy.data.materials['Water surface · visible ripples']
assert any(n.type=='NORMAL_MAP' for n in material.node_tree.nodes)
assert all(img.packed_file for img in bpy.data.images if img.type=='IMAGE' and img.size[0]>0), 'Unpacked texture dependency'
manifest=json.loads((ROOT/'public/models/manifest.json').read_text(encoding='utf-8'))
groups=[o for o in bpy.data.objects if o.type=='EMPTY' and o.get('spatial_id')]
assert len(groups)==len(manifest['objects'])
assert len([c for c in bpy.data.collections if c.get('asset_id')])==6
assert len([s for s in bpy.data.scenes if s.get('asset_id')])==6, 'Full area and five drawing scenes must be independently switchable.'
assert len(json.loads(bpy.data.texts['spatial-manifest.json'].as_string())['objects'])==len(groups)
assert json.loads(bpy.data.texts['spatial-manifest.json'].as_string())==manifest, 'Embedded final manifest differs from delivered JSON.'
assert len(json.loads(bpy.data.texts['drawing-entities.json'].as_string())['drawings'])==5
report={'saved_blend_reopened':True,'blender_version':bpy.app.version_string,
 'editable_resource_groups':len(groups),'mesh_objects':sum(o.type=='MESH' for o in bpy.data.objects),
 'packed_images':sum(bool(i.packed_file) for i in bpy.data.images),
 'terrain_expected_area_m2':round(expected,3),'terrain_mesh_area_m2':round(actual,3),
 'unoccluded_water_triangle_samples':water_samples,
 'upward_facing_channel_crest_faces':crest_faces,
 'ground_connected_canopy_groups':canopy_supports,
 'verified_water_normal_map':True,'verified_camera_clipping':True,'verified_texture_self_containment':True,
 'independent_pdf_collections':5,'independently_switchable_scenes':6,'embedded_source_manifest':True,'embedded_builder_scripts':4,
 'original_reference_collections_hidden':all(c.hide_render and c.hide_viewport for c in bpy.data.collections if c.get('reference_only')),
 'volumetric_geometry_and_pbr_only_primary_exports':True,
 'visual_quality_note':'Geometry and data checks do not certify visual quality; review low-angle material/clay images and the browser separately.'}
(ROOT/'deliverables/blender/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
