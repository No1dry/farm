"""Normalize source rows without assigning business UUIDs or inventing geometry."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal
import csv
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'audit'

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def main():
    raw = json.loads((OUT / 'workbook-raw.json').read_text(encoding='utf-8'))
    sheet = raw['sheets'][0]
    source = raw['source']
    records = []
    groups = defaultdict(list)
    for row in sheet['rows'][3:-1]:
        region, code, area, notes = row['values']
        record = {
            'source_system': 'lianghuqing-asbuilt',
            'source_instance': 'workbook-area-register',
            'collection': sheet['name'],
            'source_pk': {'code': code},
            'source_key': f"xls:workbook-area-register:{sheet['name']}:{code}",
            'record_id': code,
            'original_code': code,
            'resource_id': None,
            'region': region,
            'entity_type': 'field',
            'evidence_class': 'source-record',
            'area_original': area,
            'area_unit': None,
            'inferred_unit': '亩',
            'inference_status': 'unconfirmed',
            'inference_basis': 'Associated drawing area notes use 亩; the workbook header, formats and notes do not state a unit.',
            'geometry': None,
            'geometry_status': 'unlocated',
            'source_file': source['path'],
            'source_sheet': sheet['name'],
            'source_row': row['row'],
            'source_cell': f"C{row['row']}",
            'source_range': f"A{row['row']}:D{row['row']}",
            'source_sha256': source['sha256'],
            'source_updated_label': '2026年07月更新',
            'notes': notes,
            'operational_status': None,
            'crop': None,
            'telemetry': None,
            'drawing_match_status': 'same-code-candidate-not-georeferenced',
        }
        records.append(record)
        groups[region].append(record)
    assert len(records) == 100
    assert len({r['source_key'] for r in records}) == 100
    detail_sum = sum((Decimal(str(r['area_original'])) for r in records), Decimal(0))
    assert detail_sum == Decimal('1010.99')
    controls = [{'region': region, 'count': len(values), 'sum_original': float(sum(Decimal(str(v['area_original'])) for v in values)), 'area_unit': None, 'source_rows': [min(v['source_row'] for v in values), max(v['source_row'] for v in values)]} for region, values in groups.items()]
    save('entities.json', {'schema_version': 'audit-source-records/1', 'identity_policy': 'No business UUID assigned here. Importer persists UUIDv4 against stable canonical source key.', 'source': source, 'records': records})
    save('area-reconciliation.json', {
        'unit_status': 'source-unit-unspecified',
        'detail_count': len(records), 'unique_original_codes': len({r['original_code'] for r in records}),
        'detail_range': '全域田块面积汇总!A4:D103', 'total_cell': '全域田块面积汇总!C104',
        'detail_sum_original': float(detail_sum), 'source_total_cached': sheet['rows'][-1]['values'][2],
        'rounded_source_total': round(sheet['rows'][-1]['values'][2], 2), 'difference_at_source_precision': 0,
        'total_row_excluded_from_details': True, 'duplicate_codes': [], 'regions': controls,
        'empty_sheets': [s['name'] for s in raw['sheets'] if s['nrows'] == 0],
        'calculation_method': 'Decimal sum of the 100 numeric detail rows; source total is a cached value, no Excel recalculation performed.',
        'drawing_comparisons': [
            {'region': '庙下刘', 'source_sum_original': 151.76, 'drawing_leveled_area_mu': 151.45, 'numeric_delta_if_unit_mu_and_scope_equal': 0.31, 'status': 'unresolved-unit-version-scope', 'drawing_construction_area_mu': 262.79},
            {'region': '新屋湾', 'source_sum_original': 51.62, 'drawing_leveled_area_mu': 69.92, 'status': 'not-directly-comparable', 'reason': 'The drawing also shows D2 and D3, and an E3 label. Workbook region and drawing scope differ.', 'drawing_construction_area_mu': 122.90},
            {'region': '毛家湾', 'source_sum_original': 72.87, 'drawing_leveled_area_mu': 74.13, 'numeric_delta_if_unit_mu_and_scope_equal': -1.26, 'status': 'unresolved-unit-version-scope', 'drawing_construction_area_mu': 144.17},
            {'region': '张家湾', 'source_sum_original': 47.87, 'drawing_construction_area_mu': 61.2, 'status': 'different-area-definitions'},
            {'region': '谭湾沈湾', 'source_sum_original': 40.69, 'drawing_construction_area_mu': 54.8, 'status': 'different-area-definitions'},
        ],
        'repeated_land_acceptance_table': {'pdf_slugs': ['pdf-01','pdf-02','pdf-03','pdf-04'], 'unit': '公顷', 'table_title': '验收明细表 / 土地利用现状表', 'total_area_ha': 44.1193, 'water_field_after_ha': 23.1558, 'dry_land_after_ha': 20.96349, 'new_water_field_area_ha': 23.15581, 'add_across_pdfs': False, 'reason': 'Same project-level table is repeated; it is not four separate region totals.'}
    })
    with (OUT / 'entities.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        fields = ['source_key','original_code','region','area_original','area_unit','inferred_unit','inference_status','source_file','source_sheet','source_row','source_cell','source_sha256','geometry_status','evidence_class']
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)
    print(json.dumps({'records':len(records), 'area_sum_original':float(detail_sum), 'area_unit':None}, ensure_ascii=False))

if __name__ == '__main__':
    main()
