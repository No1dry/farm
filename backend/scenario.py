"""Explicit synthetic business scenario over separately owned real geometry references."""
from uuid import NAMESPACE_URL, uuid5
import re
import json
import math
from .contracts import ONTOLOGY
from .store import canonical,digest,now


def build_device_layout(manifest,scenario_id='full-area-demo-v1'):
    counts={};devices=[]
    for obj in sorted(manifest.get('objects',[]),key=lambda o:o.get('spatial_id','')):
        if obj.get('asset_id')!='full' or not obj.get('spatial_id','').startswith('SAT-') or obj.get('representation_only'):continue
        kind=obj.get('kind');counts[kind]=counts.get(kind,0)+1;number=counts[kind];spatial=obj['spatial_id']
        if number==1 or kind in ('settlement','channel') or number%4==1:
            water=kind in ('pond','lake','channel');camera=kind in ('settlement','road')
            devices.append({'key':spatial+':sensor','parent_spatial_id':spatial,'asset_id':'full','offset':[16,(-.78 if water else 0)-obj.get('center',[0,0,0])[1],-12],
                'class':'Camera' if camera else 'Sensor','device_type':'camera_pole' if camera else 'water_sensor' if water else 'soil_sensor',
                'name':('视频巡查点' if camera else '水情监测仪' if water else '土壤监测仪')+' · 演示','predicate':'monitors','data_nature':'synthetic'})
        if kind in ('pond','lake') and number%8==1:
            devices.append({'key':spatial+':pump','parent_spatial_id':spatial,'asset_id':'full','offset':[-18,-.78-obj.get('center',[0,0,0])[1],8],
                'class':'Pump','device_type':'aerator','name':'增氧设备登记 · 演示','predicate':'serves','data_nature':'synthetic'})
    return {'schema_version':'farm-scene-device-layout/1','scenario_id':scenario_id,'data_nature':'synthetic',
            'coordinate_system':'THREE_Y_UP','units':'metres_illustrative','position_rule':'manifest.objects[parent_spatial_id].center + offset',
            'description':'可替换合成设备位置；非现场测绘。模型与浏览器标签读取相同偏移，标签可另抬高便于阅读。','devices':devices}


