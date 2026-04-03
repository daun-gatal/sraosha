from __future__ import annotations

import re
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# YAML helpers (SodaCL / soda scan checks.yml conventions)
# ---------------------------------------------------------------------------


def _indent_lines(text: str, spaces: int) -> str:
    pad = " " * spaces
    out = []
    for line in text.splitlines():
        out.append(pad + line if line.strip() else line)
    return "\n".join(out)


def _dump_subdoc(mapping: dict[str, Any], indent: int) -> str:
    dumped = yaml.dump(
        mapping,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    ).strip()
    return _indent_lines(dumped, indent)


# ---------------------------------------------------------------------------
# Generators (table = dataset name in checks for …)
# ---------------------------------------------------------------------------


def _gen_volume(table: str, column: str | None = None, **kwargs: Any) -> str:
    return f"checks for {table}:\n  - row_count > 0\n"


def _gen_freshness(table: str, column: str | None = None, **kwargs: Any) -> str:
    if not column:
        raise ValueError("freshness requires a column")
    threshold = kwargs.get("threshold", "24h")
    return f"checks for {table}:\n  - freshness({column}) < {threshold}\n"


def _gen_freshness_warn_fail(table: str, column: str | None = None, **kwargs: Any) -> str:
    if not column:
        raise ValueError("freshness_warn_fail requires a column")
    name = (kwargs.get("check_name") or "Freshness thresholds").strip()
    warn_th = (kwargs.get("warn_threshold") or "12h").strip()
    fail_th = (kwargs.get("fail_threshold") or "24h").strip()
    block = {
        "name": name,
        "warn": f"when > {warn_th}",
        "fail": f"when > {fail_th}",
    }
    inner = _dump_subdoc(block, 6)
    return f"checks for {table}:\n  - freshness({column}):\n{inner}\n"


def _gen_completeness(table: str, column: str | None = None, **kwargs: Any) -> str:
    if not column:
        raise ValueError("completeness requires a column")
    return f"checks for {table}:\n  - missing_count({column}) = 0\n"


def _gen_missing_percent(table: str, column: str | None = None, **kwargs: Any) -> str:
    if not column:
        raise ValueError("missing_percent requires a column")
    op = (kwargs.get("operator") or "<").strip()
    val = (kwargs.get("threshold") or "5").strip().rstrip("%")
    pct = f"{val}%" if not val.endswith("%") else val
    return f"checks for {table}:\n  - missing_percent({column}) {op} {pct}\n"


def _gen_uniqueness(table: str, column: str | None = None, **kwargs: Any) -> str:
    if not column:
        raise ValueError("uniqueness requires a column")
    return f"checks for {table}:\n  - duplicate_count({column}) = 0\n"


def _gen_validity(table: str, column: str | None = None, **kwargs: Any) -> str:
    if not column:
        raise ValueError("validity requires a column")
    raw = kwargs.get("valid_values") or "ok"
    if isinstance(raw, list):
        vals = [str(v).strip() for v in raw if str(v).strip()]
    else:
        vals = [v.strip() for v in str(raw).split(",") if v.strip()]
    if not vals:
        vals = ["ok"]
    block = {"valid values": vals}
    inner = _dump_subdoc(block, 6)
    return f"checks for {table}:\n  - invalid_count({column}) = 0:\n{inner}\n"


def _gen_validity_format(table: str, column: str | None = None, **kwargs: Any) -> str:
    if not column:
        raise ValueError("validity_format requires a column")
    fmt = (kwargs.get("valid_format") or "email").strip()
    block = {"valid format": fmt}
    inner = _dump_subdoc(block, 6)
    return f"checks for {table}:\n  - invalid_count({column}) = 0:\n{inner}\n"


def _gen_validity_regex(table: str, column: str | None = None, **kwargs: Any) -> str:
    if not column:
        raise ValueError("validity_regex requires a column")
    pattern = (kwargs.get("pattern") or r"^.+$").strip()
    block = {"valid regex": pattern}
    inner = _dump_subdoc(block, 6)
    return f"checks for {table}:\n  - invalid_count({column}) = 0:\n{inner}\n"


