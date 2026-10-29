import json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TMP=ROOT/'tmp/audit/drawing-geometry'
def inside(point,ring):
    x,y=point; flag=False
    for (x1,y1),(x2,y2) in zip(ring,ring[1:]+ring[:1]):
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1: flag=not flag
    return flag
if __name__=='__main__':
    anchors=json.loads((ROOT/'data/spatial/label-anchors.json').read_text(encoding='utf8'))
    for slug,group in anchors.items():
        if not slug.startswith('pdf-'): continue
        vectors=json.loads((TMP/f'{slug}-vectors.json').read_text(encoding='utf8'))
        w,h=vectors['page_size_pt']
        print(slug)
        for code,(x,y) in group.items():
            p=[x*w/5000,y*h/3536]
            found=[v for v in vectors['paths'] if v['area_pt2']>200 and inside(p,v['points']) and (v['closed'] or math.dist(v['points'][0],v['points'][-1])<.8)]
            found.sort(key=lambda v:v['area_pt2'])
            print(code, [(v['op_index'],round(v['area_pt2']),v['stroke'],v['fill'],v['op'],len(v['points'])) for v in found[:5]])
