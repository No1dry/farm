"""Volumetric landscape construction; no source image is a model material.

XY follows the audited source. Z is an explicitly illustrative section profile.
Photographs inform material and construction type, never precise placement.
"""
import bpy
import math
import random
from mathutils import Vector
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union

API=None
CUTS=None

def polygons(geom):
    if geom.is_empty: return []
    return [geom] if geom.geom_type=='Polygon' else [p for p in getattr(geom,'geoms',[]) if p.geom_type=='Polygon']

def surface(name,geom,z,material,role,smooth=False,step=None,amplitude=0):
    """Constrained triangulation retains concavities/holes and subdivides relief."""
    verts=[]; faces=[]; ids={}
    if step:
        minx,miny,maxx,maxy=geom.bounds
        chunks=[]
        for i in range(math.ceil((maxx-minx)/step)):
            for j in range(math.ceil((maxy-miny)/step)):
                p=geom.intersection(box(minx+i*step,miny+j*step,minx+(i+1)*step,miny+(j+1)*step))
                chunks.extend(polygons(p))
    else: chunks=polygons(geom)
    for chunk in chunks:
        for tri in constrained_delaunay_triangles(chunk).geoms:
            pp=list(tri.exterior.coords)[:3]
            if API.area2(pp)<0: pp.reverse()
            face=[]
            for x,y in pp:
                key=(round(x,7),round(y,7))
                if key not in ids:
                    h=z(x,y) if callable(z) else z
                    if amplitude: h+=amplitude*(math.sin(x*1.61+y*.73)*.55+math.sin(y*2.71-x*.28)*.3)
                    ids[key]=len(verts); verts.append((x,y,h))
                face.append(ids[key])
            faces.append(face)
    if not faces: return None
    obj=API.mesh(name,verts,faces,material,role)
    if name.endswith(('__EarthBottom','__BasinUnderside','__Bottom')):
        for p in obj.data.polygons:p.flip()
    if smooth:
        for p in obj.data.polygons:p.use_smooth=True
    return obj

def walls(name,geom,top,bottom,material,role):
    verts=[];faces=[]
    for poly in polygons(geom):
        for ring in [poly.exterior,*poly.interiors]:
            pp=list(ring.coords)
            for p,q in zip(pp,pp[1:]):
                k=len(verts);verts.extend([(p[0],p[1],top),(q[0],q[1],top),(q[0],q[1],bottom),(p[0],p[1],bottom)])
                faces.append((k,k+1,k+2,k+3))
    if faces:return API.mesh(name,verts,faces,material,role)

def band(name,outer,inner,zouter,zinner,mat,role):
    geom=outer.difference(inner)
    def elevation(x,y):
        p=Point(x,y);a=outer.boundary.distance(p);b=inner.boundary.distance(p)
        return zouter+(zinner-zouter)*a/max(a+b,1e-8)
    return surface(name,geom,elevation,mat,role,True)

def cut(geom):
    return geom.difference(CUTS) if CUTS is not None and not CUTS.is_empty else geom

def seeded(name):return random.Random(sum((i+1)*ord(c) for i,c in enumerate(name))+7919)

def blades(name,geom,z,count,grass=False):
    """Sparse nonuniform real crossed blades/stubble; no asserted crop or density."""
    if geom.is_empty:return
    rng=seeded(name);verts=[];faces=[]
    triangles=list(constrained_delaunay_triangles(geom).geoms)
    if not triangles:return
    weights=[t.area for t in triangles]
    for tri in rng.choices(triangles,weights=weights,k=count*2):
        a,b,c=list(tri.exterior.coords)[:3];u=math.sqrt(rng.random());v=rng.random()
        x=(1-u)*a[0]+u*(1-v)*b[0]+u*v*c[0];y=(1-u)*a[1]+u*(1-v)*b[1]+u*v*c[1]
        if grass and math.sin(x*.31+y*.18)+math.sin(y*.53)<-.25:continue
        h=rng.uniform(.18,.56) if grass else rng.uniform(.08,.26)
        w=.018 if grass else .014;a=rng.random()*math.tau
        for da in (0,math.pi/2):
            dx=math.cos(a+da)*w;dy=math.sin(a+da)*w;k=len(verts)
            verts.extend([(x-dx,y-dy,z),(x+dx,y+dy,z),(x+dx*.3+.06,y+dy*.3,z+h*.6),(x+.09,y,z+h)])
            faces.extend([(k,k+1,k+2),(k,k+2,k+3)])
        if len(faces)>=count*4:break
    if faces:
        obj=API.mesh(name,verts,faces,API.MATERIALS['stubble' if not grass else 'blade'],'appearance only; no crop classification')
        obj['lod_detail']=True;obj['category']='vegetation';obj['layer']='vegetation'

