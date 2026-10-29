"""Behavioral acceptance for the local ontology adapter; isolated temporary databases."""
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import UUID

import pytest


def components():
    assert importlib.util.find_spec('backend') is not None, 'Persistent ontology adapter is not implemented'
    from backend.store import Store
    from backend.app import create_app
    from fastapi.testclient import TestClient
    return Store, create_app, TestClient


def record(code='L18', region='庙下刘', **changes):
    data = dict(source_id='ledger', source_key=f'{region}:{code}', record_id=code,
                original_code=code, name=code, region=region, kind='field',
                area_original=3.25, area_unit=None, inferred_unit='亩',
                source_file='area.xls', source_sheet='总表', source_row=4,
                source_sha256='a'*64, geometry=None)
    data.update(changes)
    return data


def build(tmp_path, rows=None, settings=None):
    Store, create_app, TestClient = components()
    store = Store(tmp_path/'farm.sqlite3')
    store.import_records(rows or [record()], 'real')
    return store, TestClient(create_app(store=store, settings=settings or {}))


def test_identity_survives_reimport_restart_and_source_revision(tmp_path):
    Store, _, _ = components()
    path = tmp_path/'farm.sqlite3'
    store = Store(path)
    store.import_records([record()], 'real')
    original = store.list_entities('real')['items'][0]
    assert UUID(original['id']).version == 4
    assert original['iri'] == f"urn:lzo:object:{original['id']}"
    Store(path).import_records([record(source_sha256='b'*64, area_original=4)], 'real')
    result = Store(path).list_entities('real')
    assert result['total'] == 1
    assert result['items'][0]['id'] == original['id']
    detail = Store(path).get_entity(original['id'], 'real')
    assert detail['area']['value'] == 4
    assert detail['area']['unit'] is None
    assert detail['revision'] == 2
    assert len(detail['sources']) == 2


@pytest.mark.parametrize('parent,child',[('F5','F5-1'),('L10','L10-1'),('X3','X3-1')])
def test_subparcel_identifier_does_not_also_resolve_its_parent(tmp_path,parent,child):
    from backend.assistant import resolve
    store,_=build(tmp_path,[record(parent),record(child)])
    matches=resolve(store,'进入 '+child+' 田块',None,'real')
    assert [e['code'] for e in matches]==[child]
    assert [e['code'] for e in resolve(store,'进入 '+parent+' 田块',None,'real')]==[parent]


def test_registered_entity_aliases_resolve_and_shared_aliases_remain_ambiguous(tmp_path):
    from backend.assistant import resolve
    store,_=build(tmp_path,[record('L18',aliases=['东侧试验田','测绘名称甲']),record('L19',aliases=['东侧试验田'])])
    assert [e['code'] for e in resolve(store,'进入测绘名称甲',None,'real')]==['L18']
    assert {e['code'] for e in resolve(store,'介绍东侧试验田',None,'real')}=={'L18','L19'}


def test_invalid_import_rolls_back_complete_batch(tmp_path):
    Store, _, _ = components()
    store = Store(tmp_path/'farm.sqlite3')
    with pytest.raises(ValueError):
        store.import_records([record(), record(code='L19', area_original=float('nan'))], 'real')
    assert store.list_entities('real')['total'] == 0


def test_datasets_are_isolated_and_query_is_parameterized(tmp_path):
    store, client = build(tmp_path)
    store.import_records([record()], 'demo')
    real = client.get('/api/entities?dataset=real').json()['items'][0]
    demo = client.get('/api/entities?dataset=demo').json()['items'][0]
    assert real['id'] != demo['id']
    assert demo['data_nature'] == 'synthetic'
    assert client.get(f"/api/entities/{demo['id']}?dataset=real").status_code == 404
    assert client.get('/api/entities', params={'q': "' OR 1=1 --"}).json()['total'] == 0
    assert client.get('/api/summary?dataset=wrong').status_code == 422


def test_same_code_in_distinct_regions_requires_clarification(tmp_path):
    _, client = build(tmp_path, [record(), record(region='余湾')])
    response = client.post('/api/assistant', json={'message':'查看 L18', 'dataset':'real'}).json()
    assert response['status'] == 'needs_clarification'
    assert len(response['candidates']) == 2
    assert response['entity'] is None
    assert response['actions'] == []


def test_unconfigured_assistant_reports_unknowns_and_does_not_save(tmp_path):
    store, client = build(tmp_path)
    entity = store.list_entities('real')['items'][0]
    reply = client.post('/api/assistant', json={'message':'这块田怎么灌溉', 'dataset':'real', 'selected_entity_id':entity['id']}).json()
    assert reply['status'] == 'unconfigured'
    assert reply['entity']['id'] == entity['id']
    assert reply['evidence']
    assert any('设备' in x for x in reply['gaps'])
    assert reply['model']['configured'] is False
    assert client.get('/api/plans').json()['items'] == []
    assert store.audit_entries()[-1]['tool'] == 'assistant.query'


def test_stale_unit_conflict_and_missing_observations_are_exposed(tmp_path):
    store, client = build(tmp_path, [record(observations=[
        {'metric':'soil_moisture','value':23,'unit':'%','observed_at':'2020-01-01T00:00:00Z'},
        {'metric':'soil_moisture','value':0.2,'unit':'fraction','observed_at':'2020-01-01T01:00:00Z'}])])
    identifier = store.list_entities('real')['items'][0]['id']
    detail = client.get(f'/api/entities/{identifier}').json()
    codes = {a['code'] for a in detail['alerts']}
    assert {'stale_observation','unit_conflict','missing_devices','unconfirmed_area_unit'} <= codes
    _, empty = build(tmp_path/'empty')
    item = empty.get('/api/entities').json()['items'][0]
    assert 'missing_observations' in {a['code'] for a in empty.get('/api/entities/'+item['id']).json()['alerts']}


