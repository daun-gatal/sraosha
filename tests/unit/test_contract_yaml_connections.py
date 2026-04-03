"""Tests for x-sraosha.server_connections in form/YAML conversion."""

from sraosha.api.contract_yaml import (
    connection_id_to_name_map_from_connections,
    form_to_yaml_dict,
    yaml_dict_to_form,
)


class _Conn:
    def __init__(self, id_str: str, name: str):
        self.id = id_str
        self.name = name


def test_form_to_yaml_dict_writes_server_connections():
    form = {
        "spec_version": "1.1.0",
        "contract_id": "c1",
        "title": "T",
        "server_name[]": ["prod"],
        "server_type[]": ["postgres"],
        "server_host[]": ["h"],
        "server_connection[]": ["uuid-1"],
    }
    cmap = {"uuid-1": "warehouse-prod"}
    doc = form_to_yaml_dict(form, cmap)
    assert doc["x-sraosha"]["server_connections"] == {"prod": "warehouse-prod"}


def test_yaml_dict_to_form_round_trip():
    form = {
        "spec_version": "1.1.0",
        "contract_id": "c1",
        "title": "T",
        "server_name[]": ["prod"],
        "server_type[]": ["postgres"],
        "server_connection[]": ["u1"],
    }
    conns = [_Conn("u1", "my-conn")]
    doc = form_to_yaml_dict(form, connection_id_to_name_map_from_connections(conns))
    back = yaml_dict_to_form(doc)
    assert back["servers"][0]["connection_name"] == "my-conn"


def test_connection_id_to_name_map_from_connections():
    conns = [_Conn("a", "n1"), _Conn("b", "n2")]
    m = connection_id_to_name_map_from_connections(conns)
    assert m == {"a": "n1", "b": "n2"}
