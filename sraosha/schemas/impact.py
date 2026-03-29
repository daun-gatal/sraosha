from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    owner_team: str | None = None
    status: str = "unknown"


class GraphEdge(BaseModel):
    source: str
    target: str
    shared_fields: list[str] = []


class DependencyGraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ImpactAnalysisRequest(BaseModel):
    changed_fields: list[str]


class ImpactAnalysisResponse(BaseModel):
    contract_id: str
    changed_fields: list[str]
    directly_affected: list[str]
    transitively_affected: list[str]
    severity: str
    affected_pipelines: list[str] = []


class DownstreamResponse(BaseModel):
    contract_id: str
    downstream: list[str]
