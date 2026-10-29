"""Small, independently implemented adapter of the pinned upstream contracts.

SourceKey, DataNature and object IRI follow ontology-platform/src/lzo; see
docs/audit/ontology-audit.md. This module does not claim full upstream conformance.
"""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict

UPSTREAM = {
    'repository': 'https://github.com/lianggeming14/liangzihu-ontology-traceability',
    'commit': '5776ba8d656139d3fb8dfabd137d83dd6dbba11c',
    'directory': 'ontology-platform',
    'original_commit': '8ee79416073ce91d9eb5e724fefb04241e6187b5',
    'integration': 'local_sqlite_contract_adapter',
    'full_platform_connected': False,
}
DataNature = Literal['synthetic', 'test', 'imported_unverified', 'verified']
Dataset = Literal['real', 'demo']
ONTOLOGY = 'https://w3id.org/lzo/ontology/'


class SourceKey(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    source_id: UUID
    source_system: str
    source_instance: str
    collection: str
    canonical_key: str


def object_iri(identifier):
    return f'urn:lzo:object:{UUID(str(identifier))}'


def entity_class_iris(record):
    return record.get('class_iris') or [ONTOLOGY+{'field':'Field','pond':'Pond','orchard':'Orchard',
        'device':'Device','organization':'Organization'}.get(record.get('kind','field'),'SpatialAsset')]