def _gen_consistency(table: str, column: str | None = None, **kwargs: Any) -> str:
    left = (kwargs.get("source_columns") or column or "").strip()
    if not left:
        raise ValueError("consistency requires a column or source_columns")
    other_table = (kwargs.get("other_table") or "").strip()
    right = (kwargs.get("other_columns") or kwargs.get("other_column") or "").strip()
    if not other_table or not right:
        raise ValueError("consistency requires other_table and other_column(s)")
    if "," in left and "," in right:
        left_in = ", ".join(c.strip() for c in left.split(",") if c.strip())
        right_in = ", ".join(c.strip() for c in right.split(",") if c.strip())
        return (
            f"checks for {table}:\n"
            f"  - values in ({left_in}) must exist in {other_table} ({right_in})\n"
        )
    return (
        f"checks for {table}:\n"
        f"  - values in ({left}) must exist in {other_table} ({right})\n"
    )


def _gen_statistical(table: str, column: str | None = None, **kwargs: Any) -> str:
    if not column:
        raise ValueError("statistical requires a column")
    metric = (kwargs.get("metric") or "avg").strip()
    lo = kwargs.get("min", 0)
    hi = kwargs.get("max", 100)
    return f"checks for {table}:\n  - {metric}({column}) between {lo} and {hi}\n"


def _gen_schema(table: str, column: str | None = None, **kwargs: Any) -> str:
    raw = (kwargs.get("required_columns") or "id").strip()
    cols = [c.strip() for c in raw.split(",") if c.strip()]
    if not cols:
        cols = ["id"]
    lines = [
        f"checks for {table}:",
        "  - schema:",
        "      fail:",
        "        when required column missing:",
    ]
    for c in cols:
        lines.append(f"          - {c}")
    return "\n".join(lines) + "\n"


def _gen_custom_sql(table: str, column: str | None = None, **kwargs: Any) -> str:
    expr = kwargs.get("sql") or kwargs.get("fail_condition") or "1 = 0"
    return f"checks for {table}:\n  - failed rows:\n      fail condition: {expr}\n"


def _gen_failed_rows_query(table: str, column: str | None = None, **kwargs: Any) -> str:
    name = (kwargs.get("check_name") or "Failed rows query").strip()
    query = (kwargs.get("fail_query") or "").strip()
    if not query:
        raise ValueError("failed_rows_query requires fail_query")
    qlines = query.splitlines()
    body = "\n".join("        " + (ln if ln.strip() else "") for ln in qlines)
    return (
        f"checks for {table}:\n"
        f"  - failed rows:\n"
        f"      name: {name}\n"
        f"      fail query: |\n{body}\n"
    )


def _gen_profiling(table: str, column: str | None = None, **kwargs: Any) -> str:
    raw = kwargs.get("columns")
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        cols = [column] if column else ["id"]
    elif isinstance(raw, str):
        cols = [c.strip() for c in raw.split(",") if c.strip()]
    else:
        cols = list(raw)
    if not cols:
        cols = ["id"]
    inner = _dump_subdoc({"columns": cols}, 4)
    return f"checks for {table}:\n  - profile columns:\n{inner}\n"


def _gen_cross_row_count(table: str, column: str | None = None, **kwargs: Any) -> str:
    other = (kwargs.get("other_dataset") or "").strip()
    if not other:
        raise ValueError("cross_row_count requires other_dataset")
    return f"checks for {table}:\n  - row_count same as {other}\n"


def _gen_user_defined_expression(table: str, column: str | None = None, **kwargs: Any) -> str:
    metric = (kwargs.get("metric_name") or "custom_metric").strip()
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", metric):
        raise ValueError("metric_name must be a simple identifier")
    expr = (kwargs.get("expression") or "").strip()
    if not expr:
        raise ValueError("user_defined_expression requires expression")
    op = (kwargs.get("operator") or ">").strip()
    threshold = (kwargs.get("threshold") or "0").strip()
    key = f"{metric} expression"
    block = {key: expr}
    inner = _dump_subdoc(block, 6)
    return f"checks for {table}:\n  - {metric} {op} {threshold}:\n{inner}\n"


