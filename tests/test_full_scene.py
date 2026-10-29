from backend.store import Store
from pathlib import Path
import copy
import json
import pytest


def geometry():
    return {'objects':[
        {'spatial_id':'SAT-FIELD-001','asset_id':'full','name':'田块 01','kind':'field','center':[10,0,20],'bounds':{'min':[0,0,0],'max':[20,2,40]}},
        {'spatial_id':'SAT-POND-001','asset_id':'full','name':'水塘 01','kind':'pond','center':[60,0,20],'bounds':{'min':[40,0,0],'max':[80,2,40]}},
        {'spatial_id':'SAT-VILLAGE-001','asset_id':'full','name':'村落 01','kind':'settlement','center':[110,0,20]},
        {'spatial_id':'DRAW-1','asset_id':'detail','name':'图纸','kind':'field','center':[0,0,0]},
        {'spatial_id':'BG-ROOF-001','asset_id':'full','kind':'building','representation_only':True,'source_status':'sample'}]}


def scenario():
    return json.loads((Path(__file__).resolve().parents[1]/'data/demo/full-area-scenario.json').read_text(encoding='utf-8'))


def test_full_scene_scenario_reuses_geometry_without_mutating_real_and_keeps_ids(tmp_path):
    from backend.scenario import import_full_scene
    store=Store(tmp_path/'scene.sqlite3');store.import_manifest(geometry())
    before={e['id']:e for e in store.list_entities('real')['items']}
    result=import_full_scene(store,geometry(),scenario(),'a'*64)
    demo=store.list_entities('demo')['items'];principals=[e for e in demo if e['scene_anchor'] and e['scene_anchor']['role']=='object']
    assert len(principals)==3
    assert all(e['data_nature']=='synthetic' and e['dataset']=='demo' for e in demo)
    assert {e['spatial_ids'][0] for e in principals}=={'SAT-FIELD-001','SAT-POND-001','SAT-VILLAGE-001'}
    assert not set(before)&{e['id'] for e in demo}
    assert {e['id']:e for e in store.list_entities('real')['items']}==before
    ids={e['id']:e['revision'] for e in demo};import_full_scene(store,geometry(),scenario(),'a'*64)
    assert {e['id']:e['revision'] for e in store.list_entities('demo')['items']}==ids
    assert result['principal_count']==3


def test_devices_are_entities_with_accepted_relations_observations_and_visible_scene_anchor(tmp_path):
    from backend.scenario import import_full_scene
    from backend.semantics import neighborhood
    store=Store(tmp_path/'scene.sqlite3');store.import_manifest(geometry());import_full_scene(store,geometry(),scenario(),'a'*64)
    entities=store.list_entities('demo')['items'];devices=[e for e in entities if e['kind']=='device']
    assert len(devices)>=3
    for device in devices:
        assert not device['spatial_ids']
        assert device['scene_anchor']['role']=='device' and len(device['scene_anchor']['offset'])==3
        assert device['observations'] and device['sources']
        graph=neighborhood(store,device['id'],'demo',1)
        expected='/serves' if any(c.endswith('/Pump') for c in device['class_iris']) else '/monitors'
        assert any(e['predicate_iri'].endswith(expected) for e in graph['edges'])
    pond=next(e for e in entities if e['kind']=='pond')
    assert pond['business_alerts'] and pond['business_alerts'][0]['condition_historically_met']
    assert pond['business_alerts'][0]['current_actionable'] is False
    assert store.summary('demo')['scene']['principal_count']==3


def test_render_only_geometry_is_not_imported_as_real_business_asset(tmp_path):
    store=Store(tmp_path/'scene.sqlite3');store.import_manifest(geometry())
    assert not any('BG-ROOF' in e['code'] for e in store.list_entities('real')['items'])


def test_business_and_device_overrides_are_replaceable_without_changing_identity(tmp_path):
    from backend.scenario import import_full_scene
    store=Store(tmp_path/'scene.sqlite3');config=scenario();import_full_scene(store,geometry(),config,'a'*64)
    pond=next(e for e in store.list_entities('demo')['items'] if e['kind']=='pond')
    config['overrides']={'SAT-POND-001':{'species':'鲤鱼（演示）','observations':[{'metric':'dissolved_oxygen','label':'替换观测','value':5.7,'unit':'mg/L'}]}}
    config['device_overrides']={'SAT-POND-001:sensor':{'name':'替换后的样例设备','observations':[{'metric':'dissolved_oxygen','label':'设备替换观测','value':9.2,'unit':'mg/L'}]}}
    import_full_scene(store,geometry(),config,'b'*64)
    updated=store.get_entity(pond['id'],'demo');assert updated['species']=='鲤鱼（演示）';assert updated['observations'][0]['value']==5.7
    device=next(e for e in store.list_entities('demo')['items'] if e['name']=='替换后的样例设备');assert device['observations'][0]['value']==9.2


def test_removing_scenario_device_retires_only_its_identity_and_edges_then_can_restore(tmp_path):
    from backend.scenario import import_full_scene,build_device_layout
    store=Store(tmp_path/'scene.sqlite3');layout=build_device_layout(geometry());config=scenario();import_full_scene(store,geometry(),config,'a'*64,layout)
    old=next(e for e in store.list_entities('demo')['items'] if e['code']=='DEMO-DEVICE-'+layout['devices'][0]['key'])
    external=store.import_records([{'source_id':'other-demo','source_key':'unrelated','name':'其他演示来源','kind':'organization'}],'demo')['items'][0]['id']
    updated=copy.deepcopy(layout);updated['devices']=updated['devices'][1:];import_full_scene(store,geometry(),config,'a'*64,updated)
    assert store.get_entity(old['id'],'demo')['state']=='retired'
    assert old['id'] not in {e['id'] for e in store.list_entities('demo')['items']}
    with store.connection() as db:assert db.execute('SELECT COUNT(*) FROM relations WHERE subject_id=? OR target_id=?',(old['id'],old['id'])).fetchone()[0]==0
    assert store.get_entity(external,'demo')['state']=='active'
    import_full_scene(store,geometry(),config,'a'*64,layout);assert store.get_entity(old['id'],'demo')['state']=='active'


@pytest.mark.parametrize('fault',['duplicate','unknown_parent','nonnumeric_offset'])
def test_bad_device_layout_is_rejected_before_any_scenario_write(tmp_path,fault):
    from backend.scenario import import_full_scene,build_device_layout
    store=Store(tmp_path/'scene.sqlite3');layout=build_device_layout(geometry())
    if fault=='duplicate':layout['devices'].append(copy.deepcopy(layout['devices'][0]))
    elif fault=='unknown_parent':layout['devices'][0]['parent_spatial_id']='SAT-NONEXISTENT'
    else:layout['devices'][0]['offset'][0]='not-a-coordinate'
    with pytest.raises(ValueError):import_full_scene(store,geometry(),scenario(),'a'*64,layout)
    assert store.list_entities('demo')['total']==0


@pytest.mark.parametrize('section',['defaults','device_defaults','production_context_defaults'])
def test_bad_configuration_sections_reject_as_validation_error_without_writes(tmp_path,section):
    from backend.scenario import import_full_scene
    store=Store(tmp_path/'scene.sqlite3');config=scenario();config[section]=[]
    with pytest.raises(ValueError,match='must be an object'):import_full_scene(store,geometry(),config,'a'*64)
    assert store.list_entities('demo')['total']==0