def field(name,points,height=.035,detail=False,index=0):
    poly=Polygon(points).buffer(0); clipped=cut(poly)
    obj=surface(name+'__CultivatedBed',clipped,height,API.MATERIALS['soil'],'cultivated bed with shallow soil microrelief',True,step=8 if detail else 22,amplitude=.025)
    walls(name+'__EarthSides',clipped,height,-1.6,API.MATERIALS['soil'],'field soil body thickness; not measured stratigraphy')
    surface(name+'__EarthBottom',clipped,-1.6,API.MATERIALS['earth'],'field body bottom')
    # Follow the exact source perimeter. Buffer bands provide proper constant
    # offsets instead of a radial shrink that distorts concave corners.
    crest=poly.buffer(.16,join_style='round');edge=poly.buffer(1.4,join_style='round');inside=poly.buffer(-1.35)
    if inside.is_empty:inside=poly.buffer(-.2)
    band(name+'__BermOuter',cut(edge),cut(crest),0,.26,API.MATERIALS['soil'],'sloped earth berm outer face')
    if not inside.is_empty:band(name+'__BermInner',cut(crest),cut(inside),.26,height,API.MATERIALS['soil'],'sloped earth berm inner face')
    grassband=cut(edge.difference(poly.buffer(.35)))
    blades(name+'__BankGrass',grassband,.12,min(350,int(poly.length*1.8)),True)
    if detail:blades(name+'__HarvestStubble',clipped,height+.01,min(4200,max(120,int(poly.area*.25))))
    # Low real soil ridges, rather than a stripe bitmap, make cultivated ground
    # readable in close views. They are appearance, not surveyed cultivation.
    if detail:
        x0,y0,x1,y1=clipped.bounds;verts=[];faces=[];spacing=1.25
        y=y0+.7
        while y<y1:
            segments=LineString([(x0-1,y),(x1+1,y)]).intersection(clipped.buffer(-1.4))
            for line in ([segments] if segments.geom_type=='LineString' else getattr(segments,'geoms',[])):
                if line.geom_type!='LineString' or line.length<.1:continue
                a,b=list(line.coords)[0],list(line.coords)[-1];k=len(verts)
                for p in (a,b):
                    for dy,dz in [(-.28,0),(0,.045),(.28,0)]:verts.append((p[0],p[1]+dy,height+dz+.006))
                faces.extend([(k,k+3,k+4,k+1),(k+1,k+4,k+5,k+2)])
            y+=spacing
        if faces:
            furrows=API.mesh(name+'__ShallowSoilFurrows',verts,faces,API.MATERIALS['soil'],'shallow real soil ridges; illustrative tillage appearance');furrows['lod_detail']=True
    return obj

def water(name,points,lake=False,detail=False):
    poly=Polygon(points).buffer(0);width=5.0 if lake else 3.3
    inner=poly.buffer(-width,join_style='round')
    if inner.is_empty:inner=poly.buffer(-min(width,.25*math.sqrt(poly.area)))
    if inner.is_empty:inner=poly.buffer(-.3)
    # Ground is cut at the exact source perimeter; the basin slopes down to a
    # separately editable bottom. Water is inside the bowl, below crest grade.
    band(name+'__ShoreSlope',poly,inner,0,-2.8,API.MATERIALS['soil'],'editable excavated shoreline slope')
    band(name+'__GrassBank',poly,poly.buffer(-min(1.2,width*.3)),.025,-.65,API.MATERIALS['grass'],'vegetated upper shoreline slope')
    surface(name+'__BasinBottom',inner,-2.85,API.MATERIALS['soil_dark'],'pond bottom; depth is a display parameter')
    surface(name+'__BasinUnderside',poly,-4.1,API.MATERIALS['earth'],'basin body underside')
    walls(name+'__BasinOuterBody',poly,0,-4.1,API.MATERIALS['earth'],'basin soil body')
    waterpoly=poly.buffer(-width*.29)
    obj=surface(name+'__Water',waterpoly,-.78,API.MATERIALS['water'],'water surface; measured level and depth unknown')
    obj['water_surface']=True;obj['category']='water';obj['water_kind']='lake' if lake else 'pond'
    if detail:
        blades(name+'__ShoreGrass',poly.buffer(1.2).difference(poly),.04,min(4200,int(poly.length*9)),True)
        rocks(name+'__BankStones',poly,25 if poly.area>3000 else 8)
    return obj

