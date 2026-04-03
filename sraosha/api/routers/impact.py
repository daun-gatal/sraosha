import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sraosha.api.deps import get_db
from sraosha.impact.analyzer import ImpactAnalyzer
from sraosha.models.contract import Contract
from sraosha.schemas.impact import (
    DependencyGraphResponse,
    DownstreamResponse,
    GraphEdge,
    GraphNode,
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
)

router = APIRouter()


async def _build_analyzer(db: AsyncSession) -> ImpactAnalyzer:
    result = await db.execute(select(Contract).where(Contract.is_active == True))  # noqa: E712
    contracts = result.scalars().all()

    contract_dicts = []
    for c in contracts:
        try:
            parsed = yaml.safe_load(c.raw_yaml)
            if parsed:
                contract_dicts.append(parsed)
        except yaml.YAMLError:
            pass

    return ImpactAnalyzer(contract_dicts)


@router.get("/graph", response_model=DependencyGraphResponse)
async def get_graph(db: AsyncSession = Depends(get_db)):
    analyzer = await _build_analyzer(db)
    graph_data = analyzer.to_json()
    return DependencyGraphResponse(
        nodes=[GraphNode(**n) for n in graph_data["nodes"]],
        edges=[GraphEdge(**e) for e in graph_data["edges"]],
    )


@router.get("/lineage/{contract_id}", response_model=DependencyGraphResponse)
async def get_lineage(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
    upstream_depth: int = Query(default=2, ge=0, le=10),
    downstream_depth: int = Query(default=2, ge=0, le=10),
):
    contract_result = await db.execute(
        select(Contract).where(Contract.contract_id == contract_id)
    )
    if not contract_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contract not found")

    analyzer = await _build_analyzer(db)
    graph_data = analyzer.lineage_json(contract_id, upstream_depth, downstream_depth)
    return DependencyGraphResponse(
        nodes=[GraphNode(**n) for n in graph_data["nodes"]],
        edges=[GraphEdge(**e) for e in graph_data["edges"]],
    )


@router.get("/{contract_id}/downstream", response_model=DownstreamResponse)
async def get_downstream(contract_id: str, db: AsyncSession = Depends(get_db)):
    contract_result = await db.execute(
        select(Contract).where(Contract.contract_id == contract_id)
    )
    if not contract_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contract not found")

    analyzer = await _build_analyzer(db)
    downstream = analyzer.get_downstream(contract_id)
    return DownstreamResponse(contract_id=contract_id, downstream=downstream)


@router.post("/{contract_id}/analyze", response_model=ImpactAnalysisResponse)
async def analyze_impact(
    contract_id: str, body: ImpactAnalysisRequest, db: AsyncSession = Depends(get_db)
):
    contract_result = await db.execute(
        select(Contract).where(Contract.contract_id == contract_id)
    )
    if not contract_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contract not found")

    analyzer = await _build_analyzer(db)
    impact = analyzer.analyze(contract_id, body.changed_fields)

    return ImpactAnalysisResponse(
        contract_id=contract_id,
        changed_fields=body.changed_fields,
        directly_affected=impact["directly_affected"],
        transitively_affected=impact["transitively_affected"],
        severity=impact["severity"],
        affected_pipelines=impact["affected_pipelines"],
    )
