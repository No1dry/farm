"""Shared strict structural checks before preview or any persistent record write."""
from datetime import datetime
import json
import math
import re
from uuid import UUID


def string(value,path,nullable=False):
    if nullable and value is None:return
    if not isinstance(value,str) or not value.strip():raise ValueError(path+' must be a nonempty string')


def number(value,path,nullable=False,minimum=None):
    if nullable and value is None:return
    try:finite=not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)
    except OverflowError:finite=False
    if not finite:raise ValueError(path+' must be a finite number')
    if minimum is not None and value<minimum:raise ValueError(path+' is below its allowed minimum')


def sequence(record,key,element_type):
    values=record.get(key,[])
    if not isinstance(values,list) or any(not isinstance(v,element_type) for v in values):
        raise ValueError(key+' must be a list of '+element_type.__name__+' values')
    return values


def iri(value,path):
    string(value,path)
    if not re.match(r'^(https?://|urn:)[^\s<>"{}]+$',value):raise ValueError(path+' must be an absolute IRI')


def identifier(value,path):
    string(value,path)
    try:UUID(value)
    except (ValueError,AttributeError):raise ValueError(path+' must be a UUID') from None


def validate_record(record,dataset):
    if not isinstance(record,dict):raise ValueError('Record must be an object')
    # Canonical JSON check rejects nonfinite numbers even in optional metadata.
    try:json.dumps(record,allow_nan=False)
    except (ValueError,TypeError):raise ValueError('Record must contain finite JSON values') from None
    for key in ('source_id','source_key'):string(record.get(key),key)
    for key in ('kind','name','region','original_code','record_id','source_file','source_sheet','source_description','source_system','source_instance'):
        if key in record:string(record[key],key)
    for key in ('area_unit','inferred_unit','species','source_sha256'):
        if key in record:string(record[key],key,nullable=True)
    if 'area_original' in record:number(record['area_original'],'area_original',nullable=True,minimum=0)
    if dataset=='real' and record.get('data_nature') in ('synthetic','test'):raise ValueError('Synthetic records cannot enter real dataset')
    for key in ('production_context','source_pk','spatial_metadata','scenario','scenario_properties','scene_anchor'):
        if key in record and not isinstance(record[key],dict):raise ValueError(key+' must be an object')
    if 'scene_anchor' in record:
        anchor=record['scene_anchor'];string(anchor.get('spatial_id'),'scene_anchor.spatial_id')
        if anchor.get('role') not in ('object','device'):raise ValueError('scene_anchor.role is invalid')
        offset=anchor.get('offset',[])
        if not isinstance(offset,list) or len(offset)!=3:raise ValueError('scene_anchor.offset must have three coordinates')
        for value in offset:number(value,'scene_anchor.offset')
        if anchor.get('scenario_id') and dataset!='demo':raise ValueError('Synthetic scene anchors cannot enter real dataset')
    if 'geometry' in record and record['geometry'] is not None and not isinstance(record['geometry'],dict):raise ValueError('geometry must be an object or null')
    for key in ('stage','season','weather','production','region','site_applicability'):
        context=record.get('production_context',{})
        if key in context:string(context[key],'production_context.'+key,nullable=True)
    for value in sequence(record,'class_iris',str):iri(value,'class_iris item')
    for value in sequence(record,'aliases',str):string(value,'aliases item')
    for item in sequence(record,'observations',dict):
        string(item.get('metric'),'observation.metric');string(item.get('unit'),'observation.unit')
        number(item.get('value'),'observation.value')
        if 'stale_after_hours' in item:number(item['stale_after_hours'],'observation.stale_after_hours',minimum=0)
        if 'observed_at' in item:
            string(item['observed_at'],'observation.observed_at')
            try:
                sampled=datetime.fromisoformat(item['observed_at'].replace('Z','+00:00'))
                if sampled.tzinfo is None:raise ValueError()
            except ValueError:raise ValueError('observation.observed_at must be an ISO timestamp with timezone') from None
        for key in ('id','label','device_id','source_id'):
            if key in item:string(item[key],'observation.'+key)
    for item in sequence(record,'devices',dict):
        identifier(item.get('id'),'device.id')
        for key in ('name','kind'):
            if key in item:string(item[key],'device.'+key)
    relation_keys={}
    for item in sequence(record,'relations',dict):
        iri(item.get('predicate_iri'),'relation.predicate_iri');identifier(item.get('target_id'),'relation.target_id')
        for key in ('id','external_id','state'):
            if key in item:string(item[key],'relation.'+key)
        if 'subject_id' in item:identifier(item['subject_id'],'relation.subject_id')
        if 'support' in item and not isinstance(item['support'],dict):raise ValueError('relation.support must be an object')
        external_id=item.get('external_id') or item.get('id')
        key=('external',external_id) if external_id else ('edge',item['predicate_iri'],item['target_id'])
        value=json.dumps(item,sort_keys=True,allow_nan=False)
        if key in relation_keys and relation_keys[key]!=value:raise ValueError('Conflicting duplicate relation identity within record')
        relation_keys[key]=value
    for key in ('knowledge','extra_sources'):
        for item in sequence(record,key,dict):
            for field in ('id','title','file','url','version','description'):
                if field in item:string(item[field],key+'.'+field)
    for item in sequence(record,'rules',dict):
        for field in ('id','name','version','description','metric','operator','unit'):string(item.get(field),'rule.'+field)
        number(item.get('threshold'),'rule.threshold')
        for field in ('requires','evidence_ids'):
            for value in sequence(item,field,str):string(value,'rule.'+field)
        if 'production_approved' in item and not isinstance(item['production_approved'],bool):raise ValueError('rule.production_approved must be boolean')