def _gen_user_defined_query(table: str, column: str | None = None, **kwargs: Any) -> str:
    metric = (kwargs.get("metric_name") or "custom_metric").strip()
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", metric):
        raise ValueError("metric_name must be a simple identifier")
    query = (kwargs.get("metric_query") or "").strip()
    if not query:
        raise ValueError("user_defined_query requires metric_query")
    op = (kwargs.get("operator") or "=").strip()
    threshold = (kwargs.get("threshold") or "0").strip()
    key = f"{metric} query"
    qlines = query.splitlines()
    body = "\n".join("        " + (ln if ln.strip() else "") for ln in qlines)
    return (
        f"checks for {table}:\n"
        f"  - {metric} {op} {threshold}:\n"
        f"      {key}: |\n{body}\n"
    )


def _gen_filtered_check(table: str, column: str | None = None, **kwargs: Any) -> str:
    """Section 10: metric line + filter (and optional name / validity)."""
    base = (kwargs.get("base_check") or "row_count > 0").strip()
    flt = (kwargs.get("filter_sql") or "").strip()
    if not flt:
        raise ValueError("filtered_check requires filter_sql")
    name = (kwargs.get("check_name") or "").strip()
    block: dict[str, Any] = {"filter": flt}
    if name:
        block["name"] = name
    inner = _dump_subdoc(block, 6)
    return f"checks for {table}:\n  - {base}:\n{inner}\n"