def test_manifest_does_not_merge_by_display_name(tmp_path):
    store, _ = build(tmp_path)
    original = store.list_entities('real')['items'][0]['id']
    manifest = {'objects':[{'spatial_id':'overview-L18','name':'L18','kind':'field','region':'庙下刘','center':[1,0,2], 'precision':'illustrative'}]}
    store.import_manifest(manifest)
    store.import_manifest(manifest)
    entities = store.list_entities('real')['items']
    assert len(entities) == 2
    spatial = next(e for e in entities if e['spatial_ids'])
    assert spatial['id'] != original
    assert spatial['spatial_ids'] == ['overview-L18']


def test_plan_save_validates_evidence_and_dataset(tmp_path):
    store, client = build(tmp_path)
    entity = store.get_entity(store.list_entities('real')['items'][0]['id'], 'real')
    body = dict(title='资料补全方案', entity_id=entity['id'], dataset='real', content='先核对面积单位',
                evidence_ids=[entity['sources'][0]['id']], conditions=['补齐资料后复核'], gaps=['缺少设备'])
    invalid = client.post('/api/plans', json={**body, 'evidence_ids':['unknown']})
    assert invalid.status_code == 422
    saved = client.post('/api/plans', json=body)
    assert saved.status_code == 201
    assert client.get('/api/plans?dataset=real').json()['items'][0]['id'] == saved.json()['id']
    assert client.get('/api/plans?dataset=demo').json()['items'] == []


@pytest.fixture
def model_server():
    state = {'payload':{}, 'request':None}
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state['request'] = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            data = json.dumps({'choices':[{'message':{'content':json.dumps(state['payload'])}}]}).encode()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(data)
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield state, {'model_base_url':f'http://127.0.0.1:{server.server_port}/v1','model_name':'test-model','model_api_key':'test-secret'}
    server.shutdown(); server.server_close(); thread.join()


def test_model_unknown_evidence_or_commands_rejected(tmp_path, model_server):
    state, settings = model_server
    store, client = build(tmp_path, settings=settings)
    identifier = store.list_entities('real')['items'][0]['id']
    state['payload'] = {'answer':'执行灌溉', 'evidence_ids':['invented'], 'actions':[{'type':'execute','code':'bad'}]}
    reply = client.post('/api/assistant',json={'message':'灌溉建议','dataset':'real','selected_entity_id':identifier}).json()
    assert reply['status'] == 'invalid_response'
    assert reply['actions'] == []
    assert 'test-secret' not in json.dumps(reply)
    assert store.list_plans('real')['items'] == []


def test_model_valid_structured_reply_is_grounded(tmp_path, model_server):
    state, settings = model_server
    store, client = build(tmp_path, settings=settings)
    entity = store.get_entity(store.list_entities('real')['items'][0]['id'],'real')
    state['payload'] = {'answer':'台账有记录，灌溉决策仍缺设备观测。', 'evidence_ids':[entity['sources'][0]['id']],
                        'gaps':['缺少土壤墒情'], 'actions':[], 'suggested_plan':None}
    reply = client.post('/api/assistant',json={'message':'分析','dataset':'real','selected_entity_id':entity['id']}).json()
    assert reply['status'] == 'ok'
    assert reply['evidence'][0]['id'] == entity['sources'][0]['id']
    assert state['request']['model'] == 'test-model'
    assert state['request']['messages'][0]['role'] == 'system'
    assert client.get('/api/health').json()['model']['configured'] is True


def test_local_import_validates_sources_and_preserves_sample_identity(tmp_path):
    _, create_app, TestClient = components()
    from backend import importer
    store = importer.initialize(tmp_path/'farm.sqlite3')
    assert store.summary('real')['ledger_count'] == 100
    assert store.summary('real')['area']['raw_total'] == 1010.99
    assert store.summary('real')['area']['confirmed_mu_total'] is None
    before = {e['id'] for e in store.list_entities('real')['items']}
    importer.initialize(tmp_path/'farm.sqlite3')
    assert before == {e['id'] for e in store.list_entities('real')['items']}
    client = TestClient(create_app(store=store,settings={}))
    sample = client.get('/api/entities/d2c438ec-91f0-54e2-9de2-eba7f561db58?dataset=demo')
    assert sample.status_code == 200
    assert sample.json()['data_nature'] == 'synthetic'


def test_demo_business_alert_is_historical_and_rule_evidence_is_saveable(tmp_path):
    _, create_app, TestClient = components()
    from backend.importer import initialize
    store=initialize(tmp_path/'farm.sqlite3')
    client=TestClient(create_app(store=store,settings={}))
    pond=next(e for e in store.list_entities('demo')['items'] if e['business_alerts'])
    alert=pond['business_alerts'][0]
    assert alert['status']=='stale'
    assert alert['rule_version']=='demo-oxygen/v1'
    assert alert['condition_historically_met'] is True
    assert alert['category']=='business'
    knowledge=client.get('/api/knowledge?dataset=demo&q=溶解氧').json()['items']
    synthetic=next(k for k in knowledge if k['id']=='knowledge-demo-oxygen-v1')
    assert synthetic['data_nature']=='synthetic'
    summary=client.get('/api/summary?dataset=demo').json()
    assert summary['data_status']['knowledge_base']=='public_references'
    assert summary['data_status']['public_reference_count']==4
    assert all(k.get('reference_verified') and not k.get('site_fact') for k in client.get('/api/knowledge?dataset=real').json()['items'])
    saved=client.post('/api/plans',json={'title':'演示缺氧核查','entity_id':pond['id'],'dataset':'demo',
        'content':'历史演示，先采集现状','evidence_ids':[synthetic['id']],'gaps':['无实时观测'],'conditions':['仅演示']})
    assert saved.status_code==201