def road(name,points,width):
    API.section_strip(name+'__RoadBody',points,[(-width/2-1.05,-.15),(-width/2,.24),(0,.36),(width/2,.24),(width/2+1.05,-.15)],API.MATERIALS['soil'],'real crowned road and sloping shoulders')
    API.section_strip(name+'__Surface',points,[(-width/2,.26),(0,.38),(width/2,.26)],API.MATERIALS['gravel'],'compacted gravel crown')
    for side in (-1,1):
        API.section_strip(name+'__RoadSide'+str(side),points,[(side*(width/2+1.05),-.15),(side*(width/2+1.05),-.85)],API.MATERIALS['earth'],'road foundation side')
    API.section_strip(name+'__RoadBottom',points,[(-width/2-1.05,-.85),(width/2+1.05,-.85)],API.MATERIALS['earth'],'road foundation bottom')

def rounded_path(points,radius=.75):
    """Round only display corners; original source path remains in manifest."""
    if len(points)<3:return points
    result=[points[0]]
    for a,b,c in zip(points,points[1:],points[2:]):
        ab=math.dist(a,b);bc=math.dist(b,c);r=min(radius,ab*.24,bc*.24)
        if min(ab,bc)<1e-7:continue
        u=(b[0]+(a[0]-b[0])*r/ab,b[1]+(a[1]-b[1])*r/ab)
        v=(b[0]+(c[0]-b[0])*r/bc,b[1]+(c[1]-b[1])*r/bc)
        result.append(u)
        for i in range(1,5):
            t=i/4;result.append(((1-t)**2*u[0]+2*(1-t)*t*b[0]+t*t*v[0],(1-t)**2*u[1]+2*(1-t)*t*b[1]+t*t*v[1]))
    result.append(points[-1]);return result

