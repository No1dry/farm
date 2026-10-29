"""Local, repeatable imports with source hashes checked before writing."""
import hashlib
import json
from pathlib import Path
from uuid import uuid5,NAMESPACE_URL

from .contracts import UPSTREAM, ONTOLOGY
from .store import Store

ROOT=Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def import_real(store,root=ROOT):
    audit_path=root/'data/audit/entities.json'
    payload=read_json(audit_path)
    source=payload['source']
    if file_digest(root/source['path']) != source['sha256']:
        raise ValueError('Source workbook differs from audited hash; rerun source audit first')
    rows=[]
    for row in payload['records']:
        if row['source_sha256'] != source['sha256']:
            raise ValueError('Record references unverified source version')
        rows.append({**row,'source_id':row.get('source_id') or row['source_instance'],
                     'kind':row.get('kind') or row.get('entity_type','field'),
                     'source_description':'用户提供的面积台账，工作表/行号可追溯，原表未注明面积单位。'})
    return store.import_records(rows,'real')


def import_demo(store,root=ROOT):
    sample_root=root/'deliverables/liangzihu-samples'
    manifest=read_json(sample_root/'source-manifest.json')
    if manifest['commit'] != UPSTREAM['commit'] or manifest['data_nature']!='synthetic':
        raise ValueError('Unrecognized upstream sample version or data nature')
    entries={e['path']:e for e in manifest['files']}
    records={}
    for scene in ('field','pond','orchard'):
        path=f'ontology-platform/backend/tests/fixtures/semantic/{scene}.json'
        fixture_path=sample_root/'original'/path
        if file_digest(fixture_path)!=entries[path]['sha256']:
            raise ValueError('Upstream sample hash mismatch: '+scene)
        fixture=read_json(fixture_path)
        for obj in fixture['objects']:
            identifier=obj['resource_id']
            class_name=obj['class_iris'][0].rsplit('/',1)[-1]
            kind={'Field':'field','Pond':'pond','Orchard':'orchard','Sensor':'device','Pump':'device','Camera':'device'}.get(class_name,'ontology')
            display={'Field':'演示农田','Pond':'演示水塘','Orchard':'演示果园','Sensor':'演示传感器','Pump':'演示共享水泵','Camera':'演示摄像头'}.get(class_name,obj['display_name'])
            previous=records.get(identifier,{})
            source={'id':'upstream-'+scene+'-'+identifier,'file':str(fixture_path.relative_to(root)).replace('\\','/'),
                'sha256':entries[path]['sha256'],'description':'上游合成测试fixture','upstream_commit':UPSTREAM['commit']}
            records[identifier]={**previous,'resource_id':identifier,'source_id':'upstream-semantic-fixtures',
                'source_key':identifier,'source_system':'liangzihu-ontology-platform','source_instance':UPSTREAM['commit'],
                'original_code':'DEMO-'+class_name.upper()+'-'+identifier[:8],'name':display,'region':'上游演示样例',
                'kind':kind,'class_iris':obj['class_iris'],'data_nature':'synthetic',
                'source_file':source['file'],'source_sha256':source['sha256'],'source_description':'上游合成语义对象；并非本地现场实体。',
                'upstream_commit':UPSTREAM['commit'],'relations':previous.get('relations',[]),
                'extra_sources':previous.get('extra_sources',[])+[source]}
            for assertion in obj.get('assertions',[]):
                target=assertion['object']['value']
                if target.startswith('urn:lzo:object:'):
                    records[identifier]['relations'].append({'id':assertion['assertion_id'],'subject_id':identifier,
                        'predicate_iri':assertion['predicate_iri'],'target_id':target.rsplit(':',1)[-1],
                        'data_nature':'synthetic','state':assertion['state'],'support':assertion['support']})
        for patch in fixture.get('patches',[]):
            for assertion in patch['additions']:
                target=assertion['object']['value']
                if target.startswith('urn:lzo:object:'):
                    records[patch['resource_id']]['relations'].append({'id':assertion['assertion_id'],'subject_id':patch['resource_id'],
                        'predicate_iri':assertion['predicate_iri'],'target_id':target.rsplit(':',1)[-1],
                        'data_nature':'synthetic','state':assertion['state'],'support':assertion['support']})
    # Build only relationships explicitly present in the upstream synthetic fixture.
    for item in records.values():
        item['devices']=[]
        for device in records.values():
            if device['kind']=='device' and any(r['target_id']==item['resource_id'] and r['predicate_iri'] in (ONTOLOGY+'monitors',ONTOLOGY+'serves') for r in device['relations']):
                item['devices'].append({'id':device['resource_id'],'name':device['name'],'kind':'device','data_nature':'synthetic','live_status':None})
    scenario_path=root/'data/demo/oxygen-scenario.json'
    scenario=read_json(scenario_path)
    pond=next(item for item in records.values() if item['kind']=='pond')
    # This association is an explicit additional synthetic test scenario, not an upstream fact.
    pond['knowledge']=[{**scenario['knowledge'],'sha256':file_digest(scenario_path)}]
    pond['observations']=[scenario['observation']]
    pond['rules']=[scenario['rule']]
    return store.import_records(records.values(),'demo',preserve_ids=True)