def test_verified_spatial_selection_has_allowlisted_action_without_model(tmp_path):
    store,client=build(tmp_path)
    store.import_manifest({'objects':[{'spatial_id':'DETAIL-L18','name':'L18','kind':'field','center':[1,0,2],'model_area_m2':50}]})
    spatial=next(e for e in store.list_entities('real')['items'] if e['spatial_ids'])
    reply=client.post('/api/assistant',json={'message':'查看这里','selected_entity_id':spatial['id']}).json()
    assert reply['actions']==[{'type':'focus_entity','entity_id':spatial['id']}]
    assert spatial['model_area']==50


def test_backup_can_be_reopened_with_identical_identity(tmp_path):
    Store,_,_=components()
    store,_=build(tmp_path)
    expected=store.list_entities('real')['items'][0]['id']
    backup=tmp_path/'backup.sqlite3'
    store.backup(backup)
    assert Store(backup).list_entities('real')['items'][0]['id']==expected


def test_valid_evidence_does_not_authorize_invented_species_or_actuation(tmp_path,model_server):
    state,settings=model_server
    store,client=build(tmp_path,settings=settings)
    entity=store.list_entities('real')['items'][0]
    state['payload']={'answer':'鱼种为草鱼，立即开启增氧机30分钟。',
        'evidence_ids':[entity['sources'][0]['id']],'gaps':[],'actions':[],'suggested_plan':None}
    reply=client.post('/api/assistant',json={'message':'分析','selected_entity_id':entity['id']}).json()
    assert reply['status']=='invalid_response'
    assert '草鱼' not in reply['answer']
    assert reply['suggested_plan'] is None
    assert reply['facts']['species'] is None


def test_import_rejects_changed_source_before_allocating_identity(tmp_path):
    Store,_,_=components()
    from backend.importer import import_real
    root=tmp_path/'sources';(root/'data/audit').mkdir(parents=True)
    (root/'area.xls').write_bytes(b'changed source')
    (root/'data/audit/entities.json').write_text(json.dumps({'source':{'path':'area.xls','sha256':'a'*64},'records':[record()]}),encoding='utf8')
    store=Store(tmp_path/'farm.sqlite3')
    with pytest.raises(ValueError,match='hash'):
        import_real(store,root)
    assert store.list_entities()['items']==[]


def test_reviewed_detail_binding_keeps_ledger_and_model_area_separate(tmp_path):
    store,_=build(tmp_path)
    identifier=store.list_entities()['items'][0]['id']
    store.import_manifest({'objects':[{'spatial_id':'DETAIL-L18','name':'L18','kind':'field','model_area_m2':2100,
        'business_source_key':'庙下刘:L18','link_verified':True,'link_evidence':'Reviewed drawing p1 + workbook row4'}]})
    entity=store.get_entity(identifier)
    assert store.list_entities()['total']==1
    assert entity['spatial_ids']==['DETAIL-L18']
    assert entity['area']['value']==3.25 and entity['area']['unit'] is None
    assert entity['model_area']==2100
    assert entity['model_areas'][0]['georeferenced'] is False


def test_mapping_export_uses_persisted_ids_and_does_not_claim_comparable_area(tmp_path):
    store,_=build(tmp_path)
    from backend.reporting import export_mappings
    result=export_mappings(store,tmp_path/'export')
    payload=json.loads((tmp_path/'export/entity-mapping.json').read_text(encoding='utf8'))
    assert payload['entities'][0]['resource_id']==store.list_entities()['items'][0]['id']
    report=json.loads((tmp_path/'export/ledger-model-area-reconciliation.json').read_text(encoding='utf8'))
    assert report['records'][0]['comparable'] is False
    assert report['records'][0]['difference_m2'] is None


def test_analysis_sections_have_seven_requested_parts_without_claiming_ai(tmp_path):
    store,client=build(tmp_path)
    entity=store.list_entities()['items'][0]
    reply=client.post('/api/assistant',json={'message':'分析','selected_entity_id':entity['id']}).json()
    assert [s['title'] for s in reply['analysis_sections']]==['对象','事实与证据','判断边界','处理建议','设备需求','复测与跟踪','来源']
    assert reply['analysis_kind']=='structured_database_inspection'
    assert reply['production_plan_accepted'] is False


def test_explicit_unknown_target_never_falls_back_to_previous_selection(tmp_path):
    store,client=build(tmp_path)
    selected=store.list_entities()['items'][0]['id']
    reply=client.post('/api/assistant',json={'message':'请进入L999','selected_entity_id':selected}).json()
    assert reply['status']=='not_found'
    assert reply['entity'] is None and reply['actions']==[]


def test_explicit_other_region_is_not_silently_ignored(tmp_path):
    store,client=build(tmp_path,[record(),record(code='L19',region='余湾')])
    selected=next(e['id'] for e in store.list_entities()['items'] if e['code']=='L18')
    reply=client.post('/api/assistant',json={'message':'查看余湾的L18','selected_entity_id':selected}).json()
    assert reply['status']=='not_found'
    assert reply['actions']==[]


def test_reviewed_region_spelling_alias_is_searchable_without_merging(tmp_path):
    store,client=build(tmp_path)
    page=client.get('/api/entities',params={'q':'庙下流'}).json()
    assert page['total']==1
    assert '庙下流' in page['items'][0]['region_aliases']
    reply=client.post('/api/assistant',json={'message':'查看庙下流L18'}).json()
    assert reply['entity']['id']==page['items'][0]['id']


