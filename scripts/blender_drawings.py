"""Assemble all five source PDF pages in their own paper coordinate systems.

This module never infers a field rectangle from a label or an XLS area.
Unknown-boundary records are symbolic selectable anchors with null area.
"""
import bpy
import json
import math
import pathlib

def polygon_ring(geometry):
    points=geometry.get('coordinates',[])
    if points and isinstance(points[0][0],(list,tuple)): points=points[0]
    points=[list(p[:2]) for p in points]
    if len(points)>1 and points[0]==points[-1]: points.pop()
    return points

def polygon_rings(geometry):
    coords=geometry.get('coordinates',[])
    if coords and isinstance(coords[0][0],(int,float)): coords=[coords]
    rings=[]
    for ring in coords:
        ring=[list(p[:2]) for p in ring]
        if len(ring)>1 and ring[0]==ring[-1]: ring.pop()
        rings.append(ring)
    return rings

def confirmed_polygon_mesh(api,sid,record,width,height,material):
    rings=[[[float(p[0])-width/2,height/2-float(p[1])] for p in r] for r in polygon_rings(record['geometry'])]
    poly=api.Polygon(rings[0],rings[1:]).buffer(0)
    triangles=api.constrained_delaunay_triangles(poly)
    assert abs(sum(t.area for t in triangles.geoms)-poly.area)<1e-5
    vertices=[]; faces=[]
    for tri in triangles.geoms:
        points=list(tri.exterior.coords)[:3]
        if api.area2(points)<0: points.reverse()
        first=len(vertices); vertices.extend((x,y,.45) for x,y in points); faces.append((first,first+1,first+2))
    obj=api.mesh(sid+'__ConfirmedFootprint',vertices,faces,material,'confirmed paper-space footprint; thickness illustrative')
    obj['source_area_paper_units2']=poly.area
    for i,points in enumerate(rings):
        api.ring(sid+f'__ReliefEdge{i}',points,points,0,.45,api.MATERIALS['soil'],'illustrative relief edge in paper units')
        api.section_strip(sid+f'__Boundary{i}',points,[(-.45,.65),(.45,.65)],api.MATERIALS['anchor_water' if record.get('kind') in ('pond','lake') else 'anchor_field'],'confirmed source boundary',True)
    return obj

def drawing_dimensions(drawing):
    dims=drawing.get('page_size_pt') or drawing.get('landscape_size_pt')
    if isinstance(dims,dict): dims=[dims['width'],dims['height']]
    assert dims and len(dims)==2, ('Missing rotated paper page dimensions',drawing)
    return [float(v) for v in dims]

def path_for(api,drawing):
    path=drawing.get('image_path') or drawing.get('reference_image_path')
    assert path, ('Drawing image path missing',drawing['asset_id'])
    path=pathlib.Path(path)
    if not path.is_absolute(): path=api.ROOT/path
    assert path.exists(), ('Drawing image missing',path)
    return path

def marker(api,name,point,kind):
    x,y=point; radius=.9; n=16; vertices=[]
    for r,z in [(radius,.25),(radius*.59,.25),(radius*.59,.42)]:
        vertices.extend((x+math.cos(i*2*math.pi/n)*r,y+math.sin(i*2*math.pi/n)*r,z) for i in range(n))
    faces=[]
    for j in range(2):
        for i in range(n): faces.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
    key='anchor_field' if kind=='field' else ('anchor_water' if kind in ('pond','lake') else 'anchor_facility')
    obj=api.mesh(name+'__SourceAnchor',vertices,faces,api.MATERIALS[key],'symbolic source label anchor; physical boundary unknown')
    obj['boundary_status']='boundary_unknown'; obj['representation_mode']='source_anchor'
    obj['no_physical_footprint']=True
    obj['category']='source_annotation';obj['layer']='source_annotation';obj['default_visible']=False

