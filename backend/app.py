"""Loopback-only deployment by default: python -m backend (port 8000)."""
import os
from pathlib import Path
from typing import Literal
from uuid import UUID
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .assistant import query_assistant, model_status
from .contracts import Dataset, UPSTREAM
from .store import Store
from .auth import Authorization
from .config import load_settings

ROOT=Path(__file__).resolve().parents[1]


class HistoryMessage(BaseModel):
    model_config=ConfigDict(extra='forbid')
    role: Literal['user','assistant']
    content: str = Field(max_length=4000)


class AssistantRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message: str = Field(min_length=1,max_length=4000)
    selected_entity_id: str | None = None
    dataset: Dataset = 'real'
    history: list[HistoryMessage] = Field(default_factory=list,max_length=16)


class PlanRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title: str = Field(min_length=1,max_length=200)
    entity_id: UUID
    dataset: Dataset = 'real'
    content: str = Field(min_length=1,max_length=8000)
    evidence_ids: list[str] = Field(min_length=1,max_length=50)
    conditions: list[str] = Field(default_factory=list,max_length=30)
    gaps: list[str] = Field(default_factory=list,max_length=30)


class ImportRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dataset: Dataset='real'
    records: list[dict] = Field(min_length=1,max_length=500)


class ApplyRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    preview_id: UUID
    content_digest: str=Field(pattern='^[a-f0-9]{64}$')


class ValidationRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dataset: Dataset='real'


def environment():
    # Credentials are read only by the server, never emitted in health or errors.
    return load_settings()


def create_app(store=None,settings=None):
    settings=environment() if settings is None else settings
    store=store or Store(settings.get('db_path',str(ROOT/'runtime/farm.sqlite3')))
    auth=Authorization(settings)
    app=FastAPI(title='Farm Twin Local Ontology Adapter',version='0.1.0')
    app.state.store=store

    @app.get('/api/health')
    def health():
        with store.connection() as db:
            db.execute('SELECT 1').fetchone()
        return {'status':'ok','database':'sqlite','persistence':True,'model':model_status(settings),
                'upstream':UPSTREAM,'realtime_connected':False,'device_control':False,'auth_mode':auth.mode,'schema_version':2}

    @app.post('/api/auth/local-session')
    def local_session(request:Request,response:Response):
        actor,token=auth.local_session(request)
        response.set_cookie('farm_session',token,httponly=True,samesite='strict',max_age=8*3600,path='/api')
        store.audit('auth.local_session','real',{'actor_id':actor['id'],'role':actor['role']})
        return {'actor':actor,'mode':'local_trusted_machine'}

    @app.get('/api/auth/session')
    def auth_session(request:Request):return {'actor':auth.actor(request),'mode':auth.mode}

    @app.get('/api/summary')
    def summary(dataset:Dataset='real'):
        return store.summary(dataset)

    @app.get('/api/entities')
    def entities(dataset:Dataset='real',q:str=Query('',max_length=200),kind:str|None=None,limit:int=Query(1000,ge=1,le=1000)):
        return store.list_entities(dataset,q,kind,limit)

    @app.get('/api/entities/{identifier}')
    def entity(identifier:UUID,dataset:Dataset='real'):
        try:return store.get_entity(str(identifier),dataset)
        except KeyError:raise HTTPException(404,'未找到该数据集中的实体')

    @app.get('/api/knowledge')
    def knowledge(dataset:Dataset='real',q:str=Query('',max_length=200),kind:str|None=None):
        result=store.knowledge(dataset,q,kind)
        store.audit('knowledge.search',dataset,{'query':q,'evidence_ids':[e['id'] for e in result['items']]})
        return result

    @app.get('/api/relations/{identifier}')
    def relations(identifier:UUID,dataset:Dataset='real',depth:int=Query(1,ge=1,le=2)):
        from .semantics import neighborhood
        try:result=neighborhood(store,str(identifier),dataset,depth)
        except KeyError:raise HTTPException(404,'Entity not found in dataset')
        store.audit('relations.neighborhood',dataset,{'resource_id':str(identifier),'depth':depth,'edge_count':len(result['edges'])})
        return result

    @app.get('/api/ontology/schema')
    def ontology_schema():
        from .semantics import schema_info
        return schema_info()

    @app.post('/api/ontology/validate')
    def ontology_validate(body:ValidationRequest):
        from .semantics import data_graph,validate_graph
        result=validate_graph(data_graph(store,body.dataset))
        store.audit('ontology.validate',body.dataset,{'conforms':result['conforms'],'issue_count':len(result['issues'])})
        return result

    @app.get('/api/sources/{source_id}/file')
    def source_file(source_id:str,dataset:Dataset='real'):
        import json,hashlib
        with store.connection() as db:
            row=db.execute('SELECT payload FROM sources WHERE id=? AND dataset=?',(source_id,dataset)).fetchone()
        if row is None:raise HTTPException(404,'Registered source not found')
        source=json.loads(row['payload']);relative=Path(source.get('file') or '')
        if relative.is_absolute() or '..' in relative.parts:raise HTTPException(403,'Invalid registered source path')
        candidate=(ROOT/relative).resolve()
        allowed=candidate.is_relative_to(ROOT.resolve()) and candidate.suffix.lower() in ('.pdf','.xls','.xlsx','.png','.jpg','.jpeg')
        allowed=allowed and (relative.parts and (relative.parts[0] in ('参考图','现场竣工图pdf版本') or relative.name=='梁湖情田块面积汇总202607.xls'))
        if not allowed or not candidate.is_file():raise HTTPException(404,'Original source is unavailable through this endpoint')
        if not source.get('sha256') or hashlib.sha256(candidate.read_bytes()).hexdigest()!=source['sha256']:
            raise HTTPException(409,'Original source has changed since registration')
        store.audit('sources.read_file',dataset,{'source_id':source_id})
        return FileResponse(candidate,filename=candidate.name,content_disposition_type='inline')

    @app.post('/api/assistant')
    def assistant(body:AssistantRequest):
        return query_assistant(store,settings,body)

    @app.get('/api/plans')
    def plans(dataset:Dataset='real'):
        return store.list_plans(dataset)

    @app.post('/api/plans',status_code=201)
    def save_plan(body:PlanRequest,request:Request):
        actor=auth.require(request,'operator')
        try:return store.save_plan({**body.model_dump(mode='json'),'created_by':actor['id']})
        except KeyError:raise HTTPException(404,'方案实体不属于当前数据集')
        except ValueError as exc:raise HTTPException(422,str(exc))

    @app.post('/api/admin/imports/preview',status_code=201)
    def import_preview(body:ImportRequest,request:Request):
        from .admin import preview
        actor=auth.require(request,'admin')
        try:return preview(store,body.dataset,body.records,actor)
        except ValueError as exc:raise HTTPException(422,str(exc))

    @app.post('/api/admin/imports/apply')
    def import_apply(body:ApplyRequest,request:Request):
        from .admin import apply
        actor=auth.require(request,'admin')
        try:return apply(store,str(body.preview_id),body.content_digest,actor)
        except KeyError:raise HTTPException(404,'Preview not found')
        except ValueError as exc:raise HTTPException(409 if str(exc).startswith('STALE_PREVIEW') else 422,str(exc))

    return app