def test_newer_database_schema_is_rejected_without_resetting_version(tmp_path):
    import sqlite3
    Store,_,_=components()
    path=tmp_path/'newer.sqlite3'
    with sqlite3.connect(path) as db:db.execute('PRAGMA user_version=99')
    with pytest.raises(ValueError,match='schema'):
        Store(path)
    with sqlite3.connect(path) as db:assert db.execute('PRAGMA user_version').fetchone()[0]==99


def test_assistant_returns_saved_drafts_only_for_selected_entity_and_dataset(tmp_path):
    store,client=build(tmp_path,[record(),record(code='L19')])
    entity=next(e for e in store.list_entities()['items'] if e['code']=='L18')
    plan=client.post('/api/plans',json={'title':'先核查现状','entity_id':entity['id'],'dataset':'real','content':'补充资料',
        'evidence_ids':[entity['sources'][0]['id']]}).json()
    reply=client.post('/api/assistant',json={'message':'查看历史','selected_entity_id':entity['id']}).json()
    assert reply['saved_plans'][0]['id']==plan['id']
    assert reply['saved_plans'][0]['status']=='draft'
    other=next(e for e in store.list_entities()['items'] if e['code']=='L19')
    assert client.post('/api/assistant',json={'message':'查看历史','selected_entity_id':other['id']}).json()['saved_plans']==[]


def test_explicit_spatial_retirement_preserves_business_identity_and_reimports(tmp_path):
    store,_=build(tmp_path)
    original=store.list_entities()['items'][0]['id']
    old={'objects':[{'spatial_id':'SAT-LAKE-001','name':'湖','kind':'lake'},{'spatial_id':'SAT-LAKE-002','name':'旧东汊','kind':'lake'}]}
    store.import_manifest(old)
    retired=next(e['id'] for e in store.list_entities()['items'] if e['spatial_ids']==['SAT-LAKE-002'])
    store.retire_spatial('SAT-LAKE-002','已审查：合并连续水面','real')
    store.import_manifest({'objects':[old['objects'][0]]})
    assert store.list_entities()['total']==2
    assert store.get_entity(original)['id']==original
    archived=store.get_entity(retired)
    assert archived['state']=='retired' and archived['spatial_ids']==[]
    assert store.audit_entries()[-1]['tool']=='spatial.retire'


def test_local_operator_session_rejects_cross_site_and_requires_write_role(tmp_path):
    Store,create_app,TestClient=components();store=Store(tmp_path/'farm.sqlite3');store.import_records([record()],'real')
    settings={'auth_mode':'local','admin_token':'admin-test-secret','operator_token':'operator-test-secret','session_secret':'test-session-key'}
    client=TestClient(create_app(store=store,settings=settings),client=('127.0.0.1',55123))
    entity=store.list_entities()['items'][0]
    body={'title':'核查','entity_id':entity['id'],'dataset':'real','content':'采集现状','evidence_ids':[entity['sources'][0]['id']]}
    assert client.post('/api/plans',json=body).status_code==401
    assert client.post('/api/auth/local-session',headers={'Origin':'https://evil.example','Host':'127.0.0.1:8000'}).status_code==403
    assert client.post('/api/auth/local-session',headers={'Origin':'http://127.0.0.1:5173','Host':'evil.example'}).status_code==403
    good={'Origin':'http://127.0.0.1:5173','Host':'127.0.0.1:8000'}
    assert client.post('/api/auth/local-session',headers=good).status_code==200
    assert client.post('/api/plans',json=body,headers=good).status_code==201
    assert client.post('/api/admin/imports/preview',json={'dataset':'real','records':[record('L20')]},headers=good).status_code==403


def test_admin_import_preview_apply_is_atomic_and_idempotent(tmp_path):
    store,client=build(tmp_path,settings={'auth_mode':'local','admin_token':'admin-test-secret','session_secret':'test-secret'})
    headers={'Authorization':'Bearer admin-test-secret'}
    preview=client.post('/api/admin/imports/preview',headers=headers,json={'dataset':'real','records':[record('L20')]} )
    assert preview.status_code==201
    assert store.list_entities()['total']==1
    p=preview.json()
    applied=client.post('/api/admin/imports/apply',headers=headers,json={'preview_id':p['id'],'content_digest':p['content_digest']})
    assert applied.status_code==200
    assert store.list_entities()['total']==2
    assert client.post('/api/admin/imports/apply',headers=headers,json={'preview_id':p['id'],'content_digest':p['content_digest']}).json()==applied.json()


def test_admin_stale_preview_cannot_overwrite_newer_record(tmp_path):
    store,client=build(tmp_path,settings={'auth_mode':'local','admin_token':'secret','session_secret':'key'})
    headers={'Authorization':'Bearer secret'}
    p=client.post('/api/admin/imports/preview',headers=headers,json={'dataset':'real','records':[record(area_original=5)]}).json()
    store.import_records([record(area_original=7)],'real')
    result=client.post('/api/admin/imports/apply',headers=headers,json={'preview_id':p['id'],'content_digest':p['content_digest']})
    assert result.status_code==409
    assert store.list_entities()['items'][0]['area']['value']==7


