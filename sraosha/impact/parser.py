"""Extract field-level references from data contract YAML."""

from dataclasses import dataclass, field


@dataclass
class DependencyMapping:
    """Explicit upstream dependency with table.column-level field mapping."""

    contract_id: str
    fields: dict[str, str] = field(default_factory=dict)  # "upstream_table.col": "local_table.col"


@dataclass
class ContractFields:
    contract_id: str
    owner_team: str | None
    tables: dict[str, list[str]]  # table_name -> [field_names]
    server_tables: list[str]  # tables referenced in server blocks
    depends_on: list[DependencyMapping] = field(default_factory=list)
    platform: str = ""  # primary server type (first server block in YAML order)
    platforms: list[str] = field(default_factory=list)  # distinct types in first-seen order


def parse_contract(contract: dict) -> ContractFields:
    contract_id = contract.get("id", "unknown")
    info = contract.get("info", {})
    x_sraosha = contract.get("x-sraosha", {})
    owner_team = info.get("owner") or x_sraosha.get("owner_team")

    tables: dict[str, list[str]] = {}
    models = contract.get("models", {})
    for model_name, model_def in models.items():
        if isinstance(model_def, dict):
            fields = model_def.get("fields", {})
            tables[model_name] = list(fields.keys()) if isinstance(fields, dict) else []

    server_tables: list[str] = []
    servers = contract.get("servers", {})
    platform_types: list[str] = []
    for _server_name, server_def in servers.items():
        if isinstance(server_def, dict):
            schema = server_def.get("schema")
            if schema:
                server_tables.append(schema)
            st = server_def.get("type")
            if st:
                s = str(st).strip().lower()
                if s:
                    platform_types.append(s)
    # Primary platform: first server block in YAML order; platforms: unique preserving order
    seen: set[str] = set()
    platforms_unique: list[str] = []
    for p in platform_types:
        if p not in seen:
            seen.add(p)
            platforms_unique.append(p)
    platform = platforms_unique[0] if platforms_unique else ""

    depends_on: list[DependencyMapping] = []
    raw_depends = x_sraosha.get("depends_on", [])
    if isinstance(raw_depends, list):
        for entry in raw_depends:
            if isinstance(entry, dict) and "contract" in entry:
                raw_fields = entry.get("fields", {})
                if isinstance(raw_fields, dict):
                    mapping = {str(k): str(v) for k, v in raw_fields.items()}
                else:
                    mapping = {}
                depends_on.append(
                    DependencyMapping(
                        contract_id=str(entry["contract"]),
                        fields=mapping,
                    )
                )

    return ContractFields(
        contract_id=contract_id,
        owner_team=owner_team,
        tables=tables,
        server_tables=server_tables,
        depends_on=depends_on,
        platform=platform,
        platforms=platforms_unique,
    )
