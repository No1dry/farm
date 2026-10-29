from backend.assistant import resolve
from backend.importer import initialize


def test_current_pond_reference_is_not_hijacked_by_a_generic_demo_name(tmp_path):
    store = initialize(tmp_path / 'farm.sqlite3')
    entities = store.list_entities('demo', limit=1000)['items']
    pond = next(e for e in entities if e['code'] == 'DEMO-SAT-POND-001')
    legacy = next(e for e in entities if e['code'] == 'DEMO-POND-40666cd6')
    assert pond['id'] != legacy['id']
    found = resolve(store, '分析当前演示水塘的预警，核查本体关联设备、观测与来源', pond['id'], 'demo')
    assert [e['id'] for e in found] == [pond['id']]


def test_current_reference_does_not_override_an_explicit_code_or_unknown_identifier(tmp_path):
    store = initialize(tmp_path / 'farm.sqlite3')
    entities = store.list_entities('demo', limit=1000)['items']
    pond = next(e for e in entities if e['code'] == 'DEMO-SAT-POND-001')
    legacy = next(e for e in entities if e['code'] == 'DEMO-POND-40666cd6')
    found = resolve(store, '离开当前演示水塘，进入 DEMO-POND-40666cd6', pond['id'], 'demo')
    assert [e['id'] for e in found] == [legacy['id']]
    target = next(e for e in entities if e['code'] == 'DEMO-SAT-POND-002')
    found = resolve(store, '离开当前演示水塘，进入 DEMO-SAT-POND-002', pond['id'], 'demo')
    assert [e['id'] for e in found] == [target['id']]
    assert resolve(store, '离开当前演示水塘，进入 X9999', pond['id'], 'demo') == []
