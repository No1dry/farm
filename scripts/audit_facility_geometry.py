"""Build independently traceable facilities, plus a separate native-annotation ledger."""
import json, math, re
from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter,ImageChops
from audit_match_vectors import inside
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/spatial'
TMP=ROOT/'tmp/audit/drawing-geometry'
MASK_CACHE={}

def ink_mask(image_path,category):
    key=(str(image_path),category)
    if key not in MASK_CACHE:
        im=Image.open(image_path).convert('RGB');r,g,b=im.split()
        if category=='road':
            # Source filled road hatches exclude red stroked field boundaries.
            # Raster colour alone would sometimes snap to those nearby boundaries.
            slug=Path(image_path).name[:6]
            source=json.loads((TMP/f'{slug}-vectors.json').read_text(encoding='utf8'))
            w,h=source['page_size_pt'];mask=Image.new('L',im.size);draw=ImageDraw.Draw(mask)
            for path in source['paths']:
                fill=path['fill']
                if fill and fill[0]>.75 and fill[1]<.1 and fill[2]<.1 and path['op'] in ('f','f*','F','B','B*','b','b*') and path['area_pt2']>5:
                    draw.polygon([(q[0]*5000/w,q[1]*3536/h) for q in path['points']],fill=255)
        elif category=='water':
            mask=ImageChops.multiply(r.point(lambda x:255 if x<165 else 0),ImageChops.multiply(g.point(lambda x:255 if x>165 else 0),b.point(lambda x:255 if x>175 else 0)))
        elif category=='cyan':
            mask=ImageChops.multiply(r.point(lambda x:255 if x<130 else 0),ImageChops.multiply(g.point(lambda x:255 if x>175 else 0),b.point(lambda x:255 if x>175 else 0)))
        else:
            mask=ImageChops.multiply(r.point(lambda x:255 if x<130 else 0),ImageChops.multiply(g.point(lambda x:255 if x<170 else 0),b.point(lambda x:255 if x>170 else 0)))
        if category=='water': mask=mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        else:mask=mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
        MASK_CACHE[key]=mask
    return MASK_CACHE[key]

def simplify(points,tolerance=1.5):
    if len(points)<3:return points
    a,b=points[0],points[-1];dx,dy=b[0]-a[0],b[1]-a[1];den=math.hypot(dx,dy)
    distances=[abs(dy*(p[0]-a[0])-dx*(p[1]-a[1]))/den if den else math.dist(a,p) for p in points[1:-1]]
    best=max(distances,default=0)
    if best<=tolerance:return [a,b]
    ix=distances.index(best)+1
    return simplify(points[:ix+1],tolerance)[:-1]+simplify(points[ix:],tolerance)

def raster_water_outline(image_path,seed):
    """Contour of the actual cyan source fill, not a manufactured field rectangle."""
    mask=ink_mask(image_path,'water').copy();width,height=mask.size
    x,y=seed; pix=mask.load()
    if pix[x,y]!=255:
        possible=[(math.hypot(i-x,j-y),i,j) for i in range(x-35,x+36) for j in range(y-35,y+36) if pix[i,j]==255]
        if not possible:raise ValueError(f'No source cyan fill near {seed}')
        _,x,y=min(possible)
    ImageDraw.floodfill(mask,(x,y),128,thresh=0)
    component=mask.point(lambda z:255 if z==128 else 0);bbox=component.getbbox()
    pix=component.load();x0,y0,x1,y1=bbox
    start=next((x,y0) for x in range(x0,x1) if pix[x,y0])
    dirs=[(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1)]
    cur=start;back=(start[0]-1,start[1]);ring=[]
    for step in range(200000):
        ring.append(cur);bi=dirs.index((back[0]-cur[0],back[1]-cur[1]))
        found=None
        for off in range(1,9):
            di=(bi+off)%8;dx,dy=dirs[di];n=(cur[0]+dx,cur[1]+dy)
            if 0<=n[0]<width and 0<=n[1]<height and pix[n]:
                prev=dirs[(di-1)%8];back=(cur[0]+prev[0],cur[1]+prev[1]);found=n;break
        if found is None:raise ValueError('Isolated water pixel')
        cur=found
        if cur==start:break
    else:raise ValueError('Contour failed to close')
    if len(ring)<12:raise ValueError('Water contour too small')
    mid=len(ring)//2
    ring=simplify(ring[:mid+1])+simplify(ring[mid:]+[ring[0]])[1:]
    return ring,bbox

