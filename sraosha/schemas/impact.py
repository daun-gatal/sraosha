from pydantic import BaseModel, Field


class ColumnPair(BaseModel):
    upstream_ref: str
    downstream_ref: str
    inferred: bool = False


class GraphNode(BaseModel):
    id: str
    label: str = ""
    owner_team: str | None = None
    status: str = "unknown"
    tables: list[str] = []
    platform: str = ""
    platforms: list[str] = []
    upstream_count: int = 0
    downstream_count: int = 0
    degree: int = 0


class GraphEdge(BaseModel):
    source: str
    target: str
    shared_fields: list[str] = Field(default_factory=list)
    field_mapping: dict[str, str] = Field(default_factory=dict)
    edge_type: str = "inferred"
    column_pairs: list[ColumnPair] = Field(default_factory=list)


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
