"""Validation for DQ wizard partial endpoints (SodaCL generation)."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("sraosha.dq.generate")

MAX_PARAMS_JSON_BYTES = 64 * 1024
MAX_SQL_FRAGMENT_CHARS = 100_000


def parse_dq_generate_params(raw: str | None) -> dict[str, Any]:
    """Parse JSON `params` from form body; returns empty dict if missing."""
    if not raw or not str(raw).strip():
        return {}
    data = str(raw).encode("utf-8")
    if len(data) > MAX_PARAMS_JSON_BYTES:
        raise ValueError("params JSON is too large")
    try:
        out = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid params JSON: %s", exc)
        raise ValueError("Invalid params JSON") from exc
    if out is None:
        return {}
    if not isinstance(out, dict):
        raise ValueError("params must be a JSON object")
    return _validate_param_values(out)


def _validate_param_values(params: dict[str, Any]) -> dict[str, Any]:
    """Ensure values are JSON-serializable scalars or small lists; enforce size on strings."""
    out: dict[str, Any] = {}
    for k, v in params.items():
        if not isinstance(k, str) or len(k) > 256:
            continue
        if isinstance(v, str):
            if len(v) > MAX_SQL_FRAGMENT_CHARS:
                raise ValueError(f"Parameter {k!r} is too long")
            out[k] = v
        elif isinstance(v, (int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, list) and len(v) <= 500:
            out[k] = v
        else:
            raise ValueError(f"Unsupported type for parameter {k!r}")
    return out
