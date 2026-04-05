"""Tests for Soda MySQL charset patch (no-op when soda-core-mysql is absent)."""

from sraosha.dq.backends.soda import (
    _apply_extra_params_to_mysql_connector_kwargs,
    _mysql_connect_kwargs_with_utf8mb4,
    _patch_soda_mysql_connector_charset,
)


def test_patch_is_idempotent():
    _patch_soda_mysql_connector_charset()
    _patch_soda_mysql_connector_charset()


def test_mysql_connect_kwargs_default_utf8mb4():
    k = _mysql_connect_kwargs_with_utf8mb4({})
    assert k["charset"] == "utf8mb4"
    assert k["use_unicode"] is True
    assert k["use_pure"] is True


def test_mysql_connect_kwargs_replaces_utf8_alias():
    k = _mysql_connect_kwargs_with_utf8mb4({"charset": "utf8"})
    assert k["charset"] == "utf8mb4"


def test_mysql_connect_kwargs_preserves_explicit_utf8mb4():
    k = _mysql_connect_kwargs_with_utf8mb4({"charset": "utf8mb4", "use_unicode": False})
    assert k["charset"] == "utf8mb4"
    assert k["use_unicode"] is False


def test_apply_extra_params_overrides_charset():
    merged = _mysql_connect_kwargs_with_utf8mb4({})
    _apply_extra_params_to_mysql_connector_kwargs(merged, {"charset": "latin1"})
    assert merged["charset"] == "latin1"


def test_apply_extra_params_use_unicode():
    merged = _mysql_connect_kwargs_with_utf8mb4({})
    _apply_extra_params_to_mysql_connector_kwargs(merged, {"use_unicode": False})
    assert merged["use_unicode"] is False
