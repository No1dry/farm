"""Build editable farm assets with Blender 4.5 LTS.

Run: blender --background --python scripts/blender_build.py
No Three.js scene or existing exported model is converted. This constructs
terrain, shoreline profiles, field beds, berms, road shoulders, drainage
sections, context massing, UVs and PBR material graphs in Blender.
"""
import bpy
import hashlib
import json
import math
import pathlib
import shutil
import sys
from array import array
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from blender_traces import SOURCE, BOUNDARY, FEATURES, ROADS, CHANNELS, pts

OUT = ROOT / 'public/models'
SOURCE_OUT = ROOT / 'deliverables/blender'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE_OUT.mkdir(parents=True, exist_ok=True)
TEXTURES = ROOT / 'public/focus/textures'
MANIFEST = {'version':2,'generator':'Blender 4.5 LTS / scripts/blender_build.py',
 'created':'2026-10-29','coordinate_system':{'name':'LOCAL_IMAGE_APPROX','up':'Y', 'units':'metres',
 'source_canvas':[1952,1269], 'source_image_native':[2940,1912], 'image_origin':[1110,740],
 'metres_per_pixel':SOURCE['meters_per_pixel'], 'georeferenced':False,'elevation_surveyed':False},
 'assets':[{'id':'full','url':'/models/full-area.glb','scope':'full','label':'红线全域概略模型','source_type':'satellite'}],
 'layers':[{'id':'boundary','node_name':'RedlineBoundary','visible':True},
           {'id':'satellite','node_name':'SatelliteReference','visible':True}],
 'objects':[], 'limitations':[
 '卫星片区是地物纹理解释，不是确权地块、经营边界或Excel台账分割。',
 '截图归一化到1952×1269，300米比例尺约101像素；没有投影坐标与实测控制点。',
 '全域无DEM。地形厚度、岸坡高度、田埂高、道路宽、树冠和建筑体块均为展示假设。',
 '全域沟线仅按卫星窄线纹理示意，真实断面、材质和输排水方向待测。',
 '局部图纸场景使用独立坐标系；不与全域拼接。22.75/22.30是图纸平整标高，基准未知。',
 'GLB包含可独立选择的spatial_id；业务UUID由数据库建立，模型不推断业权、作物、塘深和设施状态。']}
MATERIALS = {}
ACTIVE_COLLECTION = None
CURRENT_FEATURE = None
CURRENT_ASSET = 'full'
CURRENT_SCALE = SOURCE['meters_per_pixel']
CURRENT_ORIGIN = SOURCE['origin']

def xy(p):
    return ((p[0]-CURRENT_ORIGIN[0])*CURRENT_SCALE, -(p[1]-CURRENT_ORIGIN[1])*CURRENT_SCALE)

def area2(points):
    return sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(points,points[1:]+points[:1])) / 2

def centroid(points):
    a = area2(points)
    if abs(a) < 1e-8:
        return [sum(p[i] for p in points)/len(points) for i in (0,1)]
    return [sum((p[i]+q[i])*(p[0]*q[1]-q[0]*p[1]) for p,q in zip(points,points[1:]+points[:1]))/(6*a) for i in (0,1)]

def inside(point, polygon):
    x,y=point; result=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a[1]>y)!=(b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]: result=not result
    return result

def new_collection(name):
    col=bpy.data.collections.new(name); bpy.context.scene.collection.children.link(col); return col

def reset_scene():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    for col in list(bpy.data.collections):
        if col.name!='Collection': bpy.data.collections.remove(col)

def pbr(name, color, texture=None, roughness=.85, uv_size=10, normal_strength=.45):
    mat=bpy.data.materials.new(name); mat.use_nodes=True; mat.diffuse_color=(*color,1)
    nodes=mat.node_tree.nodes; links=mat.node_tree.links; bsdf=nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(*color,1); bsdf.inputs['Roughness'].default_value=roughness
    if texture:
        for suffix,socket,colorspace in [('diff','Base Color','sRGB'),('rough','Roughness','Non-Color')]:
            path=TEXTURES/f'{texture}-{suffix}.jpg'
            if path.exists():
                node=nodes.new('ShaderNodeTexImage'); node.image=bpy.data.images.load(str(path),check_existing=True)
                node.image.colorspace_settings.name=colorspace
                if socket=='Base Color':
                    tint=nodes.new('ShaderNodeMix');tint.data_type='RGBA';tint.blend_type='MULTIPLY';tint.inputs[0].default_value=1;tint.inputs[7].default_value=(*color,1)
                    links.new(node.outputs['Color'],tint.inputs[6]);links.new(tint.outputs[2],bsdf.inputs[socket])
                else:links.new(node.outputs['Color'],bsdf.inputs[socket])
        path=TEXTURES/f'{texture}-nor_gl.jpg'
        if path.exists():
            img=nodes.new('ShaderNodeTexImage'); img.image=bpy.data.images.load(str(path),check_existing=True)
            img.image.colorspace_settings.name='Non-Color'; normal=nodes.new('ShaderNodeNormalMap')
            normal.inputs['Strength'].default_value=normal_strength; links.new(img.outputs['Color'],normal.inputs['Color']); links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
    mat['uv_scene_units']=uv_size; return mat

