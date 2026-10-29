"""Exports project review artifacts from persisted identities, never recomputes UUIDs."""
import csv
import json
from pathlib import Path
from .contracts import UPSTREAM
from .store import now


def export_mappings(store,output_dir):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    entities=[];areas=[]
    for dataset in ('real','demo'):
        for item in store.list_entities(dataset,limit=10000)['items']:
            entities.append({'dataset':dataset,'resource_id':item['id'],'iri':item['iri'],'revision':item['revision'],
                'code':item['code'],'name':item['name'],'kind':item['kind'],'region':item['region'],
                'source_key':item['source_key'],'spatial_ids':item['spatial_ids'],
                'evidence_ids':[s['id'] for s in item['sources']],'data_nature':item['data_nature']})
            if dataset=='real' and (item['area']['value'] is not None or item['model_areas']):
                models=item['model_areas'] or [{'spatial_id':None,'area_m2':None,'precision':None}]
                for model in models:
                    areas.append({'resource_id':item['id'],'code':item['code'],'spatial_id':model['spatial_id'],
                        'ledger_value':item['area']['value'],'ledger_unit':item['area']['unit'],
                        'ledger_inferred_unit':item['area']['inferred_unit'],'model_area_m2':model['area_m2'],
                        'model_area_units2':model.get('area_units2'),'model_source_unit':model.get('source_unit'),
                        'model_area_units2':model.get('area_units2'),'model_coordinate_unit':model.get('source_unit'),
                        'model_precision':model['precision'],'comparable':False,'difference_m2':None,
                        'reason':'台账单位未确认或模型未测绘配准；不得换算比较或合计模型与台账面积。'})
    stamp=now()
    def write(name,value):
        (output_dir/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    write('entity-mapping.json',{'schema_version':'farm-entity-mapping/1','exported_at':stamp,
        'identity_source':'Persisted SQLite mapping; do not regenerate IDs from this file. Restore database backup to preserve identity.',
        'upstream':UPSTREAM,'entities':entities})
    write('ledger-model-area-reconciliation.json',{'schema_version':'farm-area-review/1','exported_at':stamp,
        'ledger_raw_total':store.summary('real')['area']['raw_total'],'ledger_unit':None,
        'notes':['同一实体的多种模型表示不重复累计。','台账总计不与片区工程量或示意模型面积相加。'], 'records':areas})
    with (output_dir/'ledger-model-area-reconciliation.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        if areas:
            writer=csv.DictWriter(stream,fieldnames=list(areas[0]));writer.writeheader();writer.writerows(areas)
    return {'entities':len(entities),'area_records':len(areas),'output_directory':str(output_dir)}
