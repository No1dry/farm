"""Transactional SQLite persistence. Imports are local administrative commands only."""
from collections import Counter, defaultdict
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import re
from uuid import UUID, uuid4

from .contracts import ONTOLOGY, UPSTREAM, SourceKey, object_iri, entity_class_iris
from .validation import validate_record


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_dataset(value):
    if value not in ('real', 'demo'):
        raise ValueError('dataset must be real or demo')


def alerts_for(entity):
    alerts = []
    def add(code, message, severity='notice',metric=None):
        alerts.append({'code':code, 'message':message, 'severity':severity, 'entity_id':entity['id'], 'data_nature':entity['data_nature'],'category':'quality','status':'needs_review','metric':metric})
    operational = entity['kind'] in ('field','pond','orchard')
    if entity['area']['value'] is not None and not entity['area']['unit']:
        add('unconfirmed_area_unit','台账面积未标注单位，不能直接作为亩累计。')
    if operational and not entity['devices']:
        add('missing_devices','未发现已登记的现场设备，无法判断实时运行状态。')
    if operational and not entity['observations']:
        add('missing_observations','缺少观测记录，不能判断当前农情或水情。')
    units = defaultdict(set)
    current = datetime.now(timezone.utc)
    for obs in entity['observations']:
        metric = obs.get('metric', 'unknown')
        units[metric].add(obs.get('unit'))
        try:
            sampled = datetime.fromisoformat(obs['observed_at'].replace('Z','+00:00'))
            if sampled.tzinfo is None:
                raise ValueError('timezone missing')
            age = (current-sampled).total_seconds()
            if age > obs.get('stale_after_hours',24)*3600:
                add('stale_observation',f'{metric} 观测已超过有效时限。', 'warning',metric)
            elif age < -300:
                add('future_observation',f'{metric} 观测时间晚于系统时间。', 'warning',metric)
        except (KeyError, TypeError, ValueError):
            add('invalid_observation_time',f'{metric} 缺少有效时区时间，不能作为实时依据。','warning',metric)
    for metric, values in units.items():
        if len(values)>1:
            add('unit_conflict',f'{metric} 存在不同单位，尚未确认换算规则。','warning',metric)
    if entity['kind']=='pond' and not entity.get('species'):
        add('missing_species','缺少鱼种和养殖阶段，不能生成物种专属建议。')
    return alerts


def business_alerts_for(entity, rules):
    """Evaluate explicitly registered rules; no universal agronomic thresholds."""
    output=[]
    for rule in rules:
        matches=[o for o in entity['observations'] if o.get('metric')==rule['metric']]
        latest=max(matches,key=lambda o:o.get('observed_at','')) if matches else None
        codes={a['code'] for a in entity['quality_alerts'] if a.get('metric')==rule['metric']}
        valid=latest is not None and latest.get('unit')==rule['unit']
        met=bool(valid and rule.get('operator')=='lt' and float(latest['value'])<rule['threshold'])
        stale='stale_observation' in codes
        conflict='unit_conflict' in codes or 'invalid_observation_time' in codes or 'future_observation' in codes
        required=rule.get('requires',[])
        missing=[key for key in required if not entity.get(key) and not entity.get('production_context',{}).get(key)]
        approved=rule.get('production_approved') is True
        status='unknown' if not valid or conflict else 'stale' if stale else 'needs_context' if missing or not approved else 'active' if met else 'normal'
        output.append({'id':rule['id']+':'+entity['id'],'code':rule['id'],'title':rule['name'],
            'message':rule['description'],'category':'business','entity_id':entity['id'],'data_nature':entity['data_nature'],
            'status':status,'severity':'warning' if status=='active' else 'notice','rule_id':rule['id'],
            'rule_version':rule['version'],'triggered_at':latest.get('observed_at') if met else None,
            'condition_historically_met':met,'evidence_ids':rule['evidence_ids'],
            'threshold':rule['threshold'],'unit':rule['unit'],'current_actionable':False,
            'applicability':{'production_approved':approved,'missing_context':missing,'unit_matches':valid,'site_fact_verified':entity['data_nature']=='verified'}})
    return output