def import_full_scene(store,manifest,scenario,source_hash,layout=None):
    scenario_id=scenario['id'];reference_time=scenario['reference_time']
    source_file='data/demo/full-area-scenario.json';source_label='full-area-synthetic-scenario'
    objects=[o for o in manifest.get('objects',[]) if o.get('asset_id')=='full'
             and o.get('spatial_id','').startswith('SAT-') and not o.get('representation_only') and o.get('business_entity') is not False]
    objects.sort(key=lambda o:o['spatial_id'])
    uid=lambda key:str(uuid5(NAMESPACE_URL,'farm:scenario:'+scenario_id+':'+key))
    source_id='scenario-'+scenario_id+'-recipe-'+source_hash[:12]
    scenario_meta={key:scenario[key] for key in ('id','label','reference_time','description')}
    scenario_meta.update(data_nature='synthetic',site_fact=False,source_file=source_file,configuration_version=source_hash)
    base={'source_id':source_label,'source_system':'farm-synthetic-scenario','source_instance':scenario_id,
          'source_file':source_file,'source_sha256':source_hash,'source_description':scenario['description'],
          'data_nature':'synthetic','region':'卫星全域 · 合成演示','scenario':scenario_meta,
          'extra_sources':[{'id':source_id,'file':source_file,'sha256':source_hash,'version':scenario_id,
                            'title':scenario['label'],'description':scenario['description'],'kind':'synthetic_scenario'}]}
    organization=uid('organization')
    records=[{**base,'resource_id':organization,'source_key':scenario_id+':organization','original_code':'DEMO-FULL-ORG',
              'name':'全域演示管理组','kind':'organization','class_iris':[ONTOLOGY+'Organization']}]
    kind_names={'field':'田块','pond':'水塘','lake':'湖面','settlement':'村落','woodland':'林地','road':'道路','channel':'沟渠','bare':'待用地'}
    counts={};bindings=[];layout=layout or build_device_layout(manifest,scenario_id)
    if layout.get('scenario_id')!=scenario_id or layout.get('coordinate_system')!='THREE_Y_UP':raise ValueError('Scenario device layout coordinate/identity mismatch')
    try:json.dumps([scenario,layout],allow_nan=False)
    except (ValueError,TypeError):raise ValueError('Scenario configuration must be finite JSON') from None
    for section in ('defaults','device_defaults','production_context_defaults'):
        value=scenario.get(section,{})
        if not isinstance(value,dict):raise ValueError(section+' must be an object')
        if section!='production_context_defaults' and any(not isinstance(item,dict) for item in value.values()):raise ValueError(section+' entries must be an object')
    parents={o['spatial_id'] for o in objects};device_keys=set()
    if not isinstance(layout.get('devices'),list):raise ValueError('Device layout must contain a devices list')
    for device in layout['devices']:
        if not isinstance(device,dict):raise ValueError('Device layout entry must be an object')
        key=device.get('key');parent=device.get('parent_spatial_id');offset=device.get('offset')
        if not isinstance(key,str) or key in device_keys:raise ValueError('Duplicate or invalid device key')
        if parent not in parents or not key.startswith(parent+':'):raise ValueError('Device references an unknown or mismatched parent')
        if not isinstance(offset,list) or len(offset)!=3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in offset):raise ValueError('Device offset must contain three finite numbers')
        if device.get('class') not in ('Sensor','Camera','Pump','Device') or device.get('predicate') not in ('monitors','serves'):raise ValueError('Unsupported scenario device class or relation')
        if not isinstance(device.get('name'),str) or not isinstance(device.get('device_type'),str):raise ValueError('Device name and type are required')
        device_keys.add(key)
    for section,allowed in (('overrides',parents),('device_overrides',device_keys)):
        values=scenario.get(section,{})
        if not isinstance(values,dict) or any(key not in allowed or not isinstance(value,dict) for key,value in values.items()):raise ValueError(section+' contains an unknown key or invalid override')
    if layout.get('_source_sha256'):
        base['extra_sources'].append({'id':'scenario-'+scenario_id+'-device-layout-'+layout['_source_sha256'][:12],'file':'data/demo/full-area-device-layout.json',
            'sha256':layout['_source_sha256'],'version':layout['_source_sha256'],'title':'全域样例设备可替换位置参数','kind':'synthetic_scenario',
            'description':'Three Y-up；父空间中心加offset。设备及位置为样例，不是现场核验资产。'})
    def relation(predicate,target):
        return {'predicate_iri':ONTOLOGY+predicate,'target_id':target,'state':'accepted','data_nature':'synthetic',
                'support':{'source_file':source_file,'source_sha256':source_hash,'scenario_id':scenario_id,'site_fact':False}}
    def observations(specs,number):
        if not isinstance(specs,list):raise ValueError('Scenario observations must be a list')
        output=[]
        for spec in specs:
            if not isinstance(spec,dict):raise ValueError('Scenario observation must be an object')
            sample={key:value for key,value in spec.items() if key!='sample_case'};case=spec.get('sample_case')
            if case:
                every=case.get('every')
                if isinstance(every,bool) or not isinstance(every,int) or every<1:raise ValueError('sample_case.every must be a positive integer')
                if (number-1)%every==0:sample['value']=case['value']
            sample.setdefault('observed_at',reference_time);sample.setdefault('stale_after_hours',24)
            sample['label']=sample.get('label',sample.get('metric','观测')).replace('（演示）','')+'（演示）'
            sample.update(source_id=source_id,data_nature='synthetic',site_fact=False);output.append(sample)
        return output
    for index,obj in enumerate(objects):
        spatial=obj['spatial_id'];kind=obj.get('kind','spatial');counts[kind]=counts.get(kind,0)+1;number=counts[kind]
        geometry_name=obj.get('name') or spatial;place_name=re.sub(r'可见.*$','',geometry_name)
        identifier=uid(spatial);anchor={'spatial_id':spatial,'asset_id':'full','offset':[0,6,0],'role':'object',
            'scenario_id':scenario_id,'reference_kind':'scenario_geometry_reference','data_nature':'synthetic','site_fact':False}
        config={**scenario.get('defaults',{}).get(kind,{}),**scenario.get('overrides',{}).get(spatial,{})}
        readings=observations(config.get('observations',[]),number)
        device_specs=[d for d in layout['devices'] if d['parent_spatial_id']==spatial]
        sensor_spec=next((d for d in device_specs if d['predicate']=='monitors'),None)
        sensor=uid(sensor_spec['key']) if sensor_spec else None
        if sensor:
            readings=[{**reading,'device_id':sensor} for reading in readings]
        record={**base,'resource_id':identifier,'source_key':scenario_id+':'+spatial,'original_code':'DEMO-'+spatial,
                'name':config.get('name') or (place_name if kind=='settlement' else kind_names.get(kind,'空间')+f' {number:02d}')+' · 演示','kind':kind,
                'aliases':list(dict.fromkeys([spatial,geometry_name,place_name]+re.findall(r'[\u4e00-\u9fff]+?(?:村|湾)',place_name))),
                'class_iris':[ONTOLOGY+{'field':'Field','pond':'Pond','lake':'Pond'}.get(kind,'SpatialAsset')],
                'scene_anchor':anchor,'scenario_properties':{'geometry_source':obj.get('precision','approximate_satellite'),
                    'usage':config.get('usage','空间管理样例'),
                    'original_geometry_name':obj.get('name'),'real_business_identity_claimed':False},
                'species':config.get('species'),
                'production_context':{**scenario.get('production_context_defaults',{}),'production':config.get('production','spatial_management'),**config.get('production_context',{})},
                'observations':readings,'devices':[],'relations':[relation('managedBy',organization)],'rules':[]}
        record['scenario_properties'].update(model_area_m2=config.get('model_area_m2',obj.get('model_area_m2')),area_basis='卫星概略轮廓模型估算或配置样例；非现场台账或测绘面积')
        rule=config.get('rule')
        if rule:
            every=rule.get('every',1)
            if not isinstance(every,int) or isinstance(every,bool) or every<1 or rule.get('operator')!='lt':raise ValueError('Scenario rule requires positive every and supported lt operator')
            if (number-1)%every==0:record['rules']=[{**{k:v for k,v in rule.items() if k!='every'},'id':'demo-'+scenario_id+'-'+spatial,
                'evidence_ids':[source_id],'production_approved':False}]
        records.append(record)
        bindings.append((spatial,identifier,{**obj,'entity_uuid':identifier,'data_nature':'synthetic','scenario_id':scenario_id,
            'business_source_key':record['source_key'],'link_verified':False,'link_evidence':'Explicit synthetic scenario placement; not a real-world identity assertion.'}))
        for spec in device_specs:
            device_config={**scenario.get('device_defaults',{}).get(spec['class'],{}),**scenario.get('device_overrides',{}).get(spec['key'],{})}
            device_id=uid(spec['key']);name=device_config.get('name',spec['name']);record['devices'].append({'id':device_id,'name':name,'kind':'device','data_nature':'synthetic','live_status':None})
            device_readings=observations(device_config['observations'],number) if 'observations' in device_config else readings if device_config.get('inherit_observations') else []
            records.append({**base,'resource_id':device_id,'source_key':scenario_id+':'+spec['key'],'original_code':'DEMO-DEVICE-'+spec['key'],
                'name':name,'kind':'device','class_iris':[ONTOLOGY+spec['class']],
                'scene_anchor':{**anchor,'offset':spec['offset'],'role':'device'},
                'observations':[{**reading,'device_id':device_id} for reading in device_readings],
                'relations':[relation('managedBy',organization),relation(spec['predicate'],identifier)],
                'scenario_properties':{'device_key':spec['key'],'device_type':spec['device_type'],'live_connection':False,'readiness':device_config.get('readiness','固定合成记录；未接现场，运行适用性须核查'),
                    'geometry_source':'data/demo/full-area-device-layout.json','layout_version':layout.get('schema_version'),'device_control':False}})
    # One transaction covers object records, independent device identities and demo-only geometry links.
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE');token=store._active_connection.set(db)
        try:
            previous=[dict(row) for row in db.execute("SELECT e.* FROM entities e JOIN source_systems s ON e.source_id=s.id WHERE e.dataset='demo' AND s.source_key=?",(source_label,)) if json.loads(row['payload']).get('scenario',{}).get('id')==scenario_id]
            store.import_records(records,'demo',preserve_ids=True)
            for spatial,identifier,metadata in bindings:
                prior=db.execute('SELECT entity_id FROM spatial_bindings WHERE dataset=? AND spatial_id=?',('demo',spatial)).fetchone()
                if prior and prior['entity_id']!=identifier:raise ValueError('Demo spatial identity already belongs to another scenario')
                db.execute('INSERT OR REPLACE INTO spatial_bindings VALUES (?,?,?,?)',('demo',spatial,identifier,canonical(metadata)))
            current={r['resource_id'] for r in records};retired=[];restored=[]
            for row in previous:
                payload=json.loads(row['payload'])
                if row['id'] in current:
                    if payload.get('state')=='retired':restored.append(row['id'])
                    continue
                if payload.get('state')=='retired':continue
                payload.update(state='retired',retired_at=now(),retirement_reason='Removed from synthetic scenario configuration '+scenario_id)
                revision=row['revision']+1;db.execute('UPDATE entities SET payload=?,content_digest=?,revision=?,updated_at=? WHERE id=?',(canonical(payload),digest(payload),revision,now(),row['id']))
                db.execute('INSERT INTO entity_versions VALUES (?,?,?,?)',(row['id'],revision,canonical(payload),now()))
                db.execute("DELETE FROM relations WHERE dataset='demo' AND (subject_id=? OR target_id=?)",(row['id'],row['id']))
                for binding in db.execute("SELECT spatial_id,payload FROM spatial_bindings WHERE dataset='demo' AND entity_id=?",(row['id'],)).fetchall():
                    metadata=json.loads(binding['payload']);metadata.update(state='retired',retirement_reason=payload['retirement_reason'])
                    db.execute("UPDATE spatial_bindings SET payload=? WHERE dataset='demo' AND spatial_id=?",(canonical(metadata),binding['spatial_id']))
                retired.append(row['id'])
            store.audit('scenario.import','demo',{'scenario_id':scenario_id,'principal_count':len(bindings),'record_count':len(records),'retired_ids':retired,'restored_ids':restored,'source_sha256':source_hash,'real_records_modified':False})
        finally:store._active_connection.reset(token)
    return {'scenario_id':scenario_id,'principal_count':len(bindings),'record_count':len(records)}
