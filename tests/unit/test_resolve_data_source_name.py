"""Tests for Soda data source name resolution."""

from sraosha.dq.config_builder import (
    explicit_data_source_for_form,
    resolve_data_source_name,
    sanitize_data_source_name,
)


def test_resolve_explicit_valid() -> None:
    name, err = resolve_data_source_name("postgres", "mysql")
    assert err is None
    assert name == sanitize_data_source_name("mysql")


def test_resolve_explicit_invalid() -> None:
    name, err = resolve_data_source_name("postgres", "not_a_connector")
    assert name == ""
    assert err is not None


def test_resolve_default_from_server_type() -> None:
    name, err = resolve_data_source_name("snowflake", "")
    assert err is None
    assert name == sanitize_data_source_name("snowflake")


def test_explicit_for_form_matches_default() -> None:
    default, _ = resolve_data_source_name("postgres", "")
    assert explicit_data_source_for_form(default, "postgres") == ""


def test_explicit_for_form_non_default() -> None:
    assert explicit_data_source_for_form("mysql", "postgres") == "mysql"
