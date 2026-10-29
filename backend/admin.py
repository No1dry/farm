"""Administrator-only preview/apply imports, with optimistic revisions and receipts."""
from datetime import datetime,timezone
import json
from uuid import uuid4
from .store import canonical,digest,now,validate_dataset
from .validation import validate_record


def validate_records(records,dataset):
    validate_dataset(dataset)
    if not records or len(records)>500:raise ValueError('Import must contain 1–500 records')
    seen=set()
    for record in records:
        validate_record(record,dataset)
        key=canonical([record['source_id'],record['source_key']])
        if key in seen:raise ValueError('Duplicate source key within import')
        seen.add(key)
        value=record.get('area_original')
        if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or value<0):raise ValueError('Invalid area')
        if dataset=='real' and record.get('data_nature') in ('test','synthetic'):raise ValueError('Synthetic records cannot enter real dataset')
        if record.get('resource_id') or record.get('knowledge') or record.get('rules') or record.get('extra_sources'):
            raise ValueError('Administrative record API cannot assign UUIDs or publish trusted knowledge/rules')


def preview(store,dataset,records,actor):
    validate_records(records,dataset)
    from .semantics import preview_validation
    semantic=preview_validation(store,dataset,records)
    identifier=str(uuid4());baseline={};content=digest({'dataset':dataset,'records':records})
    with store.connection() as db:
        for record in records:
            row=db.execute('''SELECT e.revision FROM entities e JOIN source_systems s ON e.source_id=s.id
                WHERE e.dataset=? AND s.source_key=? AND e.canonical_key=?''',(dataset,record['source_id'],record['source_key'])).fetchone()
            baseline[canonical([record['source_id'],record['source_key']])]=row['revision'] if row else 0
        db.execute('INSERT INTO import_previews VALUES (?,?,?,?,?,?,?,?,?)',
            (identifier,dataset,canonical(records),content,canonical(baseline),actor['id'],now(),'preview',None))
    store.audit('imports.preview',dataset,{'preview_id':identifier,'actor_id':actor['id'],'record_count':len(records),'content_digest':content})
    return {'id':identifier,'dataset':dataset,'content_digest':content,'record_count':len(records),'state':'preview',
            'new_records':sum(v==0 for v in baseline.values()),'updated_records':sum(v>0 for v in baseline.values()),
            'expires_in_seconds':1800,'requires_explicit_apply':True,'semantic_validation':semantic}


def apply(store,preview_id,content_digest,actor):
    from .semantics import preview_validation
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM import_previews WHERE id=?',(preview_id,)).fetchone()
        if row is None:raise KeyError('Unknown preview')
        if row['content_digest']!=content_digest:raise ValueError('STALE_PREVIEW: digest mismatch')
        if row['state']=='applied':return json.loads(row['receipt'])
        records=json.loads(row['payload'])
        validate_records(records,row['dataset'])
        # Hold the writer lock while revalidating the current graph and applying the same records.
        if not preview_validation(store,row['dataset'],records)['conforms']:
            raise ValueError('Import fails pinned upstream SHACL constraints')
        if (datetime.now(timezone.utc)-datetime.fromisoformat(row['created_at'])).total_seconds()>1800:
            raise ValueError('STALE_PREVIEW: preview expired')
        receipt=store.import_records(records,row['dataset'],db_connection=db,expected_revisions=json.loads(row['baseline']))
        receipt.update(preview_id=preview_id,state='applied',actor_id=actor['id'])
        db.execute('UPDATE import_previews SET state=?,receipt=? WHERE id=?',('applied',canonical(receipt),preview_id))
        db.execute('INSERT INTO audit_log VALUES (?,?,?,?,?)',(str(uuid4()),now(),'imports.apply',row['dataset'],
            canonical({'preview_id':preview_id,'actor_id':actor['id'],'resource_ids':[x['id'] for x in receipt['items']]})))
    return receipt