def initialize(path=None,root=ROOT):
    store=Store(path or root/'runtime/farm.sqlite3')
    import_real(store,root)
    import_demo(store,root)
    independent=root/'data/demo/inspection-ready-scenario.json'
    if independent.exists():
        scenario=read_json(independent);records=[]
        ids={o['key']:str(uuid5(NAMESPACE_URL,'farm:synthetic:'+scenario['id']+':'+o['key'])) for o in scenario['objects']}
        for obj in scenario['objects']:
            record={**obj,'resource_id':ids[obj['key']],'source_id':'farm-synthetic-scenarios',
                'source_key':scenario['id']+':'+obj['key'],'original_code':obj['code'],
                'class_iris':[ONTOLOGY+obj['class']],'region':'独立合成情景','data_nature':'synthetic',
                'source_file':independent.relative_to(root).as_posix(),'source_sha256':file_digest(independent),
                'source_description':scenario['description'],
                'relations':[{'predicate_iri':ONTOLOGY+r['predicate'],'target_id':ids[r['target']],'data_nature':'synthetic',
                              'state':'accepted','support':{'source_file':independent.relative_to(root).as_posix()}} for r in obj.get('relations',[])]}
            record['observations']=[{**o,'device_id':ids[o['device_key']]} for o in obj.get('observations',[])]
            record['devices']=[{'id':ids[d['key']],'name':d['name'],'kind':'device','data_nature':'synthetic',
                'live_status':None,'scenario_readiness':d['readiness']} for d in scenario['objects'] if d['kind']=='device'
                and any(r['target']==obj['key'] and r['predicate'] in ('monitors','serves') for r in d.get('relations',[]))]
            records.append(record)
        store.import_records(records,'demo',preserve_ids=True)
    knowledge=root/'data/knowledge/curated.json'
    if knowledge.exists():
        store.import_knowledge(read_json(knowledge)['entries'])
    manifest=root/'public/models/manifest.json'
    if manifest.exists():
        snapshot=read_json(manifest);checked=set()
        for obj in snapshot.get('objects',[]):
            for evidence in obj.get('source_evidence',[]):
                name=evidence.get('source_file');expected=evidence.get('source_sha256')
                if name and expected and (name,expected) not in checked:
                    source_path=(root/name).resolve()
                    if not source_path.is_relative_to(root.resolve()) or file_digest(source_path)!=expected:
                        raise ValueError('Manifest evidence hash/path does not match reviewed source')
                    checked.add((name,expected))
        store.import_manifest(snapshot,complete_snapshot=True)
        scenario=root/'data/demo/full-area-scenario.json'
        if scenario.exists():
            from .scenario import import_full_scene
            layout=root/'data/demo/full-area-device-layout.json'
            import_full_scene(store,snapshot,read_json(scenario),file_digest(scenario),dict(read_json(layout),_source_sha256=file_digest(layout)) if layout.exists() else None)
    return store
