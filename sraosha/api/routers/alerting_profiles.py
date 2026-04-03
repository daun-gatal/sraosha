import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sraosha.api.deps import get_db
from sraosha.models.alerting import AlertingProfile, AlertingProfileChannel
from sraosha.schemas.alerting_profile import (
    AlertingChannelCreate,
    AlertingChannelResponse,
    AlertingChannelUpdate,
    AlertingProfileCreate,
    AlertingProfileListResponse,
    AlertingProfileResponse,
    AlertingProfileUpdate,
)

router = APIRouter()


def _profile_to_response(profile: AlertingProfile) -> AlertingProfileResponse:
    ch = [AlertingChannelResponse.model_validate(c) for c in profile.channels]
    return AlertingProfileResponse(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        channels=ch,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("", response_model=AlertingProfileListResponse)
async def list_profiles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AlertingProfile)
        .options(selectinload(AlertingProfile.channels))
        .order_by(AlertingProfile.name)
    )
    profiles = result.scalars().unique().all()
    items = [_profile_to_response(p) for p in profiles]
    return AlertingProfileListResponse(items=items, total=len(items))


@router.post("", response_model=AlertingProfileResponse, status_code=201)
async def create_profile(body: AlertingProfileCreate, db: AsyncSession = Depends(get_db)):
    profile = AlertingProfile(
        name=body.name.strip(),
        description=body.description,
    )
    db.add(profile)
    await db.flush()
    for i, ch in enumerate(body.channels):
        db.add(
            AlertingProfileChannel(
                alerting_profile_id=profile.id,
                channel_type=ch.channel_type,
                config=ch.config,
                is_enabled=ch.is_enabled,
                sort_order=ch.sort_order if ch.sort_order else i,
            )
        )
    await db.flush()
    await db.refresh(profile, ["channels"])
    result = await db.execute(
        select(AlertingProfile)
        .where(AlertingProfile.id == profile.id)
        .options(selectinload(AlertingProfile.channels))
    )
    profile = result.scalar_one()
    return _profile_to_response(profile)


@router.get("/{profile_id}", response_model=AlertingProfileResponse)
async def get_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = uuid.UUID(profile_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile ID")
    result = await db.execute(
        select(AlertingProfile)
        .where(AlertingProfile.id == uid)
        .options(selectinload(AlertingProfile.channels))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Alerting profile not found")
    return _profile_to_response(profile)


@router.patch("/{profile_id}", response_model=AlertingProfileResponse)
async def update_profile(
    profile_id: str, body: AlertingProfileUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        uid = uuid.UUID(profile_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile ID")
    profile = await db.get(AlertingProfile, uid)
    if not profile:
        raise HTTPException(status_code=404, detail="Alerting profile not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(profile, k, v)
    await db.flush()
    result = await db.execute(
        select(AlertingProfile)
        .where(AlertingProfile.id == uid)
        .options(selectinload(AlertingProfile.channels))
    )
    profile = result.scalar_one()
    return _profile_to_response(profile)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = uuid.UUID(profile_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile ID")
    profile = await db.get(AlertingProfile, uid)
    if not profile:
        raise HTTPException(status_code=404, detail="Alerting profile not found")
    await db.delete(profile)


@router.post("/{profile_id}/channels", response_model=AlertingChannelResponse, status_code=201)
async def add_channel(
    profile_id: str, body: AlertingChannelCreate, db: AsyncSession = Depends(get_db)
):
    try:
        uid = uuid.UUID(profile_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile ID")
    profile = await db.get(AlertingProfile, uid)
    if not profile:
        raise HTTPException(status_code=404, detail="Alerting profile not found")
    row = AlertingProfileChannel(
        alerting_profile_id=uid,
        channel_type=body.channel_type,
        config=body.config,
        is_enabled=body.is_enabled,
        sort_order=body.sort_order,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return AlertingChannelResponse.model_validate(row)


@router.patch("/{profile_id}/channels/{channel_id}", response_model=AlertingChannelResponse)
async def update_channel(
    profile_id: str,
    channel_id: str,
    body: AlertingChannelUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        puid = uuid.UUID(profile_id)
        cid = uuid.UUID(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")
    row = await db.get(AlertingProfileChannel, cid)
    if not row or row.alerting_profile_id != puid:
        raise HTTPException(status_code=404, detail="Channel not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    await db.flush()
    await db.refresh(row)
    return AlertingChannelResponse.model_validate(row)


@router.delete("/{profile_id}/channels/{channel_id}", status_code=204)
async def delete_channel(
    profile_id: str, channel_id: str, db: AsyncSession = Depends(get_db)
):
    try:
        puid = uuid.UUID(profile_id)
        cid = uuid.UUID(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")
    row = await db.get(AlertingProfileChannel, cid)
    if not row or row.alerting_profile_id != puid:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.delete(row)
