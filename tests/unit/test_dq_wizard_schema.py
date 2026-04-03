from __future__ import annotations

import pytest

from sraosha.schemas.dq_wizard import MAX_PARAMS_JSON_BYTES, parse_dq_generate_params


def test_parse_empty():
    assert parse_dq_generate_params(None) == {}
    assert parse_dq_generate_params("") == {}
    assert parse_dq_generate_params("   ") == {}


def test_parse_object():
    assert parse_dq_generate_params('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_rejects_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        parse_dq_generate_params("[1,2]")


def test_size_limit():
    big = '{"x": "%s"}' % ("y" * (MAX_PARAMS_JSON_BYTES + 10))
    with pytest.raises(ValueError, match="too large"):
        parse_dq_generate_params(big)
