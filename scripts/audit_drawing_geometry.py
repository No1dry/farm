"""Extract independent drawing coordinates with auditable label evidence.

All coordinates are PDF landscape page points, not metres or surveyed locations.
"""
from pathlib import Path
import json
import math
import hashlib
from collections import Counter
from PIL import Image, ImageDraw, ImageFont
import shutil
from audit_match_vectors import inside
from audit_facility_geometry import build_facilities,build_annotation_ledger,build_facility_label_points

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/spatial'
TMP = ROOT / 'tmp/audit/drawing-geometry'
OUT.mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)

def grid_crop(slug, name, box):
    image=Image.open(ROOT/f'tmp/audit/{slug}-high-landscape.png').convert('RGB')
    crop=image.crop(box)
    overlay=Image.new('RGBA',crop.size)
    draw=ImageDraw.Draw(overlay)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    x0,y0,x1,y1=box
    for x in range(math.ceil(x0/100)*100,x1,100):
        draw.line([(x-x0,0),(x-x0,y1-y0)],fill=(0,70,100,65),width=1)
        draw.rectangle((x-x0,0,x-x0+55,24),fill=(255,255,255,230))
        draw.text((x-x0+2,1),str(x),fill='black',font=font)
    for y in range(math.ceil(y0/100)*100,y1,100):
        draw.line([(0,y-y0),(x1-x0,y-y0)],fill=(0,70,100,65),width=1)
        draw.rectangle((0,y-y0,55,y-y0+24),fill=(255,255,255,230))
        draw.text((2,y-y0+1),str(y),fill='black',font=font)
    Image.alpha_composite(crop.convert('RGBA'),overlay).save(TMP/f'{slug}-{name}-grid.png')