def create_materials():
    MATERIALS['terrain']=pbr('Context ground · unsurveyed datum',(.17,.23,.105),roughness=.95)
    MATERIALS['forest_ground']=pbr('Under-canopy ground',(.075,.14,.045),roughness=.96)
    MATERIALS['grass']=pbr('Vegetated soil · reused photographic PBR',(.28,.34,.12),'grass',uv_size=4,normal_strength=.2)
    MATERIALS['soil']=pbr('Cultivated soil · reused photographic PBR',(.30,.24,.13),'soil',uv_size=12)
    MATERIALS['gravel']=pbr('Compacted gravel road · PBR',(.51,.46,.33),'gravel',uv_size=6)
    MATERIALS['concrete']=pbr('Concrete lining · appearance only',(.57,.58,.55),'concrete',uv_size=4)
    MATERIALS['water']=pbr('Water surface · visible ripples',(.035,.16,.14),roughness=.26,uv_size=28)
    bsdf=MATERIALS['water'].node_tree.nodes.get('Principled BSDF'); bsdf.inputs['Metallic'].default_value=.18
    n=MATERIALS['water'].node_tree.nodes.new('ShaderNodeTexImage'); n.image=bpy.data.images.load(str(TEXTURES/'water-normal.jpg'),check_existing=True); n.image.colorspace_settings.name='Non-Color'
    normal=MATERIALS['water'].node_tree.nodes.new('ShaderNodeNormalMap'); normal.inputs['Strength'].default_value=.30
    MATERIALS['water'].node_tree.links.new(n.outputs['Color'],normal.inputs['Color']); MATERIALS['water'].node_tree.links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
    # Seamless, deliberately non-measurement water appearance for drawing-only
    # areas. Whole-area water replaces this color with the original satellite.
    image=bpy.data.images.new('Illustrative water color variation',width=256,height=256,alpha=True)
    pixels=array('f')
    for y in range(256):
        for x in range(256):
            u,v=x/256,y/256
            value=(math.sin(2*math.pi*(u+2*v))+.45*math.cos(2*math.pi*(3*u-v))+.22*math.sin(2*math.pi*(5*u+4*v)))/1.67
            pixels.extend((.032+.010*value,.145+.040*value,.125+.032*value,1))
    image.pixels.foreach_set(pixels)
    texture_dir=SOURCE_OUT/'textures'; texture_dir.mkdir(exist_ok=True)
    image.filepath_raw=str(texture_dir/'water-appearance.png'); image.file_format='PNG'; image.save(); image.pack()
    color=MATERIALS['water'].node_tree.nodes.new('ShaderNodeTexImage'); color.image=image
    color_uv=MATERIALS['water'].node_tree.nodes.new('ShaderNodeUVMap'); color_uv.uv_map='AppearanceUV'
    MATERIALS['water'].node_tree.links.new(color_uv.outputs['UV'],color.inputs['Vector'])
    MATERIALS['water'].node_tree.links.new(color.outputs['Color'],bsdf.inputs['Base Color'])
    for i,c in enumerate([(.11,.22,.07),(.16,.27,.08),(.22,.30,.10),(.30,.35,.11)]): MATERIALS[f'foliage{i}']=pbr(f'Canopy tone {i}',c)
    MATERIALS['trunk']=pbr('Tree bark',(.18,.12,.065))
    MATERIALS['roof']=pbr('Generic observed roof massing',(.29,.31,.29),roughness=.72)
    MATERIALS['roof_red']=pbr('Generic brick roof massing',(.35,.19,.12),roughness=.8)
    MATERIALS['wall']=pbr('Generic pale building massing',(.68,.66,.55))
    MATERIALS['earth']=pbr('Terrain section earth',(.20,.16,.09))
    MATERIALS['redline']=pbr('Source redline boundary',(.95,.025,.012),roughness=.6)
    red=MATERIALS['redline'].node_tree.nodes.get('Principled BSDF'); red.inputs['Emission Color'].default_value=(.55,.004,.002,1); red.inputs['Emission Strength'].default_value=.25
    mat=pbr('Supplied satellite · projected image provenance',(.3,.4,.2),roughness=1)
    nodes=mat.node_tree.nodes; links=mat.node_tree.links; bsdf=nodes.get('Principled BSDF')
    img=nodes.new('ShaderNodeTexImage'); img.image=bpy.data.images.load(str(ROOT/'参考图/卫星图.png'),check_existing=True)
    links.new(img.outputs['Color'],bsdf.inputs['Base Color']); links.new(img.outputs['Color'],bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value=.12
    MATERIALS['satellite']=mat
    for key,base in [('water_satellite',MATERIALS['water']),('field_satellite',MATERIALS['soil'])]:
        material=base.copy(); material.name='Source-projected '+key+' · independent PBR microtexture'
        nodes=material.node_tree.nodes; links=material.node_tree.links; bsdf=nodes.get('Principled BSDF')
        photo=nodes.new('ShaderNodeTexImage'); photo.image=img.image
        coordinates=nodes.new('ShaderNodeUVMap'); coordinates.uv_map='SourceUV'
        links.new(coordinates.outputs['UV'],photo.inputs['Vector']); links.new(photo.outputs['Color'],bsdf.inputs['Base Color'])
        if key=='water_satellite': bsdf.inputs['Metallic'].default_value=.05; bsdf.inputs['Roughness'].default_value=.24
        MATERIALS[key]=material

def layer_for(kind):
    return {'field':'field','pond':'pond','lake':'pond','road':'road','channel':'channel',
            'woodland':'vegetation','settlement':'building','bare':'field'}.get(kind,'facility')

def tag(obj, role=None):
    if CURRENT_FEATURE:
        obj['spatial_id']=CURRENT_FEATURE['spatial_id']; obj['owner_spatial_id']=CURRENT_FEATURE['spatial_id']
        obj['kind']=CURRENT_FEATURE['kind']; obj['layer']=layer_for(CURRENT_FEATURE['kind'])
        obj['precision']=CURRENT_FEATURE['precision']; obj['asset_id']=CURRENT_ASSET
        parent=bpy.data.objects.get('Resource_'+CURRENT_FEATURE['spatial_id'])
        if parent and obj!=parent: obj.parent=parent
    if role: obj['model_role']=role
    return obj

def mesh(name,vertices,faces,material,role=None,uv_size=None):
    data=bpy.data.meshes.new(name+'Geometry'); data.from_pydata(vertices,[],faces); data.update()
    obj=bpy.data.objects.new(name,data); ACTIVE_COLLECTION.objects.link(obj)
    if material: data.materials.append(material)
    uv=data.uv_layers.new(name='UVMap'); scale=uv_size or (material.get('uv_scene_units',10) if material else 10)
    for poly in data.polygons:
        for li in poly.loop_indices:
            v=data.vertices[data.loops[li].vertex_index].co; uv.data[li].uv=(v.x/scale,v.y/scale)
    if material and material.get('uv_detail'):
        detail=data.uv_layers.new(name='DetailUV');detail_scale=material['uv_detail']
        for poly in data.polygons:
            for li in poly.loop_indices:
                v=data.vertices[data.loops[li].vertex_index].co;detail.data[li].uv=(v.x/detail_scale,v.y/detail_scale)
    if material==MATERIALS.get('water'):
        # Broad albedo variation spans the water object once; only the normal
        # texture tiles, avoiding diagonal/color checkerboard repeats.
        appearance=data.uv_layers.new(name='AppearanceUV')
        minx=min(v.co.x for v in data.vertices); maxx=max(v.co.x for v in data.vertices)
        miny=min(v.co.y for v in data.vertices); maxy=max(v.co.y for v in data.vertices)
        for poly in data.polygons:
            for li in poly.loop_indices:
                v=data.vertices[data.loops[li].vertex_index].co
                appearance.data[li].uv=((v.x-minx)/max(maxx-minx,.001),(v.y-miny)/max(maxy-miny,.001))
    return tag(obj,role)

def poly_surface(name,points,z,material,role=None):
    pp=list(points)
    if area2(pp)<0: pp.reverse()
    verts=[(p[0],p[1],z) for p in pp]
    vec=[Vector(v) for v in verts]; faces=tessellate_polygon([vec])
    faces=[tuple(reversed(f)) if (vec[f[1]]-vec[f[0]]).cross(vec[f[2]]-vec[f[0]]).z<0 else f for f in faces]
    return mesh(name,verts,faces,material,role)

def inward(points,distance):
    c=centroid(points); out=[]
    for p in points:
        dx,dy=c[0]-p[0],c[1]-p[1]; length=math.hypot(dx,dy); f=min(.35,distance/max(length,1e-9)); out.append((p[0]+dx*f,p[1]+dy*f))
    return out

def ring(name,outer,inner,z_outer,z_inner,material,role):
    if area2(outer)<0: outer=list(reversed(outer)); inner=list(reversed(inner))
    n=len(outer); verts=[(p[0],p[1],z_outer) for p in outer]+[(p[0],p[1],z_inner) for p in inner]
    faces=[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh(name,verts,faces,material,role)

def section_strip(name,points,profile,material,role,closed=False):
    """Sweep a real cross-section along an editable polyline, with mitred corners."""
    pp=list(points); n=len(pp); vertices=[]
    for i,p in enumerate(pp):
        a=pp[(i-1)%n] if closed or i else pp[0]
        b=pp[(i+1)%n] if closed or i<n-1 else pp[-1]
        dx,dy=b[0]-a[0],b[1]-a[1]; length=math.hypot(dx,dy) or 1
        normal=(-dy/length,dx/length)
        for offset,z in profile: vertices.append((p[0]+normal[0]*offset,p[1]+normal[1]*offset,z))
    m=len(profile); faces=[]
    for i in range(n if closed else n-1):
        j=(i+1)%n
        for k in range(m-1): faces.append((i*m+k,j*m+k,j*m+k+1,i*m+k+1))
    return mesh(name,vertices,faces,material,role)

def clip_axis(points,axis,limit,keep_above):
    out=[]
    for a,b in zip(points,points[1:]+points[:1]):
        ai=a[axis]>=limit if keep_above else a[axis]<=limit; bi=b[axis]>=limit if keep_above else b[axis]<=limit
        if ai: out.append(a)
        if ai!=bi:
            t=(limit-a[axis])/(b[axis]-a[axis]); out.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
    return out

def field(name,points,height=2.5,detail=False,index=0):
    bed=poly_surface(name+'__CultivatedBed',points,height,MATERIALS['soil'] if detail else MATERIALS['field_satellite'],'field bed')
    if not detail: satellite_uv(bed,'SourceUV')
    inn=inward(points,1.4 if detail else 2.0)
    ring(name+'__EarthSides',points,points,1.6,height,MATERIALS['soil'],'raised earth side')
    section_strip(name+'__FieldBerm',points,[(-1.4,height-.25),(-.65,height+.6),(.65,height+.6),(1.4,height-.25)],MATERIALS['grass'],'raised vegetated field berm',True)
    if not detail: return
    # Clipped low beds are editable agricultural texture geometry, not claims about a planted crop.
    spacing=2.8 if detail else 5.5; width=1.1 if detail else 3.0
    lo=min(p[1] for p in inn); hi=max(p[1] for p in inn); vertices=[]; faces=[]
    cursor=lo+spacing*.6
    while cursor<hi:
        strip=clip_axis(clip_axis(inn,1,cursor,True),1,cursor+width,False)
        if len(strip)>=3:
            if area2(strip)<0: strip.reverse()
            base=len(vertices); vectors=[Vector((p[0],p[1],height+.09)) for p in strip]
            vertices.extend(tuple(v) for v in vectors)
            faces.extend(tuple(base+i for i in tri) for tri in tessellate_polygon([vectors]))
        cursor+=spacing
    if faces: mesh(name+'__LowVegetationRows',vertices,faces,MATERIALS['grass'],'illustrative low vegetation rows')

def water(name,points,lake=False,detail=False):
    slope_width=4.2 if lake else (3.1 if detail else 3.8); inn=inward(points,slope_width)
    ring(name+'__ShoreSlope',points,inn,2.7,1.0,MATERIALS['soil'],'editable earth shoreline slope')
    surface=poly_surface(name+'__Water',inn,1.03,MATERIALS['water'] if detail else MATERIALS['water_satellite'],'water surface; depth unknown')
    if not detail: satellite_uv(surface,'SourceUV')
    section_strip(name+'__VegetatedCrest',points,[(-1.2,2.35),(-.45,3.05),(.45,3.05),(1.2,2.35)],MATERIALS['grass'],'shore embankment crest',True)

def road(name,points,width):
    section_strip(name+'__Shoulders',points,[(-width/2-1.2,2.05),(-width/2,2.6),(width/2,2.6),(width/2+1.2,2.05)],MATERIALS['soil'],'road shoulder profile')
    section_strip(name+'__Surface',points,[(-width/2,2.65),(0,2.70),(width/2,2.65)],MATERIALS['gravel'],'crowned gravel road')

def channel(name,points,top_width,bottom_width=1.0,depth=1.0,lined=False):
    top=2.5; bottom=top-depth
    section_strip(name+'__Trapezoid',points,[(-top_width/2,top),(-bottom_width/2,bottom),(bottom_width/2,bottom),(top_width/2,top)],MATERIALS['concrete'] if lined else MATERIALS['soil'],'editable trapezoidal drainage section')
    section_strip(name+'__ShallowWater',points,[(-bottom_width*.4,bottom+.08),(bottom_width*.4,bottom+.08)],MATERIALS['water'],'illustrative shallow water; flow unknown')
    for sign in (-1,1): section_strip(name+f'__Edge{sign}',points,[(sign*(top_width/2+.5),top),(sign*(top_width/2),top+.15)],MATERIALS['grass'],'vegetated channel edge')


def woodland(name,points):
    surface=poly_surface(name+'__Ground',points,2.05,MATERIALS['satellite'],'observed woodland image surface; no individual tree survey')
    satellite_uv(surface)

def settlement(name,points):
    surface=poly_surface(name+'__SettlementFootprint',points,2.05,MATERIALS['satellite'],'observed settlement image surface; individual building footprints unknown')
    satellite_uv(surface)

def record(feature,asset='full',line=False,width=None):
    global CURRENT_FEATURE
    points=feature['points']; world=[xy(p) for p in points]; c=centroid(world) if not line else [sum(p[i] for p in world)/len(world) for i in (0,1)]
    precision='approximate_satellite' if asset=='full' else 'unregistered_drawing_detail'
    obj={**feature,'asset_id':asset,'precision':precision,'entity_uuid':None,'code':feature.get('code',feature['spatial_id']),
      'center':[round(c[0],3),3,round(-c[1],3)],'centroid':[round(c[0],3),3,round(-c[1],3)],
      'bounds':{'min':[min(p[0] for p in world),0,min(-p[1] for p in world)],'max':[max(p[0] for p in world),14,max(-p[1] for p in world)]},
      'geometry':{'type':'LineString' if line else 'Polygon','coordinates':[[round(p[0],4),round(-p[1],4)] for p in world]},
      'source':'卫星图.png；2026-10-29独立纹理描绘；非台账边界' if asset=='full' else '2026.4.16竣工图（庙下流）.pdf；东侧局部轮廓；未测绘配准',
      'model_area_m2':round(sum(math.dist(a,b) for a,b in zip(world,world[1:]))*(width or 1) if line else abs(area2(world)),2),
      'accuracy_note':'截图概略；物理厚度和高程为展示假设' if asset=='full' else '局部绘图坐标；尺寸缩放待复核；标高基准未知'}
    if line: obj['model_length_m']=round(sum(math.dist(a,b) for a,b in zip(world,world[1:])),2)
    MANIFEST['objects'].append(obj); CURRENT_FEATURE=obj
    parent=bpy.data.objects.new('Resource_'+feature['spatial_id'],None); ACTIVE_COLLECTION.objects.link(parent)
    tag(parent,'independent editable spatial resource group'); parent['display_name']=feature['name']
    return world

def satellite_uv(obj,layer_name='UVMap'):
    uv=obj.data.uv_layers.get(layer_name) or obj.data.uv_layers.new(name=layer_name)
    for polygon in obj.data.polygons:
        for li in polygon.loop_indices:
            v=obj.data.vertices[obj.data.loops[li].vertex_index].co
            px=v.x/SOURCE['meters_per_pixel']+SOURCE['origin'][0]
            py=-v.y/SOURCE['meters_per_pixel']+SOURCE['origin'][1]
            uv.data[li].uv=(px/1952,1-py/1269)

def context_base(points,detail=False,water_holes=None):
    global CURRENT_FEATURE
    CURRENT_FEATURE=None
    # GEOS constrained triangulation preserves many disjoint shoreline holes.
    # A single ear-clipping tessellator can bridge unrelated holes incorrectly.
    land=Polygon(points).buffer(0)
    if water_holes:
        water_union=unary_union([Polygon(p).buffer(0) for p in water_holes])
        land=land.difference(water_union)
    triangles_geom=constrained_delaunay_triangles(land)
    assert abs(sum(t.area for t in triangles_geom.geoms)-land.area)<1e-4, 'Terrain triangulation must cover exactly the land area.'
    z=.35 if detail else 1.6
    vertices=[]; triangles=[]; vertex_ids={}
    for tri in triangles_geom.geoms:
        coords=list(tri.exterior.coords)[:3]
        if area2(coords)<0: coords.reverse()
        ids=[]
        for x,y in coords:
            key=(x,y)
            if key not in vertex_ids: vertex_ids[key]=len(vertices); vertices.append((x,y,z))
            ids.append(vertex_ids[key])
        triangles.append(tuple(ids))
    top=mesh('DetailTerrain' if detail else 'WholeRedlineTerrain',vertices,triangles,MATERIALS['terrain'],'terrain top with real openings below water bodies')
    top['surface_area_m2']=land.area
    top['layer']='terrain'; top['precision']='illustrative_elevation'; top['asset_id']=CURRENT_ASSET
    if not detail:
        photo=mesh('SatelliteTerrain',[(x,y,z+.04) for x,y,z in vertices],triangles,MATERIALS['satellite'],'source image projected on uncertain context land')
        satellite_uv(photo); photo['layer']='satellite'; photo['asset_id']='full'; photo['default_visible']=True
    side=ring('TerrainEarthSection',points,points,z,-18 if not detail else -6,MATERIALS['earth'],'model section, not geology')
    side['layer']='terrain'; side['asset_id']=CURRENT_ASSET

def satellite_reference():
    global CURRENT_FEATURE
    CURRENT_FEATURE=None
    mat=MATERIALS['satellite']
    points=[xy(p) for p in [(680,315),(1535,315),(1535,1170),(680,1170)]]
    obj=mesh('SatelliteReference',[(x,y,-20) for x,y in points],[(3,2,1,0)],mat)
    image_uv=[(680/1952,1-315/1269),(1535/1952,1-315/1269),(1535/1952,1-1170/1269),(680/1952,1-1170/1269)]
    for poly in obj.data.polygons:
        for li in poly.loop_indices: obj.data.uv_layers.active.data[li].uv=image_uv[obj.data.loops[li].vertex_index]
    obj['layer']='satellite'; obj['asset_id']='full'; obj['default_visible']=False

def build_full():
    global ACTIVE_COLLECTION, CURRENT_ASSET, CURRENT_SCALE, CURRENT_ORIGIN, CURRENT_FEATURE
    CURRENT_ASSET='full'; CURRENT_SCALE=SOURCE['meters_per_pixel']; CURRENT_ORIGIN=SOURCE['origin']
    ACTIVE_COLLECTION=new_collection('FULL · redline landscape · image based approximation')
    boundary=[xy(p) for p in BOUNDARY]
    # Source-projected field/woodland/settlement faces also replace the context
    # surface. Removing their underlying triangles avoids far-view Z fighting.
    context_base(boundary,water_holes=[[xy(p) for p in f['points']] for f in FEATURES])
    for index,feature in enumerate(FEATURES):
        points=record(feature); name=feature['spatial_id']; kind=feature['kind']
        if kind=='field': field(name,points,index=index)
        elif kind in ('pond','lake'): water(name,points,kind=='lake')
        elif kind=='woodland': woodland(name,points)
        elif kind=='settlement': settlement(name,points)
        else:
            surface=poly_surface(name+'__ExposedSoil',points,2.15,MATERIALS['field_satellite'],'ambiguous disturbed land cover')
            satellite_uv(surface,'SourceUV')
    for i,(name,text,width) in enumerate(ROADS):
        f={'spatial_id':f'SAT-ROAD-{i+1:03d}','name':name+'（概略）','kind':'road','region':'全域','points':pts(text),'assumed_width_m':width}
        road(f['spatial_id'],record(f,line=True,width=width),width)
    for i,(name,text,width) in enumerate(CHANNELS):
        f={'spatial_id':f'SAT-CHANNEL-{i+1:03d}','name':name+'（判读待核）','kind':'channel','region':'全域','points':pts(text),'assumed_width_m':width}
        channel(f['spatial_id'],record(f,line=True,width=width),width,1.0,.9)
    CURRENT_FEATURE=None
    red=section_strip('RedlineBoundary',boundary,[(-1.8,4),(1.8,4)],MATERIALS['redline'],'source screenshot redline, not surveyed cadastral line',True)
    red['layer']='boundary'; red['asset_id']='full'; satellite_reference()
    MANIFEST['boundary']={'points':BOUNDARY,'center':[0,0,0],'model_area_m2':round(abs(area2(boundary)),2),'precision':'screenshot_redline_approximate'}
    return ACTIVE_COLLECTION


def lights_and_camera():
    scene=bpy.context.scene; scene.render.engine='BLENDER_EEVEE_NEXT'
    scene.render.resolution_x=1800; scene.render.resolution_y=1500; scene.render.resolution_percentage=100
    scene.world.color=(.32,.38,.45)
    world=scene.world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.40,.48,.58,1); world.node_tree.nodes['Background'].inputs[1].default_value=.45
    bpy.ops.object.light_add(type='SUN',location=(0,0,2000)); sun=bpy.context.object; sun.name='AfternoonSun'; sun.data.energy=2.2; sun.rotation_euler=(math.radians(24),math.radians(-28),math.radians(-25)); sun.data.angle=math.radians(15)
    bpy.ops.object.camera_add(location=(1700,-2900,3600)); camera=bpy.context.object; camera.name='FullAreaReviewCamera'; camera.data.type='ORTHO'; camera.data.ortho_scale=3200; camera.data.clip_end=20000
    camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler(); scene.camera=camera
    scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'
    return camera

def export_collection(collection,filename):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in collection.objects: obj.hide_set(False); obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/filename),export_format='GLB',use_selection=True,use_active_scene=True,export_extras=True,export_yup=True,
                              export_apply=True,export_animations=False,export_cameras=False,export_lights=False,export_materials='EXPORT',export_image_format='AUTO')

