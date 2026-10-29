"""V0.6 full-redline scene: observed contours plus replaceable sample appearance.

This module constructs Blender meshes directly. No satellite/CAD screenshot is
used on a main model material. Native pixel geometries remain source evidence;
wall heights, vegetation, crop states and equipment are explicit demonstrations.
"""
import bpy
import bmesh
import json
import math
import random
import hashlib
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mathutils import Vector
from shapely.geometry import Polygon, LineString, Point, box, shape
from shapely.affinity import rotate
from shapely.ops import unary_union, transform
from shapely.ops import nearest_points
from shapely import constrained_delaunay_triangles
import blender_volume as V

A=None
P={}
M={}
INSTANCES=[]
STATS={}
HEIGHT_FUNCTIONS={}
BUILDING_SOLIDS={}
TREE_ARCHETYPES={}

def seeded(name):return V.seeded(str(P.get('seed',20261029))+':'+name)

def native(p):
    return A.xy((p[0]*1952/2940,p[1]*1269/1912))

def geom(row):
    return transform(lambda x,y,z=None: ((x*1952/2940-1110)*300/101,-(y*1269/1912-740)*300/101),shape(row['geometry'])).buffer(0) if row['geometry']['type']=='Polygon' else LineString([native(p) for p in row['geometry']['coordinates']])

def owner(sid):
    A.CURRENT_FEATURE=next((o for o in A.MANIFEST['objects'] if o['spatial_id']==sid),None)

def appearance(obj,status='sample',record=None):
    if obj is None:return
    obj['data_nature']='synthetic_appearance' if status=='sample' else 'observed_footprint_with_synthetic_height'
    obj['source_status']=status;obj['business_entity']=False;obj['asset_id']='full'
    obj['replaceable_parameter_file']='data/model/full-region-parameters.json'
    if record:obj['appearance_id']=record['id'];obj['source_record_id']=record['id']
    return obj

class Mesh:
    """Small direct mesh accumulator; separately editable building or land patch."""
    def __init__(self):self.v=[];self.f=[];self.mi=[];self.materials=[]
    def face(self,pp,mat):
        if mat not in self.materials:self.materials.append(mat)
        k=len(self.v);self.v.extend(pp);self.f.append(tuple(range(k,k+len(pp))));self.mi.append(self.materials.index(mat))
    def cube(self,center,size,mat,angle=0):
        x,y,z=center;w,d,h=size;c=math.cos(angle);s=math.sin(angle)
        pp=[]
        for zz in (-h/2,h/2):
            for xx,yy in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]:pp.append((x+xx*c-yy*s,y+xx*s+yy*c,z+zz))
        for inds in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.face([pp[i] for i in inds],mat)
    def limb(self,a,b,r0,r1,mat,n=6):
        a=Vector(a);b=Vector(b);axis=(b-a).normalized();ref=Vector((0,1,0)) if abs(axis.y)<.9 else Vector((1,0,0));u=axis.cross(ref).normalized();v=axis.cross(u)
        rings=[[tuple(center+(u*math.cos(j*math.tau/n)+v*math.sin(j*math.tau/n))*r) for j in range(n)] for center,r in [(a,r0),(b,r1)]]
        for j in range(n):self.face([rings[0][j],rings[0][(j+1)%n],rings[1][(j+1)%n],rings[1][j]],mat)
        self.face(list(reversed(rings[0])),mat);self.face(rings[1],mat)
    def ellipsoid(self,center,radii,mat,rng,n=8):
        x,y,z=center;rx,ry,rz=radii;rings=[]
        for h,r in [(-.90,.27),(-.47,.85),(.13,1),(.66,.72)]:
            rings.append([(x+math.cos(j*math.tau/n)*rx*r*rng.uniform(.86,1.13),y+math.sin(j*math.tau/n)*ry*r*rng.uniform(.86,1.13),z+rz*h+rng.uniform(-.12,.12)*rz) for j in range(n)])
        self.face(list(reversed(rings[0])),mat)
        for a,b in zip(rings,rings[1:]):
            for j in range(n):self.face([a[j],a[(j+1)%n],b[(j+1)%n],b[j]],mat)
        for j in range(n):self.face([rings[-1][j],rings[-1][(j+1)%n],(x,y,z+rz)],mat)
    def object(self,name,role,smooth=False):
        if not self.f:return None
        obj=A.mesh(name,self.v,self.f,None,role)
        for mat in self.materials:obj.data.materials.append(mat)
        for face,mi in zip(obj.data.polygons,self.mi):face.material_index=mi;face.use_smooth=smooth
        if smooth:
            bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free();obj.data.update()
        return appearance(obj)

