"""Golden tests for Soda `configuration.yml` fragments built from connection params."""

from __future__ import annotations

import yaml

from sraosha.dq.config_builder import build_datasource_config


def _parsed_body(yaml_str: str) -> dict:
    data = yaml.safe_load(yaml_str)
    assert isinstance(data, dict)
    key = next(iter(data))
    body = data[key]
    assert isinstance(body, dict)
    return body


def test_clickhouse_maps_to_mysql_wire():
    y = build_datasource_config(
        "warehouse",
        "clickhouse",
        {
            "host": "127.0.0.1",
            "port": 9004,
            "username": "u",
            "password": "p",
            "database": "db1",
        },
    )
    body = _parsed_body(y)
    assert body["type"] == "mysql"
    assert body["host"] == "127.0.0.1"
    assert body["port"] == 9004
    assert body["database"] == "db1"


def test_redshift_includes_schema():
    y = build_datasource_config(
        "rs",
        "redshift",
        {
            "host": "h",
            "username": "u",
            "password": "p",
            "database": "d",
            "schema": "analytics",
        },
    )
    body = _parsed_body(y)
    assert body["type"] == "redshift"
    assert body["schema"] == "analytics"


def test_motherduck_emits_duckdb_md_uri():
    y = build_datasource_config(
        "md",
        "motherduck",
        {
            "token": "tok",
            "database": "sample_data",
        },
    )
    body = _parsed_body(y)
    assert body["type"] == "duckdb"
    assert body["database"] == "md:sample_data?motherduck_token=tok"
    assert body["read_only"] is True


def test_oracle_connectstring_from_params():
    y = build_datasource_config(
        "ora",
        "oracle",
        {
            "username": "scott",
            "password": "tiger",
            "connectstring": "host:1521/XE",
        },
    )
    body = _parsed_body(y)
    assert body["type"] == "oracle"
    assert body["connectstring"] == "host:1521/XE"


def test_passthrough_oauth_from_merged_extra():
    y = build_datasource_config(
        "tr",
        "trino",
        {
            "host": "t.example.com",
            "catalog": "hive",
            "schema": "s",
            "username": "u",
            "password": "p",
            "oauth": {"token_url": "https://idp/token", "client_id": "x", "client_secret": "y"},
        },
    )
    body = _parsed_body(y)
    assert body["type"] == "trino"
    assert "oauth" in body
    assert body["oauth"]["client_id"] == "x"


def test_mysql_standalone():
    y = build_datasource_config(
        "my",
        "mysql",
        {
            "host": "127.0.0.1",
            "username": "root",
            "password": "pw",
            "database": "app",
        },
    )
    body = _parsed_body(y)
    assert body["type"] == "mysql"
    assert body["port"] == 3306
    assert body["charset"] == "utf8mb4"
    assert body["use_unicode"] is True


def test_mysql_extra_params_override_charset_and_use_unicode():
    y = build_datasource_config(
        "my",
        "mysql",
        {
            "host": "127.0.0.1",
            "username": "root",
            "password": "pw",
            "database": "app",
            "charset": "latin1",
            "use_unicode": False,
        },
    )
    body = _parsed_body(y)
    assert body["charset"] == "latin1"
    assert body["use_unicode"] is False