class Store:
    def __init__(self, path):
        self._active_connection=ContextVar('store_connection_'+str(id(self)),default=None)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] not in (0,1,2):
                raise ValueError('Unsupported database schema version; no automatic migration performed')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS source_systems (
                id TEXT PRIMARY KEY, dataset TEXT NOT NULL, source_key TEXT NOT NULL,
                UNIQUE(dataset, source_key));
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY, dataset TEXT NOT NULL CHECK(dataset IN ('real','demo')),
                source_id TEXT NOT NULL, canonical_key TEXT NOT NULL, code TEXT NOT NULL,
                name TEXT NOT NULL, region TEXT NOT NULL, kind TEXT NOT NULL,
                payload TEXT NOT NULL, content_digest TEXT NOT NULL, revision INTEGER NOT NULL,
                updated_at TEXT NOT NULL, UNIQUE(dataset,source_id,canonical_key));
            CREATE TABLE IF NOT EXISTS entity_versions (
                entity_id TEXT NOT NULL REFERENCES entities(id), revision INTEGER NOT NULL,
                payload TEXT NOT NULL, recorded_at TEXT NOT NULL, PRIMARY KEY(entity_id,revision));
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY, dataset TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS entity_sources (
                entity_id TEXT NOT NULL REFERENCES entities(id), source_id TEXT NOT NULL REFERENCES sources(id),
                PRIMARY KEY(entity_id,source_id));
            CREATE TABLE IF NOT EXISTS spatial_bindings (
                dataset TEXT NOT NULL, spatial_id TEXT NOT NULL, entity_id TEXT NOT NULL REFERENCES entities(id),
                payload TEXT NOT NULL, PRIMARY KEY(dataset,spatial_id));
            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY, dataset TEXT NOT NULL, subject_id TEXT NOT NULL,
                predicate_iri TEXT NOT NULL, target_id TEXT, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY, dataset TEXT NOT NULL, entity_id TEXT NOT NULL REFERENCES entities(id),
                payload TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, tool TEXT NOT NULL,
                dataset TEXT NOT NULL, payload TEXT NOT NULL);
            ''')
            from .migrations import migrate
            migrate(db)

    @contextmanager
    def connection(self):
        active=self._active_connection.get()
        if active is not None:
            yield active
            return
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def import_records(self, records, dataset, preserve_ids=False, db_connection=None, expected_revisions=None):
        validate_dataset(dataset)
        records = list(records)
        # Validate the complete batch before any identities are allocated.
        for record in records:
            validate_record(record,dataset)
            canonical(record)  # rejects NaN/Infinity at any depth
            area = record.get('area_original')
            if area is not None and (isinstance(area,bool) or not isinstance(area,(int,float)) or area < 0):
                raise ValueError('area must be a finite nonnegative number or null')
            if dataset=='real' and record.get('data_nature') in ('synthetic','test'):
                raise ValueError('synthetic records cannot enter real dataset')
            if preserve_ids and record.get('resource_id'):
                UUID(record['resource_id'])
        results=[]
        with (nullcontext(db_connection) if db_connection is not None else self.connection()) as db:
            if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
            for record in records:
                source_label = str(record['source_id'])
                source_row = db.execute('SELECT id FROM source_systems WHERE dataset=? AND source_key=?',(dataset,source_label)).fetchone()
                source_id = source_row['id'] if source_row else str(uuid4())
                if source_row is None:
                    db.execute('INSERT INTO source_systems VALUES (?,?,?)',(source_id,dataset,source_label))
                key = SourceKey(source_id=source_id, source_system=record.get('source_system','farm-twin'),
                    source_instance=record.get('source_instance',source_label), collection=record.get('source_sheet',source_label),
                    canonical_key=str(record['source_key']))
                existing = db.execute('SELECT * FROM entities WHERE dataset=? AND source_id=? AND canonical_key=?',
                    (dataset,source_id,key.canonical_key)).fetchone()
                if expected_revisions is not None:
                    expected=expected_revisions[canonical([source_label,key.canonical_key])]
                    if (existing['revision'] if existing else 0)!=expected:
                        raise ValueError('STALE_PREVIEW: target revision changed')
                identifier = existing['id'] if existing else (record['resource_id'] if dataset=='demo' and preserve_ids and record.get('resource_id') else str(uuid4()))
                payload = dict(record)
                payload['source_key_contract']=key.model_dump(mode='json')
                payload['data_nature']='synthetic' if dataset=='demo' else 'imported_unverified'
                payload['resource_id']=identifier
                content_digest=digest(payload)
                revision = existing['revision'] if existing else 0
                if not existing or existing['content_digest'] != content_digest:
                    revision += 1
                    code=str(record.get('original_code') or record.get('record_id') or record['source_key'])
                    values=(identifier,dataset,source_id,key.canonical_key,code,record.get('name') or code,
                        record.get('region') or '未归属',record.get('kind','field'),canonical(payload),content_digest,revision,now())
                    db.execute('''INSERT INTO entities VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id)
                        DO UPDATE SET code=excluded.code,name=excluded.name,region=excluded.region,kind=excluded.kind,
                        payload=excluded.payload,content_digest=excluded.content_digest,revision=excluded.revision,updated_at=excluded.updated_at''',values)
                    db.execute('INSERT INTO entity_versions VALUES (?,?,?,?)',(identifier,revision,canonical(payload),now()))
                source = {'dataset':dataset,'source_key':key.canonical_key,'file':record.get('source_file'),
                    'sheet':record.get('source_sheet'),'row':record.get('source_row'),'cell':record.get('source_cell'),
                    'sha256':record.get('source_sha256'), 'page':record.get('source_page'),
                    'data_nature':payload['data_nature'],'version':record.get('source_sha256') or content_digest,
                    'description':record.get('source_description') or '来源记录，未经现场核验',
                    'upstream_commit':record.get('upstream_commit')}
                evidence_id='src-'+digest(source)[:24]
                source['id']=evidence_id
                db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?)',(evidence_id,dataset,canonical(source)))
                db.execute('INSERT OR IGNORE INTO entity_sources VALUES (?,?)',(identifier,evidence_id))
                for extra in record.get('knowledge',[])+record.get('extra_sources',[]):
                    extra=dict(extra,dataset=dataset,data_nature=payload['data_nature'])
                    extra_id=extra.get('id') or 'src-'+digest(extra)[:24]
                    extra['id']=extra_id
                    db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?)',(extra_id,dataset,canonical(extra)))
                    db.execute('INSERT OR IGNORE INTO entity_sources VALUES (?,?)',(identifier,extra_id))
                if 'relations' in record:
                    db.execute('DELETE FROM relations WHERE dataset=? AND subject_id=?',(dataset,identifier))
                for relation in record.get('relations',[]):
                    external_id=relation.get('external_id') or relation.get('id')
                    local_key=['external',external_id] if external_id else ['edge',relation['predicate_iri'],relation['target_id']]
                    rid='rel-'+digest([dataset,identifier,source_id,local_key])
                    relation={**relation,'id':rid,'external_id':external_id,'subject_id':identifier,
                        'source_id':source_id,'source_key':key.canonical_key}
                    db.execute('INSERT INTO relations VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,predicate_iri=excluded.predicate_iri,target_id=excluded.target_id',
                        (rid,dataset,identifier,relation.get('predicate_iri',ONTOLOGY+'relatedTo'),relation.get('target_id'),canonical(relation)))
                results.append({'id':identifier,'revision':revision,'source_id':evidence_id})
        return {'count':len(results),'items':results,'dataset':dataset}

    def import_manifest(self, manifest, dataset='real',complete_snapshot=False):
        # Context-local reuse keeps all nested imports, audit entries and retirements in one transaction.
        with self.connection() as db:
            if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
            token=self._active_connection.set(db)
            try:return self._import_manifest(manifest,dataset,complete_snapshot)
            finally:self._active_connection.reset(token)

    def _import_manifest(self, manifest, dataset='real',complete_snapshot=False):
        validate_dataset(dataset)
        objects=manifest.get('objects',[])
        if isinstance(objects,dict):
            objects=[dict(value,spatial_id=key) for key,value in objects.items()]
        count=0
        for obj in objects:
            if obj.get('representation_only') or obj.get('business_entity') is False:
                continue
            spatial_id=obj.get('spatial_id')
            if not spatial_id:
                continue
            with self.connection() as db:
                prior_binding=db.execute('SELECT payload FROM spatial_bindings WHERE dataset=? AND spatial_id=?',(dataset,spatial_id)).fetchone()
                if prior_binding and json.loads(prior_binding['payload']).get('state')=='retired':
                    raise ValueError('Retired spatial identity requires explicit reviewed restoration')
            # A name/code match never constitutes an identity link.
            target=None
            if obj.get('business_source_key') and obj.get('link_verified') and obj.get('link_evidence'):
                with self.connection() as db:
                    rows=db.execute('SELECT id FROM entities WHERE dataset=? AND canonical_key=?',
                        (dataset,obj['business_source_key'])).fetchall()
                    if len(rows)==1:
                        target=rows[0]['id']
            # Validate detachment before allocating an independent object, so rejected mappings leave no orphan.
            with self.connection() as db:
                former=db.execute('SELECT e.id,e.canonical_key,s.source_key FROM spatial_bindings b JOIN entities e ON b.entity_id=e.id JOIN source_systems s ON e.source_id=s.id WHERE b.dataset=? AND b.spatial_id=?',(dataset,spatial_id)).fetchone()
            if former and target!=former['id']:
                same_spatial_source=target is None and former['source_key']=='blender-manifest' and former['canonical_key']==spatial_id
                reviewed_detach=complete_snapshot and target is None and obj.get('identity_match_status')=='ambiguous_repeated_code' and obj.get('link_verified') is False and obj.get('link_evidence') and obj.get('candidate_source_key')==former['canonical_key']
                if not same_spatial_source and not reviewed_detach:raise ValueError('spatial identity cannot be silently rebound')
            if target is None:
                result=self.import_records([{'source_id':'blender-manifest','source_key':spatial_id,
                    'original_code':obj.get('code') or spatial_id, 'name':obj.get('name') or spatial_id,
                    'kind':obj.get('kind','spatial'),'region':obj.get('region','空间示意'),
                    'source_file':'public/models/manifest.json','source_sha256':manifest.get('source_sha256'),
                    'source_description':obj.get('precision') or obj.get('accuracy') or '空间示意，未经现场配准',
                    'geometry':{'coordinate_system':obj.get('coordinate_system','LOCAL_ILLUSTRATIVE'),'center':obj.get('center'),
                        'georeferenced':False,'source_unit':obj.get('source_unit') or obj.get('coordinate_units') or obj.get('units'),
                        'precision':obj.get('precision') or obj.get('accuracy') or 'illustrative'},
                    'model_area':obj.get('model_area',obj.get('model_area_m2')), 'spatial_metadata':obj}],dataset)
                target=result['items'][0]['id']
            with self.connection() as db:
                existing=db.execute('SELECT entity_id,payload FROM spatial_bindings WHERE dataset=? AND spatial_id=?',(dataset,spatial_id)).fetchone()
                if existing and existing['entity_id'] != target:
                    former=db.execute('SELECT canonical_key FROM entities WHERE id=?',(existing['entity_id'],)).fetchone()
                    reviewed_detach=complete_snapshot and obj.get('identity_match_status')=='ambiguous_repeated_code' and obj.get('link_verified') is False and obj.get('link_evidence') and obj.get('candidate_source_key')==former['canonical_key']
                    if not reviewed_detach:raise ValueError('spatial identity cannot be silently rebound')
                    other_documents=set()
                    for remaining in db.execute('SELECT payload FROM spatial_bindings WHERE entity_id=? AND spatial_id!=?',(existing['entity_id'],spatial_id)):
                        representation=json.loads(remaining['payload'])
                        if representation.get('state')=='retired':continue
                        other_documents.update((d.get('source_file'),d.get('source_sha256'),d.get('page')) for d in representation.get('source_evidence',[]))
                    detached=[]
                    for previous_document in json.loads(existing['payload']).get('source_evidence',[]):
                        document_key=(previous_document.get('source_file'),previous_document.get('source_sha256'),previous_document.get('page'))
                        if document_key in other_documents:continue
                        for source in db.execute('SELECT s.id,s.payload FROM sources s JOIN entity_sources e ON e.source_id=s.id WHERE e.entity_id=?',(existing['entity_id'],)).fetchall():
                            evidence=json.loads(source['payload'])
                            if evidence.get('kind')=='source_document' and (evidence.get('file'),evidence.get('sha256'),evidence.get('page'))==document_key:
                                db.execute('DELETE FROM entity_sources WHERE entity_id=? AND source_id=?',(existing['entity_id'],source['id']))
                                detached.append(source['id'])
                    db.execute('INSERT INTO audit_log VALUES (?,?,?,?,?)',(str(uuid4()),now(),'spatial.reviewed_detach',dataset,
                        canonical({'spatial_id':spatial_id,'previous_entity_id':existing['entity_id'],'independent_entity_id':target,
                            'previous':json.loads(existing['payload']),'current':obj,'source_ids_detached':detached,
                            'reason':'Reviewed repeated code is ambiguous; preserve both business and drawing identities and historical source rows.'})))
                if existing and existing['payload']!=canonical(obj):
                    db.execute('INSERT INTO audit_log VALUES (?,?,?,?,?)',(str(uuid4()),now(),'spatial.representation_update',dataset,
                        canonical({'entity_id':target,'spatial_id':spatial_id,'previous':json.loads(existing['payload']),'current':obj})))
                db.execute('INSERT OR REPLACE INTO spatial_bindings VALUES (?,?,?,?)',(dataset,spatial_id,target,canonical(obj)))
                for item in obj.get('source_evidence',[]):
                    evidence={'dataset':dataset,'kind':'source_document','file':item.get('source_file'),
                        'sha256':item.get('source_sha256'),'page':item.get('page'),
                        'version':item.get('source_sha256'),'description':'已核查图纸表示来源；业务关联不等于测绘配准。',
                        'data_nature':'synthetic' if dataset=='demo' else 'imported_unverified'}
                    evidence_id='src-'+digest(evidence)[:24];evidence['id']=evidence_id
                    db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?)',(evidence_id,dataset,canonical(evidence)))
                    db.execute('INSERT OR IGNORE INTO entity_sources VALUES (?,?)',(target,evidence_id))
            count+=1
        retired=[]
        if complete_snapshot:
            current={o['spatial_id'] for o in objects if o.get('spatial_id')}
            with self.connection() as db:
                missing=[dict(r) for r in db.execute('SELECT * FROM spatial_bindings WHERE dataset=?',(dataset,))
                         if r['spatial_id'] not in current and json.loads(r['payload']).get('state')!='retired']
            for binding in missing:
                reason='Absent from reviewed complete manifest snapshot '+digest(manifest)
                with self.connection() as db:
                    source=db.execute('SELECT s.source_key FROM source_systems s JOIN entities e ON e.source_id=s.id WHERE e.id=?',(binding['entity_id'],)).fetchone()
                if source['source_key']=='blender-manifest':
                    self.retire_spatial(binding['spatial_id'],reason,dataset)
                else:
                    metadata=json.loads(binding['payload']);metadata.update(state='retired',retirement_reason=reason,retired_at=now())
                    with self.connection() as db:
                        db.execute('UPDATE spatial_bindings SET payload=? WHERE dataset=? AND spatial_id=?',(canonical(metadata),dataset,binding['spatial_id']))
                    self.audit('spatial.representation_retire',dataset,{'entity_id':binding['entity_id'],'spatial_id':binding['spatial_id'],
                        'previous':json.loads(binding['payload']),'reason':reason})
                retired.append(binding['spatial_id'])
        return {'count':count,'retired':retired}

    def retire_spatial(self,spatial_id,reason,dataset='real'):
        """Explicit administrative correction; preserve the identity and its history."""
        validate_dataset(dataset)
        if not reason.strip():
            raise ValueError('A reviewed retirement reason is required')
        with self.connection() as db:
            if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
            binding=db.execute('SELECT * FROM spatial_bindings WHERE dataset=? AND spatial_id=?',(dataset,spatial_id)).fetchone()
            if binding is None:
                return {'state':'not_found','spatial_id':spatial_id}
            row=db.execute('SELECT * FROM entities WHERE id=?',(binding['entity_id'],)).fetchone()
            source=db.execute('SELECT source_key FROM source_systems WHERE id=?',(row['source_id'],)).fetchone()
            if not source or source['source_key']!='blender-manifest':
                raise ValueError('Retirement cannot change a business ledger identity')
            if db.execute('SELECT 1 FROM plans WHERE entity_id=?',(row['id'],)).fetchone():
                raise ValueError('Spatial entity has saved plans; review them before retiring')
            payload=json.loads(row['payload']);metadata=json.loads(binding['payload'])
            if payload.get('state')=='retired':
                return {'state':'retired','id':row['id'],'spatial_id':spatial_id}
            payload.update(state='retired',retirement_reason=reason,retired_at=now())
            metadata.update(state='retired',retirement_reason=reason)
            revision=row['revision']+1
            db.execute('UPDATE entities SET payload=?,content_digest=?,revision=?,updated_at=? WHERE id=?',
                (canonical(payload),digest(payload),revision,now(),row['id']))
            db.execute('INSERT INTO entity_versions VALUES (?,?,?,?)',(row['id'],revision,canonical(payload),now()))
            db.execute('UPDATE spatial_bindings SET payload=? WHERE dataset=? AND spatial_id=?',(canonical(metadata),dataset,spatial_id))
        self.audit('spatial.retire',dataset,{'entity_id':row['id'],'spatial_id':spatial_id,'reason':reason})
        return {'state':'retired','id':row['id'],'spatial_id':spatial_id}

    def restore_spatial(self,spatial_id,reason,dataset='real'):
        """Explicit reviewed restoration; never allocate a replacement identity."""
        validate_dataset(dataset)
        if not reason.strip():raise ValueError('A reviewed restoration reason is required')
        with self.connection() as db:
            if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
            binding=db.execute('SELECT * FROM spatial_bindings WHERE dataset=? AND spatial_id=?',(dataset,spatial_id)).fetchone()
            if binding is None:raise ValueError('No historical spatial identity exists')
            metadata=json.loads(binding['payload'])
            if metadata.get('state')!='retired':return {'state':'active','id':binding['entity_id'],'spatial_id':spatial_id}
            row=db.execute('SELECT * FROM entities WHERE id=?',(binding['entity_id'],)).fetchone()
            payload=json.loads(row['payload'])
            if payload.get('state')=='retired':
                source=db.execute('SELECT source_key FROM source_systems WHERE id=?',(row['source_id'],)).fetchone()
                if source['source_key']!='blender-manifest':raise ValueError('Cannot restore a business identity through spatial tooling')
                payload={k:v for k,v in payload.items() if k not in ('state','retired_at','retirement_reason')}
                revision=row['revision']+1
                db.execute('UPDATE entities SET payload=?,content_digest=?,revision=?,updated_at=? WHERE id=?',(canonical(payload),digest(payload),revision,now(),row['id']))
                db.execute('INSERT INTO entity_versions VALUES (?,?,?,?)',(row['id'],revision,canonical(payload),now()))
            restored={k:v for k,v in metadata.items() if k not in ('state','retired_at','retirement_reason')}
            db.execute('UPDATE spatial_bindings SET payload=? WHERE dataset=? AND spatial_id=?',(canonical(restored),dataset,spatial_id))
            db.execute('INSERT INTO audit_log VALUES (?,?,?,?,?)',(str(uuid4()),now(),'spatial.restore',dataset,
                canonical({'entity_id':row['id'],'spatial_id':spatial_id,'reason':reason,'previous':metadata})))
        return {'state':'active','id':row['id'],'spatial_id':spatial_id}

    def _entity(self, row, db):
        payload=json.loads(row['payload'])
        bindings=[dict(r) for r in db.execute('SELECT spatial_id,payload FROM spatial_bindings WHERE entity_id=? ORDER BY spatial_id',(row['id'],)) if json.loads(r['payload']).get('state')!='retired']
        spatial=[r['spatial_id'] for r in bindings]
        model_areas=[{'spatial_id':r['spatial_id'],'area_m2':json.loads(r['payload']).get('model_area_m2',json.loads(r['payload']).get('model_area')),
                      'area_units2':json.loads(r['payload']).get('model_area_units2'),
                      'source_unit':json.loads(r['payload']).get('source_unit') or json.loads(r['payload']).get('coordinate_units') or json.loads(r['payload']).get('units'),
                      'precision':json.loads(r['payload']).get('precision'),'georeferenced':False} for r in bindings]
        evidence=[json.loads(r['payload']) for r in db.execute('SELECT s.payload FROM sources s JOIN entity_sources e ON e.source_id=s.id WHERE e.entity_id=? ORDER BY s.id',(row['id'],))]
        area={'value':payload.get('area_original'),'unit':payload.get('area_unit'),'inferred_unit':payload.get('inferred_unit'),
            'verification':payload.get('inference_status','unconfirmed'),'source_id':next((s['id'] for s in evidence if s.get('sha256')==payload.get('source_sha256')),None),
            'inference_basis':payload.get('inference_basis')}
        entity={'id':row['id'],'resource_id':row['id'],'iri':object_iri(row['id']), 'revision':row['revision'],'state':payload.get('state','active'),
            'code':row['code'],'name':row['name'],'display_name':row['name'],'region':row['region'],'kind':row['kind'],
            'dataset':row['dataset'],'data_nature':payload['data_nature'],'class_iris':entity_class_iris(payload),
            'spatial_ids':spatial,'area':area,'geometry':payload.get('geometry'),
            'model_area':model_areas[0]['area_m2'] if len(model_areas)==1 else payload.get('model_area'), 'model_areas':model_areas,
            'sources':evidence,'source_key':payload['source_key_contract'], 'devices':payload.get('devices',[]),
            'observations':payload.get('observations',[]),'species':payload.get('species'),'production_context':payload.get('production_context',{}),
            'scene_anchor':payload.get('scene_anchor'),'scenario':payload.get('scenario'),'scenario_properties':payload.get('scenario_properties',{}),
            'relations':[json.loads(r['payload']) for r in db.execute('SELECT payload FROM relations WHERE dataset=? AND (subject_id=? OR target_id=?)',(row['dataset'],row['id'],row['id']))],
            'updated_at':row['updated_at']}
        entity['knowledge']=[s for s in evidence if s.get('kind')=='knowledge']
        region_aliases=[row['region']]
        if '庙下刘' in row['region']:
            region_aliases+=['庙下刘','庙下流',row['region'].replace('庙下刘','庙下流')]
        if '庙下流' in row['region']:
            region_aliases+=['庙下刘','庙下流',row['region'].replace('庙下流','庙下刘')]
        entity['representations']=[dict(json.loads(r['payload']),spatial_id=r['spatial_id']) for r in bindings]
        entity['region_aliases']=list(dict.fromkeys(region_aliases))
        entity['aliases']=list(dict.fromkeys(payload.get('aliases',[])+[a+' '+row['code'] for a in entity['region_aliases']]))
        entity['rules']=payload.get('rules',[])
        entity['quality_alerts']=alerts_for(entity)
        entity['business_alerts']=business_alerts_for(entity,entity['rules'])
        entity['alerts']=entity['quality_alerts']+entity['business_alerts']
        entity['missing_fields']=[a['message'] for a in entity['quality_alerts']]
        return entity

    def list_entities(self,dataset='real',q='',kind=None,limit=500):
        validate_dataset(dataset)
        args=[dataset];where="dataset=? AND COALESCE(json_extract(payload,'$.state'),'active')!='retired'"
        if q:
            q=q.replace('庙下流','庙下刘')
            escaped=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            where+=" AND (code LIKE ? ESCAPE '\\' OR name LIKE ? ESCAPE '\\' OR region LIKE ? ESCAPE '\\')"
            args.extend(['%'+escaped+'%']*3)
        if kind:
            where+=' AND kind=?';args.append(kind)
        with self.connection() as db:
            total=db.execute('SELECT COUNT(*) FROM entities WHERE '+where,args).fetchone()[0]
            rows=db.execute('SELECT * FROM entities WHERE '+where+' ORDER BY region,code LIMIT ?',args+[limit]).fetchall()
            items=[self._entity(row,db) for row in rows]
        return {'items':items,'total':total,'dataset':dataset}

    def get_entity(self,identifier,dataset='real'):
        validate_dataset(dataset)
        with self.connection() as db:
            row=db.execute('SELECT * FROM entities WHERE id=? AND dataset=?',(str(identifier),dataset)).fetchone()
            if row is None:
                raise KeyError('Entity not found in selected dataset')
            return self._entity(row,db)

    def summary(self,dataset='real'):
        page=self.list_entities(dataset,limit=10000);items=page['items']
        ledger=[e for e in items if e['area']['value'] is not None]
        verified_area=[e['area']['value'] for e in ledger if e['area']['unit']=='亩']
        with self.connection() as db:public_count=db.execute('SELECT COUNT(*) FROM knowledge_entries').fetchone()[0]
        scene_items=[e for e in items if (e.get('scene_anchor') or {}).get('asset_id')=='full' or any(r.get('asset_id')=='full' for r in e['representations'])]
        return {'dataset':dataset,'counts':dict(Counter(e['kind'] for e in items)), 'entity_count':len(items),
            'scene':{'asset_id':'full','principal_count':sum(e['kind']!='device' for e in scene_items),'device_count':sum(e['kind']=='device' for e in scene_items),
                'counts':dict(Counter(e['kind'] for e in scene_items)),'observation_count':sum(len(e['observations']) for e in scene_items),
                'business_alert_count':sum(bool(e['business_alerts']) for e in scene_items),
                'reference_time':next((e['scenario']['reference_time'] for e in scene_items if e.get('scenario')),None),
                'data_nature':'synthetic' if dataset=='demo' else 'imported_unverified'},
            'spatial_count':sum(bool(e['spatial_ids']) for e in items), 'ledger_count':len(ledger),
            'representation_count':sum(len(e['spatial_ids']) for e in items),
            'area':{'raw_total':round(sum(e['area']['value'] for e in ledger),4),'unit':None,
                'confirmed_mu_total':round(sum(verified_area),4) if verified_area else None,
                'unconfirmed_unit_count':sum(e['area']['unit'] is None for e in ledger),
                'note':'仅汇总地块台账原值，不叠加图纸片区总计；原表单位待确认。'},
            'alerts':[a for e in items for a in e['alerts']],
            'data_status':{'realtime_connected':False,'model_geometry_surveyed':False,
                'public_reference_count':public_count,'knowledge_base':'public_references' if public_count else 'synthetic_fixture' if dataset=='demo' and any(e['knowledge'] for e in items) else 'unconfigured'},
            'upstream':UPSTREAM}

    def import_knowledge(self,entries):
        for entry in entries:
            if not entry.get('id') or not entry.get('url','').startswith('https://') or not entry.get('source_sha256'):
                raise ValueError('Public references require id, HTTPS source URL and source hash')
            canonical(entry)
        with self.connection() as db:
            for entry in entries:
                body={**entry,'data_nature':'imported_unverified','reference_verified':True,'site_fact':False,
                      'status':'reference_not_site_fact','kind':'knowledge'}
                db.execute('INSERT INTO knowledge_entries VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,payload=excluded.payload,content_digest=excluded.content_digest',
                    (body['id'],body.get('version','unversioned'),canonical(body),digest(body)))
        return {'count':len(entries)}

    def knowledge(self,dataset='real',q='',kind=None,context=None):
        validate_dataset(dataset)
        with self.connection() as db:
            rows=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM sources WHERE dataset=?',(dataset,))]
            public=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM knowledge_entries')]
        selected=[r for r in rows if r.get('kind')=='knowledge' and (not q or q.casefold() in canonical(r).casefold())]
        for item in public:
            productions=item.get('scope',{}).get('production',[])
            seasons=item.get('scope',{}).get('season',[])
            if context is not None and seasons and 'all' not in seasons and context.get('season') not in seasons:
                continue
            allowed={'pond':{'pond_fish','aquaculture','pond'},'field':{'crop','field_crop','rice','field'},'orchard':{'orchard','fruit'}}
            tagged=item.get('entity_kinds')
            if kind and tagged and kind not in tagged:continue
            if kind and not tagged and productions and not set(productions)&allowed.get(kind,set()):continue
            searchable=canonical(item).casefold();terms=re.findall(r'[a-zA-Z]{3,}|[\u4e00-\u9fff]{2,}',q)
            score=sum(1 for word in terms if word.casefold() in searchable)
            score+=sum(1 for word in ('溶解氧','缺氧','增氧','水温','灌溉','水稻','高温','设备') if word in q and word in searchable)
            if q and not score and not kind:continue
            selected.append({**item,'dataset':dataset,'retrieval_score':score,'applicability':{'status':'requires_site_confirmation','requires':item.get('scope',{}).get('requires',[]),'exclusions':item.get('scope',{}).get('exclusions',[])}})
        selected.sort(key=lambda r:(-r.get('retrieval_score',0),r['id']))
        return {'dataset':dataset,'items':selected[:8]}

    def audit(self,tool,dataset,payload):
        identifier=str(uuid4())
        with self.connection() as db:
            db.execute('INSERT INTO audit_log VALUES (?,?,?,?,?)',(identifier,now(),tool,dataset,canonical(payload)))
        return identifier

    def audit_entries(self):
        with self.connection() as db:
            return [dict(r, payload=json.loads(r['payload'])) for r in db.execute('SELECT * FROM audit_log ORDER BY created_at')]

    def save_plan(self,body):
        entity=self.get_entity(body['entity_id'],body['dataset'])
        known={s['id'] for s in entity['sources']}
        known.update(s['id'] for s in self.knowledge(body['dataset'],kind=entity['kind'])['items'])
        if not body['evidence_ids'] or not set(body['evidence_ids']) <= known:
            raise ValueError('Evidence must refer to the selected entity and dataset')
        plan={**body,'id':str(uuid4()),'created_at':now(),'status':'draft','device_control':False,
            'entity_revision':entity['revision'],'data_nature':entity['data_nature']}
        with self.connection() as db:
            db.execute('INSERT INTO plans VALUES (?,?,?,?,?)',(plan['id'],body['dataset'],body['entity_id'],canonical(plan),plan['created_at']))
        self.audit('plans.save',body['dataset'],{'plan_id':plan['id'],'entity_id':body['entity_id']})
        return plan

    def list_plans(self,dataset='real'):
        validate_dataset(dataset)
        with self.connection() as db:
            return {'items':[json.loads(r['payload']) for r in db.execute('SELECT payload FROM plans WHERE dataset=? ORDER BY created_at DESC',(dataset,))],'dataset':dataset}

    def backup(self,destination):
        destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.resolve()==self.path.resolve():
            raise ValueError('Backup destination must differ from active database')
        with self.connection() as db, sqlite3.connect(destination) as target:
            db.backup(target)
        return str(destination)
