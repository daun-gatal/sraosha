"""Extract field-level references from data contract YAML."""

from dataclasses import dataclass


@dataclass
class ContractFields:
    contract_id: str
    owner_team: str | None
    tables: dict[str, list[str]]  # table_name -> [field_names]
    server_tables: list[str]  # tables referenced in server blocks


def parse_contract(contract: dict) -> ContractFields:
    contract_id = contract.get("id", "unknown")
    info = contract.get("info", {})
    owner_team = info.get("owner") or contract.get("x-sraosha", {}).get("owner_team")

    tables: dict[str, list[str]] = {}
    models = contract.get("models", {})
    for model_name, model_def in models.items():
        if isinstance(model_def, dict):
            fields = model_def.get("fields", {})
            tables[model_name] = list(fields.keys()) if isinstance(fields, dict) else []

    server_tables: list[str] = []
    servers = contract.get("servers", {})
    for _server_name, server_def in servers.items():
        if isinstance(server_def, dict):
            schema = server_def.get("schema")
            if schema:
                server_tables.append(schema)

    return ContractFields(
        contract_id=contract_id,
        owner_team=owner_team,
        tables=tables,
        server_tables=server_tables,
    )