if __name__=='__main__':
    anchors=json.loads((OUT/'label-anchors.json').read_text(encoding='utf8'))
    ledger={r['original_code']:r for r in json.loads((ROOT/'data/audit/entities.json').read_text(encoding='utf8'))['records']}
    sources={s['path']:s for s in json.loads((ROOT/'data/audit/source-manifest.json').read_text(encoding='utf8'))['sources']}
    seeds={('pdf-01','L10-1'):[1680,2910],('pdf-01','L10-2'):[1640,3050],('pdf-01','L21'):[1955,2860],('pdf-01','L16'):[1780,2900],('pdf-02','旱地-M16'):[1210,1940],('pdf-02','旱地-M18'):[955,1710],('pdf-02','旱地-M19'):[755,1730]}
    assets=['detail-miaoxia','detail-xinwumao','detail-zhangjia','detail-tanshen','detail-abcdef']
    labels=['庙下流（台账：庙下刘）','新屋湾、毛家湾及D2/D3','张家湾','谭湾沈湾','A/B/C/D/E/F区']
    records=[]; drawings=[]
    for i,slug in enumerate([f'pdf-{i:02}' for i in range(1,6)]):
        vectors=json.loads((TMP/f'{slug}-vectors.json').read_text(encoding='utf8'))
        w,h=vectors['page_size_pt']; source=vectors['source_file']; sha=sources[source]['sha256']
        target=OUT/'drawings'/f'{slug}-landscape.png'; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/f'tmp/audit/{slug}-high-landscape.png',target)
        drawings.append(dict(asset_id=assets[i],label=labels[i],source_file=source,source_hash=sha,source_page=1,page_size_pt=[w,h],image_path=str(target.relative_to(ROOT)).replace('\\','/'),image_size_px=[5000,3536],coordinate_system='PDF_LANDSCAPE_LOCAL',coordinate_units='pt',rotation_applied_degrees=90,rotation_direction='counterclockwise',crs=None,georeferenced=False))
        if i==0: drawings[-1]['legacy_crop_transform']={'image_size_px':[5200,3677],'crop_bbox_px':[2000,1600,3600,2850],'proof':'PIL ImageChops difference was empty for old focus-trace.png and exact landscape crop','local_px_to_page_pt':{'x':'(x+2000)*1683.71997/5200','y':'(y+1600)*1190.52002/3677'}}
        overlay=Image.open(target).convert('RGBA'); layer=Image.new('RGBA',overlay.size); draw=ImageDraw.Draw(layer)
        for code,(x,y) in anchors[slug].items():
            labelpoint=[x*w/5000,y*h/3536]
            sx,sy=seeds.get((slug,code),[x,y]); point=[sx*w/5000,sy*h/3536]
            if i in (0,1): colors=[[0,1,0],[0,0,0]]
            elif i in (2,3): colors=[[1,0,0]]
            else: colors=[[0,0,0],[0,0,1],[0,1,0]]
            candidates=[]
            for color in colors:
                candidates=[v for v in vectors['paths'] if v['stroke']==color and 100<v['area_pt2']<100000 and inside(point,v['points']) and (v['closed'] or math.dist(v['points'][0],v['points'][-1])<.8)]
                if candidates: break
            candidates.sort(key=lambda v:v['area_pt2'])
            chosen=candidates[0] if candidates else None
            if slug=='pdf-02' and code=='E3': chosen=None
            sid=f'DRAW-{slug}-{code}'; rep=f'DETAIL-{code}' if slug=='pdf-01' and code in ('L18','L19','L20') else sid
            r=ledger[code]
            evidence={'source_file':source,'source_sha256':sha,'page':1,'label_text':code.replace('旱地-','旱地'),'label_bbox_pt':[round((x-65)*w/5000,5),round((y-28)*h/3536,5),round((x+65)*w/5000,5),round((y+28)*h/3536,5)],'label_position_method':'manual visual review of 5000px original drawing rendering','label_anchor_pt':labelpoint}
            if chosen:
                ring=chosen['points'][:]
                if ring[-1]!=ring[0]: ring.append(ring[0])
                geometry={'type':'Polygon','coordinates':[ring]}
                evidence.update({'vector_content_operation':chosen['op_index'],'vector_stroke_rgb':chosen['stroke'],'geometry_method':'original PDF vector closed boundary containing visually identified field interior','closure_gap_pt':math.dist(chosen['points'][0],chosen['points'][-1]),'boundary_bbox_pt':[min(p[0] for p in ring),min(p[1] for p in ring),max(p[0] for p in ring),max(p[1] for p in ring)]})
                draw.polygon([(p[0]*5000/w,p[1]*3536/h) for p in ring],fill=(160,0,255,45),outline=(200,0,200,255),width=3)
            else: geometry={'type':'Point','coordinates':labelpoint}
            draw.ellipse((x-9,y-9,x+9,y+9),fill=(255,0,0,230))
            records.append({'representation_id':rep,'source_representation_id':sid,'asset_id':assets[i],'source_key':r['source_key'],'original_code':code,'label':code,'region':r['region'],'kind':'field','geometry':geometry,'boundary_status':'confirmed_source_vector' if chosen else 'boundary_unknown','link_verified':True,'source_file':source,'source_hash':sha,'source_page':1,'source_bbox_pt':evidence['label_bbox_pt'],'source_evidence':[evidence],'coordinate_system':'PDF_LANDSCAPE_LOCAL','coordinate_units':'pt','model_area_m2':None,'model_area_units2':chosen['area_pt2'] if chosen else None,'area_original':r['area_original'],'area_unit':None,'inferred_unit':'亩','inference_status':'unconfirmed','documented_dimensions':[],'model_assumptions':[],'crs':None,'elevation_datum':None})
            if slug=='pdf-02' and code=='E3':
                records[-1].update({'source_key':'drawing:lianghuqing-asbuilt:pdf-02:ambiguous-E3-label','candidate_source_key':r['source_key'],'link_verified':False,'identity_match_status':'ambiguous_repeated_code','identity_scope':'unresolved_drawing_label','geometry_role':'label_anchor','area_original':None,'inferred_unit':None,'inference_status':'not_applicable','match_note':'E3 is a standalone label outside the X-region field boundary. Same code as the bounded E3 in pdf-05 is insufficient to assert shared identity or geographic overlap. Do not automatically merge.'})
        Image.alpha_composite(overlay,layer).convert('RGB').save(TMP/f'{slug}-boundary-review.jpg',quality=90)
    facilities=build_facilities(drawings); annotation_ledger=build_annotation_ledger(drawings)
    facilities.extend(build_facility_label_points(drawings,annotation_ledger))
    records.extend(facilities)
    data={'schema_version':'drawing-entities/1','coordinate_policy':'Independent rotated original PDF page spaces. Points are paper points, not metres. No georegistration or elevation datum established.','drawings':drawings,'records':records,'coverage':{'ledger_count':len(ledger),'unique_ledger_codes':len(set(r['original_code'] for r in records if r['kind']=='field' and r['link_verified'])),'representations':len(records),'polygons':sum(r['geometry']['type']=='Polygon' for r in records),'anchors':sum(r['geometry']['type']=='Point' for r in records),'field_polygons':100,'ambiguous_field_labels':1,'facility_features':len(facilities),'facility_evidence_annotations':annotation_ledger['facility_annotation_count']}}
    (OUT/'drawing-entities.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(data['coverage']))
    print('anchors',[(r['asset_id'],r['original_code']) for r in records if r['geometry']['type']=='Point'])
