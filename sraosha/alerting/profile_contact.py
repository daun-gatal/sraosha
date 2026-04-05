"""Resolve display contact fields from an alerting profile (e.g. API summaries)."""

from __future__ import annotations

from typing import Any

from sraosha.alerting.channel_types import CHANNEL_EMAIL, CHANNEL_SLACK
from sraosha.models.alerting import AlertingProfile


def slack_and_email_from_profile(profile: AlertingProfile | None) -> tuple[str | None, str | None]:
    """First enabled slack channel name and first email destination, for legacy API fields."""
    if profile is None:
        return None, None
    slack: str | None = None
    email: str | None = None
    for ch in sorted(profile.channels, key=lambda c: (c.sort_order, str(c.id))):
        if not ch.is_enabled:
            continue
        cfg: dict[str, Any] = ch.config if isinstance(ch.config, dict) else {}
        if ch.channel_type == CHANNEL_SLACK and slack is None:
            slack = (cfg.get("channel") or cfg.get("slack_channel") or "").strip() or None
        elif ch.channel_type == CHANNEL_EMAIL and email is None:
            to = cfg.get("to")
            if isinstance(to, list) and to:
                email = str(to[0]).strip() or None
            elif isinstance(to, str) and to.strip():
                email = to.strip()
            elif cfg.get("email"):
                email = str(cfg["email"]).strip() or None
    return slack, email
