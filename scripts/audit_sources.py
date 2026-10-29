"""Read-only source extraction. Writes reproducible audit intermediates, never sources.

Install requirements-audit.txt; use POPPLER_BIN or a pdftoppm on PATH.
The optional local tmp/.audit-deps directory supports this workspace's runtime.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tmp' / '.audit-deps'))
import xlrd
from pypdf import PdfReader
from PIL import Image

OUT = ROOT / 'data' / 'audit'
PREVIEW = ROOT / 'tmp' / 'audit'
OUT.mkdir(parents=True, exist_ok=True)
PREVIEW.mkdir(parents=True, exist_ok=True)
def resolve_pdftoppm():
    """Prefer an explicit Poppler installation, then PATH, then bundled runtime."""
    executable = 'pdftoppm.exe' if os.name == 'nt' else 'pdftoppm'
    configured = os.environ.get('POPPLER_BIN')
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_dir():
            candidate = candidate / executable
        if not candidate.is_file():
            raise FileNotFoundError(f'POPPLER_BIN does not contain pdftoppm: {candidate}')
        return candidate
    on_path = shutil.which('pdftoppm')
    if on_path:
        return Path(on_path)
    bundled = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin' / executable
    if bundled.is_file():
        return bundled
    raise FileNotFoundError('pdftoppm not found. Install Poppler and set POPPLER_BIN to its bin directory, or add it to PATH.')

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def relative(path):
    return path.relative_to(ROOT).as_posix()

def main():
    pdftoppm = resolve_pdftoppm()
    sources = []
    source_paths = sorted(list(ROOT.glob('*.xls')) + list((ROOT / '现场竣工图pdf版本').glob('*.pdf')) + list((ROOT / '参考图').glob('*')))
    for path in source_paths:
        if not path.is_file():
            continue
        record = {'path': relative(path), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'evidenceClass': 'user-supplied-source'}
        if path.suffix.lower() == '.xls':
            book = xlrd.open_workbook(str(path), formatting_info=True)
            sheets = []
            for sheet in book.sheets():
                rows = [{'row': i + 1, 'values': sheet.row_values(i)} for i in range(sheet.nrows)]
                sheets.append({'name': sheet.name, 'nrows': sheet.nrows, 'ncols': sheet.ncols, 'merged_cells': sheet.merged_cells, 'rows': rows})
            write_json(OUT / 'workbook-raw.json', {'source': record, 'sheets': sheets, 'reader': 'xlrd (cached values; no source recalculation or formula audit)'})
            record['sheets'] = [{'name': s['name'], 'nrows': s['nrows'], 'ncols': s['ncols']} for s in sheets]
        elif path.suffix.lower() == '.pdf':
            reader = PdfReader(str(path))
            pages = []
            slug = f'pdf-{sum(1 for s in sources if "pages" in s) + 1:02d}'
            for index, page in enumerate(reader.pages):
                text_path = OUT / f'{slug}-page-{index+1:02d}.txt'
                extracted = page.extract_text() or ''
                text_path.write_text(extracted, encoding='utf-8')
                pages.append({'page': index + 1, 'mediaBoxPoints': [float(n) for n in page.mediabox], 'rotation': page.get('/Rotate', 0), 'extractedTextCharacters': len(extracted), 'textPath': relative(text_path)})
                preview_path = PREVIEW / f'{slug}-page-{index+1:02d}'
                subprocess.run([str(pdftoppm), '-f', str(index+1), '-singlefile', '-scale-to', '2400', '-png', str(path), str(preview_path)], check=True, capture_output=True)
                pages[-1]['previewPath'] = relative(preview_path.with_suffix('.png'))
            record.update({'pages': pages, 'pageCount': len(pages), 'slug': slug})
        elif path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
            with Image.open(path) as img:
                record.update({'width': img.width, 'height': img.height, 'exifPresent': bool(img.getexif())})
        sources.append(record)
    write_json(OUT / 'source-manifest.json', {'sources': sources, 'coverage': {'sourceFiles': len(sources), 'pdfFiles': sum('pages' in s for s in sources), 'pdfPages': sum(s.get('pageCount', 0) for s in sources)}})
    print(json.dumps({'sources': len(sources), 'pdfPages': sum(s.get('pageCount',0) for s in sources), 'output': relative(OUT)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