TEMPLATES: dict[str, dict[str, Any]] = {
    "volume": {
        "label": "Volume",
        "description": "Table has at least one row (row_count > 0).",
        "icon": "chart-bar",
        "category": "integrity",
        "soda_section": 1,
        "needs_column": False,
        "column_types": [],
        "params": [],
        "generate": _gen_volume,
    },
    "freshness": {
        "label": "Freshness",
        "description": "Timestamp column is newer than a threshold (e.g. 24h, 1d).",
        "icon": "clock",
        "category": "timeliness",
        "soda_section": 4,
        "needs_column": True,
        "column_types": ["timestamp", "date"],
        "params": [
            {
                "name": "threshold",
                "label": "Max age",
                "type": "text",
                "default": "24h",
                "placeholder": "e.g. 24h, 1d, 6h",
            },
        ],
        "generate": _gen_freshness,
    },
    "freshness_warn_fail": {
        "label": "Freshness (warn / fail)",
        "description": (
            "Named freshness check with warn and fail when data is older than thresholds."
        ),
        "icon": "clock",
        "category": "timeliness",
        "soda_section": 4,
        "needs_column": True,
        "column_types": ["timestamp", "date"],
        "params": [
            {"name": "check_name", "label": "Check name", "type": "text",
             "default": "Freshness thresholds", "placeholder": ""},
            {"name": "warn_threshold", "label": "Warn when older than", "type": "text",
             "default": "12h", "placeholder": "12h"},
            {"name": "fail_threshold", "label": "Fail when older than", "type": "text",
             "default": "24h", "placeholder": "24h"},
        ],
        "generate": _gen_freshness_warn_fail,
    },
    "completeness": {
        "label": "Completeness",
        "description": "No nulls in the column (missing_count = 0).",
        "icon": "check-circle",
        "category": "integrity",
        "soda_section": 2,
        "needs_column": True,
        "column_types": [],
        "params": [],
        "generate": _gen_completeness,
    },
    "missing_percent": {
        "label": "Missing percent",
        "description": "Cap the percentage of missing values in a column.",
        "icon": "check-circle",
        "category": "integrity",
        "soda_section": 2,
        "needs_column": True,
        "column_types": [],
        "params": [
            {"name": "operator", "label": "Operator", "type": "select",
             "default": "<", "options": ["<", "<=", "=", ">", ">="]},
            {"name": "threshold", "label": "Threshold (percent)", "type": "text",
             "default": "5", "placeholder": "5"},
        ],
        "generate": _gen_missing_percent,
    },
    "uniqueness": {
        "label": "Uniqueness",
        "description": "No duplicate values (duplicate_count = 0).",
        "icon": "finger-print",
        "category": "integrity",
        "soda_section": 3,
        "needs_column": True,
        "column_types": [],
        "params": [],
        "generate": _gen_uniqueness,
    },
    "validity": {
        "label": "Validity (allowed values)",
        "description": "Values must match an allowed list.",
        "icon": "shield-check",
        "category": "validation",
        "soda_section": 3,
        "needs_column": True,
        "column_types": [],
        "params": [
            {
                "name": "valid_values",
                "label": "Valid values (comma-separated)",
                "type": "text",
                "default": "ok",
                "placeholder": "e.g. active, inactive, pending",
            },
        ],
        "generate": _gen_validity,
    },
    "validity_format": {
        "label": "Validity (built-in format)",
        "description": "Use Soda valid format checks (email, uuid, etc.).",
        "icon": "shield-check",
        "category": "validation",
        "soda_section": 3,
        "needs_column": True,
        "column_types": [],
        "params": [
            {
                "name": "valid_format",
                "label": "Format",
                "type": "select",
                "default": "email",
                "options": [
                    "email",
                    "phone number",
                    "number",
                    "date us",
                    "uuid",
                    "ip address",
                ],
            },
        ],
        "generate": _gen_validity_format,
    },
    "validity_regex": {
        "label": "Validity (regex)",
        "description": "Values must match a regular expression.",
        "icon": "shield-check",
        "category": "validation",
        "soda_section": 3,
        "needs_column": True,
        "column_types": [],
        "params": [
            {
                "name": "pattern",
                "label": "Regex pattern",
                "type": "text",
                "default": r"^[A-Z]{3}-[0-9]{4}$",
                "placeholder": "^[A-Z]{3}-[0-9]{4}$",
            },
        ],
        "generate": _gen_validity_regex,
    },
    "consistency": {
        "label": "Referential integrity",
        "description": "Values must exist in a related table (single- or multi-column).",
        "icon": "arrows-right-left",
        "category": "validation",
        "soda_section": 6,
        "needs_column": True,
        "column_types": [],
        "params": [
            {
                "name": "other_table",
                "label": "Reference table",
                "type": "text",
                "default": "",
                "placeholder": "e.g. customers",
            },
            {
                "name": "other_column",
                "label": "Reference column(s)",
                "type": "text",
                "default": "",
                "placeholder": "id or region_id, country_code",
            },
            {
                "name": "source_columns",
                "label": "Source column(s) (optional)",
                "type": "text",
                "default": "",
                "placeholder": "Leave blank to use selected column, or a,b for multi-column",
            },
        ],
        "generate": _gen_consistency,
    },
    "statistical": {
        "label": "Statistical bounds",
        "description": "Aggregate metric stays between min and max.",
        "icon": "chart-bar",
        "category": "statistical",
        "soda_section": 1,
        "needs_column": True,
        "column_types": ["integer", "float"],
        "params": [
            {
                "name": "metric",
                "label": "Metric",
                "type": "select",
                "default": "avg",
                "options": ["avg", "min", "max", "sum", "stddev"],
            },
            {"name": "min", "label": "Min", "type": "text", "default": "0", "placeholder": "0"},
            {"name": "max", "label": "Max", "type": "text", "default": "100", "placeholder": "100"},
        ],
        "generate": _gen_statistical,
    },
    "schema": {
        "label": "Schema",
        "description": "Required columns must exist (fail if missing).",
        "icon": "table-cells",
        "category": "integrity",
        "soda_section": 5,
        "needs_column": False,
        "column_types": [],
        "params": [
            {
                "name": "required_columns",
                "label": "Required columns (comma-separated)",
                "type": "text",
                "default": "id",
                "placeholder": "e.g. id, name, created_at",
            },
        ],
        "generate": _gen_schema,
    },
    "custom_sql": {
        "label": "Failed rows (condition)",
        "description": "Rows failing a SQL boolean expression.",
        "icon": "code-bracket",
        "category": "advanced",
        "soda_section": 8,
        "needs_column": False,
        "column_types": [],
        "params": [
            {
                "name": "fail_condition",
                "label": "Fail condition SQL",
                "type": "sql",
                "default": "1 = 0",
                "placeholder": "e.g. amount < 0 OR status IS NULL",
            },
        ],
        "generate": _gen_custom_sql,
    },
    "failed_rows_query": {
        "label": "Failed rows (SQL query)",
        "description": "Explicit query that returns failing rows.",
        "icon": "code-bracket",
        "category": "advanced",
        "soda_section": 8,
        "needs_column": False,
        "column_types": [],
        "params": [
            {"name": "check_name", "label": "Check name", "type": "text",
             "default": "Failed rows query", "placeholder": ""},
            {
                "name": "fail_query",
                "label": "SQL (SELECT …)",
                "type": "sql",
                "default": "SELECT * FROM my_table WHERE 1=0",
                "placeholder": "SELECT …",
            },
        ],
        "generate": _gen_failed_rows_query,
    },
    "cross_row_count": {
        "label": "Cross dataset row count",
        "description": "Row count must match another dataset in the same connection.",
        "icon": "arrows-right-left",
        "category": "validation",
        "soda_section": 7,
        "needs_column": False,
        "column_types": [],
        "params": [
            {
                "name": "other_dataset",
                "label": "Other dataset name",
                "type": "text",
                "default": "",
                "placeholder": "e.g. dim_customer_backup",
            },
        ],
        "generate": _gen_cross_row_count,
    },
    "user_defined_expression": {
        "label": "User-defined metric (expression)",
        "description": "Custom named metric from a SQL expression.",
        "icon": "calculator",
        "category": "advanced",
        "soda_section": 9,
        "needs_column": False,
        "column_types": [],
        "params": [
            {"name": "metric_name", "label": "Metric name", "type": "text",
             "default": "net_revenue", "placeholder": "net_revenue"},
            {"name": "operator", "label": "Operator", "type": "select",
             "default": ">", "options": [">", ">=", "<", "<=", "=", "!="]},
            {"name": "threshold", "label": "Threshold", "type": "text",
             "default": "0", "placeholder": "100000"},
            {
                "name": "expression",
                "label": "SQL expression",
                "type": "sql",
                "default": "SUM(order_amount)",
                "placeholder": "SUM(amount) - SUM(refund)",
            },
        ],
        "generate": _gen_user_defined_expression,
    },
    "user_defined_query": {
        "label": "User-defined metric (query)",
        "description": "Custom metric from a scalar SQL query.",
        "icon": "calculator",
        "category": "advanced",
        "soda_section": 9,
        "needs_column": False,
        "column_types": [],
        "params": [
            {"name": "metric_name", "label": "Metric name", "type": "text",
             "default": "my_metric", "placeholder": "orders_without_items"},
            {"name": "operator", "label": "Operator", "type": "select",
             "default": "=", "options": ["=", ">", ">=", "<", "<=", "!="]},
            {"name": "threshold", "label": "Threshold", "type": "text",
             "default": "0", "placeholder": "0"},
            {
                "name": "metric_query",
                "label": "SQL query (scalar)",
                "type": "sql",
                "default": "SELECT COUNT(*) FROM my_table",
                "placeholder": "SELECT COUNT(*) …",
            },
        ],
        "generate": _gen_user_defined_query,
    },
    "filtered_check": {
        "label": "Filtered check",
        "description": "Apply a check only to rows matching a filter (Soda filter:).",
        "icon": "funnel",
        "category": "advanced",
        "soda_section": 10,
        "needs_column": False,
        "column_types": [],
        "params": [
            {"name": "check_name", "label": "Name (optional)", "type": "text",
             "default": "", "placeholder": ""},
            {
                "name": "base_check",
                "label": "Check line (SodaCL)",
                "type": "text",
                "default": "row_count > 0",
                "placeholder": "row_count > 0",
            },
            {
                "name": "filter_sql",
                "label": "Filter SQL",
                "type": "sql",
                "default": "status = 'shipped'",
                "placeholder": "status = 'completed' AND region = 'APAC'",
            },
        ],
        "generate": _gen_filtered_check,
    },
    "profiling": {
        "label": "Profiling",
        "description": "Column profiling (profile columns).",
        "icon": "magnifying-glass-circle",
        "category": "advanced",
        "soda_section": 1,
        "needs_column": False,
        "column_types": [],
        "params": [
            {
                "name": "columns",
                "label": "Columns (comma-separated, optional)",
                "type": "text",
                "default": "",
                "placeholder": "Leave empty to use id or selected column",
            },
        ],
        "generate": _gen_profiling,
    },
}