def export_low_cost_lod(collection):
    """Keep all section profiles and IDs; omit only grass/stubble/stone microdetail."""
    selected=[o for o in collection.objects if not o.get('lod_detail')]
    swapped=[]; cache={}
    for obj in selected:
        if obj.type!='MESH': continue
        for slot in obj.material_slots:
            original=slot.material
            if original.name not in cache:
                mat=original.copy(); mat.name=original.name+' · far-view LOD'; cache[original.name]=mat
                bsdf=mat.node_tree.nodes.get('Principled BSDF')
                if bsdf:
                    for socket in ('Normal','Roughness'):
                        for link in list(bsdf.inputs[socket].links): mat.node_tree.links.remove(link)
                    bsdf.inputs['Roughness'].default_value=.85
            swapped.append((slot,original)); slot.material=cache[original.name]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected: obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/'full-area-lod.glb'),export_format='GLB',use_selection=True,export_extras=True,export_yup=True,
      export_apply=True,export_animations=False,export_cameras=False,export_lights=False)
    for slot,original in swapped: slot.material=original
    asset=next(a for a in MANIFEST['assets'] if a['id']=='full')
    asset['lod_url']='/models/full-area-lod.glb'; asset['lod_policy']='Far view; identical source IDs and terrain/shore/road/channel cross-sections; omit only vegetation/stone microdetail and normal/roughness maps'
    asset['lod_meshes']=sum(o.type=='MESH' for o in selected)