def perforated_blocks(name,points,top_width,bottom_width,depth,max_length=55):
    """Merged actual hollow frames on a limited illustrative photo-type segment.

    Hole walls are modelled. Ground remains visible through openings. This is
    not an assertion that the entire source drainage line uses this lining.
    """
    line=LineString(points);narrow=(top_width-bottom_width)/2
    slope=math.hypot(narrow,depth);rows=max(2,round(slope/.52));step=.82
    verts=[];faces=[]
    length=min(line.length,max_length);start=max(0,line.length*.28-length/2)
    for di in range(int(length/step)):
        d=start+(di+.5)*step;p=line.interpolate(d);a=line.interpolate(max(0,d-.08));b=line.interpolate(min(line.length,d+.08))
        tangent=Vector((b.x-a.x,b.y-a.y,0)).normalized();normal=Vector((-tangent.y,tangent.x,0))
        for side in (-1,1):
            uphill=(normal*side*narrow+Vector((0,0,depth))).normalized();u=tangent*(-side)
            out=u.cross(uphill).normalized()
            if out.z<0:out=-out
            for row in range(rows):
                f=(row+.5)/rows;offset=bottom_width/2+narrow*f
                center=Vector((p.x,p.y,-depth+depth*f))+normal*(side*offset)+out*.035
                sx=.75;sy=slope/rows*.92;thick=.07
                # One frame with two openings: four outer bars plus a central rib.
                rects=[(-sx/2,-sy/2,sx/2,-sy/2+.09),(-sx/2,sy/2-.09,sx/2,sy/2),(-sx/2,-sy/2+.09,-sx/2+.085,sy/2-.09),(sx/2-.085,-sy/2+.09,sx/2,sy/2-.09),(-.045,-sy/2+.09,.045,sy/2-.09)]
                for x0,y0,x1,y1 in rects:
                    k=len(verts)
                    for z in (0,thick):
                        for x,y in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]:verts.append(tuple(center+u*x+uphill*y+out*z))
                    faces.extend(tuple(k+i for i in face) for face in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    obj=API.mesh(name+'__PerforatedRevetment',verts,faces,API.MATERIALS['concrete'],'illustrative photo-type open-cell concrete lining; position/material not surveyed')
    obj['lod_detail']=True;obj['appearance_evidence']='参考图/农田现场参考照片3.jpg; public/focus/photos/channel-02.jpg; unlocated material reference'
    obj['lining_display_length']=length
    return start,length

def channel(name,points,top_width,bottom_width=1.0,depth=1.8,lined=False):
    points=rounded_path(points)
    line=LineString(points)
    # Constant-width polygon offsets resolve inside-corner overlaps. Sweeping
    # wide profiles over tiny rounded segments can fold faces upside down.
    top=line.buffer(top_width/2,quad_segs=4);bed=line.buffer(bottom_width/2,quad_segs=4)
    band(name+'__Trapezoid',top,bed,0,-depth,API.MATERIALS['soil_dark'],'excavated trapezoid side slopes')
    surface(name+'__ChannelBed',bed,-depth,API.MATERIALS['soil_dark'],'excavated channel bottom')
    obj=surface(name+'__ShallowWater',line.buffer(bottom_width*.43,quad_segs=4),-depth+.18,API.MATERIALS['water'],'narrow shallow channel water; no flow simulation')
    obj['water_surface']=True;obj['water_kind']='channel';obj['category']='water'
    outer=line.buffer(top_width/2+.8,quad_segs=4);crest=line.buffer(top_width/2+.22,quad_segs=4)
    band(name+'__ChannelCrestOuter',outer,crest,0,.2,API.MATERIALS['grass'],'channel crest outer slope; upward-facing normals')
    band(name+'__ChannelCrestInner',crest,top,.2,0,API.MATERIALS['grass'],'channel crest inner slope; upward-facing normals')
    walls(name+'__ChannelBody',outer,0,-depth-.55,API.MATERIALS['earth'],'excavated channel body sides')
    underside=surface(name+'__ChannelUnderside',outer,-depth-.55,API.MATERIALS['earth'],'channel body underside')
    for p in underside.data.polygons:p.flip()
    if lined:
        perforated_blocks(name,points,top_width,bottom_width,depth)
        grass=line.buffer(top_width/2+.85).difference(line.buffer(top_width/2+.25))
        blades(name+'__CrestGrass',grass,.04,min(2200,int(line.length*10)),True)
    return obj

def rocks(name,poly,count):
    rng=seeded(name);verts=[];faces=[];ring=poly.exterior
    for i in range(count):
        p=ring.interpolate(rng.random()*ring.length);radius=rng.uniform(.22,.65)
        k=len(verts);n=6;ang=rng.random()*math.tau
        for z,mult in [(0,1),(.45,.7)]:
            for j in range(n):
                a=ang+math.tau*j/n;rr=radius*rng.uniform(.8,1.15)*mult;verts.append((p.x+math.cos(a)*rr,p.y+math.sin(a)*rr,z*radius))
        verts.append((p.x,p.y,radius*.64))
        for j in range(n):faces.extend([(k+j,k+(j+1)%n,k+(j+1)%n+n,k+j+n),(k+j+n,k+(j+1)%n+n,k+12)])
    obj=API.mesh(name,verts,faces,API.MATERIALS['concrete'],'sparse shore stone appearance; not surveyed individual boulders');obj['lod_detail']=True

def woodland(name,points):
    poly=cut(Polygon(points).buffer(0));surface(name+'__Ground',poly,0,API.MATERIALS['forest_ground'],'observed woodland cover ground')
    rng=seeded(name);x0,y0,x1,y1=poly.bounds;verts=[];faces=[];stems=[];stem_faces=[]
    def limb(start,end,r0,r1):
        start=Vector(start);end=Vector(end);axis=(end-start).normalized()
        ref=Vector((0,1,0)) if abs(axis.y)<.9 else Vector((1,0,0))
        u=axis.cross(ref).normalized();v=axis.cross(u);k=len(stems);n=6
        for center,radius in [(start,r0),(end,r1)]:
            for j in range(n):stems.append(tuple(center+(u*math.cos(j*math.tau/n)+v*math.sin(j*math.tau/n))*radius))
        for j in range(n):stem_faces.append((k+j,k+(j+1)%n,k+(j+1)%n+n,k+j+n))
        stem_faces.extend([tuple(k+j for j in reversed(range(n))),tuple(k+n+j for j in range(n))])
    # Grouped irregular lobes replace a regular grid of spheres. Crown positions
    # are illustrative within the observed cover, not individually catalogued.
    count=min(260,max(7,int(poly.area/700)))
    for i in range(count*3):
        x=rng.uniform(x0,x1);y=rng.uniform(y0,y1)
        if not poly.buffer(-5).contains(Point(x,y)):continue
        if math.sin(x*.023+y*.035)<-.45:continue
        h=rng.uniform(7,14);r=rng.uniform(6,12)
        # Supporting geometry is appearance under the existing canopy, not a
        # new surveyed tree entity. Its base penetrates the ground slightly.
        limb((x,y,-.12),(x,y,h*.76),.32,.17)
        for lobe in range(rng.randint(3,5)):
            cx=x+rng.uniform(-r*.5,r*.5);cy=y+rng.uniform(-r*.5,r*.5);rr=r*rng.uniform(.5,.9);cz=h*rng.uniform(.62,.92)
            limb((x,y,h*.46),(cx,cy,cz),.16,.065)
            k=len(verts);n=9
            verts.append((cx,cy,cz+rr*.67))
            for j in range(n):
                a=math.tau*j/n;f=rng.uniform(.75,1.2);verts.append((cx+math.cos(a)*rr*f,cy+math.sin(a)*rr*f,cz+rng.uniform(-.7,.7)))
            verts.append((cx,cy,cz-rr*.7))
            for j in range(n):faces.extend([(k,k+1+j,k+1+(j+1)%n),(k+10,k+1+(j+1)%n,k+1+j)])
        if len(verts)>count*45:break
    if faces:
        obj=API.mesh(name+'__CanopyMass',verts,faces,API.MATERIALS['foliage1'],'irregular canopy cover mass; tree positions and heights illustrative')
        for p in obj.data.polygons:p.use_smooth=True
    if stem_faces:
        support=API.mesh(name+'__TrunksAndBranches',stems,stem_faces,API.MATERIALS['trunk'],'ground-connected support for illustrative canopy; not surveyed individual trees')
        support['appearance_only']=True;support['category']='vegetation'

def settlement(name,points):
    poly=cut(Polygon(points).buffer(0));surface(name+'__SettlementFootprint',poly,.03,API.MATERIALS['gravel'],'observed settlement coverage; individual building footprints unknown')
    walls(name+'__CoverageBody',poly,.03,-.8,API.MATERIALS['earth'],'coverage body; not invented building footprint')

def terrain(name,outer,holes=None,bottom=-5):
    API.CURRENT_FEATURE=None
    land=outer.difference(holes) if holes is not None else outer
    obj=surface(name,land,0,API.MATERIALS['terrain'],'continuous excavated terrain with actual pond/channel openings')
    obj['surface_area_units2']=land.area;obj['layer']='terrain';obj['asset_id']=API.CURRENT_ASSET
    side=walls(name+'__EarthSection',outer,0,bottom,API.MATERIALS['earth'],'terrain soil volume section, not measured geology');side['layer']='terrain';side['asset_id']=API.CURRENT_ASSET
    under=surface(name+'__Bottom',outer,bottom,API.MATERIALS['earth'],'continuous terrain underside');under['layer']='terrain';under['asset_id']=API.CURRENT_ASSET
    return obj

def materials(api):
    global API
    API=api
    api.create_materials()
    m=api.MATERIALS
    m['terrain']=api.pbr('Dry grass and exposed soil ground',(.50,.38,.23),'grass',uv_size=8,normal_strength=.12)
    m['soil']=api.pbr('Warm cultivated soil photographic PBR',(.82,.58,.33),'soil',uv_size=3.5,normal_strength=.48)
    m['soil_dark']=api.pbr('Damp excavated soil',(.46,.33,.21),'soil',uv_size=3,normal_strength=.50)
    m['grass']=api.pbr('Dry mixed grass bank PBR',(.46,.41,.22),'grass',uv_size=3.5,normal_strength=.10)
    m['gravel']=api.pbr('Pale compacted gravel PBR',(.65,.61,.51),'gravel',uv_size=2.5,normal_strength=.6)
    m['concrete']=api.pbr('Weathered concrete cell frames PBR',(.60,.58,.50),'concrete',uv_size=1.1,normal_strength=.4)
    m['stubble']=api.pbr('Dry harvested stubble appearance',(.32,.25,.14),roughness=1)
    m['blade']=api.pbr('Sparse mixed bank grass blades',(.20,.24,.09),roughness=1)
    m['forest_ground']=api.pbr('Dry woodland understory',(.18,.22,.10),'grass',uv_size=22)
    m['earth']=api.pbr('Cut soil body',(.24,.18,.12),'soil',uv_size=5)
    water=m['water'];bs=water.node_tree.nodes.get('Principled BSDF')
    for link in list(bs.inputs['Base Color'].links):water.node_tree.links.remove(link)
    bs.inputs['Base Color'].default_value=(.025,.055,.04,1);bs.inputs['Metallic'].default_value=0;bs.inputs['Roughness'].default_value=.24
    bs.inputs['IOR'].default_value=1.333;bs.inputs['Coat Weight'].default_value=.28
    for n in water.node_tree.nodes:
        if n.type=='NORMAL_MAP':n.inputs['Strength'].default_value=.34
    water['uv_scene_units']=4.5
    # A deterministic stochastic photo bake removes conspicuous rectangular
    # repeats. This is a PBR material bake, not a projected site screenshot.
    import numpy as np
    original=bpy.data.images.load(str(api.TEXTURES/'grass-diff.jpg'),check_existing=True)
    w,h=original.size;raw=np.empty(w*h*4,dtype=np.float32);original.pixels.foreach_get(raw);raw=raw.reshape(h,w,4)
    size=2048;yy,xx=np.mgrid[0:size,0:size];u=xx/size*4;v=yy/size*4
    cx=np.floor(u/2);cy=np.floor(v/2);fx=u/2-cx;fy=v/2-cy;fx=fx*fx*(3-2*fx);fy=fy*fy*(3-2*fy)
    baked=np.zeros((size,size,4),dtype=np.float32)
    for dx,dy in [(0,0),(1,0),(0,1),(1,1)]:
        # Periodic hashes at outer edges keep the baked texture seamless.
        hx=np.mod(cx+dx,2);hy=np.mod(cy+dy,2)
        ox=np.sin(hx*127.1+hy*311.7)*18.5;oy=np.sin(hx*269.5+hy*183.3)*18.5
        sample=raw[np.mod(((v+oy)*h).astype(np.int64),h),np.mod(((u+ox)*w).astype(np.int64),w)]
        weight=(fx if dx else 1-fx)*(fy if dy else 1-fy);baked+=sample*weight[...,None]
    # Reduce yellow/green mottling without erasing photographic grain.
    luma=baked[:,:,:3].mean(axis=2);baked[:,:,:3]=baked[:,:,:3]*.55+luma[...,None]*.45;baked[:,:,3]=1
    mean=baked[:,:,:3].mean(axis=(0,1));baked[:,:,:3]=mean+(baked[:,:,:3]-mean)*.32
    ground=bpy.data.images.new('Baked stochastic dry-ground PBR albedo',width=size,height=size,alpha=False)
    ground.pixels.foreach_set(baked.ravel());ground.filepath_raw=str(api.SOURCE_OUT/'textures/dry-ground-stochastic.png');ground.file_format='PNG';ground.save();ground.pack()
    for key in ('terrain','forest_ground'):
        for n in m[key].node_tree.nodes:
            if n.type=='TEX_IMAGE' and n.image and '-diff' in n.image.name:n.image=ground
        m[key]['uv_scene_units']=12;m[key]['uv_detail']=3
        detail=m[key].node_tree.nodes.new('ShaderNodeUVMap');detail.uv_map='DetailUV'
        for n in m[key].node_tree.nodes:
            if n.type=='TEX_IMAGE' and n.image and n.image!=ground:m[key].node_tree.links.new(detail.outputs[0],n.inputs['Vector'])
    for key in ['terrain','soil','soil_dark','grass','gravel','concrete','earth','forest_ground']:
        m[key].use_backface_culling=True

def install(api):
    global API
    API=api
    for name in ['field','water','road','channel','woodland','settlement']:setattr(api,name,globals()[name])

def build_full(api):
    global CUTS
    api.CURRENT_ASSET='full';api.CURRENT_SCALE=api.SOURCE['meters_per_pixel'];api.CURRENT_ORIGIN=api.SOURCE['origin']
    col=api.new_collection('FULL · volumetric redline landscape');col['asset_id']='full';api.ACTIVE_COLLECTION=col
    boundary=[api.xy(p) for p in api.BOUNDARY];source_polys=[Polygon([api.xy(p) for p in f['points']]).buffer(0) for f in api.FEATURES]
    holes=[p for p,f in zip(source_polys,api.FEATURES) if f['kind'] in ('pond','lake')]
    for name,text,width in api.CHANNELS:holes.append(LineString([api.xy(p) for p in api.pts(text)]).buffer(width/2+.3))
    CUTS=unary_union(holes)
    terrain('WholeRedlineTerrain',Polygon(boundary).buffer(0),unary_union(source_polys+holes),bottom=-6)
    # Context outside the redline prevents an edge drainage body floating beside
    # the clipped project terrain. It has no business/spatial identity and does
    # not extend the project boundary or infer outside land ownership.
    border=Polygon(boundary).buffer(0);expanded=border.buffer(500)
    outside=expanded.difference(border).difference(unary_union(source_polys+holes))
    context=surface('FullExteriorContext',outside,0,api.MATERIALS['terrain'],'neutral outside context; no ownership or source feature inferred')
    context['layer']='terrain';context['asset_id']='full';context['context_only']=True
    outer_section=walls('FullExteriorContextSection',expanded,0,-6,api.MATERIALS['earth'],'context ground section')
    outer_section['layer']='terrain';outer_section['asset_id']='full';outer_section['context_only']=True
    world={}
    for index,feature in enumerate(api.FEATURES):
        points=api.record(feature);name=feature['spatial_id'];kind=feature['kind'];world[name]=points
        if kind=='field':field(name,points,index=index)
        elif kind in ('pond','lake'):water(name,points,kind=='lake')
        elif kind=='woodland':woodland(name,points)
        elif kind=='settlement':settlement(name,points)
        else:
            poly=cut(Polygon(points).buffer(0));surface(name+'__ExposedSoil',poly,.04,api.MATERIALS['soil'],'observed disturbed land cover');walls(name+'__SoilBody',poly,.04,-1,api.MATERIALS['earth'],'soil body')
    for i,(name,text,width) in enumerate(api.ROADS):
        f={'spatial_id':f'SAT-ROAD-{i+1:03d}','name':name+'（概略）','kind':'road','region':'全域','points':api.pts(text),'assumed_width_m':width}
        points=api.record(f,line=True,width=width);road(f['spatial_id'],points,width);world[f['spatial_id']]=points
    for i,(name,text,width) in enumerate(api.CHANNELS):
        f={'spatial_id':f'SAT-CHANNEL-{i+1:03d}','name':name+'（判读待核）','kind':'channel','region':'全域','points':api.pts(text),'assumed_width_m':width}
        points=api.record(f,line=True,width=width);channel(f['spatial_id'],points,width,1,1.4);world[f['spatial_id']]=points
    # Only two source-reviewed roof-like outlines are available. They remain
    # appearance children of the existing settlement, never invented resources.
    import json
    roof_source=api.ROOT/'data/spatial/appearance-roof-footprints.json'
    if roof_source.exists():
        roofs=json.loads(roof_source.read_text(encoding='utf8'))
        for row in roofs['records']:
            api.CURRENT_FEATURE=next(o for o in api.MANIFEST['objects'] if o['spatial_id']==row['parent_spatial_id'])
            points=[api.xy(p) for p in row['points_reference_px']]
            poly=Polygon(points).buffer(0);name=row['appearance_id']
            mat=api.pbr('Observed '+row['observed_color']+' roof-like cover',(.07,.13,.20) if row['observed_color']=='blue' else (.29,.10,.06),roughness=.7)
            obj=surface(name+'__Roof',poly,5.2,mat,'source-reviewed roof-like outline; elevation and structure illustrative')
            obj['appearance_id']=name;obj['source_hash']=roofs['source_hash'];obj['height_assumption']=5.2
            walls(name+'__Massing',poly,5.2,0,api.MATERIALS['wall'],'background building massing under observed roof; wall base unverified')
        api.MANIFEST['appearance_sources']=[{'file':'data/spatial/appearance-roof-footprints.json','appearance_children':2,'business_entities_added':0}]
    api.CURRENT_FEATURE=None
    red=api.section_strip('RedlineBoundary',boundary,[(-.7,.22),(.7,.22)],api.MATERIALS['redline'],'source redline, not surveyed cadastral boundary',True)
    red['layer']='boundary';red['asset_id']='full'
    reference=api.new_collection('REFERENCE ONLY · source satellite');bpy.context.scene.collection.children.unlink(reference);col.children.link(reference)
    api.ACTIVE_COLLECTION=reference;api.satellite_reference();reference.hide_render=True;reference.hide_viewport=True;reference['reference_only']=True;api.ACTIVE_COLLECTION=col
    api.MANIFEST['boundary']={'points':api.BOUNDARY,'center':[0,0,0],'model_area_m2':round(abs(api.area2(boundary)),2),'precision':'screenshot_redline_approximate'}
    asset=next(a for a in api.MANIFEST['assets'] if a['id']=='full');p=Polygon(boundary)
    asset['bounds']={'min':[p.bounds[0],-6,-p.bounds[3]],'max':[p.bounds[2],16,-p.bounds[1]]}
    asset['camera_views']={'overview':camera_view(boundary),'field':camera_view(world['SAT-FIELD-001'],'field'),'pond':camera_view(world['SAT-POND-001'],'pond'),'channel':camera_view(world['SAT-CHANNEL-005'],'channel')}
    asset['camera_views']['focus']=asset['camera_views']['overview'];asset['reference_exported']=False
    asset['model_representation']='volumetric_source_geometry'
    return col

def camera_view(points,kind='overview',span=None):
    """Three Y-up cameras, calculated from real source geometry."""
    if kind=='channel':
        line=LineString(points);d=line.length*.26;p=line.interpolate(d);q=line.interpolate(min(line.length,d+18));a=line.interpolate(max(0,d-4))
        dx,dy=q.x-a.x,q.y-a.y;length=math.hypot(dx,dy);nx,ny=-dy/length,dx/length
        return {'position':[a.x+nx*3.8,3.5,-a.y-ny*3.8],'target':[q.x,-.6,-q.y],'hint':'按源图沟线；断面与局部镂空护坡为照片类型表现，尺寸未测绘'}
    poly=Polygon(points).buffer(0);c=poly.centroid;b=poly.bounds;size=span or max(b[2]-b[0],b[3]-b[1])
    if kind in ('field','pond'):
        outside=Point(c.x+size*.3,c.y-size*.85);edge=poly.exterior.interpolate(poly.exterior.project(outside))
        dx,dy=outside.x-edge.x,outside.y-edge.y;dist=math.hypot(dx,dy) or 1;dx/=dist;dy/=dist
        ahead=10 if kind=='field' else 9;back=11 if kind=='field' else 12
        tangent=(-dy,dx);behind=-12 if kind=='field' else -6;along=25 if kind=='field' else 15
        return {'position':[edge.x+dx*back+tangent[0]*behind,3.8,-edge.y-dy*back-tangent[1]*behind],
                'target':[edge.x-dx*ahead+tangent[0]*along,.15 if kind=='field' else -.5,-edge.y+dy*ahead-tangent[1]*along],
                'hint':'源轮廓近岸视点；田埂/残茬/岸坡/深度为未测绘表现参数'}
    cx=(b[0]+b[2])/2;cy=(b[1]+b[3])/2
    return {'position':[cx+size*.65,size*1.05,-cy+size*1.3],'target':[cx,0,-cy]}

def set_camera(scene,view,orthographic=False):
    camera=scene.camera
    camera.location=(view['position'][0],-view['position'][2],view['position'][1])
    target=Vector((view['target'][0],-view['target'][2],view['target'][1]))
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO' if orthographic else 'PERSP';camera.data.lens=42
    camera.data.clip_start=max(.05,(target-camera.location).length/600);camera.data.clip_end=30000

def lighting(scene):
    scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-.45
    scene.eevee.use_raytracing=True
    world=scene.world;world.use_nodes=True;nodes=world.node_tree.nodes;links=world.node_tree.links
    environment=nodes.get('Environment Texture') or nodes.new('ShaderNodeTexEnvironment')
    environment.image=bpy.data.images.load(str(API.TEXTURES/'daylight-sky.hdr'),check_existing=True)
    links.new(environment.outputs['Color'],nodes['Background'].inputs[0]);nodes['Background'].inputs[1].default_value=.65
    sun=bpy.data.objects.get('AfternoonSun')
    if sun:sun.data.energy=2.5;sun.data.angle=math.radians(4)

def render_pair(scene,view,stem):
    set_camera(scene,view);lighting(scene);scene.render.filepath=str(API.SOURCE_OUT/(stem+'-material.png'));bpy.ops.render.render(write_still=True,scene=scene.name)
    clay=API.pbr('Clay inspection material',(.55,.55,.55),roughness=.95)
    swapped=[]
    for obj in scene.objects:
        if obj.type!='MESH':continue
        for slot in obj.material_slots:swapped.append((slot,slot.material));slot.material=clay
    hidden=[]
    if stem=='correction-pond':
        for obj in scene.objects:
            if obj.get('water_surface') and obj.get('water_kind')=='pond':hidden.append((obj,obj.hide_render));obj.hide_render=True
    scene.render.filepath=str(API.SOURCE_OUT/(stem+'-clay.png'));bpy.ops.render.render(write_still=True,scene=scene.name)
    for slot,material in swapped:slot.material=material
    for obj,hidden_state in hidden:obj.hide_render=hidden_state