def test_v1_to_v2_migration_preserves_uuid_and_is_repeatable(tmp_path):
    import sqlite3
    Store,_,_=components();store,_=build(tmp_path);identifier=store.list_entities()['items'][0]['id']
    with sqlite3.connect(store.path) as db:db.execute('PRAGMA user_version=1')
    migrated=Store(store.path);again=Store(store.path)
    assert again.list_entities()['items'][0]['id']==identifier
    with sqlite3.connect(store.path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==2
        assert db.execute('SELECT COUNT(*) FROM schema_migrations WHERE version=2').fetchone()[0]==1


def test_public_reference_is_searchable_but_not_a_verified_site_fact(tmp_path):
    store,client=build(tmp_path,[record(kind='pond')])
    entry={'id':'official-pond-guide','kind':'knowledge','title':'池塘溶解氧核查','url':'https://example.gov.cn/guide',
        'publisher':'技术推广机构','version':'2026-v1','summary':'先监测并核实设备。','source_sha256':'b'*64,
        'data_nature':'verified_reference','scope':{'production':['pond_fish'],'requires':['species','current_observation']},
        'status':'reference_not_site_fact','steps':[]}
    store.import_knowledge([entry])
    results=client.get('/api/knowledge',params={'q':'溶解氧','dataset':'real','kind':'pond'}).json()['items']
    assert results[0]['reference_verified'] is True
    assert results[0]['site_fact'] is False and results[0]['data_nature']=='imported_unverified'
    entity=store.list_entities()['items'][0]
    reply=client.post('/api/assistant',json={'message':'溶解氧核查','selected_entity_id':entity['id']}).json()
    assert any(e['id']=='official-pond-guide' for e in reply['evidence'])
    assert reply['retrieval']['knowledge_ids']==['official-pond-guide']
    assert reply['production_plan_accepted'] is False


def test_upstream_shacl_rejects_device_without_manager(tmp_path):
    store,client=build(tmp_path,[record(kind='device',class_iris=['https://w3id.org/lzo/ontology/Sensor'])])
    result=client.post('/api/ontology/validate',json={'dataset':'real'} )
    assert result.status_code==200
    report=result.json();assert report['conforms'] is False
    assert any('managedBy' in issue['path'] for issue in report['issues'])
    assert report['upstream_commit']=='5776ba8d656139d3fb8dfabd137d83dd6dbba11c'


def test_relation_query_keeps_dataset_boundary(tmp_path):
    from backend.importer import initialize
    _,create_app,TestClient=components();store=initialize(tmp_path/'farm.sqlite3');client=TestClient(create_app(store=store,settings={}))
    identifier='d2c438ec-91f0-54e2-9de2-eba7f561db58'
    result=client.get('/api/relations/'+identifier+'?dataset=demo&depth=1')
    assert result.status_code==200 and result.json()['edges']
    assert all(n['dataset']=='demo' for n in result.json()['nodes'])
    assert client.get('/api/relations/'+identifier+'?dataset=real').status_code==404


def test_constrained_provider_cannot_generate_focus_without_spatial_binding(tmp_path,model_server):
    state,settings=model_server;settings['model_constrained_json']=True
    store,client=build(tmp_path,settings=settings);entity=store.list_entities()['items'][0]
    state['payload']={'answer':'先核查资料。','evidence_ids':[entity['sources'][0]['id']],'actions':[],'gaps':[],'suggested_plan':None}
    reply=client.post('/api/assistant',json={'message':'核查','selected_entity_id':entity['id']}).json()
    schema=state['request']['response_format']['schema']
    assert schema['properties']['actions']['maxItems']==0
    assert schema['properties']['evidence_ids']['items']['enum']==[entity['sources'][0]['id']]
    assert reply['status']=='ok'


def test_admin_semantic_preview_blocks_unmanaged_device(tmp_path):
    store,client=build(tmp_path,settings={'auth_mode':'local','admin_token':'secret','session_secret':'key'})
    headers={'Authorization':'Bearer secret'}
    p=client.post('/api/admin/imports/preview',headers=headers,json={'dataset':'real','records':[record('S1',kind='device')]}).json()
    assert p['semantic_validation']['conforms'] is False
    applied=client.post('/api/admin/imports/apply',headers=headers,json={'preview_id':p['id'],'content_digest':p['content_digest']})
    assert applied.status_code==422
    assert store.list_entities()['total']==1


def test_rule_uses_its_own_metric_freshness_and_checks_applicability(tmp_path):
    from datetime import datetime,timezone
    stamp=datetime.now(timezone.utc).isoformat()
    store,_=build(tmp_path,[record(kind='pond',observations=[{'metric':'dissolved_oxygen','value':2.4,'unit':'mg/L','observed_at':stamp},
        {'metric':'water_temperature','value':20,'unit':'C','observed_at':'2020-01-01T00:00:00Z'}],rules=[
        {'id':'r','name':'test','version':'v1','metric':'dissolved_oxygen','operator':'lt','threshold':3,'unit':'mg/L',
         'description':'review required','evidence_ids':[],'requires':['species']}])])
    alert=store.list_entities()['items'][0]['business_alerts'][0]
    assert alert['status']=='needs_context'
    assert 'species' in alert['applicability']['missing_context']
    assert alert['current_actionable'] is False


def test_registered_source_download_cannot_read_unregistered_or_traversal_path(tmp_path):
    store,client=build(tmp_path,[record(source_file='../.env',source_sha256='a'*64)])
    source=store.list_entities()['items'][0]['sources'][0]['id']
    assert client.get('/api/sources/'+source+'/file').status_code==403
    assert client.get('/api/sources/arbitrary/file').status_code==404


def test_public_kind_tags_include_freshwater_pond_reference(tmp_path):
    store,_=build(tmp_path)
    store.import_knowledge([{'id':'pond-ref','title':'溶解氧','url':'https://example.gov.cn/a','source_sha256':'a'*64,'version':'v1',
        'entity_kinds':['pond','lake'],'scope':{'production':['freshwater_pond']},'summary':'复测'}])
    assert store.knowledge('real','溶解氧','pond')['items'][0]['id']=='pond-ref'
    assert store.knowledge('real','溶解氧','field')['items']==[]


def test_complete_manifest_retires_missing_representation_without_changing_ledger_uuid(tmp_path):
    store,_=build(tmp_path);ledger=store.list_entities()['items'][0]
    linked={'spatial_id':'DETAIL-L18','business_source_key':ledger['source_key']['canonical_key'],
            'link_verified':True,'link_evidence':'review','model_area_m2':11772}
    store.import_manifest({'objects':[linked,{'spatial_id':'OLD-ROAD','kind':'road'}]})
    old=next(e for e in store.list_entities()['items'] if e['spatial_ids']==['OLD-ROAD'])
    current={'objects':[{**linked,'model_area_m2':None,'model_area_units2':200,'units':'paper_point',
                         'precision':'unregistered_drawing_geometry'}]}
    store.import_manifest(current,complete_snapshot=True)
    entity=store.get_entity(ledger['id'])
    assert entity['model_area'] is None and entity['spatial_ids']==['DETAIL-L18']
    assert entity['model_areas'][0]['area_units2']==200
    assert store.get_entity(old['id'])['state']=='retired'
    before=len(store.audit_entries());store.import_manifest(current,complete_snapshot=True)
    assert len(store.audit_entries())==before
    store.import_manifest({'objects':[]},complete_snapshot=True)
    assert store.get_entity(ledger['id'])['state']=='active'
    assert store.get_entity(ledger['id'])['spatial_ids']==[]


def test_runtime_archive_reuse_does_not_rewrite_running_files(tmp_path):
    import zipfile
    from scripts.setup_local_model import extract_verified
    archive=tmp_path/'runtime.zip';destination=tmp_path/'installed'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('runtime.dll',b'known official bytes')
    extract_verified(archive,destination)
    target=destination/'runtime.dll';stamp=target.stat().st_mtime_ns
    extract_verified(archive,destination)
    assert target.stat().st_mtime_ns==stamp
    with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape.dll',b'bad')
    with pytest.raises(ValueError,match='Unsafe archive'):
        extract_verified(archive,destination)


def test_independent_synthetic_scenario_has_complete_context_and_real_relations(tmp_path):
    from backend.importer import initialize
    store=initialize(tmp_path/'farm.sqlite3')
    pond=next(e for e in store.list_entities('demo')['items'] if e['code']=='DEMO-CHECK-POND')
    assert pond['species'] and pond['production_context']['stage']
    assert len(pond['devices'])==2 and len(pond['observations'])==2
    assert pond['spatial_ids']==[] and pond['data_nature']=='synthetic'
    assert all(o['observed_at']=='2026-10-29T01:00:00Z' for o in pond['observations'])
    assert len(pond['relations'])>=2
    identifier=pond['id'];again=initialize(store.path)
    assert again.get_entity(identifier,'demo')['revision']==pond['revision']
    assert all(e['code']!='DEMO-CHECK-POND' for e in store.list_entities('real')['items'])


def test_representation_sources_are_registered_and_paper_units_remain_explicit(tmp_path):
    store,_=build(tmp_path);ledger=store.list_entities()['items'][0]
    store.import_manifest({'objects':[{'spatial_id':'DRAW-L18','business_source_key':ledger['source_key']['canonical_key'],
        'link_verified':True,'link_evidence':'review','coordinate_units':'paper_point','model_area_m2':None,
        'source_evidence':[{'source_file':'sample.pdf','source_sha256':'a'*64,'page':1}]}]})
    updated=store.get_entity(ledger['id'])
    assert any(s.get('file')=='sample.pdf' and s.get('sha256')=='a'*64 for s in updated['sources'])
    assert updated['model_areas'][0]['source_unit']=='paper_point'


def test_assistant_does_not_mix_hot_weather_and_freezing_references(tmp_path):
    from backend.importer import initialize
    _,create_app,TestClient=components();store=initialize(tmp_path/'farm.sqlite3')
    client=TestClient(create_app(store=store,settings={}))
    pond=next(e for e in store.list_entities('demo')['items'] if e['code']=='DEMO-CHECK-POND')
    reply=client.post('/api/assistant',json={'message':'核查溶解氧和设备','dataset':'demo','selected_entity_id':pond['id']}).json()
    assert 'kb-hubei-pond-hot-weather-2024' in reply['retrieval']['knowledge_ids']
    assert 'kb-hubei-aquaculture-freezing-2024' not in reply['retrieval']['knowledge_ids']


def test_summary_reports_actual_public_knowledge_and_representation_counts(tmp_path):
    store,_=build(tmp_path)
    store.import_knowledge([{'id':'guide','url':'https://example.gov.cn/guide','source_sha256':'a'*64,'version':'v1'}])
    summary=store.summary()
    assert summary['data_status']['knowledge_base']=='public_references'
    assert summary['data_status']['public_reference_count']==1
    assert summary['representation_count']==0


def test_reviewed_ambiguous_representation_detaches_without_replacing_business_uuid(tmp_path):
    store,_=build(tmp_path);entity=store.list_entities()['items'][0];key=entity['source_key']['canonical_key']
    document={'source_file':'candidate.pdf','source_sha256':'a'*64,'page':1}
    original={'spatial_id':'DRAW-E3','business_source_key':key,'link_verified':True,'link_evidence':'old review','source_evidence':[document]}
    store.import_manifest({'objects':[original]})
    corrected={'spatial_id':'DRAW-E3','code':'E3','candidate_source_key':key,'link_verified':False,
        'identity_match_status':'ambiguous_repeated_code','link_evidence':'Reviewed repeated label belongs to a different drawing','source_evidence':[document]}
    store.import_manifest({'objects':[corrected]},complete_snapshot=True)
    assert store.get_entity(entity['id'])['spatial_ids']==[]
    independent=next(e for e in store.list_entities()['items'] if e['spatial_ids'])
    assert independent['id']!=entity['id']
    assert not any(e.get('file')=='candidate.pdf' for e in store.get_entity(entity['id'])['sources'])
    assert any(e.get('file')=='candidate.pdf' for e in independent['sources'])
    assert any(a['tool']=='spatial.reviewed_detach' for a in store.audit_entries())
    store.import_manifest({'objects':[corrected]},complete_snapshot=True)
    assert store.list_entities()['total']==2


def test_admin_semantic_preview_can_repair_an_existing_unmanaged_device(tmp_path):
    from backend.contracts import ONTOLOGY
    store,client=build(tmp_path,[record('ORG',kind='organization',class_iris=[ONTOLOGY+'Organization']),record('SENSOR',kind='device')],
        settings={'auth_mode':'local','admin_token':'secret','session_secret':'key'})
    manager=next(e for e in store.list_entities()['items'] if e['code']=='ORG')
    update=record('SENSOR',kind='device',relations=[{'predicate_iri':ONTOLOGY+'managedBy','target_id':manager['id']}])
    p=client.post('/api/admin/imports/preview',headers={'Authorization':'Bearer secret'},json={'dataset':'real','records':[update]}).json()
    assert p['semantic_validation']['conforms'] is True
    headers={'Authorization':'Bearer secret'}
    assert client.post('/api/admin/imports/apply',headers=headers,json={'preview_id':p['id'],'content_digest':p['content_digest']}).status_code==200
    assert client.post('/api/ontology/validate',json={'dataset':'real'}).json()['conforms'] is True
    # Omitting relations preserves existing owned assertions in both preview and persistence.
    p=client.post('/api/admin/imports/preview',headers=headers,json={'dataset':'real','records':[record('SENSOR',kind='device',name='Updated sensor')]}).json()
    assert p['semantic_validation']['conforms'] is True
    assert client.post('/api/admin/imports/apply',headers=headers,json={'preview_id':p['id'],'content_digest':p['content_digest']}).status_code==200
    assert client.post('/api/ontology/validate',json={'dataset':'real'}).json()['conforms'] is True


def test_unreviewed_spatial_detachment_does_not_leave_orphan_identity(tmp_path):
    store,_=build(tmp_path);entity=store.list_entities()['items'][0]
    store.import_manifest({'objects':[{'spatial_id':'DRAW','business_source_key':entity['source_key']['canonical_key'],
        'link_verified':True,'link_evidence':'review'}]})
    with pytest.raises(ValueError,match='silently rebound'):
        store.import_manifest({'objects':[{'spatial_id':'DRAW'}]})
    assert store.list_entities()['total']==1


def test_explicit_configuration_loads_dotenv_and_environment_precedence(tmp_path,monkeypatch):
    from backend.config import load_settings
    (tmp_path/'.env').write_text('FARM_MODEL_NAME=dotenv-model\nFARM_MODEL_MAX_TOKENS=1234\nFARM_MODEL_CONSTRAINED_JSON=false\n',encoding='utf8')
    monkeypatch.setenv('FARM_MODEL_NAME','environment-model')
    monkeypatch.setenv('FARM_CONFIG_FILE',str(tmp_path/'runtime/backend-config.json'))
    settings=load_settings(tmp_path)
    assert settings['model_name']=='environment-model'
    assert settings['model_max_tokens']==1234
    assert settings['model_constrained_json'] is False
    assert settings['auth_mode']=='local' and settings['admin_token']


def test_manifest_failure_rolls_back_the_whole_snapshot(tmp_path):
    store,_=build(tmp_path);entity=store.list_entities()['items'][0]
    store.import_manifest({'objects':[{'spatial_id':'BOUND','business_source_key':entity['source_key']['canonical_key'],
        'link_verified':True,'link_evidence':'review'}]})
    with pytest.raises(ValueError,match='silently rebound'):
        store.import_manifest({'objects':[{'spatial_id':'NEW'},{'spatial_id':'BOUND'}]},complete_snapshot=True)
    assert store.list_entities()['total']==1
    assert store.get_entity(entity['id'])['spatial_ids']==['BOUND']


def test_reviewed_restoration_reuses_retired_uuid_and_keeps_history(tmp_path):
    store,_=build(tmp_path)
    obj={'spatial_id':'DETAIL-QING17','code':'QING17','kind':'facility'}
    store.import_manifest({'objects':[obj]});entity=next(e for e in store.list_entities()['items'] if e['spatial_ids'])
    store.retire_spatial('DETAIL-QING17','Intermediate snapshot absent')
    store.restore_spatial('DETAIL-QING17','Reviewed same drawing facility is present in final snapshot')
    store.import_manifest({'objects':[obj]},complete_snapshot=True)
    restored=store.get_entity(entity['id'])
    assert restored['state']=='active' and restored['spatial_ids']==['DETAIL-QING17']
    assert restored['revision']>entity['revision']
    assert any(a['tool']=='spatial.restore' for a in store.audit_entries())


def test_token_mode_rejects_existing_local_cookie_but_keeps_bearer_roles(tmp_path):
    store,_=build(tmp_path);_,create_app,TestClient=components()
    settings={'auth_mode':'local','session_secret':'review-secret','admin_token':'review-admin','operator_token':'review-operator'}
    client=TestClient(create_app(store=store,settings=settings),client=('127.0.0.1',12345))
    headers={'Origin':'http://127.0.0.1:5173','Host':'127.0.0.1:8000'}
    assert client.post('/api/auth/local-session',headers=headers).status_code==200
    old_cookie=client.cookies.get('farm_session')
    token_client=TestClient(create_app(store=store,settings={**settings,'auth_mode':'token'}),client=('127.0.0.1',12345))
    token_client.cookies.set('farm_session',old_cookie)
    entity=store.list_entities()['items'][0]
    body={'title':'review','entity_id':entity['id'],'dataset':'real','content':'check','evidence_ids':[entity['sources'][0]['id']]}
    assert token_client.post('/api/plans',headers=headers,json=body).status_code==401
    for role in ('operator','admin'):
        assert token_client.post('/api/plans',headers={'Authorization':'Bearer review-'+role},json=body).status_code==201
    readonly=TestClient(create_app(store=store,settings={**settings,'auth_mode':'readonly'}))
    assert readonly.post('/api/plans',headers={'Authorization':'Bearer review-admin'},json=body).status_code==403


@pytest.mark.parametrize('change',[
    {'observations':None},{'observations':[None]},
    {'observations':[{'metric':'oxygen','value':'2.4','unit':'mg/L','observed_at':'2026-10-29T01:00:00Z'}]},
    {'observations':[{'metric':'oxygen','value':2.4,'unit':'mg/L','observed_at':123}]},
    {'observations':[{'metric':'oxygen','value':2.4,'unit':{},'observed_at':'2026-10-29T01:00:00Z'}]},
    {'devices':[{}]},{'relations':None},{'class_iris':'not-a-list'},{'production_context':[]},
])
def test_invalid_nested_import_is_rejected_before_preview_or_store_write(tmp_path,change):
    store,client=build(tmp_path,settings={'auth_mode':'token','admin_token':'review-admin'})
    rows=[record('GOOD'),record('BAD',**change)]
    response=client.post('/api/admin/imports/preview',headers={'Authorization':'Bearer review-admin'},json={'dataset':'real','records':rows})
    assert response.status_code==422
    with pytest.raises(ValueError):store.import_records(rows,'real')
    assert client.get('/api/entities').status_code==200 and client.get('/api/summary').status_code==200
    assert store.list_entities()['total']==1
    with store.connection() as db:assert db.execute('SELECT COUNT(*) FROM import_previews').fetchone()[0]==0


def test_external_relation_id_cannot_overwrite_other_dataset_or_subject(tmp_path):
    from backend.contracts import ONTOLOGY
    store,client=build(tmp_path,[record('REAL-TARGET')],settings={'auth_mode':'token','admin_token':'review-admin'})
    real_target=store.list_entities()['items'][0]['id']
    demo_target=store.import_records([record('DEMO-TARGET')],'demo')['items'][0]['id']
    external='same-external-relation-id'
    rel=lambda target:{'id':external,'predicate_iri':ONTOLOGY+'relatedTo','target_id':target,'state':'accepted','support':{'source':'review-test'}}
    demo_subject=store.import_records([record('DEMO-SUBJECT',relations=[rel(demo_target)])],'demo')['items'][0]['id']
    previous=next(r for r in store.get_entity(demo_subject,'demo')['relations'] if r['subject_id']==demo_subject)
    p=client.post('/api/admin/imports/preview',headers={'Authorization':'Bearer review-admin'},json={'dataset':'real','records':[
        record('SUBJECT-ONE',relations=[rel(real_target)]),record('SUBJECT-TWO',relations=[rel(real_target)])]}).json()
    assert client.post('/api/admin/imports/apply',headers={'Authorization':'Bearer review-admin'},json={'preview_id':p['id'],'content_digest':p['content_digest']}).status_code==200
    assert store.get_entity(demo_subject,'demo')['relations']==[previous]
    with store.connection() as db:
        rows=db.execute('SELECT id,payload FROM relations').fetchall()
        assert len(rows)==3 and len({r['id'] for r in rows})==3
        assert all(json.loads(r['payload'])['external_id']==external for r in rows)
        assert all(json.loads(r['payload'])['support']=={'source':'review-test'} for r in rows)


@pytest.mark.parametrize('state',['rejected','tentative'])
def test_semantic_preview_and_persisted_graph_share_relation_state_filter(tmp_path,state):
    from backend.contracts import ONTOLOGY
    store,client=build(tmp_path,[record('ORG',kind='organization',class_iris=[ONTOLOGY+'Organization'])],
        settings={'auth_mode':'token','admin_token':'review-admin'})
    manager=store.list_entities()['items'][0]['id']
    update=record('SENSOR',kind='device',relations=[{'predicate_iri':ONTOLOGY+'managedBy','target_id':manager,'state':state}])
    headers={'Authorization':'Bearer review-admin'}
    p=client.post('/api/admin/imports/preview',headers=headers,json={'dataset':'real','records':[update]}).json()
    assert p['semantic_validation']['conforms'] is False
    assert client.post('/api/admin/imports/apply',headers=headers,json={'preview_id':p['id'],'content_digest':p['content_digest']}).status_code==422
    assert store.list_entities()['total']==1


def test_no_applicable_knowledge_reports_retrieval_gap_not_empty_library(tmp_path):
    store,client=build(tmp_path)
    store.import_knowledge([{'id':'pond-only','url':'https://example.gov.cn/a','source_sha256':'a'*64,'entity_kinds':['pond']}])
    entity=store.list_entities()['items'][0]
    reply=client.post('/api/assistant',json={'message':'查看资料','selected_entity_id':entity['id']}).json()
    assert any('未检索到适用于当前对象的知识依据' in gap for gap in reply['gaps'])


def test_conflicting_duplicate_relation_identity_cannot_pass_semantic_preview(tmp_path):
    from backend.contracts import ONTOLOGY
    store,client=build(tmp_path,[record('ORG',kind='organization')],settings={'auth_mode':'token','admin_token':'review-admin'})
    manager=store.list_entities()['items'][0]['id']
    relation={'id':'same-assertion','predicate_iri':ONTOLOGY+'managedBy','target_id':manager,'state':'accepted'}
    malformed=record('SENSOR',kind='device',relations=[relation,{**relation,'state':'rejected'}])
    response=client.post('/api/admin/imports/preview',headers={'Authorization':'Bearer review-admin'},json={'dataset':'real','records':[malformed]})
    assert response.status_code==422
    with pytest.raises(ValueError,match='Conflicting duplicate relation'):store.import_records([malformed],'real')
    assert store.list_entities()['total']==1