def reference_plane(api,drawing,width,height):
    material=api.pbr('Drawing reference · '+drawing['asset_id'],(.92,.92,.90),roughness=1)
    nodes=material.node_tree.nodes; links=material.node_tree.links
    image=nodes.new('ShaderNodeTexImage'); image.image=bpy.data.images.load(str(path_for(api,drawing)),check_existing=True)
    # Unlit original drafting lines remain readable independent of the site's daylight.
    emission=nodes.new('ShaderNodeEmission'); emission.inputs['Strength'].default_value=1
    links.new(image.outputs['Color'],emission.inputs['Color'])
    links.new(emission.outputs['Emission'],nodes.get('Material Output').inputs['Surface'])
    verts=[(-width/2,height/2,0),(width/2,height/2,0),(width/2,-height/2,0),(-width/2,-height/2,0)]
    obj=api.mesh('DrawingReference_'+drawing['asset_id'],verts,[(3,2,1,0)],material,'original full PDF page reference')
    uv=[(0,1),(1,1),(1,0),(0,0)]
    for poly in obj.data.polygons:
        for li in poly.loop_indices: obj.data.uv_layers.active.data[li].uv=uv[obj.data.loops[li].vertex_index]
    obj['layer']='drawing_reference'; obj['asset_id']=drawing['asset_id']; obj['source_file']=drawing['source_file']; obj['coordinate_system']='PDF_PAGE_LOCAL'
    return obj

def make_record(api,record,drawing,width,height):
    geometry=record['geometry']; kind=record.get('kind','field'); source_id=record['representation_id']
    code=record.get('original_code') or record.get('code') or source_id
    aliases={'L18':'DETAIL-L18','L19':'DETAIL-L19','L20':'DETAIL-L20','清-17':'DETAIL-QING17','清17':'DETAIL-QING17'}
    spatial_id=aliases.get(code,source_id) if drawing['asset_id']=='detail-miaoxia' else source_id
    def to_world(p): return [float(p[0])-width/2,height/2-float(p[1])]
    typ=geometry['type']
    if typ=='Point':
        world=[to_world(geometry['coordinates'])]; center=world[0]; area=None
    elif typ=='Polygon':
        rings=[[to_world(p) for p in r] for r in polygon_rings(geometry)]
        world=rings[0]; polygon=api.Polygon(world,rings[1:]).buffer(0)
        center=[polygon.centroid.x,polygon.centroid.y]; area=polygon.area
    elif typ=='LineString':
        world=[to_world(p) for p in geometry['coordinates']]; center=[sum(p[k] for p in world)/len(world) for k in (0,1)]; area=None
    else: raise ValueError(('Unsupported source geometry',typ,source_id))
    status=record.get('boundary_status') or ('boundary_unknown' if typ=='Point' else 'confirmed_visual')
    assert not(status=='boundary_unknown' and typ!='Point'), ('Unknown boundary must remain an anchor',source_id)
    evidence=record.get('source_evidence') or record.get('evidence')
    assert evidence, ('Source evidence missing',source_id)
    source_key=record.get('source_key') or record.get('business_source_key')
    obj={
      'spatial_id':spatial_id,'source_record_id':source_id,'source_representation_id':record.get('source_representation_id',source_id),'asset_id':drawing['asset_id'],
      'name':record.get('name') or (str(record.get('label') or code)+' · '+drawing['label']), 'code':code,'kind':kind,
      'original_code':record.get('original_code'),'facility_type':record.get('facility_type'),
      'geometry_role':record.get('geometry_role'),'identity_scope':record.get('identity_scope'),
      'region':record.get('region') or drawing['label'],'center':[center[0],2,-center[1]],'centroid':[center[0],2,-center[1]],
      'bounds':{'min':[min(p[0] for p in world)-4,0,min(-p[1] for p in world)-4],
                'max':[max(p[0] for p in world)+4,3,max(-p[1] for p in world)+4]},
      'precision':'drawing_anchor' if typ=='Point' else 'unregistered_drawing_geometry',
      'boundary_status':status,'position_status':record.get('position_status','source_label_anchor' if typ=='Point' else 'source_drawing_local'),
      'coordinate_system':'PDF_PAGE_LOCAL','coordinate_units':'paper_point','scene_units_per_paper_point':1,
      'geometry':geometry,'points':polygon_ring(geometry) if typ=='Polygon' else geometry['coordinates'],
      'model_area_m2':None,'model_area_units2':area,'entity_uuid':None,
      'source':drawing['source_file']+' · 第1页 · '+str(code),'source_evidence':evidence,
      'source_file':drawing['source_file'],'source_hash':drawing.get('source_hash'),
      'source_page':record.get('source_page',1),'source_bbox_pt':record.get('source_bbox_pt'),
      'documented_dimensions':record.get('documented_dimensions'),
      'candidate_source_key':record.get('candidate_source_key'),
      'identity_match_status':record.get('identity_match_status'),'match_note':record.get('match_note'),
      'source_model_assumptions':record.get('model_assumptions'),
      'model_assumptions':{'vertical_relief':'0–2 paper display units; not an engineering elevation','anchor_radius':'3.7 paper display units; not a footprint'},
      'accuracy_note':'图纸纸页局部坐标；未与卫星配准；无可靠米制比例。'+('仅图内编号锚点，边界未知。' if typ=='Point' else '保留图纸可确认的轮廓。')}
    if source_key:
        obj.update(business_source_key=source_key,link_verified=record.get('link_verified',False),link_evidence=evidence)
    api.CURRENT_FEATURE=obj
    parent=bpy.data.objects.new('Resource_'+spatial_id,None); api.ACTIVE_COLLECTION.objects.link(parent); api.tag(parent,'independent editable source drawing representation')
    parent['boundary_status']=status; parent['display_name']=obj['name']; parent['source_representation_id']=source_id
    api.MANIFEST['objects'].append(obj)
    return obj,world