def palette():
    colors=[(.33,.52,.10),(.22,.40,.065),(.42,.56,.15),(.18,.35,.058),(.51,.53,.19),(.32,.43,.14)]
    for i,c in enumerate(colors):M['crop'+str(i)]=A.pbr('V06 growing crop canopy '+str(i),c,'grass',uv_size=5.2,normal_strength=.28)
    for i,c in enumerate([(.065,.15,.025),(.095,.22,.035),(.14,.25,.05),(.18,.30,.065),(.09,.19,.055)]):M['leaf'+str(i)]=A.pbr('V06 varied broadleaf crown '+str(i),c,'grass',uv_size=1.6,normal_strength=.6,roughness=.88)
    for i,c in enumerate([(.57,.55,.46),(.72,.70,.61),(.48,.46,.40),(.57,.44,.31)]):M['wall'+str(i)]=A.pbr('V06 rural plaster masonry '+str(i),c,'concrete',uv_size=3,normal_strength=.16)
    for key,c in [('gray',(.20,.23,.22)),('red',(.29,.10,.06)),('blue',(.055,.15,.19)),('brown',(.25,.19,.11))]:M['roof_'+key]=A.pbr('V06 '+key+' tile or sheet roof',c,roughness=.65)
    M['window']=A.pbr('V06 recessed blue gray glazing',(.035,.075,.095),roughness=.28)
    M['frame']=A.pbr('V06 window and eave frames',(.31,.34,.32),roughness=.73)
    M['door']=A.pbr('V06 timber doors',(.16,.12,.075),roughness=.8)
    M['bark']=A.pbr('V06 textured tree bark',(.20,.13,.065),'soil',uv_size=1.5,normal_strength=.4)
    M['understory']=A.pbr('V06 green forest floor',(.18,.27,.065),'grass',uv_size=7,normal_strength=.18)
    M['meadow']=A.pbr('V06 mixed green field margins',(.33,.43,.13),'grass',uv_size=6,normal_strength=.15)
    M['yard']=A.pbr('V06 village gravel courtyards',(.50,.48,.40),'gravel',uv_size=3.5,normal_strength=.3)
    M['asphalt']=A.pbr('V06 weathered rural pavement',(.30,.30,.27),'concrete',uv_size=4,normal_strength=.18)
    M['metal']=A.pbr('V06 sample equipment galvanized metal',(.39,.44,.46),roughness=.4)
    M['panel']=A.pbr('V06 sample solar panel',(.015,.045,.075),roughness=.25)
    M['blue']=A.pbr('V06 sample equipment blue polymer',(.045,.23,.32),roughness=.4)
    M['orange']=A.pbr('V06 sample buoy orange',(.75,.29,.035),roughness=.5)
    M['leaf_card']=A.pbr('V06 CC0 photographic broadleaf sprays',(.75,.85,.65),roughness=.82)
    leaf=M['leaf_card'];nodes=leaf.node_tree.nodes;links=leaf.node_tree.links;bs=nodes.get('Principled BSDF')
    color=nodes.new('ShaderNodeTexImage');color.image=bpy.data.images.load(str(A.TEXTURES/'foliage/leaves_diff.png'),check_existing=True);links.new(color.outputs['Color'],bs.inputs['Base Color'])
    alpha=nodes.new('ShaderNodeTexImage');alpha.image=bpy.data.images.load(str(A.TEXTURES/'foliage/leaves_alpha.png'),check_existing=True);alpha.image.colorspace_settings.name='Non-Color';clip=nodes.new('ShaderNodeMath');clip.operation='GREATER_THAN';clip.inputs[1].default_value=.5;links.new(alpha.outputs['Color'],clip.inputs[0]);links.new(clip.outputs[0],bs.inputs['Alpha']);leaf.surface_render_method='DITHERED';leaf.use_backface_culling=False
    normal=nodes.new('ShaderNodeTexImage');normal.image=bpy.data.images.load(str(A.TEXTURES/'foliage/leaves_nor_gl.jpg'),check_existing=True);normal.image.colorspace_settings.name='Non-Color';nm=nodes.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.4;links.new(normal.outputs['Color'],nm.inputs['Color']);links.new(nm.outputs[0],bs.inputs['Normal'])
    # Normalize photographic albedo exposure before tinting. Multiplying the
    # original dark grass photograph by a green factor produced muddy brown
    # fields; this material bake preserves photo detail with a growing crop hue.
    import numpy as np
    raw=bpy.data.images.load(str(A.TEXTURES/'grass-diff.jpg'),check_existing=True);w,h=raw.size;px=np.empty(w*h*4,dtype=np.float32);raw.pixels.foreach_get(px);px=px.reshape(h,w,4)
    gray=px[:,:,:3].mean(axis=2);normalized=np.clip(.76+(gray-gray.mean())*.70,.42,.97)
    pixels=np.ones_like(px);pixels[:,:,:3]=normalized[:,:,None]
    image=bpy.data.images.new('V06 normalized photographic crop albedo',width=w,height=h,alpha=False);image.pixels.foreach_set(pixels.ravel());image.filepath_raw=str(A.SOURCE_OUT/'textures/v06-crop-photo.png');image.file_format='PNG';image.save();image.pack()
    for key in [*[f'crop{i}' for i in range(6)],*[f'leaf{i}' for i in range(5)],'meadow','understory']:
        for node in M[key].node_tree.nodes:
            if node.type=='TEX_IMAGE' and node.image and '-diff' in node.image.name:node.image=image
    for key in [f'wall{i}' for i in range(4)]:
        bs=M[key].node_tree.nodes.get('Principled BSDF')
        for link in list(bs.inputs['Base Color'].links):M[key].node_tree.links.remove(link)
    size=512;yy,xx=np.mgrid[0:size,0:size];tilex=(xx+(yy//43%2)*32)%64;tileY=yy%43
    noise=np.random.default_rng(P['seed']).normal(0,.035,(size,size));shade=.75+.18*np.sin(tilex/64*np.pi)+noise
    shade=np.where((tilex<3)|(tileY<4),.34,shade);rgba=np.ones((size,size,4),dtype=np.float32);rgba[:,:,:3]=np.clip(shade[:,:,None],.25,1)
    tile=bpy.data.images.new('V06 replaceable clay tile and sheet roof detail',width=size,height=size,alpha=False);tile.pixels.foreach_set(rgba.ravel());tile.filepath_raw=str(A.SOURCE_OUT/'textures/v06-roof-tiles.png');tile.file_format='PNG';tile.save();tile.pack()
    for key in ('roof_gray','roof_red','roof_blue','roof_brown'):
        mat=M[key];nodes=mat.node_tree.nodes;links=mat.node_tree.links;bs=nodes.get('Principled BSDF');tex=nodes.new('ShaderNodeTexImage');tex.image=tile;tint=nodes.new('ShaderNodeMix');tint.data_type='RGBA';tint.blend_type='MULTIPLY';tint.inputs[0].default_value=1;tint.inputs[7].default_value=bs.inputs['Base Color'].default_value;links.new(tex.outputs['Color'],tint.inputs[6]);links.new(tint.outputs[2],bs.inputs['Base Color'])

def roof_basis(poly):
    pp=list(poly.minimum_rotated_rectangle.exterior.coords)[:4]
    edges=[(Vector(pp[(i+1)%4])-Vector(pp[i])).length for i in range(4)]
    i=max(range(4),key=lambda j:edges[j]);a=Vector(pp[i]);b=Vector(pp[(i+1)%4]);u=(b-a).normalized();v=Vector((-u.y,u.x));c=poly.centroid
    return c.x,c.y,edges[i],edges[(i+1)%4],u,v

def building(row,poly,rng):
    name=row['id'];cx,cy,w,d,u,v=roof_basis(poly)
    h=rng.uniform(*P['buildings']['height_range']);rise=rng.uniform(*P['buildings']['roof_rise_range']);floor_height=P['buildings']['floor_height'];floors=max(1,round(h/floor_height));h=floors*floor_height
    roofkind=row.get('roof_type') or rng.choices(['gable','hip','flat'],[.68,.22,.1])[0]
    roofcolor=row.get('observed_roof_color','gray');roofmat=M.get('roof_'+roofcolor,M['roof_gray']);wall=M['wall'+str(rng.randrange(4))]
    mesh=Mesh();pp=list(poly.exterior.coords)[:-1]
    for a,b in zip(pp,pp[1:]+pp[:1]):mesh.face([(a[0],a[1],.12),(b[0],b[1],.12),(b[0],b[1],h),(a[0],a[1],h)],wall)
    def pos(x,y,z):return (cx+u.x*x+v.x*y,cy+u.y*x+v.y*y,z)
    e=P['buildings']['eaves'];ww=w/2+e;dd=d/2+e
    if roofkind=='flat':
        mesh.face([pos(-ww,-dd,h+.2),pos(ww,-dd,h+.2),pos(ww,dd,h+.2),pos(-ww,dd,h+.2)],roofmat)
        for sy in (-1,1):mesh.cube(pos(0,sy*dd,h+.4),(w+e*2,.18,.4),wall,math.atan2(u.y,u.x))
    else:
        inset=min(w*.2,d*.35) if roofkind=='hip' else 0
        mesh.face([pos(-ww,-dd,h),pos(ww,-dd,h),pos(ww-inset,0,h+rise),pos(-ww+inset,0,h+rise)],roofmat)
        mesh.face([pos(-ww+inset,0,h+rise),pos(ww-inset,0,h+rise),pos(ww,dd,h),pos(-ww,dd,h)],roofmat)
        for s in (-1,1):
            mesh.face([pos(s*ww,-dd,h),pos(s*(ww-inset),0,h+rise),pos(s*ww,dd,h)],roofmat if inset else wall)
        mesh.limb(pos(-ww+inset,0,h+rise+.02),pos(ww-inset,0,h+rise+.02),.13,.13,roofmat,5)
        # Visible roof seams/tile ridges, low cost and real geometry.
        count=max(2,min(24,round(w/1.5)))
        for j in range(1,count):
            xx=-ww+2*ww*j/count
            for s in (-1,1):mesh.limb(pos(xx,s*dd,h+.035),pos(xx,0,h+rise+.035),.025,.025,M['frame'],4)
    # Window assemblies follow actual wall edges rather than being painted on.
    for ai,(a,b) in enumerate(zip(pp,pp[1:]+pp[:1])):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length<3:continue
        ux,uy=dx/length,dy/length;nx,ny=uy,-ux;mid=Point((a[0]+b[0])/2+nx*.15,(a[1]+b[1])/2+ny*.15)
        if poly.contains(mid):nx,ny=-nx,-ny
        for floor in range(floors):
            count=max(1,int(length/P['buildings']['window_spacing']))
            for j in range(count):
                t=(j+.5)/count;x=a[0]+dx*t+nx*.06;y=a[1]+dy*t+ny*.06;z=1.75+floor*floor_height;hw=min(.62,length/count*.23);hh=.72
                if floor==0 and j==count//2 and ai==0:
                    z=1.2;hh=1.1;hw=.65;mat=M['door']
                else:mat=M['window']
                corners=[(x-ux*hw,y-uy*hw,z-hh),(x+ux*hw,y+uy*hw,z-hh),(x+ux*hw,y+uy*hw,z+hh),(x-ux*hw,y-uy*hw,z+hh)]
                mesh.face(corners,mat)
                for aa,bb in zip(corners,corners[1:]+corners[:1]):mesh.limb(aa,bb,.045,.045,M['frame'],4)
        if ai==0 and length>6:
            # A small shaded entrance canopy with two slender real columns.
            mx=(a[0]+b[0])/2;my=(a[1]+b[1])/2;hw=1.35;out=1.65
            canopy=[(mx-ux*hw,my-uy*hw,2.7),(mx+ux*hw,my+uy*hw,2.7),(mx+ux*hw+nx*out,my+uy*hw+ny*out,2.52),(mx-ux*hw+nx*out,my-uy*hw+ny*out,2.52)]
            mesh.face(canopy,M['roof_gray'])
            for sign in (-1,1):mesh.limb((mx+ux*hw*sign+nx*out,my+uy*hw*sign+ny*out,.12),(mx+ux*hw*sign+nx*out,my+uy*hw*sign+ny*out,2.52),.065,.065,M['frame'],5)
    obj=mesh.object(name+'__EditableBuilding','building with source roof outline; sample walls, height, windows and roof structure')
    uv=obj.data.uv_layers['UVMap']
    for face in obj.data.polygons:
        if 'roof' in obj.data.materials[face.material_index].name.lower():
            for li in face.loop_indices:
                p=obj.data.vertices[obj.data.loops[li].vertex_index].co;uv.data[li].uv=((p.x*u.x+p.y*u.y)/4,(p.x*v.x+p.y*v.y)/4)
    appearance(obj,row['source_status'],row);obj['height_display_m']=h;obj['roof_rise_display_m']=rise;obj['roof_type_sample']=roofkind;obj['layer']='building';obj['merge_static']=True
    INSTANCES.append({'id':name,'parent_spatial_id':row.get('parent_spatial_id'),'source_status':row['source_status'],'source_geometry':row['geometry'],'coordinate_system':'BLENDER_LOCAL_XY' if row['source_status']=='sample' else 'SATELLITE_SCREENSHOT_NATIVE_PIXELS','coordinate_units':'metres_illustrative' if row['source_status']=='sample' else 'native_image_pixels','height':h,'roof_rise':rise,'roof_type':roofkind,'source_record_id':row.get('source_record_id',name),'replaceable':True})
    BUILDING_SOLIDS.setdefault(row.get('parent_spatial_id'),[]).append(poly)
    return obj

def tree_archetype(variant):
    if variant in TREE_ARCHETYPES:return TREE_ARCHETYPES[variant]
    rng=seeded('linked-tree-archetype-'+str(variant));h=12;r=5;trunks=Mesh();foliage=Mesh();cards=Mesh()
    trunks.limb((0,0,-.12),(.3,-.2,h*.75),.30,.12,M['bark'],6)
    for j in range(P['forest']['crown_lobes']):
        ang=j*math.tau/P['forest']['crown_lobes']+rng.random();off=r*.46;cc=(math.cos(ang)*off,math.sin(ang)*off,h*.68+rng.uniform(-.7,.7));trunks.limb((0,0,h*.32),cc,.15,.055,M['bark'],5)
        rx=r*rng.uniform(.48,.68);ry=r*rng.uniform(.48,.68);rz=h*rng.uniform(.21,.29)
        foliage.ellipsoid(cc,(rx*.70,ry*.70,rz*.78),M['leaf'+str((variant+1)%5)],rng,n=7)
        for spray in range(24):
            aa=rng.random()*math.tau;zz=rng.uniform(-.7,.9);rr=math.sqrt(1-zz*zz);c=Vector((cc[0]+math.cos(aa)*rx*rr,cc[1]+math.sin(aa)*ry*rr,cc[2]+zz*rz));size=rng.uniform(1.4,2.45);u=Vector((math.cos(aa),math.sin(aa),rng.uniform(-.65,.65))).normalized()*size*.46;tilt=rng.uniform(.15,1.1);v=Vector((-math.sin(aa)*tilt,math.cos(aa)*tilt,rng.uniform(.25,.95))).normalized()*size
            cards.face([tuple(c-u-v),tuple(c+u-v),tuple(c+u+v),tuple(c-u+v)],M['leaf_card'])
    meshes={}
    saved=A.CURRENT_FEATURE;A.CURRENT_FEATURE=None
    for key,mesh,smooth in [('Trunk',trunks,True),('Crown',foliage,True),('Leaves',cards,False)]:
        obj=mesh.object('TREE_ARCHETYPE_'+str(variant)+'_'+key,'reusable sample tree geometry',smooth)
        if key=='Leaves':
            uv=obj.data.uv_layers['UVMap']
            for face in obj.data.polygons:
                for li,coord in zip(face.loop_indices,[(.015,.02),(.455,.02),(.455,.98),(.015,.98)]):uv.data[li].uv=coord
        obj.data.use_fake_user=True;meshes[key]=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
    A.CURRENT_FEATURE=saved;TREE_ARCHETYPES[variant]=meshes;return meshes

def forest(name,poly,spacing=None,ground=True,relief=True,clustered=False):
    if poly.is_empty:return
    rng=seeded(name);spacing=spacing or P['forest']['spacing'];trim=poly.buffer(-P['forest']['edge_setback'])
    if trim.is_empty:trim=poly
    def elevation(x,y):
        if not relief or not poly.contains(Point(x,y)):return 0
        edge=poly.boundary.distance(Point(x,y));return min(1,edge/28)**2*P['terrain']['woodland_relief_max']*(.60+.20*math.sin(x*.012+y*.015)+.20*math.sin(y*.019))
    if name.startswith('SAT-WOODLAND-'):HEIGHT_FUNCTIONS[name]=elevation
    if ground:
        ob=V.surface(name+'__WoodedRelief',poly,elevation,M['understory'],'sample gently rolling wooded terrain; boundaries constrained by source',True,step=14)
        appearance(ob);ob['layer']='vegetation'
    x0,y0,x1,y1=trim.bounds;count=0;y=y0
    parent_name='Vegetation_'+A.CURRENT_FEATURE['spatial_id'] if A.CURRENT_FEATURE else 'SampleBackgroundVegetation';parent=bpy.data.objects.get(parent_name)
    if parent is None:
        parent=bpy.data.objects.new(parent_name,None);A.ACTIVE_COLLECTION.objects.link(parent);A.tag(parent,'sample vegetation instances within owner source extent');parent['asset_id']='full';parent['layer']='vegetation';parent['category']='tree';parent['data_nature']='synthetic_appearance';parent['business_entity']=False
    while y<y1:
        x=x0+rng.uniform(0,spacing)
        while x<x1:
            xx=x+rng.uniform(-spacing*.34,spacing*.34);yy=y+rng.uniform(-spacing*.34,spacing*.34)
            cluster=math.sin(xx*.034+yy*.012)+math.sin(yy*.030)+math.sin(xx*.019-yy*.024)
            if trim.contains(Point(xx,yy)) and (not clustered or cluster>1.35) and rng.random()>.035:
                z=elevation(xx,yy);h=rng.uniform(*P['forest']['height_range']);r=rng.uniform(*P['forest']['crown_radius_range']);h=max(h,r*1.6)
                if not ground:h*=.68;r*=.66
                angle=rng.random()*math.tau;variant=rng.randrange(3)
                for part,data in tree_archetype(variant).items():
                    obj=bpy.data.objects.new(name+f'__Tree{count:05d}_{part}',data);A.ACTIVE_COLLECTION.objects.link(obj);A.tag(obj,'linked editable sample tree '+part);obj.parent=parent;obj.location=(xx,yy,z);obj.rotation_euler[2]=angle;obj.scale=(r/5,r/5,h/12);appearance(obj);obj['layer']='vegetation';obj['category']='tree';obj['tree_instance']=True;obj['tree_part']=part;obj['tree_archetype']=variant
                count+=1
            x+=spacing
        y+=spacing*.86
    STATS['sample_tree_count']=STATS.get('sample_tree_count',0)+count

def cultivated(name,poly,index=0,rows=True):
    if poly.is_empty:return
    rng=seeded(name);mat=M['crop'+str(index%6)];inner=poly.buffer(-1.3)
    V.surface(name+'__GrowingCropBed',poly,.05,mat,'source parcel with replaceable growing-season crop appearance',True,step=24,amplitude=.025)
    V.walls(name+'__CultivatedSoilBody',poly,.05,-1.2,A.MATERIALS['earth'],'soil volume below crop roots')
    V.band(name+'__EarthBermOuter',poly.buffer(1),poly,0,.30,M['meadow'],'sloped planted field margin')
    if not inner.is_empty:V.band(name+'__EarthBermInner',poly,inner,.30,.05,M['meadow'],'sloped inner field bund')
    if rows and not inner.is_empty:
        cx,cy,w,d,u,v=roof_basis(poly);theta=math.degrees(math.atan2(u.y,u.x));local=rotate(inner,-theta,origin=(cx,cy));x0,y0,x1,y1=local.bounds
        mesh=Mesh();spacing=P['crops']['row_spacing'];height=rng.uniform(*P['crops']['height_range']);y=y0+spacing*.5;co=math.cos(math.radians(theta));si=math.sin(math.radians(theta))
        def world(x,y,z):xx=x-cx;yy=y-cy;return (cx+xx*co-yy*si,cy+xx*si+yy*co,z)
        while y<y1:
            cutline=LineString([(x0-1,y),(x1+1,y)]).intersection(local)
            for line in ([cutline] if cutline.geom_type=='LineString' else getattr(cutline,'geoms',[])):
                if line.geom_type!='LineString' or line.length<4:continue
                aa,bb=list(line.coords)[0],list(line.coords)[-1];hw=P['crops']['row_width']/2
                mesh.face([world(aa[0],y-hw,.06),world(bb[0],y-hw,.06),world(bb[0],y,height),world(aa[0],y,height)],mat)
                mesh.face([world(aa[0],y,height),world(bb[0],y,height),world(bb[0],y+hw,.06),world(aa[0],y+hw,.06)],mat)
            y+=spacing
        ob=mesh.object(name+'__CropRows','real raised crop rows; sample crop state, spacing and height')
        if ob:ob['merge_static']=True;ob['sample_crop_height']=height
    if name.startswith('SAT-FIELD-'):
        mesh=Mesh();tris=list(constrained_delaunay_triangles(poly).geoms);count=min(2600,max(250,int(poly.area*.07)))
        for tri in rng.choices(tris,weights=[t.area for t in tris],k=count):
            a,b,c=list(tri.exterior.coords)[:3];u=math.sqrt(rng.random());v=rng.random();x=(1-u)*a[0]+u*(1-v)*b[0]+u*v*c[0];y=(1-u)*a[1]+u*(1-v)*b[1]+u*v*c[1];h=rng.uniform(*P['crops']['tuft_height_range'])
            for j in range(4):
                angle=j*math.pi/2+rng.random()*.5;dx=math.cos(angle)*h*.52;dy=math.sin(angle)*h*.52;w=.055
                mesh.face([(x-dy*w,y+dx*w,.08),(x+dy*w,y-dx*w,.08),(x+dx*.65+dy*w,y+dy*.65-dx*w,h*.70),(x+dx,y+dy,h*.82)],M['crop'+str((index+1)%6)])
        ob=mesh.object(name+'__SampleCropLeafTufts','editable sample crop leaves; generic appearance, no species or actual planting claim');ob['lod_detail']=True;ob['category']='grass';ob['layer']='vegetation'
        V.blades(name+'__FieldMarginGrass',poly.buffer(.8).difference(poly),.08,min(2400,int(poly.length*3)),True)

def sample_parcels(geom,name,theta=18):
    if geom.is_empty:return
    rng=seeded(name);center=geom.centroid;local=rotate(geom,-theta,origin=center);x0,y0,x1,y1=local.bounds;yy=y0;index=0
    while yy<y1:
        hh=rng.uniform(*P['crops']['sample_parcel_width_range']);xx=x0-rng.uniform(0,80)
        while xx<x1:
            ww=rng.uniform(*P['crops']['sample_parcel_length_range']);part=local.intersection(box(xx+1.3,yy+1.3,xx+ww-1.3,yy+hh-1.3))
            part=rotate(part,theta,origin=center)
            for pp in V.polygons(part):
                if pp.area>120:
                    cultivated(name+f'__SampleParcel{index:03d}',pp,index,rows=pp.area<25000);index+=1
            xx+=ww
        yy+=hh
    STATS['sample_infill_parcels']=STATS.get('sample_infill_parcels',0)+index

def road_surface(name,line,width,mat=None):
    top=line.buffer(width/2,join_style='round',quad_segs=4);outer=line.buffer(width/2+P['roads']['shoulder_width'],join_style='round',quad_segs=4)
    V.band(name+'__Shoulders',outer,top,0,.31,M['meadow'],'continuous sloping road shoulders')
    V.surface(name+'__Crown',top,.32,mat or A.MATERIALS['gravel'],'connected road pavement with thickness')
    V.walls(name+'__Foundation',outer,0,-.75,A.MATERIALS['earth'],'road foundation body')
    return outer

def water_body(name,poly,lake=False,context=False):
    width=6 if lake else 3.3;depth=P['water']['lake_depth' if lake else 'pond_depth'];level=P['water']['level'];inner=poly.buffer(-width)
    if inner.is_empty:inner=poly.buffer(-.4)
    V.band(name+'__ShoreSlope',poly,inner,0,-depth,A.MATERIALS['soil'],'source shoreline with sample excavated bank section')
    V.band(name+'__GreenUpperBank',poly,poly.buffer(-min(1.6,width*.32)),.025,-.65,M['meadow'],'irregular vegetated upper bank')
    V.surface(name+'__BasinBottom',inner,-depth-.05,A.MATERIALS['soil_dark'],'editable sample basin depth')
    V.walls(name+'__BasinSoilBody',poly,0,-depth-1,A.MATERIALS['earth'],'bank soil mass')
    surf=V.surface(name+'__Water',poly.buffer(-width*abs(level)/depth),level,M['regional_water'],'independent water surface below shoreline')
    if surf:
        surf['water_surface']=True;surf['water_kind']='lake' if lake else 'pond';surf['category']='water';surf['layer']='pond';surf['context_only']=context
    if not context:
        V.blades(name+'__BankGrass',poly.buffer(1).difference(poly),.06,min(3000,int(poly.length*4)),True)
        V.rocks(name+'__ShoreStones',poly,30 if lake else 12)
    return surf

def cover_region(row,poly,exclusions):
    A.CURRENT_FEATURE=None;poly=poly.difference(exclusions);kind=row.get('landcover_class','mixed');name=row['id'];params=row.get('sample_appearance',{})
    if poly.is_empty:return
    if row.get('context_only') and row.get('source_status')=='sample':
        # Outside sample masks end at screenshot/interpretation rectangles.
        # Rendering those edges or populating arbitrary rectangular blue ponds
        # created a visible patchwork. Continuous background already supplies
        # ground here; only source-observed external water/island is modeled.
        return
    before=set(A.ACTIVE_COLLECTION.objects)
    if kind=='woodland':forest(name,poly)
    elif kind=='cropland':sample_parcels(poly,name,theta=seeded(name).uniform(10,30))
    elif kind=='bare':
        V.surface(name+'__BareSoilMosaic',poly,.06,A.MATERIALS['soil'],'observed disturbed land class with sample soil appearance')
        margin=poly.difference(poly.buffer(-2.5));V.surface(name+'__GreenMargins',margin,.08,M['meadow'],'sample vegetation along disturbed soil edge')
    elif kind=='grass':
        V.surface(name+'__GrassMeadow',poly,.065,M['meadow'],'sample grass cover constrained by source broad land class')
        forest(name+'__SparseHedgerow',poly,spacing=16,ground=False,relief=False,clustered=True)
    else:
        # The source distinguishes mixed vegetation rather than a surveyed
        # cadastral partition. Keep a low meadow and sparse tree groups, then
        # use only the explicitly authorized fraction for replaceable gardens.
        sample_parcels(poly,name,theta=seeded(name).uniform(-12,25))
        fraction=params.get('canopy_cover_fraction',.12)
        if fraction>0:forest(name+'__MixedTrees',poly,spacing=max(10.5,4.2/math.sqrt(fraction)),ground=False,relief=False,clustered=True)
    for obj in set(A.ACTIVE_COLLECTION.objects)-before:
        appearance(obj,row['source_status'],row);obj['context_only']=row.get('context_only',False);obj['landcover_class']=kind

def snapped_roads(roads,water):
    result=[];limit=P['roads']['maximum_endpoint_snap'];count=0
    for i,line in enumerate(roads):
        others=unary_union(roads[:i]+roads[i+1:]);pp=list(line.coords)
        for index in (0,-1):
            p=Point(pp[index]);q=nearest_points(p,others)[1]
            if .05<p.distance(q)<=limit:
                segment=LineString([p,q])
                if not segment.intersects(water):pp[index]=(q.x,q.y);count+=1
        result.append(LineString(pp))
    STATS['road_endpoint_snaps_within_parameter']=count
    return result

def village(sid,poly,rows,exclusions):
    owner(sid);rng=seeded(sid);roofrows=[r for r in rows if r['kind']=='roof'];roads=[r for r in rows if r['kind']=='road'];infill=next((r for r in rows if r['kind']=='building_infill'),None)
    V.surface(sid+'__VillageGround',poly,.035,M['meadow'],'source corrected village extent with sample garden ground')
    lane_geoms=[]
    for row in roads:
        ln=geom(row);lane_geoms.append(road_surface(row['id'],ln,row.get('appearance_width_px',2.5)*1952/2940*300/101,M['asphalt']))
    roofpolys=[]
    for row in roofrows:
        pp=geom(row);building(row,pp,rng);roofpolys.append(pp)
        yard=pp.buffer(P['buildings']['courtyard_buffer']).difference(pp)
        V.surface(row['id']+'__Courtyard',yard,.11,M['yard'],'sample courtyard around observed roof outline')
    avoidance=unary_union([*roofpolys,*lane_geoms,*[geom(r) for r in rows if r['kind']=='avoidance'],exclusions])
    free=poly.buffer(-3.5).difference(avoidance.buffer(2.2));samplecount=0
    if infill and not free.is_empty:
        target=max(0,round(poly.area/(300/101*1952/2940)**2/1000*infill['desired_density']['value']*P['buildings']['sample_density_multiplier']))
        x0,y0,x1,y1=free.bounds;params=infill['sample_parameters'];angle=-infill['street_orientation_deg'];occupied=avoidance
        for attempt in range(target*80):
            if samplecount>=target:break
            x=rng.uniform(x0,x1);y=rng.uniform(y0,y1);w=rng.uniform(*params['footprint_width_px'])*1.972;d=rng.uniform(*params['footprint_depth_px'])*1.972
            pp=rotate(box(x-w/2,y-d/2,x+w/2,y+d/2),angle,origin=(x,y))
            if not free.contains(pp) or occupied.intersects(pp.buffer(2.8)):continue
            row={'id':sid+f'__SAMPLE-BUILDING-{samplecount:03d}','parent_spatial_id':sid,'source_status':'sample','geometry':{'type':'Polygon','coordinates':[list(pp.exterior.coords)]},'source_record_id':infill['id'],'roof_type':rng.choice(['gable','gable','hip','flat']),'observed_roof_color':rng.choice(['gray','gray','red','brown'])}
            building(row,pp,rng);V.surface(row['id']+'__Yard',pp.buffer(2.0).difference(pp),.1,M['yard'],'sample editable private courtyard');occupied=unary_union([occupied,pp.buffer(2.8)]);samplecount+=1
    # Small grouped garden trees within unused observed village space.
    greens=poly.buffer(-3).difference(occupied.buffer(4) if infill and not free.is_empty else avoidance.buffer(4))
    for j,pp in enumerate(V.polygons(greens)):
        if pp.area>150:forest(sid+f'__GardenTrees{j}',pp,spacing=19,ground=False,relief=False)
    STATS.setdefault('villages',[]).append({'spatial_id':sid,'observed_roof_candidates':len(roofrows),'sample_buildings':samplecount,'lanes':len(roads)})

def equipment(layout,source):
    updates=[]
    for row in layout['devices']:
        owner(row['parent_spatial_id']);base=A.CURRENT_FEATURE['center'];offset=row['offset'];x=base[0]+offset[0];y=-(base[2]+offset[2]);z=base[1]+offset[1];typ=row['device_type'];m=Mesh();reason=[]
        sid=row['parent_spatial_id'];poly=source.get(sid)
        if typ in ('water_sensor','aerator'):
            if A.CURRENT_FEATURE['kind']=='channel':
                q=poly.interpolate(poly.project(Point(x,y)));x,y=q.x,q.y;z=-1.4+.18;reason.append('small channel buoy at actual modeled drainage centerline and shallow water level')
            else:
                z=P['water']['level'];safe=poly.buffer(-5)
                if not safe.is_empty and not safe.contains(Point(x,y)):
                    q=nearest_points(Point(x,y),safe)[1];c=safe.representative_point();d=q.distance(c) or 1;x=q.x+(c.x-q.x)/d;y=q.y+(c.y-q.y)/d;reason.append('keep floating sample within revised water outline')
        else:
            z=HEIGHT_FUNCTIONS.get(sid,lambda x,y:0)(x,y)
            buildings=unary_union(BUILDING_SOLIDS.get(sid,[]))
            if not buildings.is_empty and buildings.buffer(1.2).contains(Point(x,y)):
                found=False
                for radius in (5,10,15,22,30,40):
                    for j in range(12):
                        xx=x+radius*math.cos(j*math.tau/12);yy=y+radius*math.sin(j*math.tau/12)
                        if poly.contains(Point(xx,yy)) and not buildings.buffer(1.2).contains(Point(xx,yy)):
                            x,y=xx,yy;found=True;reason.append('sample equipment moved clear of modeled wall footprint');break
                    if found:break
        updates.append({'key':row['key'],'parent_spatial_id':sid,'parent_center':base,'offset':[round(x-base[0],5),round(z-base[1],5),round(-y-base[2],5)],'base_position':[round(x,5),round(z,5),round(-y,5)],'reason':reason or ['ground or water level sampled from same model profile']})
        if typ in ('camera_pole','soil_sensor'):
            h=6 if typ=='camera_pole' else 2.3;m.cube((x,y,z+.12),(.8,.8,.24),A.MATERIALS['concrete']);m.limb((x,y,z+.24),(x,y,z+h),.085,.065,M['metal'],8)
            m.cube((x+.23,y,z+h*.62),(.38,.25,.48),M['metal']);m.cube((x,y-.32,z+h-.45),(1.1,.75,.06),M['panel'])
            if typ=='camera_pole':m.limb((x,y,z+h),(x+1,y,z+h),.045,.045,M['metal']);m.cube((x+1,y,z+h-.12),(.42,.25,.25),M['window'])
            else:
                for dx in (-.26,.26):m.limb((x+dx,y+.35,z+.02),(x+dx,y+.35,z+.55),.025,.025,M['metal'],5)
        elif typ=='water_sensor':
            buoy_radius=.28 if A.CURRENT_FEATURE['kind']=='channel' else .72
            m.ellipsoid((x,y,z+.16),(buoy_radius,buoy_radius,.23),M['orange'],seeded(row['key']),10);m.limb((x,y,z+.2),(x,y,z+1.7),.045,.035,M['metal'],8);m.cube((x,y,z+1.25),(.45,.35,.16),M['blue']);m.cube((x,y,z+1.55),(.62,.46,.05),M['panel']);m.limb((x,y,z),(x,y,z-.65),.025,.025,M['metal'],5)
        elif typ=='aerator':
            for dx in (-1.1,1.1):m.cube((x+dx,y,z+.12),(.5,2.6,.38),M['blue'])
            m.cube((x,y,z+.5),(2.4,1.1,.15),M['metal']);m.cube((x,y,z+.86),(.6,.7,.6),M['blue']);m.limb((x-1.5,y,z+.53),(x+1.5,y,z+.53),.07,.07,M['metal'],8)
            for dx in (-1.55,1.55):
                for j in range(6):
                    ang=j*math.tau/6;m.cube((x+dx,y+math.sin(ang)*.48,z+.53+math.cos(ang)*.48),(.3,.34,.14),M['blue'])
        obj=m.object('DEMO_DEVICE__'+row['key'],'replaceable synthetic '+typ+' apparatus');obj['scene_device_key']=row['key'];obj['scene_scenario_id']=layout['scenario_id'];obj['data_nature']='synthetic';obj['device_type']=typ;obj['base_position_three']=[x,z,-y];obj['layer']='facility';obj['merge_static']=False
    STATS['sample_device_count']=len(layout['devices'])
    (A.ROOT/'data/model/device-grounding-updates.json').write_text(json.dumps({'coordinate_system':'THREE_Y_UP','center_y':3,'model_revision':'v06','devices':updates},ensure_ascii=False,indent=2),encoding='utf8')

def context_ponds(rows,excluded):
    result=[]
    for row in rows:
        fraction=row.get('sample_appearance',{}).get('water_fraction',0)
        if not row.get('context_only') or fraction<=0:continue
        poly=geom(row).difference(excluded);rng=seeded(row['id']+'ponds');x0,y0,x1,y1=poly.bounds;target=poly.area*fraction;area=0;occupied=Polygon()
        for attempt in range(300):
            if area>=target:break
            x=rng.uniform(x0,x1);y=rng.uniform(y0,y1);w=rng.uniform(45,105);d=rng.uniform(40,90);pp=rotate(box(x-w/2,y-d/2,x+w/2,y+d/2),rng.uniform(-15,25),origin=(x,y)).buffer(-4).buffer(4)
            if poly.contains(pp) and not occupied.intersects(pp.buffer(8)):
                result.append((row['id']+f'__SampleOutsidePond{len(result):03d}',pp));area+=pp.area;occupied=unary_union([occupied,pp.buffer(8)])
    STATS['sample_context_ponds']=len(result)
    return result

def build(api):
    global A,P,M,INSTANCES,STATS,HEIGHT_FUNCTIONS,BUILDING_SOLIDS,TREE_ARCHETYPES
    A=api;V.API=api;P=json.loads((A.ROOT/'data/model/full-region-parameters.json').read_text(encoding='utf8'));M={};INSTANCES=[];STATS={};HEIGHT_FUNCTIONS={};BUILDING_SOLIDS={};TREE_ARCHETYPES={}
    A.CURRENT_ASSET='full';A.CURRENT_SCALE=A.SOURCE['meters_per_pixel'];A.CURRENT_ORIGIN=A.SOURCE['origin'];A.CURRENT_FEATURE=None
    col=A.new_collection('FULL V06 complete redline landscape');col['asset_id']='full';A.ACTIVE_COLLECTION=col;palette()
    data=json.loads((A.ROOT/'data/spatial/full-region-enrichment.json').read_text(encoding='utf8'));rows=data['records'];corrected={r['parent_spatial_id']:geom(r) for r in rows if r['kind']=='settlement'}
    M['regional_water']=A.MATERIALS['water'].copy();M['regional_water'].name='V06 natural green freshwater photographic ripples';bs=M['regional_water'].node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.025,.085,.065,1);bs.inputs['Roughness'].default_value=.18;M['regional_water']['uv_scene_units']=5
    border=Polygon([A.xy(p) for p in A.BOUNDARY]).buffer(0);source={f['spatial_id']:Polygon([A.xy(p) for p in f['points']]).buffer(0) for f in A.FEATURES}
    original=dict(source);source.update(corrected);water_overrides={r['parent_spatial_id']:geom(r) for r in rows if r.get('status')=='image_refined_water_outline'};source.update(water_overrides)
    water=[source[f['spatial_id']] for f in A.FEATURES if f['kind'] in ('pond','lake')];channels=[LineString([A.xy(p) for p in A.pts(text)]).buffer(width/2+.3) for _,text,width in A.CHANNELS];V.CUTS=unary_union(water+channels)
    original_roads=[LineString([A.xy(p) for p in A.pts(text)]) for _,text,width in A.ROADS];roadlines=snapped_roads(original_roads,unary_union(water));extra_roads=[r for r in rows if r['kind']=='road' and r.get('status')=='visible_connecting_lane'];roadcuts=unary_union([line.buffer(width/2+1.3) for line,(_,_,width) in zip(roadlines,A.ROADS)]+[geom(r).buffer(r.get('appearance_width_px',2.5)*1.972/2+1.3) for r in extra_roads])
    claimed=unary_union(list(source.values())+[V.CUTS,roadcuts]);remaining=border.difference(claimed)
    A.CURRENT_FEATURE=None
    V.surface('FullAgriculturalContextGround',border.difference(V.CUTS),0,M['meadow'],'continuous context soil supporting all sample subdivisions')
    V.walls('FullRedlineSoilSection',border,0,-6,A.MATERIALS['earth'],'continuous terrain volume')
    context_water=[r for r in rows if r.get('context_only') and r['kind'] in ('water','lake','pond')];context_holes=unary_union([geom(r) for r in context_water]);sample_water=[];STATS['sample_context_ponds']=0;STATS['context_mosaic_policy']='Unverified external pond/parcel infill disabled after visual review; continuous meadow and source-observed lake/river/island only';outside=border.buffer(P['terrain']['context_buffer']).difference(border).difference(V.CUTS).difference(context_holes)
    V.surface('FullExteriorContext',outside,0,M['meadow'],'non-business surrounding context for redline edge continuity')
    covers=[r for r in rows if r['kind']=='landcover'];coverage=[]
    for row in covers:
        pp=geom(row);coverage.append(pp if not row.get('context_only') else Polygon());cover_region(row,pp,unary_union([V.CUTS,roadcuts,*corrected.values(),context_holes]))
    uncovered=remaining.difference(unary_union(coverage))
    if uncovered.area>1:sample_parcels(uncovered,'BACKGROUND-UNCLASSIFIED-SAMPLE',theta=18)
    for row in context_water:
        for j,p in enumerate(V.polygons(geom(row))):water_body(row['id']+str(j),p,True,context=True)
    for name,p in sample_water:water_body(name,p,False,context=True)
    for i,f in enumerate(A.FEATURES):
        points=A.record(f);sid=f['spatial_id'];p=source[sid];kind=f['kind'];A.CURRENT_FEATURE['appearance_revision']='v06';A.CURRENT_FEATURE['appearance_data_nature']='observed_outline_with_replaceable_sample_details'
        if sid in corrected or sid in water_overrides:
            record=A.CURRENT_FEATURE;record['source_center']=record['center'];record['source_bounds']=record.get('bounds');record['source_model_area_m2']=record.get('model_area_m2');record['center']=[round(p.centroid.x,3),3,round(-p.centroid.y,3)];record['model_area_m2']=round(p.area,2);record['bounds']={'min':[p.bounds[0],-6,-p.bounds[3]],'max':[p.bounds[2],24,-p.bounds[1]]}
            A.CURRENT_FEATURE['appearance_geometry_override']={'source':'data/spatial/full-region-enrichment.json','record_id':next(r['id'] for r in rows if r.get('parent_spatial_id')==sid and r['kind'] in ('settlement','pond','lake')),'supersedes_source_outline_for_appearance':True,'original_geometry_retained':True}
        if kind=='field':cultivated(sid,V.cut(p).difference(unary_union(list(corrected.values())+[roadcuts])),i)
        elif kind in ('pond','lake'):
            water_body(sid,p,kind=='lake')
        elif kind=='woodland':forest(sid,V.cut(p).difference(unary_union(list(corrected.values())+[roadcuts])))
        elif kind=='settlement':village(sid,p,[r for r in rows if r.get('parent_spatial_id')==sid],V.CUTS)
        else:
            cultivated(sid,V.cut(p).difference(roadcuts),i,rows=False)
    # Original road/channel resource records remain stable. Joined buffer-based
    # road surfaces replace folded swept strips and support intersections.
    for i,(name,text,width) in enumerate(A.ROADS):
        f={'spatial_id':f'SAT-ROAD-{i+1:03d}','name':name+'（概略）','kind':'road','region':'全域','points':A.pts(text),'assumed_width_m':width};points=A.record(f,line=True,width=width);road_surface(f['spatial_id'],roadlines[i],width);source[f['spatial_id']]=roadlines[i].buffer(width/2)
    for row in extra_roads:
        owner(row.get('parent_spatial_id'));road_surface(row['id'],geom(row),row.get('appearance_width_px',2.5)*1.972)
    for i,(name,text,width) in enumerate(A.CHANNELS):
        f={'spatial_id':f'SAT-CHANNEL-{i+1:03d}','name':name+'（判读待核）','kind':'channel','region':'全域','points':A.pts(text),'assumed_width_m':width};points=A.record(f,line=True,width=width);V.channel(f['spatial_id'],points,width,1,1.4);source[f['spatial_id']]=LineString(V.rounded_path(points))
    equipment(json.loads((A.ROOT/'data/demo/full-area-device-layout.json').read_text(encoding='utf8')),source)
    A.CURRENT_FEATURE=None
    red=A.section_strip('RedlineBoundary',[A.xy(p) for p in A.BOUNDARY],[(-.75,.45),(.75,.45)],A.MATERIALS['redline'],'source redline boundary, not a surveyed cadastral wall',True);red['layer']='boundary';red['asset_id']='full'
    ref=A.new_collection('REFERENCE ONLY source satellite');bpy.context.scene.collection.children.unlink(ref);col.children.link(ref);A.ACTIVE_COLLECTION=ref;A.satellite_reference();ref.hide_render=True;ref.hide_viewport=True;ref['reference_only']=True;A.ACTIVE_COLLECTION=col
    asset=next(a for a in A.MANIFEST['assets'] if a['id']=='full');b=border.bounds;cx=(b[0]+b[2])/2;cy=(b[1]+b[3])/2;span=max(b[2]-b[0],b[3]-b[1])
    asset['bounds']={'min':[b[0],-6,-b[3]],'max':[b[2],30,-b[1]]};overview={'position':[460,2472.5,1760],'target':[0,0,154.455]}
    asset['camera_views']={'overview':overview,'focus':overview,'field':V.camera_view(list(source['SAT-FIELD-001'].exterior.coords)[:-1],'field'),'pond':V.camera_view(list(source['SAT-POND-001'].exterior.coords)[:-1],'pond'),'channel':V.camera_view([A.xy(p) for p in A.pts(A.CHANNELS[4][1])],'channel')}
    asset['village_views']={}
    for sid,p in corrected.items():
        c=p.centroid;bb=p.bounds;ss=max(bb[2]-bb[0],bb[3]-bb[1]);asset['village_views'][sid]={'position':[c.x+ss*.52,ss*.62,-c.y+ss*.78],'target':[c.x,2,-c.y]}
    asset['reference_exported']=False;asset['model_representation']='volumetric_full_region_with_replaceable_sample_completion';A.MANIFEST['default_asset_id']='full';A.MANIFEST['model_revision']='v06'
    A.MANIFEST['sample_data_policy']={'authorization':'Missing information may use sample data first and be replaced later.','observed':'Satellite outlines and roof-like surfaces remain approximate image interpretations.','synthetic':'Heights, roof structures, walls/windows, crops, individual trees, equipment and terrain relief are replaceable sample appearance.','new_real_business_entities':0}
    for layer in A.MANIFEST.get('layers',[]):
        if layer.get('id')=='satellite':layer['visible']=False;layer['exported']=False;layer['reference_only']=True
    A.MANIFEST['boundary']={'points':A.BOUNDARY,'center':[0,0,0],'model_area_m2':round(border.area,2),'precision':'screenshot_redline_approximate'}
    A.MANIFEST['appearance_sources']=[{'file':'data/spatial/full-region-enrichment.json','sha256':hashlib.sha256((A.ROOT/'data/spatial/full-region-enrichment.json').read_bytes()).hexdigest(),'revision':data['revision'],'business_entities_added':0},{'file':'data/model/full-region-parameters.json','data_nature':'synthetic_appearance'},{'file':'data/demo/full-area-device-layout.json','data_nature':'synthetic'}]
    STATS['observed_roof_candidates']=sum(r['kind']=='roof' for r in rows);STATS['redline_area']=border.area;STATS['sample_completion_area']=remaining.area;STATS['building_instances']=len(INSTANCES)
    A.MANIFEST['full_region_appearance_statistics']=STATS
    (A.ROOT/'data/model/full-region-generated-instances.json').write_text(json.dumps({'schema_version':'full-region-generated/1','data_nature':'appearance_only','replaceable':True,'parameters_file':'data/model/full-region-parameters.json','statistics':STATS,'buildings':INSTANCES},ensure_ascii=False,indent=2),encoding='utf8')
    print('FULL_REGION_BUILD '+json.dumps(STATS))
    return col

def preview():
    import blender_build as api
    api.reset_scene();V.materials(api);V.install(api);col=build(api);api.lights_and_camera();V.lighting(bpy.context.scene)
    scene=bpy.context.scene;asset=api.MANIFEST['assets'][0]
    for name,view in [('v06-full-preview',asset['camera_views']['overview']),('v06-village-preview',asset['village_views']['SAT-SETTLEMENT-007']),('v06-field-preview',asset['camera_views']['field'])]:
        V.set_camera(scene,view);scene.render.filepath=str(api.SOURCE_OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(api.SOURCE_OUT/'v06-full-preview.blend'))

def export_full(collection,filename,lod=False):
    """Retain editable source objects; export temporary static batches and GPU
    instances. Every sample device keeps a separate node and stable device key.
    """
    temp=A.new_collection('TEMP_EXPORT_FULL');groups={};selected=[];tree_data={};swapped=[];made=[]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in list(collection.objects):
        if obj.type=='EMPTY':selected.append(obj);continue
        if obj.type!='MESH' or (lod and obj.get('lod_detail')):continue
        if obj.get('tree_instance'):
            if lod:
                original=obj.data;key=original.name
                if key not in tree_data:
                    data=original.copy()
                    if obj.get('tree_part')=='Leaves':
                        bm=bmesh.new();bm.from_mesh(data);bm.faces.ensure_lookup_table();bmesh.ops.delete(bm,geom=[f for i,f in enumerate(bm.faces) if i%2],context='FACES');bm.to_mesh(data);bm.free()
                    tree_data[key]=data
                swapped.append((obj,original));obj.data=tree_data[key]
            selected.append(obj);continue
        if obj.get('scene_device_key') or obj.name=='RedlineBoundary':selected.append(obj);continue
        key=(obj.get('spatial_id','background'),obj.get('layer','terrain'),bool(obj.get('water_surface')),obj.get('water_kind',''),bool(obj.get('context_only')))
        groups.setdefault(key,[]).append(obj)
    print('EXPORT_BUFFER_MERGE_START',filename,len(groups),flush=True)
    for key,objects in groups.items():
        if not P['performance']['merge_static_by_owner_and_material_on_export']:
            selected.extend(objects);continue
        verts=[];faces=[];indices=[];smooth=[];materials=[];uvnames=sorted({u.name for o in objects for u in o.data.uv_layers});uvs={name:[] for name in uvnames}
        for obj in objects:
            data=obj.data;offset=len(verts);matrix=obj.matrix_world;verts.extend(tuple(matrix@v.co) for v in data.vertices);mapping=[]
            for mat in data.materials:
                if mat not in materials:materials.append(mat)
                mapping.append(materials.index(mat))
            for face in data.polygons:
                mat=data.materials[face.material_index]
                if lod and obj.name.endswith('__EditableBuilding') and 'window and eave frames' in mat.name:continue
                faces.append(tuple(offset+i for i in face.vertices));indices.append(mapping[face.material_index]);smooth.append(face.use_smooth)
                for name in uvnames:
                    layer=data.uv_layers.get(name)
                    for li in face.loop_indices:uvs[name].extend(tuple(layer.data[li].uv) if layer else (0,0))
        if not faces:continue
        name='FULL_BATCH__'+'_'.join(str(x) for x in key);data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces)
        for mat in materials:data.materials.append(mat)
        data.polygons.foreach_set('material_index',indices);data.polygons.foreach_set('use_smooth',smooth)
        for uvname,coords in uvs.items():data.uv_layers.new(name=uvname).data.foreach_set('uv',coords)
        data.validate(clean_customdata=False);data.update();merged=bpy.data.objects.new(name,data);temp.objects.link(merged);merged.parent=objects[0].parent
        for prop,value in objects[0].items():merged[prop]=value
        merged['model_role']='static batch of editable source components; independent meshes retained in Blend';selected.append(merged);made.append(merged)
    if lod:
        material_cache={};seen_data=set()
        for obj in selected:
            if obj.type!='MESH':continue
            if obj not in made and not obj.get('tree_instance'):continue
            if obj.data.name in seen_data:continue
            seen_data.add(obj.data.name)
            for slot in obj.material_slots:
                original=slot.material
                if original.name not in material_cache:
                    mat=original.copy();mat.name=original.name+' LOD';bs=mat.node_tree.nodes.get('Principled BSDF')
                    if bs:
                        for socket in ('Normal','Roughness'):
                            for link in list(bs.inputs[socket].links):mat.node_tree.links.remove(link)
                    material_cache[original.name]=mat
                slot.material=material_cache[original.name]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected:obj.hide_set(False);obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(A.OUT/filename),export_format='GLB',use_selection=True,use_active_scene=True,export_extras=True,export_yup=True,export_apply=True,export_gpu_instances=True,export_animations=False,export_cameras=False,export_lights=False,export_materials='EXPORT')
    for obj,data in swapped:obj.data=data
    for obj in list(temp.objects):bpy.data.objects.remove(obj,do_unlink=True)
    bpy.data.collections.remove(temp)
    if lod:
        asset=next(a for a in A.MANIFEST['assets'] if a['id']=='full');asset['lod_url']='/models/full-area-lod.glb';asset['lod_policy']='Same source owners, all building bodies, equipment and GPU-instanced tree crowns; leaf-card density halved, fine window frames and grass microdetail omitted.'

if __name__=='__main__':preview()
