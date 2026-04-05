"""Build form-shaped dicts for contract_yaml.form_to_yaml_dict from guided UI input."""

from __future__ import annotations

from typing import Any

from sraosha.models.connection import Connection
from sraosha.schemas.contract import ContractPreviewRequest
from sraosha.services.connection_introspect import default_schema_for_connection


def preview_request_to_form_dict(
    connection: Connection,
    body: ContractPreviewRequest,
) -> dict[str, Any]:
    """Flat form dict compatible with :func:`sraosha.api.contract_yaml.form_to_yaml_dict`."""
    schema = (body.schema_name or "").strip() or default_schema_for_connection(connection)
    table = body.table_name.strip()
    if not table:
        raise ValueError("table_name is required")

    c = connection
    sk = body.server_key.strip() or "production"

    form: dict[str, Any] = {
        "contract_id": body.contract_id.strip(),
        "spec_version": body.spec_version,
        "title": body.title.strip(),
        "version": body.version,
        "description": body.description or "",
        "owner": body.owner or "",
        "contact_name": body.contact_name or "",
        "contact_email": body.contact_email or "",
        "enforcement_mode": body.enforcement_mode,
        "server_name[]": [sk],
        "server_type[]": [c.server_type or "postgres"],
        "server_host[]": [c.host or ""],
        "server_port[]": [str(c.port) if c.port is not None else ""],
        "server_database[]": [c.database or ""],
        "server_schema[]": [schema],
        "server_account[]": [c.account or ""],
        "server_warehouse[]": [c.warehouse or ""],
        "server_role[]": [c.role or ""],
        "server_catalog[]": [c.catalog or ""],
        "server_httppath[]": [c.http_path or ""],
        "server_project[]": [c.project or ""],
        "server_dataset[]": [c.dataset or ""],
        "server_location[]": [c.location or ""],
        "server_path[]": [c.path or ""],
        "server_connection[]": [str(c.id)],
        "model_name[]": [table],
        "model_type[]": ["table"],
    }

    if body.team_id:
        form["team_id"] = str(body.team_id)
    if body.alerting_profile_id:
        form["alerting_profile_id"] = str(body.alerting_profile_id)

    field_model: list[str] = []
    field_name: list[str] = []
    field_type: list[str] = []
    field_required: list[str] = []
    field_unique: list[str] = []

    for col in body.columns:
        name = col.name.strip()
        if not name:
            continue
        field_model.append(table)
        field_name.append(name)
        field_type.append((col.field_type or "text").strip())
        field_required.append("true" if col.required else "")
        field_unique.append("true" if col.unique else "")

    if not field_name:
        raise ValueError("At least one column is required")

    form["field_model[]"] = field_model
    form["field_name[]"] = field_name
    form["field_type[]"] = field_type
    form["field_required[]"] = field_required
    form["field_unique[]"] = field_unique

    return form