def create_drawing_scenes(details):
    import blender_volume as volume
    main=bpy.context.scene; main.name='FULL · satellite area'; main['asset_id']='full'
    scenes=[]
    for collection in details:
        asset=next(a for a in MANIFEST['assets'] if a['id']==collection['asset_id'])
        scene=bpy.data.scenes.new(asset['id']+' · '+asset['label'])
        scene['asset_id']=asset['id']; scene['coordinate_units']='paper_point'; scene['georeferenced']=False
        scene.collection.children.link(collection); scene.collection.objects.link(bpy.data.objects['AfternoonSun'])
        scene.world=main.world; scene.render.engine='BLENDER_EEVEE_NEXT'; scene.view_settings.view_transform='AgX'
        scene.render.resolution_x=2000; scene.render.resolution_y=1450; scene.render.resolution_percentage=100
        scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(SOURCE_OUT/(asset['id']+'-review.png'))
        data=bpy.data.cameras.new(asset['id']+'Camera'); data.type='ORTHO'; data.ortho_scale=asset['page_size_pt'][0]*1.08; data.clip_end=20000
        camera=bpy.data.objects.new(asset['id']+'Camera',data); scene.collection.objects.link(camera); scene.camera=camera
        volume.set_camera(scene,asset['camera_views']['focus']);volume.lighting(scene)
        main.view_layers[0].layer_collection.children[collection.name].exclude=True
        scenes.append(scene)
    return scenes