def snap_visible_line(image_path,points,kind,identity):
    """Refine manually identified corridor to nearby coloured source ink."""
    category='road' if kind=='road' else 'cyan' if identity in ('PIPE-PE','CHANNEL-MAIN') else 'blue'
    mask=ink_mask(image_path,category);width,height=mask.size;pix=mask.load()
    samples=[]
    for a,b in zip(points,points[1:]):
        n=max(1,math.ceil(math.dist(a,b)/12))
        samples.extend([(round(a[0]+(b[0]-a[0])*t/n),round(a[1]+(b[1]-a[1])*t/n)) for t in range(n)])
    samples.append(tuple(points[-1]));snapped=[];max_shift=0;unresolved=0
    for x,y in samples:
        found=None
        for radius in range(0,91,2):
            ring=[(x+dx,y+dy) for dx in range(-radius,radius+1,2) for dy in (-radius,radius)]
            ring.extend((x+dx,y+dy) for dy in range(-radius,radius+1,2) for dx in (-radius,radius))
            candidates=[q for q in ring if 0<=q[0]<width and 0<=q[1]<height and pix[q]]
            if candidates:
                found=min(candidates,key=lambda q:math.dist(q,(x,y)));break
        if found is None:
            unresolved+=1;continue
        nearby=[(u,v) for u in range(found[0]-4,found[0]+5) for v in range(found[1]-4,found[1]+5) if pix[u,v]]
        q=(sum(p[0] for p in nearby)/len(nearby),sum(p[1] for p in nearby)/len(nearby))
        max_shift=max(max_shift,math.dist(q,(x,y)))
        if not snapped or math.dist(q,snapped[-1])>1:snapped.append(q)
    if unresolved>len(samples)*.08:raise ValueError(f'Cannot align {identity}: {unresolved}/{len(samples)}')
    return simplify(snapped,2.0),{'max_refinement_px':round(max_shift,2),'unresolved_samples':unresolved,'sample_count':len(samples)}

