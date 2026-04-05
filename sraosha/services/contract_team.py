"""Resolve team ownership from contract YAML ``x-sraosha`` (shared by API/CLI)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sraosha.models.team import Team


def _parse_uuid(val: object) -> uuid.UUID | None:
    if not val:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return uuid.UUID(s)
    except ValueError:
        return None


async def resolve_team_id_from_doc(
    db: AsyncSession, xs: dict, info: dict
) -> tuple[uuid.UUID | None, list[str]]:
    """Resolve team FK from x-sraosha.

    Explicit team_id UUID must exist; owner_team/info.owner only match existing teams.
    """
    errs: list[str] = []
    raw_tid = xs.get("team_id")
    if raw_tid is not None and str(raw_tid).strip():
        tid = _parse_uuid(raw_tid)
        if tid is None:
            return None, ["x-sraosha.team_id must be a valid UUID if set."]
        t = await db.get(Team, tid)
        if not t:
            return None, ["x-sraosha.team_id does not match any registered team."]
        return t.id, errs
    name = xs.get("owner_team") or info.get("owner")
    if isinstance(name, str) and name.strip():
        r = await db.execute(select(Team.id).where(Team.name == name.strip()))
        return r.scalar_one_or_none(), errs
    return None, errs
