"""Extract source vector paths from CAD PDF content, without geometry inference."""
import json, math
from pathlib import Path
from collections import Counter
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
TMP=ROOT/'tmp/audit/drawing-geometry'

def transform(p,m):
    x,y=p; a,b,c,d,e,f=m
    return (a*x+c*y+e,b*x+d*y+f)

def concat(m,n):
    a,b,c,d,e,f=m; A,B,C,D,E,F=n
    return (a*A+c*B,b*A+d*B,a*C+c*D,b*C+d*D,a*E+c*F+e,b*E+d*F+f)

def area(r):
    return abs(sum(x*y1-x1*y for (x,y),(x1,y1) in zip(r,r[1:]+r[:1]))/2)

def extract(pdf):
    page=PdfReader(pdf).pages[0]; W,H=float(page.mediabox.width),float(page.mediabox.height)
    m=(1,0,0,1,0,0); fill=None; stroke=None; stack=[]; paths=[]; sub=[]; result=[]
    def point(v):
        x,y=transform(tuple(map(float,v)),m)
        return [round(H-y,5),round(W-x,5)]
    for ix,(args,op) in enumerate(page.get_contents().operations):
        if op==b'q': stack.append((m,fill,stroke))
        elif op==b'Q':
            if stack: m,fill,stroke=stack.pop()
        elif op==b'cm': m=concat(m,tuple(map(float,args)))
        elif op==b'rg': fill=list(map(float,args))
        elif op==b'RG': stroke=list(map(float,args))
        elif op==b'g': fill=[float(args[0])]*3
        elif op==b'G': stroke=[float(args[0])]*3
        elif op==b'm':
            if sub: paths.append(sub)
            sub=[point(args)]
        elif op==b'l': sub.append(point(args))
        elif op==b're':
            x,y,w,h=map(float,args)
            if sub: paths.append(sub)
            sub=[point([x,y]),point([x+w,y]),point([x+w,y+h]),point([x,y+h]),point([x,y])]
        elif op==b'h':
            if sub and sub[-1]!=sub[0]: sub.append(sub[0])
        elif op in (b'S',b's',b'f',b'F',b'f*',b'B',b'B*',b'b',b'b*',b'n'):
            if sub: paths.append(sub)
            if op!=b'n':
                for path in paths:
                    if len(path)>=3:
                        ar=area(path); closed=path[0]==path[-1]
                        if ar>5:
                            result.append(dict(op_index=ix,op=op.decode(),fill=fill,stroke=stroke,closed=closed,area_pt2=round(ar,4),points=path))
            paths=[];sub=[]
    return dict(source_file=str(pdf.relative_to(ROOT)).replace('\\','/'),page_size_pt=[H,W],paths=result)

if __name__=='__main__':
    for i,pdf in enumerate(sorted((ROOT/'现场竣工图pdf版本').glob('*.pdf')),1):
        data=extract(pdf)
        (TMP/f'pdf-{i:02}-vectors.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
        major=[p for p in data['paths'] if p['area_pt2']>300]
        print(i,len(data['paths']),len(major),Counter(str(p['stroke']) for p in major),flush=True)
