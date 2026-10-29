"""Actual RDF/SHACL execution using pinned upstream ontology assets."""
from pathlib import Path
import hashlib
import json
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, OWL, SH
from pyshacl import validate
from .contracts import ONTOLOGY,UPSTREAM,object_iri,entity_class_iris

ROOT=Path(__file__).parent/'ontology'


def schema_graphs():
    manifest=json.loads((ROOT/'source-manifest.json').read_text())
    ontology=Graph();shapes=Graph()
    for item in manifest['files']:
        path=ROOT/item['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Pinned ontology asset hash mismatch')
        if path.suffix=='.ttl':
            (shapes if 'shapes/' in item['path'] else ontology).parse(path,format='turtle')
    return ontology,shapes


def add_entity_facts(graph,subject,record,relations):
    """One graph conversion for both staged and persisted records."""
    for cls in entity_class_iris(record):graph.add((subject,RDF.type,URIRef(cls)))
    for relation in relations:
        if relation.get('state','accepted')!='accepted':continue
        graph.add((subject,URIRef(relation['predicate_iri']),URIRef(object_iri(relation['target_id']))))


def data_graph(store,dataset):
    graph=Graph()
    for entity in store.list_entities(dataset,limit=10000)['items']:
        subject=URIRef(entity['iri'])
        add_entity_facts(graph,subject,entity,[r for r in entity['relations'] if r.get('subject_id')==entity['id']])
    return graph


def validate_graph(graph):
    ontology,shapes=schema_graphs()
    conforms,report,_=validate(graph,shacl_graph=shapes,ont_graph=ontology,inference='rdfs',advanced=False,js=False)
    issues=[]
    for node in report.subjects(RDF.type,SH.ValidationResult):
        issues.append({'focus':str(report.value(node,SH.focusNode) or ''),'path':str(report.value(node,SH.resultPath) or ''),
            'message':str(report.value(node,SH.resultMessage) or ''),'severity':str(report.value(node,SH.resultSeverity) or '')})
    return {'conforms':bool(conforms),'issues':issues,'upstream_commit':UPSTREAM['commit'],
        'engine':'pyshacl','inference':'rdfs','data_triples':len(graph),'scope':'Upstream DeviceShape requires exactly one Organization manager; no claim of biological safety validation'}


def schema_info():
    ontology,shapes=schema_graphs()
    return {'upstream_commit':UPSTREAM['commit'],'classes':sorted(str(x) for x in ontology.subjects(RDF.type,OWL.Class)),
        'properties':sorted(str(x) for x in ontology.subjects(RDF.type,OWL.ObjectProperty)),
        'shape_triples':len(shapes),'ontology_triples':len(ontology),'validation_engine':'pyshacl'}


def preview_validation(store,dataset,records):
    from .store import digest
    graph=data_graph(store,dataset)
    entities=store.list_entities(dataset,limit=10000)['items']
    known={e['id'] for e in entities}
    by_id={e['id']:e for e in entities}
    with store.connection() as db:
        existing={(r['source_label'],r['canonical_key']):r['id'] for r in db.execute('SELECT e.id,e.canonical_key,s.source_key AS source_label FROM entities e JOIN source_systems s ON e.source_id=s.id WHERE e.dataset=?',(dataset,))}
    for record in records:
        identifier=existing.get((record['source_id'],record['source_key']))
        subject=URIRef(object_iri(identifier) if identifier else 'urn:farm:preview:'+digest([record['source_id'],record['source_key']]))
        if identifier:graph.remove((subject,None,None))
        relations=record.get('relations',[r for r in by_id.get(identifier,{}).get('relations',[]) if r.get('subject_id')==identifier])
        for relation in relations:
            if relation.get('target_id') not in known:raise ValueError('Relation target must already exist in the same dataset')
        add_entity_facts(graph,subject,record,relations)
    return validate_graph(graph)


def neighborhood(store,identifier,dataset,depth=1):
    root=store.get_entity(identifier,dataset)
    entities={e['id']:e for e in store.list_entities(dataset,limit=10000)['items']}
    selected={root['id']};frontier={root['id']};edges={}
    for _ in range(depth):
        next_ids=set()
        for node_id in frontier:
            for edge in entities[node_id]['relations']:
                subject=edge.get('subject_id');target=edge.get('target_id')
                if subject not in entities or target not in entities:continue
                edges[edge.get('id') or subject+edge['predicate_iri']+target]=edge
                next_ids.update((subject,target))
        frontier=next_ids-selected;selected|=next_ids
    nodes=[{'id':i,'name':entities[i]['name'],'kind':entities[i]['kind'],'class_iris':entities[i]['class_iris'],
            'dataset':dataset,'data_nature':entities[i]['data_nature']} for i in sorted(selected)]
    return {'root_id':identifier,'dataset':dataset,'depth':depth,'nodes':nodes,'edges':list(edges.values()),'upstream':UPSTREAM}
