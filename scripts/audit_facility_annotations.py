"""Preserve every extractable native drawing annotation with its original matrix."""
from pathlib import Path
import json, re
from pypdf import PdfReader
from audit_pdf_vectors import concat,transform
ROOT=Path(__file__).resolve().parents[1]
def extract():
    out=[]
    for i,pdf in enumerate(sorted((ROOT/'现场竣工图pdf版本').glob('*.pdf')),1):
        page=PdfReader(pdf).pages[0]; W,H=float(page.mediabox.width),float(page.mediabox.height)
        rows=[]
        def visitor(text,cm,tm,font,size):
            text=text.strip()
            if not text:return
            x,y=transform((0,0),concat(cm,tm))
            rows.append({'text':text,'page_point_pt':[H-y,W-x],'font_size_original':size,'cm':cm,'tm':tm})
        page.extract_text(visitor_text=visitor)
        out.append({'slug':f'pdf-{i:02}','source_file':pdf.relative_to(ROOT).as_posix(),'page':1,'annotations':rows})
        print(i,len(rows),[r['text'] for r in rows[:15]],flush=True)
    (ROOT/'data/spatial/native-annotations.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':extract()