def main():
    import blender_drawings,blender_volume,blender_full_region
    api=sys.modules[__name__]
    reset_scene();blender_volume.materials(api);blender_volume.install(api);full=blender_full_region.build(api);details=blender_drawings.build(api);camera=lights_and_camera()
    blender_volume.lighting(bpy.context.scene);blender_volume.set_camera(bpy.context.scene,MANIFEST['assets'][0]['camera_views']['overview'])
    blender_full_region.export_full(full,'full-area.glb');blender_full_region.export_full(full,'full-area-lod.glb',lod=True)
    for collection in details: export_collection(collection,collection['asset_id']+'.glb')
    from blender_material_verify import capture_blender_materials,verify as verify_material_export
    verify_material_export(capture_blender_materials(),MANIFEST)
    drawing_scenes=create_drawing_scenes(details)
    for obj in bpy.data.objects:
        if obj.get('category')=='source_annotation':obj.hide_render=True
    for obj in full.objects: obj.hide_set(False)
    bpy.data.objects['SatelliteReference'].hide_render=True; bpy.data.objects['SatelliteReference'].hide_set(True)
    scene=bpy.context.scene; scene['model_readme']='Choose Scene: FULL or one of five PDF drawing scenes. Every source object is separately editable. Paper coordinates are unregistered. See docs/model-methodology.md.'
    scene['source_precision']='Approximate screenshot, not surveyed geometry'; scene['source_date']='2026-10-29'; scene.unit_settings.system='METRIC'
    # Keep provenance and the exact build inputs readable inside the standalone Blend.
    for name,value in [('spatial-manifest.json',MANIFEST),('drawing-entities.json',DRAWING_DATA)]:
        block=bpy.data.texts.get(name) or bpy.data.texts.new(name); block.clear(); block.write(json.dumps(value,ensure_ascii=False,indent=2))
    for filename in ('blender_build.py','blender_drawings.py','blender_traces.py','blender_volume.py','blender_full_region.py'):
        block=bpy.data.texts.get(filename) or bpy.data.texts.new(filename); block.clear(); block.write((ROOT/'scripts'/filename).read_text(encoding='utf-8'))
    for filename in ('data/model/full-region-parameters.json','data/model/full-region-generated-instances.json','data/demo/full-area-device-layout.json','data/spatial/full-region-enrichment.json'):
        block=bpy.data.texts.get(pathlib.Path(filename).name) or bpy.data.texts.new(pathlib.Path(filename).name);block.clear();block.write((ROOT/filename).read_text(encoding='utf8'))
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active; space.clip_end=20000; space.region_3d.view_distance=3400; space.region_3d.view_location=(0,0,0); space.region_3d.view_rotation=camera.rotation_euler.to_quaternion(); space.region_3d.view_perspective='CAMERA'
    # Pack texture dependencies, making the .blend independently editable on another computer.
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.file.pack_all(); bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE_OUT/'farm-full.blend'))
    # Render high resolution reviews from the actual Blender scene used for export.
    scene.render.filepath=str(SOURCE_OUT/'full-area-review.png'); bpy.ops.render.render(write_still=True)
    for drawing_scene in drawing_scenes: bpy.ops.render.render(write_still=True,scene=drawing_scene.name)
    miaoxia=next(s for s in drawing_scenes if s.get('asset_id')=='detail-miaoxia')
    views=next(a for a in MANIFEST['assets'] if a['id']=='detail-miaoxia')['camera_views']
    for kind in ('field','channel','pond'):blender_volume.render_pair(miaoxia,views[kind],'correction-'+kind)
    blender_volume.set_camera(miaoxia,views['focus'])
    for asset in MANIFEST['assets']:
        path=OUT/pathlib.Path(asset['url']).name; asset['bytes']=path.stat().st_size; asset['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        if asset.get('lod_url'):
            lod=OUT/pathlib.Path(asset['lod_url']).name; asset['lod_bytes']=lod.stat().st_size; asset['lod_sha256']=hashlib.sha256(lod.read_bytes()).hexdigest()
    MANIFEST['statistics']={'full_area_objects':sum(x['asset_id']=='full' for x in MANIFEST['objects']),
      'detail_objects':sum(x['asset_id']!='full' for x in MANIFEST['objects']),
      'drawing_assets':len(details),
      'mesh_objects':sum(o.type=='MESH' for col in [full]+details for o in col.objects),
      'vertices':sum(len(o.data.vertices) for col in [full]+details for o in col.objects if o.type=='MESH'),
      'polygons':sum(len(o.data.polygons) for col in [full]+details for o in col.objects if o.type=='MESH')}
    (OUT/'manifest.json').write_text(json.dumps(MANIFEST,ensure_ascii=False,indent=2),encoding='utf-8')
    block=bpy.data.texts['spatial-manifest.json'];block.clear();block.write(json.dumps(MANIFEST,ensure_ascii=False,indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE_OUT/'farm-full.blend'))
    print('MODEL_BUILD_COMPLETE '+json.dumps(MANIFEST['statistics']))

if __name__=='__main__': main()
