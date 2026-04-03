from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sraosha.api.deps import get_db
from sraosha.models.alerting import AlertingProfile
from sraosha.models.contract import Contract
from sraosha.models.run import ValidationRun
from sraosha.models.team import Team
from sraosha.schemas.contract import (
    ContractCreateRequest,
    ContractDetailResponse,
    ContractListResponse,
    ContractResponse,
    ContractUpdateRequest,
)
from sraosha.schemas.run import ValidationRunResponse

router = APIRouter()


async def _validate_team_and_profile(
    db: AsyncSession, team_id, alerting_profile_id
) -> None:
    if team_id is not None and not await db.get(Team, team_id):
        raise HTTPException(status_code=400, detail="team_id not found")
    if alerting_profile_id is not None and not await db.get(AlertingProfile, alerting_profile_id):
        raise HTTPException(status_code=400, detail="alerting_profile_id not found")


async def _contract_eager_for_response(db: AsyncSession, contract: Contract) -> Contract:
    """Load team/alerting_profile so `owner_team` does not trigger async lazy-load."""
    res = await db.execute(
        select(Contract)
        .where(Contract.id == contract.id)
        .options(selectinload(Contract.team), selectinload(Contract.alerting_profile))
    )
    return res.scalar_one()


@router.get("", response_model=ContractListResponse)
async def list_contracts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Contract)
        .options(selectinload(Contract.team), selectinload(Contract.alerting_profile))
        .order_by(Contract.created_at.desc())
    )
    contracts = result.scalars().all()
    total = len(contracts)
    return ContractListResponse(
        items=[ContractResponse.model_validate(c) for c in contracts],
        total=total,
    )


@router.post("", response_model=ContractResponse, status_code=201)
async def create_contract(body: ContractCreateRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(Contract).where(Contract.contract_id == body.contract_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Contract ID already exists")

    await _validate_team_and_profile(db, body.team_id, body.alerting_profile_id)

    contract = Contract(
        contract_id=body.contract_id,
        title=body.title,
        description=body.description,
        file_path=body.file_path,
        team_id=body.team_id,
        alerting_profile_id=body.alerting_profile_id,
        raw_yaml=body.raw_yaml,
        enforcement_mode=body.enforcement_mode,
    )
    db.add(contract)
    await db.flush()
    contract = await _contract_eager_for_response(db, contract)
    return ContractResponse.model_validate(contract)


@router.get("/{contract_id}", response_model=ContractDetailResponse)
async def get_contract(contract_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Contract)
        .where(Contract.contract_id == contract_id)
        .options(selectinload(Contract.team), selectinload(Contract.alerting_profile))
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return ContractDetailResponse.model_validate(contract)


@router.put("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: str, body: ContractUpdateRequest, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Contract)
        .where(Contract.contract_id == contract_id)
        .options(selectinload(Contract.team), selectinload(Contract.alerting_profile))
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    update_data = body.model_dump(exclude_unset=True)
    tid = update_data.get("team_id", contract.team_id)
    aid = update_data.get("alerting_profile_id", contract.alerting_profile_id)
    if "team_id" in update_data or "alerting_profile_id" in update_data:
        await _validate_team_and_profile(db, tid, aid)

    for field, value in update_data.items():
        setattr(contract, field, value)
    contract.updated_at = datetime.now(timezone.utc)

    await db.flush()
    contract = await _contract_eager_for_response(db, contract)
    return ContractResponse.model_validate(contract)


@router.delete("/{contract_id}", status_code=204)
async def delete_contract(contract_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Contract).where(Contract.contract_id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    await db.delete(contract)


@router.post("/{contract_id}/run", response_model=ValidationRunResponse)
async def trigger_run(contract_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Contract).where(Contract.contract_id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    import tempfile

    from sraosha.core.credentials import inject_credentials, resolve_connection_credentials_async
    from sraosha.core.engine import ContractEngine, ContractViolationError, EnforcementMode

    server_type, creds = await resolve_connection_credentials_async(contract_id, db)

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as tmp:
            tmp.write(contract.raw_yaml)
            tmp_path = tmp.name

        engine = ContractEngine(
            contract_path=tmp_path,
            enforcement_mode=EnforcementMode(contract.enforcement_mode),
            dry_run=True,
        )
        with inject_credentials(server_type or "", creds):
            validation_result = engine.run()
    except ContractViolationError as exc:
        validation_result = exc.result
    except Exception as exc:
        run = ValidationRun(
            contract_id=contract_id,
            status="error",
            enforcement_mode=contract.enforcement_mode,
            triggered_by="api",
            error_message=str(exc),
        )
        db.add(run)
        await db.flush()
        await db.refresh(run)
        return ValidationRunResponse.model_validate(run)

    run = ValidationRun(
        contract_id=contract_id,
        status="passed" if validation_result.passed else "failed",
        enforcement_mode=validation_result.enforcement_mode.value,
        checks_total=validation_result.checks_total,
        checks_passed=validation_result.checks_passed,
        checks_failed=validation_result.checks_failed,
        failures=validation_result.failures,
        duration_ms=int(validation_result.duration_seconds * 1000),
        triggered_by="api",
        run_log=validation_result.log or None,
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    return ValidationRunResponse.model_validate(run)