def build_facilities(drawings):
    features=json.loads((OUT/'facility-features.json').read_text(encoding='utf8'))
    records=[]
    for d in drawings:
        slug=Path(d['image_path']).name[:6]; w,h=d['page_size_pt']
        vectors=json.loads((TMP/f'{slug}-vectors.json').read_text(encoding='utf8'))['paths']
        def pt(p): return [round(p[0]*w/5000,5),round(p[1]*h/3536,5)]
        layer=Image.open(ROOT/d['image_path']).convert('RGBA'); draw=ImageDraw.Draw(layer)
        def record(item,kind,geometry,method,bbox,operation=None):
            sid=f'DRAW-{slug}-{item["id"]}'
            return {'representation_id':'DETAIL-QING17' if slug=='pdf-01' and item['id']=='QING17' else sid,'source_representation_id':sid,'asset_id':d['asset_id'],'source_key':f'drawing:lianghuqing-asbuilt:{slug}:{item["id"]}','original_code':item.get('label'),'label':item['label'],'kind':kind,'facility_type':item.get('facility_type',kind),'region':d['label'],'geometry':geometry,'geometry_role':'source_feature','boundary_status':'confirmed_source_vector' if geometry['type']=='Polygon' else 'confirmed_line','link_verified':False,'identity_scope':'independent_drawing_feature','source_file':d['source_file'],'source_hash':d['source_hash'],'source_page':1,'source_bbox_pt':bbox,'source_evidence':[{'source_file':d['source_file'],'source_sha256':d['source_hash'],'page':1,'bbox_pt':bbox,'bbox_coordinate_system':'PDF_LANDSCAPE_LOCAL','method':method,'vector_content_operation':operation,'source_label':item['label']}],'coordinate_system':'PDF_LANDSCAPE_LOCAL','coordinate_units':'pt','model_area_m2':None,'model_area_units2':None,'documented_dimensions':[{'source_text':item['dimensions_text'],'status':'as_labelled_not_survey_verified'}] if item.get('dimensions_text') else [],'model_assumptions':['Line display width is a visualization choice, not an as-built dimension.'] if geometry['type']=='LineString' else [],'crs':None,'elevation_datum':None}
        for item in features['ponds'].get(slug,[]):
            p=pt(item['point'])
            candidates=[v for v in vectors if v['stroke']==[0,0,1] and 20<v['area_pt2']<150000 and inside(p,v['points']) and (v['closed'] or math.dist(v['points'][0],v['points'][-1])<.8)]
            if not candidates:
                candidates=[v for v in vectors if v['stroke'] in ([0,0,0],[0,1,0]) and 20<v['area_pt2']<150000 and inside(p,v['points']) and (v['closed'] or math.dist(v['points'][0],v['points'][-1])<.8)]
            candidates.sort(key=lambda v:v['area_pt2'])
            chosen=candidates[0] if candidates else None
            if chosen: ring=chosen['points'][:]
            else:
                pixels,raster_bbox=raster_water_outline(ROOT/d['image_path'],item['point'])
                ring=[pt(q) for q in pixels]
            if ring[-1]!=ring[0]:ring.append(ring[0])
            bbox=[min(p[0] for p in ring),min(p[1] for p in ring),max(p[0] for p in ring),max(p[1] for p in ring)]
            method='Original PDF closed vector outline, matched by visually reviewed pond label/interior' if chosen else 'Contour of original cyan water fill in 5000px rendering; 3px binary closing bridges drawing hatch/text; 1.5px contour simplification. Visually reviewed approximate source boundary.'
            r=record(item,'pond',{'type':'Polygon','coordinates':[ring]},method,bbox,chosen['op_index'] if chosen else None)
            r['model_area_units2']=chosen['area_pt2'] if chosen else abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(ring,ring[1:])))/2
            r['source_evidence'][0]['label_anchor_pt']=p
            if not chosen:r.update({'boundary_status':'confirmed_visual','precision':'approximate_source_contour'})
            records.append(r)
            draw.line([(q[0]*5000/w,q[1]*3536/h) for q in ring],fill=(255,0,180,255),width=5)
        for item in features['lines']:
            if item['slug']!=slug:continue
            pixels,refinement=snap_visible_line(ROOT/d['image_path'],item['coordinates'],item['kind'],item['id'])
            line=[pt(p) for p in pixels]
            bbox=[min(p[0] for p in line),min(p[1] for p in line),max(p[0] for p in line),max(p[1] for p in line)]
            r=record(item,item['kind'],{'type':'LineString','coordinates':line},'Manual visual corridor trace refined to nearby source road/channel ink; generalized paper-coordinate geometry, not a survey',bbox)
            r['source_evidence'][0]['refinement']=refinement
            r['precision']='approximate_source_trace';r['identity_scope']='drawing_corridor_segment';records.append(r)
            draw.line([tuple(p) for p in pixels],fill=(255,0,180,255),width=6)
        layer.convert('RGB').save(TMP/f'{slug}-facility-review.jpg',quality=94)
    return records

