"""Utilities to convert between form POST data and data-contract YAML."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, cast

import yaml


class _OrderedDumper(yaml.SafeDumper):
    """YAML dumper that preserves insertion order of dicts."""


def _dict_representer(dumper: yaml.Dumper, data: dict) -> Any:
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())


_OrderedDumper.add_representer(dict, _dict_representer)  # type: ignore[arg-type]
_OrderedDumper.add_representer(OrderedDict, _dict_representer)  # type: ignore[arg-type]


def connection_id_to_name_map_from_connections(connections: list[Any]) -> dict[str, str]:
    """Map connection UUID string -> saved connection name (for form POST resolution)."""
    return {str(c.id): c.name for c in connections}


def form_to_yaml_dict(
    form: dict[str, Any],
    connection_id_to_name: dict[str, str] | None = None,
) -> dict:
    """Build a data-contract dict from flat form fields.

    Expected form keys (all strings from POST):
      contract_id, spec_version, title, version, description, owner,
      contact_name, contact_email,
      server_name[], server_type[], server_host[], server_port[],
        server_database[], server_schema[],
      model_name[], model_type[],
      field_model[], field_name[], field_type[], field_required[], field_unique[],
      enforcement_mode, owner_team, team_id, alerting_profile_id,
      notify_slack, notify_email
      server_connection[] (optional): parallel to server_name[], values are connection UUIDs

    If ``connection_id_to_name`` is provided, non-empty ``server_connection[]`` entries
    are written under ``x-sraosha.server_connections`` as server_key -> connection name.
    """
    doc: dict[str, Any] = {}

    doc["dataContractSpecification"] = form.get("spec_version", "1.1.0") or "1.1.0"
    doc["id"] = form.get("contract_id", "")

    info: dict[str, Any] = {}
    if form.get("title"):
        info["title"] = form["title"]
    if form.get("version"):
        info["version"] = form["version"]
    if form.get("description"):
        info["description"] = form["description"]
    if form.get("owner"):
        info["owner"] = form["owner"]

    contact: dict[str, str] = {}
    if form.get("contact_name"):
        contact["name"] = form["contact_name"]
    if form.get("contact_email"):
        contact["email"] = form["contact_email"]
    if contact:
        info["contact"] = contact
    if info:
        doc["info"] = info

    server_names = _listify(form.get("server_name[]", []))
    server_types = _listify(form.get("server_type[]", []))
    server_hosts = _listify(form.get("server_host[]", []))
    server_ports = _listify(form.get("server_port[]", []))
    server_dbs = _listify(form.get("server_database[]", []))
    server_schemas = _listify(form.get("server_schema[]", []))
    server_accounts = _listify(form.get("server_account[]", []))
    server_warehouses = _listify(form.get("server_warehouse[]", []))
    server_roles = _listify(form.get("server_role[]", []))
    server_catalogs = _listify(form.get("server_catalog[]", []))
    server_httppaths = _listify(form.get("server_httppath[]", []))
    server_projects = _listify(form.get("server_project[]", []))
    server_datasets = _listify(form.get("server_dataset[]", []))
    server_locations = _listify(form.get("server_location[]", []))
    server_paths = _listify(form.get("server_path[]", []))
    server_conns = _listify(form.get("server_connection[]", []))
    server_connections_map: dict[str, str] = {}

    if server_names:
        servers: dict[str, Any] = {}
        for i, name in enumerate(server_names):
            if not name:
                continue
            if connection_id_to_name and i < len(server_conns) and server_conns[i]:
                cid = str(server_conns[i]).strip()
                cname = connection_id_to_name.get(cid)
                if cname:
                    server_connections_map[name] = cname
            srv: dict[str, Any] = {}
            if i < len(server_types) and server_types[i]:
                srv["type"] = server_types[i]
            if i < len(server_hosts) and server_hosts[i]:
                srv["host"] = server_hosts[i]
            port_val = server_ports[i] if i < len(server_ports) else ""
            if port_val:
                try:
                    srv["port"] = int(port_val)
                except ValueError:
                    srv["port"] = port_val
            if i < len(server_dbs) and server_dbs[i]:
                srv["database"] = server_dbs[i]
            if i < len(server_schemas) and server_schemas[i]:
                srv["schema"] = server_schemas[i]
            if i < len(server_accounts) and server_accounts[i]:
                srv["account"] = server_accounts[i]
            if i < len(server_warehouses) and server_warehouses[i]:
                srv["warehouse"] = server_warehouses[i]
            if i < len(server_roles) and server_roles[i]:
                srv["role"] = server_roles[i]
            if i < len(server_catalogs) and server_catalogs[i]:
                srv["catalog"] = server_catalogs[i]
            if i < len(server_httppaths) and server_httppaths[i]:
                srv["httpPath"] = server_httppaths[i]
            if i < len(server_projects) and server_projects[i]:
                srv["project"] = server_projects[i]
            if i < len(server_datasets) and server_datasets[i]:
                srv["dataset"] = server_datasets[i]
            if i < len(server_locations) and server_locations[i]:
                srv["location"] = server_locations[i]
            if i < len(server_paths) and server_paths[i]:
                srv["path"] = server_paths[i]
            servers[name] = srv
        if servers:
            doc["servers"] = servers

    model_names = _listify(form.get("model_name[]", []))
    model_types = _listify(form.get("model_type[]", []))
    field_models = _listify(form.get("field_model[]", []))
    field_names = _listify(form.get("field_name[]", []))
    field_types = _listify(form.get("field_type[]", []))
    field_requireds = _listify(form.get("field_required[]", []))
    field_uniques = _listify(form.get("field_unique[]", []))

    if model_names:
        models: dict[str, Any] = {}
        for i, mname in enumerate(model_names):
            if not mname:
                continue
            model_def: dict[str, Any] = {}
            if i < len(model_types) and model_types[i]:
                model_def["type"] = model_types[i]
            model_def["fields"] = {}
            models[mname] = model_def

        for i, fname in enumerate(field_names):
            if not fname:
                continue
            parent_model = field_models[i] if i < len(field_models) else ""
            if parent_model not in models:
                continue
            fdef: dict[str, Any] = {}
            if i < len(field_types) and field_types[i]:
                fdef["type"] = field_types[i]
            if i < len(field_requireds) and field_requireds[i] == "true":
                fdef["required"] = True
            if i < len(field_uniques) and field_uniques[i] == "true":
                fdef["unique"] = True
            models[parent_model]["fields"][fname] = fdef

        if models:
            doc["models"] = models

    x_sraosha: dict[str, Any] = {}
    tid = (form.get("team_id") or "").strip()
    if tid:
        x_sraosha["team_id"] = tid
    apid = (form.get("alerting_profile_id") or "").strip()
    if apid:
        x_sraosha["alerting_profile_id"] = apid
    if form.get("owner_team"):
        x_sraosha["owner_team"] = form["owner_team"]
    if form.get("enforcement_mode"):
        x_sraosha["enforcement_mode"] = form["enforcement_mode"]
    if server_connections_map:
        x_sraosha["server_connections"] = server_connections_map

    dep_contracts = _listify(form.get("dep_contract_id[]", []))
    dep_upstreams = _listify(form.get("dep_upstream_ref[]", []))
    dep_locals = _listify(form.get("dep_local_ref[]", []))
    dep_groups: dict[str, dict[str, str]] = {}
    for i, cid in enumerate(dep_contracts):
        if not cid:
            continue
        up = dep_upstreams[i] if i < len(dep_upstreams) else ""
        lo = dep_locals[i] if i < len(dep_locals) else ""
        if cid not in dep_groups:
            dep_groups[cid] = {}
        if up and lo:
            dep_groups[cid][up] = lo
    if dep_groups:
        dep_list: list[dict] = []
        for cid, fmap in dep_groups.items():
            entry: dict[str, Any] = {"contract": cid}
            if fmap:
                entry["fields"] = fmap
            dep_list.append(entry)
        x_sraosha["depends_on"] = dep_list

    notify: dict[str, str] = {}
    if form.get("notify_slack"):
        notify["slack_channel"] = form["notify_slack"]
    if form.get("notify_email"):
        notify["email"] = form["notify_email"]
    if notify:
        x_sraosha["notify"] = notify

    if x_sraosha:
        doc["x-sraosha"] = x_sraosha

    return doc


def yaml_dict_to_form(doc: dict) -> dict[str, Any]:
    """Convert a parsed YAML dict into a flat dict suitable for template rendering."""
    form: dict[str, Any] = {}
    form["contract_id"] = doc.get("id", "")
    form["spec_version"] = doc.get("dataContractSpecification", "1.1.0")

    info = doc.get("info", {})
    form["title"] = info.get("title", "")
    form["version"] = info.get("version", "")
    form["description"] = info.get("description", "")
    form["owner"] = info.get("owner", "")

    contact = info.get("contact", {})
    form["contact_name"] = contact.get("name", "")
    form["contact_email"] = contact.get("email", "")

    xs = doc.get("x-sraosha", {})
    if not isinstance(xs, dict):
        xs = {}
    sc_map = xs.get("server_connections") or {}
    if not isinstance(sc_map, dict):
        sc_map = {}

    servers_list = []
    for name, sdef in doc.get("servers", {}).items():
        if not isinstance(sdef, dict):
            continue
        conn_name = ""
        if name in sc_map:
            ref = sc_map[name]
            if isinstance(ref, str):
                conn_name = ref.strip()
            elif isinstance(ref, dict) and ref.get("name") is not None:
                conn_name = str(ref.get("name", "")).strip()
        servers_list.append(
            {
                "name": name,
                "type": sdef.get("type", ""),
                "host": sdef.get("host", ""),
                "port": str(sdef.get("port", "")),
                "database": sdef.get("database", ""),
                "schema": sdef.get("schema", ""),
                "account": sdef.get("account", ""),
                "warehouse": sdef.get("warehouse", ""),
                "role": sdef.get("role", ""),
                "catalog": sdef.get("catalog", ""),
                "httpPath": sdef.get("httpPath", ""),
                "project": sdef.get("project", ""),
                "dataset": sdef.get("dataset", ""),
                "location": sdef.get("location", ""),
                "path": sdef.get("path", ""),
                "connection_name": conn_name,
            }
        )
    form["servers"] = servers_list

    models_list = []
    for mname, mdef in doc.get("models", {}).items():
        if not isinstance(mdef, dict):
            continue
        fields = []
        for fname, fdef in mdef.get("fields", {}).items():
            if not isinstance(fdef, dict):
                fdef = {}
            fields.append(
                {
                    "name": fname,
                    "type": fdef.get("type", ""),
                    "required": fdef.get("required", False),
                    "unique": fdef.get("unique", False),
                }
            )
        models_list.append(
            {
                "name": mname,
                "type": mdef.get("type", "table"),
                "fields": fields,
            }
        )
    form["models"] = models_list

    form["team_id"] = str(xs.get("team_id", "") or "")
    form["alerting_profile_id"] = str(xs.get("alerting_profile_id", "") or "")
    form["owner_team"] = xs.get("owner_team", "")
    form["enforcement_mode"] = xs.get("enforcement_mode", "block")

    deps_list: list[dict] = []
    for entry in xs.get("depends_on", []):
        if isinstance(entry, dict) and "contract" in entry:
            raw_fields = entry.get("fields", {})
            mappings = []
            if isinstance(raw_fields, dict):
                for up, lo in raw_fields.items():
                    mappings.append({"upstream": str(up), "local": str(lo)})
            deps_list.append({"contract": str(entry["contract"]), "mappings": mappings})
    form["depends_on"] = deps_list

    notify = xs.get("notify", {})
    form["notify_slack"] = notify.get("slack_channel", "")
    form["notify_email"] = notify.get("email", "")

    return form


def dict_to_yaml_string(doc: dict) -> str:
    """Render a data-contract dict as a YAML string."""
    return cast(
        str,
        yaml.dump(doc, Dumper=_OrderedDumper, default_flow_style=False, sort_keys=False),
    )


def yaml_string_to_dict(raw: str) -> dict:
    """Parse a YAML string into a dict, raising ValueError on failure."""
    try:
        result = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc
    if not isinstance(result, dict):
        raise ValueError("YAML must be a mapping at the top level")
    return result


def build_raw_yaml_from_form(
    form: dict[str, Any],
    connection_id_to_name: dict[str, str] | None = None,
) -> str:
    """Convenience: form POST data -> YAML string."""
    return dict_to_yaml_string(form_to_yaml_dict(form, connection_id_to_name))


def _listify(val: Any) -> list:
    """Ensure a value is a list (form fields may be a single string or a list)."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]
