"""Golden-style tests for SodaCL snippets from check templates."""

from __future__ import annotations

import pytest

from sraosha.dq.check_templates import TEMPLATES


def _gen(key: str, table: str, column: str | None = None, **kwargs):
    return TEMPLATES[key]["generate"](table, column, **kwargs)


def test_volume_row_count():
    y = _gen("volume", "orders")
    assert "checks for orders:" in y
    assert "row_count > 0" in y


def test_no_anomaly_templates_in_registry():
    assert "anomaly" not in TEMPLATES
    assert "distribution" not in TEMPLATES


def test_schema_uses_explicit_columns_not_auto_discover():
    y = _gen("schema", "dim_product", required_columns="product_id, product_name, list_price")
    assert "when required column missing:" in y
    assert "- product_id" in y
    assert "- list_price" in y


def test_statistical_metric_select():
    y = _gen("statistical", "orders", "order_amount", metric="min", min=0, max=1_000_000)
    assert "min(order_amount) between 0 and 1000000" in y


def test_consistency_multi_column():
    y = _gen(
        "consistency",
        "orders",
        None,
        source_columns="region_id, country_code",
        other_table="regions",
        other_columns="region_id, country_code",
    )
    assert "values in (region_id, country_code) must exist in regions (region_id, country_code)" in y


def test_cross_row_count():
    y = _gen("cross_row_count", "dim_customer", other_dataset="dim_customer_backup")
    assert "row_count same as dim_customer_backup" in y


def test_validity_format_email():
    y = _gen("validity_format", "customers", "email", valid_format="email")
    assert "invalid_count(email) = 0" in y
    assert "valid format: email" in y


def test_user_defined_expression_matches_reference_shape():
    y = _gen(
        "user_defined_expression",
        "orders",
        None,
        metric_name="net_revenue",
        operator=">",
        threshold="100000",
        expression="SUM(order_amount) - SUM(refund_amount)",
    )
    assert "net_revenue > 100000" in y
    assert "net_revenue expression:" in y


def test_failed_rows_query_block_scalar():
    y = _gen(
        "failed_rows_query",
        "orders",
        fail_query="SELECT *\nFROM orders\nWHERE id IS NULL",
        check_name="Bad rows",
    )
    assert "fail query: |" in y
    assert "FROM orders" in y


def test_all_templates_have_soda_section():
    for key, meta in TEMPLATES.items():
        assert "soda_section" in meta and isinstance(meta["soda_section"], int)


@pytest.mark.parametrize("key", list(TEMPLATES.keys()))
def test_generate_does_not_raise_for_minimal_args(key: str):
    meta = TEMPLATES[key]
    gen = meta["generate"]
    needs_col = meta.get("needs_column", False)
    params = {p["name"]: p.get("default", "") for p in meta.get("params", [])}
    col = "c" if needs_col else None

    if key == "volume":
        gen("t", None)
        return
    if key == "schema":
        gen("t", col, **{**params, "required_columns": "id"})
        return
    if key == "custom_sql":
        gen("t", col, **{**params, "fail_condition": "1=0"})
        return
    if key == "failed_rows_query":
        gen("t", col, **{**params, "fail_query": "SELECT 1"})
        return
    if key == "cross_row_count":
        gen("t", col, **{**params, "other_dataset": "other_t"})
        return
    if key == "user_defined_expression":
        gen(
            "t",
            col,
            metric_name="m",
            expression="COUNT(*)",
            operator=">",
            threshold="0",
        )
        return
    if key == "user_defined_query":
        gen("t", col, metric_name="m", metric_query="SELECT 1", operator="=", threshold="1")
        return
    if key == "filtered_check":
        gen("t", col, **{**params, "filter_sql": "TRUE", "base_check": "row_count > 0"})
        return
    if key == "profiling":
        gen("t", col, **params)
        return
    if key == "consistency":
        gen(
            "t",
            "src_col",
            **{
                **params,
                "other_table": "ref_t",
                "other_column": "id",
            },
        )
        return

    gen("t", col, **params)
