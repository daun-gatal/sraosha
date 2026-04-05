"""Tests for connection test param merging."""

import uuid

from sraosha.crypto import encrypt
from sraosha.models.connection import Connection
from sraosha.schemas.connection import ConnectionTestRequest
from sraosha.services.connection_test import params_for_connection_test, verify_connection_params


def test_params_create_no_merge():
    body = ConnectionTestRequest(
        name="x",
        server_type="postgres",
        host="h",
        port=5432,
        database="db",
        username="u",
        password="pw",
    )
    p = params_for_connection_test(body, None)
    assert p["host"] == "h"
    assert p["password"] == "pw"
    assert "schema" not in p


def test_params_edit_merges_stored_password():
    cid = uuid.uuid4()
    c = Connection(
        id=cid,
        name="n",
        server_type="postgres",
        host="oldhost",
        database="db",
        username="u",
        password_encrypted=encrypt("secret"),
    )
    body = ConnectionTestRequest(
        name="n",
        server_type="postgres",
        host="newhost",
        database="db",
        username="u",
        password=None,
        existing_connection_id=cid,
    )
    p = params_for_connection_test(body, c)
    assert p["host"] == "newhost"
    assert p["password"] == "secret"


def test_verify_connection_params_unknown_type():
    ok, msg = verify_connection_params("unsupported_engine", {})
    assert ok is False
    assert msg is not None