def build(api):
    import blender_volume as volume
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    path=api.ROOT/'data/spatial/drawing-entities.json'
    source=json.loads(path.read_text(encoding='utf-8'))
    api.DRAWING_DATA=source
    assert len(source['drawings'])==5, 'Require all five reviewed drawings.'
    api.MATERIALS['anchor_field']=api.pbr('Source anchor · field',(.06,.33,.12),roughness=.5)
    api.MATERIALS['anchor_water']=api.pbr('Source anchor · water',(.025,.30,.41),roughness=.5)
    api.MATERIALS['anchor_facility']=api.pbr('Source anchor · facility',(.72,.28,.025),roughness=.5)
    api.MATERIALS['drawing_line']=api.pbr('Source geometry · confirmed line',(.36,.18,.035),roughness=.8)
    collections=[]
    for drawing in source['drawings']:
        asset_id=drawing['asset_id']; width,height=drawing_dimensions(drawing)
        api.CURRENT_ASSET=asset_id; api.CURRENT_FEATURE=None
        collection=api.new_collection('DRAWING · '+drawing['label']+' · paper-local, unregistered')
        collection['asset_id']=asset_id
        api.ACTIVE_COLLECTION=collection
        # Reference lives only in a hidden child Collection; neither primary
        # geometry selection nor export recursively includes this Collection.
        reference=api.new_collection('REFERENCE ONLY · '+asset_id)
        bpy.context.scene.collection.children.unlink(reference);collection.children.link(reference)
        api.ACTIVE_COLLECTION=reference;reference_plane(api,drawing,width,height)
        reference.hide_render=True;reference.hide_viewport=True;reference['reference_only']=True
        api.ACTIVE_COLLECTION=collection
        api.MANIFEST['assets'].append({'id':asset_id,'url':f'/models/{asset_id}.glb','scope':'detail','source_type':'drawing',
          'label':drawing['label'],'source_file':drawing['source_file'],'source_hash':drawing.get('source_hash'),
          'coordinate_system':'PDF_PAGE_LOCAL','units':'paper_point','center':[0,0,0],
          'bounds':{'min':[-width/2,0,-height/2],'max':[width/2,4,height/2]},'page_size_pt':[width,height],
          'reference_image':drawing.get('image_path'),'georeferenced':False})
        rows=[r for r in source['records'] if r['asset_id']==asset_id]
        assert rows, ('Source drawing has no records',asset_id)
        source_shapes=[];excavations=[];field_shapes=[]
        to_world=lambda p:(float(p[0])-width/2,height/2-float(p[1]))
        for row in rows:
            typ=row['geometry']['type']
            if typ=='Polygon':
                rings=[[to_world(p) for p in r] for r in polygon_rings(row['geometry'])]
                poly=api.Polygon(rings[0],rings[1:]).buffer(0);source_shapes.append(poly);field_shapes.append(poly)
                if row['kind'] in ('pond','lake'):excavations.append(poly)
            elif typ=='LineString':
                line=LineString([to_world(p) for p in row['geometry']['coordinates']])
                source_shapes.append(line.buffer(4))
                if row['kind']=='channel':excavations.append(line.buffer(3.7))
        volume.CUTS=unary_union(excavations)
        # A continuous neutral context surface extends beyond the drawing
        # features. It has no spatial/business ID and is not an inferred parcel.
        source_envelope=unary_union(source_shapes).convex_hull
        envelope=source_envelope.buffer(500)
        volume.terrain('ExcavatedTerrain_'+asset_id,envelope,unary_union(field_shapes+excavations))
        cameras={};world_geometry={}
        for row in rows:
            obj,points=make_record(api,row,drawing,width,height); typ=row['geometry']['type']; sid=obj['spatial_id']; kind=obj['kind']
            obj['model_assumptions']={'vertical_units':'paper display units; no engineering elevation inference',
              'field_height':.035,'berm_height':.26,'pond_bottom':-2.85,'pond_water':-.78,
              'channel_top_width':6.4,'channel_bottom_width':1.2,'channel_depth':1.8,
              'road_width':3.3,'road_crown':.38,'photo_material_location':'not matched to individual drawing objects'}
            obj['bounds']['min'][1]=-5;obj['bounds']['max'][1]=3
            world_geometry[sid]=points
            if typ=='Point': marker(api,sid,points[0],kind)
            elif typ=='LineString':
                if kind=='channel':
                    volume.channel(sid,points,6.4,1.2,1.8,lined=asset_id=='detail-miaoxia')
                    cameras.setdefault('channel',volume.camera_view(points,'channel'))
                else:volume.road(sid,points,3.3)
            else:
                if kind in ('pond','lake'):
                    volume.water(sid,points,detail=True)
                    if 'pond' not in cameras or sid=='DETAIL-QING17':cameras['pond']=volume.camera_view(points,'pond')
                else:
                    volume.field(sid,points,detail=True)
                    if 'field' not in cameras or sid=='DETAIL-L19':cameras['field']=volume.camera_view(points,'field')
        members=[o for o in api.MANIFEST['objects'] if o['asset_id']==asset_id]
        focus_min=[min(o['bounds']['min'][axis] for o in members) for axis in range(3)]
        focus_max=[max(o['bounds']['max'][axis] for o in members) for axis in range(3)]
        asset_meta=next(a for a in api.MANIFEST['assets'] if a['id']==asset_id)
        asset_meta['focus_bounds']={'min':focus_min,'max':focus_max}
        asset_meta['focus_center']=[(a+b)/2 for a,b in zip(focus_min,focus_max)]
        env=source_envelope;outline=list(env.exterior.coords)[:-1]
        cameras['overview']=volume.camera_view(outline)
        if asset_id=='detail-miaoxia':
            focus=unary_union([api.Polygon(world_geometry[sid]) for sid in ['DETAIL-L18','DETAIL-L19','DETAIL-L20','DETAIL-QING17']]).convex_hull
            cameras['focus']=volume.camera_view(list(focus.exterior.coords)[:-1])
            # Readable source-relative compositions: west edge of L19 by the
            # confirmed road, and the southwest shoreline of Qing17.
            cameras['field']={'position':[-152,6.5,182],'target':[-119,.1,151],'hint':'L19西侧田埂与已提取道路附近，局部图纸坐标'}
            cameras['pond']={'position':[107,5.2,189],'target':[137,-.6,161],'hint':'清-17西南缓岸，水深水位与散石为外观表现参数'}
        else:cameras['focus']=cameras['overview']
        for key in ['field','pond','channel']:cameras.setdefault(key,cameras['overview'])
        asset_meta['camera_views']=cameras
        asset_meta['bounds']={'min':[source_envelope.bounds[0],-5,-source_envelope.bounds[3]],'max':[source_envelope.bounds[2],3,-source_envelope.bounds[1]]}
        asset_meta['context_ground']='Neutral continuous appearance outside documented objects; no inferred parcel or land ownership.'
        asset_meta['reference_exported']=False;asset_meta['model_representation']='volumetric_source_geometry'
        api.CURRENT_FEATURE=None
        collections.append(collection)
    api.MANIFEST['drawing_source']={'file':'data/spatial/drawing-entities.json','records':len(source['records']),'drawings':5,'coordinate_units':'paper_point','not_georeferenced':True}
    return collections
