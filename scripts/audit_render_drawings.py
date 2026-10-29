"""Rebuild 5000px landscape evidence images from all five source PDFs."""
from pathlib import Path
import subprocess
from PIL import Image
from audit_sources import resolve_pdftoppm
ROOT=Path(__file__).resolve().parents[1]
def main():
    binary=resolve_pdftoppm()
    for i,pdf in enumerate(sorted((ROOT/'现场竣工图pdf版本').glob('*.pdf')),1):
        prefix=ROOT/f'tmp/audit/pdf-{i:02}-high-portrait'
        prefix.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run([str(binary),'-f','1','-singlefile','-scale-to','5000','-png',str(pdf),str(prefix)],check=True)
        image=Image.open(prefix.with_suffix('.png')).rotate(90,expand=True)
        if image.size!=(5000,3536):raise ValueError(f'Unexpected drawing dimensions {image.size}; anchors require explicit re-review')
        image.save(ROOT/f'tmp/audit/pdf-{i:02}-high-landscape.png')
        print(pdf.name,image.size,flush=True)
if __name__=='__main__':main()