def build_annotation_ledger(drawings):
    native=json.loads((OUT/'native-annotations.json').read_text(encoding='utf8'))
    bounds={'pdf-01':[(750,1250,3600,3250)],'pdf-02':[(300,1000,850,1700),(650,1550,2100,2800),(2700,800,3950,1700)],'pdf-03':[(700,650,2300,2450)],'pdf-04':[(650,350,2200,3050)],'pdf-05':[(150,450,4900,2700),(700,2700,4900,3250)]}
    records=[];excluded=[]
    for index,group in enumerate(native):
        d=drawings[index];w,h=d['page_size_pt'];slug=group['slug']
        for j,a in enumerate(group['annotations']):
            text=a['text']
            if not any(k in text for k in ('涵','渠','管','闸','泵','沟','路','池','井','塘','步','墩')):continue
            point=a['page_point_pt'];x,y=point[0]*5000/w,point[1]*3536/h
            if not any(x0<=x<=x1 and y0<=y<=y1 for x0,y0,x1,y1 in bounds[slug]):
                excluded.append({'drawing':slug,'native_index':j,'text':text,'reason':'Outside visually reviewed project drawing extents; may be legend/table/title or unresolved text transform'})
                continue
            records.append({'evidence_id':f'ANNOTATION-{slug}-{j:03}','asset_id':d['asset_id'],'text_original':text,'source_file':d['source_file'],'source_hash':d['source_hash'],'source_page':1,'source_position_pt':point,'position_role':'text_baseline_anchor_not_facility_location','source_matrix':{'cm':a['cm'],'tm':a['tm'],'font_size_original':a['font_size_original']},'source_bbox_pt':None,'bbox_status':'font_outline_bounds_not_available_from_native_text_visitor','identity_status':'annotation_evidence_only_not_unique_facility','documented_dimensions':re.findall(r'\d+(?:\.\d+)?\s*(?:kw|kW|m|米|亩|mm)',text),'coordinate_system':'PDF_LANDSCAPE_LOCAL','coordinate_units':'pt'})
    result={'schema_version':'facility-evidence/1','scope':'Every native text annotation containing a facility keyword within the visually reviewed drawing extents. Vector-outlined text remains visible in full original drawing images; this ledger is not an exhaustive semantic OCR of outlined labels.','native_annotation_count':sum(len(g['annotations']) for g in native),'facility_annotation_count':len(records),'unique_facility_count':None,'records':records,'excluded':excluded}
    (OUT/'facility-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result

def build_facility_label_points(drawings,ledger):
    records=[];drawings_by_id={d['asset_id']:d for d in drawings}
    for a in ledger['records']:
        text=a['text_original']
        if not any(k in text for k in ('太阳能智能闸','一体化泵','PE管','污水池')):continue
        d=drawings_by_id[a['asset_id']];x,y=a['source_position_pt'];bbox=[x-5,y-10,x+65,y+6]
        facility_type='gate' if '闸' in text else 'pump' if '泵' in text else 'pipe' if '管' in text else 'wastewater_basin'
        sid=a['evidence_id'].replace('ANNOTATION-','DRAW-LABEL-')
        records.append({'representation_id':sid,'source_representation_id':sid,'asset_id':d['asset_id'],'source_key':f'drawing:lianghuqing-asbuilt:{a["evidence_id"]}','original_code':None,'label':text+'（图纸标注位置）','kind':'facility','facility_type':facility_type,'region':d['label'],'geometry':{'type':'Point','coordinates':[x,y]},'geometry_role':'source_label_anchor','boundary_status':'boundary_unknown','link_verified':False,'identity_scope':'drawing_annotation_not_verified_unique_asset','source_file':d['source_file'],'source_hash':d['source_hash'],'source_page':1,'source_bbox_pt':bbox,'source_evidence':[{'evidence_id':a['evidence_id'],'source_file':d['source_file'],'source_sha256':d['source_hash'],'page':1,'bbox_pt':bbox,'bbox_role':'review_window_around_exact_native_text_baseline','bbox_coordinate_system':'PDF_LANDSCAPE_LOCAL','source_text':text,'source_matrix':a['source_matrix'],'method':'Exact native text baseline anchor; facility footprint/location not inferred from leader line'}],'coordinate_system':'PDF_LANDSCAPE_LOCAL','coordinate_units':'pt','model_area_m2':None,'model_area_units2':None,'documented_dimensions':[{'source_text':text,'status':'as_labelled_not_survey_verified'}],'model_assumptions':[],'crs':None,'elevation_datum':None})
    d=drawings[0];w,h=d['page_size_pt'];p=[2970*w/5000,2395*h/3536];bbox=[2900*w/5000,2370*h/3536,3100*w/5000,2440*h/3536]
    records.append({'representation_id':'DRAW-pdf-01-PUMP37-LABEL','source_representation_id':'DRAW-pdf-01-PUMP37-LABEL','asset_id':d['asset_id'],'source_key':'drawing:lianghuqing-asbuilt:pdf-01:PUMP37-LABEL','original_code':'新建泵站-1','label':'新建泵站-1（37kW，图纸标注位置）','kind':'facility','facility_type':'pump','region':d['label'],'geometry':{'type':'Point','coordinates':p},'geometry_role':'source_label_anchor','boundary_status':'boundary_unknown','link_verified':False,'identity_scope':'drawing_annotation_not_verified_unique_asset','source_file':d['source_file'],'source_hash':d['source_hash'],'source_page':1,'source_bbox_pt':bbox,'source_evidence':[{'source_file':d['source_file'],'source_sha256':d['source_hash'],'page':1,'bbox_pt':bbox,'bbox_coordinate_system':'PDF_LANDSCAPE_LOCAL','source_text':'新建泵站-1(37kw) 泵房设备-3','method':'Manual visual review of source vector-outlined label beside 清-17; point is label anchor, not building footprint'}],'coordinate_system':'PDF_LANDSCAPE_LOCAL','coordinate_units':'pt','model_area_m2':None,'model_area_units2':None,'documented_dimensions':[{'source_text':'37kw','value':37,'unit':'kW','status':'as_labelled_not_survey_verified'}],'model_assumptions':[],'crs':None,'elevation_datum':None})
    return records
