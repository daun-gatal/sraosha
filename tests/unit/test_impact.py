from sraosha.impact.graph import ContractDependencyGraph
from sraosha.impact.parser import DependencyMapping, parse_contract

CONTRACT_A = {
    "id": "orders-v1",
    "info": {"title": "Orders", "owner": "team-checkout", "version": "1.0.0"},
    "servers": {"production": {"type": "postgres", "schema": "orders"}},
    "models": {
        "orders": {
            "type": "table",
            "fields": {
                "order_id": {"type": "uuid"},
                "customer_id": {"type": "text"},
                "order_total": {"type": "integer"},
            },
        }
    },
}

CONTRACT_B = {
    "id": "order-analytics-v1",
    "info": {"title": "Order Analytics", "owner": "team-analytics", "version": "1.0.0"},
    "servers": {"production": {"type": "postgres", "schema": "analytics"}},
    "models": {
        "orders": {
            "type": "table",
            "fields": {
                "order_id": {"type": "uuid"},
                "customer_id": {"type": "text"},
                "total_orders": {"type": "integer"},
            },
        }
    },
}

CONTRACT_C = {
    "id": "customer-dashboard-v1",
    "info": {"title": "Customer Dashboard", "owner": "team-dashboard", "version": "1.0.0"},
    "servers": {"production": {"type": "postgres", "schema": "dashboard"}},
    "models": {
        "orders": {
            "type": "table",
            "fields": {
                "order_id": {"type": "uuid"},
                "customer_id": {"type": "text"},
            },
        }
    },
}

# Contract with explicit column-level depends_on using dot notation
CONTRACT_D = {
    "id": "reporting-v1",
    "info": {"title": "Reporting", "owner": "team-reporting", "version": "1.0.0"},
    "servers": {"production": {"type": "postgres", "schema": "reporting"}},
    "models": {
        "daily_report": {
            "type": "table",
            "fields": {
                "report_date": {"type": "date"},
                "cust_id": {"type": "text"},
                "total": {"type": "integer"},
            },
        }
    },
    "x-sraosha": {
        "depends_on": [
            {
                "contract": "orders-v1",
                "fields": {
                    "orders.customer_id": "daily_report.cust_id",
                    "orders.order_total": "daily_report.total",
                },
            }
        ]
    },
}

# Contract with multiple upstreams mapping to the same local column
CONTRACT_E = {
    "id": "unified-customers-v1",
    "info": {"title": "Unified Customers", "owner": "team-platform", "version": "1.0.0"},
    "servers": {"production": {"type": "postgres", "schema": "unified"}},
    "models": {
        "customers": {
            "type": "table",
            "fields": {
                "customer_id": {"type": "text"},
                "name": {"type": "text"},
            },
        }
    },
    "x-sraosha": {
        "depends_on": [
            {
                "contract": "orders-v1",
                "fields": {"orders.customer_id": "customers.customer_id"},
            },
            {
                "contract": "order-analytics-v1",
                "fields": {"orders.customer_id": "customers.customer_id"},
            },
        ]
    },
}


class TestParser:
    def test_parse_basic_contract(self):
        result = parse_contract(CONTRACT_A)
        assert result.contract_id == "orders-v1"
        assert result.owner_team == "team-checkout"
        assert "orders" in result.tables
        assert "order_id" in result.tables["orders"]
        assert "customer_id" in result.tables["orders"]

    def test_parse_server_tables(self):
        result = parse_contract(CONTRACT_A)
        assert "orders" in result.server_tables

    def test_parse_depends_on_with_field_mapping(self):
        result = parse_contract(CONTRACT_D)
        assert len(result.depends_on) == 1
        dep = result.depends_on[0]
        assert isinstance(dep, DependencyMapping)
        assert dep.contract_id == "orders-v1"
        assert dep.fields == {
            "orders.customer_id": "daily_report.cust_id",
            "orders.order_total": "daily_report.total",
        }

    def test_parse_multi_upstream_depends_on(self):
        result = parse_contract(CONTRACT_E)
        assert len(result.depends_on) == 2
        contract_ids = [d.contract_id for d in result.depends_on]
        assert "orders-v1" in contract_ids
        assert "order-analytics-v1" in contract_ids

    def test_parse_no_depends_on(self):
        result = parse_contract(CONTRACT_A)
        assert result.depends_on == []

    def test_parse_skips_malformed_depends_on(self):
        contract = {
            "id": "test",
            "x-sraosha": {
                "depends_on": [
                    "plain-string",
                    {"no_contract_key": True},
                    {"contract": "valid-id", "fields": {"a.b": "c.d"}},
                ]
            },
        }
        result = parse_contract(contract)
        assert len(result.depends_on) == 1
        assert result.depends_on[0].contract_id == "valid-id"


class TestContractDependencyGraph:
    def _build_graph(self, contracts: list[dict]) -> ContractDependencyGraph:
        graph = ContractDependencyGraph()
        for c in contracts:
            graph.add_contract(c)
        graph.build_edges()
        return graph

    def test_single_contract_no_edges(self):
        graph = self._build_graph([CONTRACT_A])
        assert len(graph.graph.nodes) == 1
        assert len(graph.graph.edges) == 0

    def test_shared_table_creates_edges(self):
        graph = self._build_graph([CONTRACT_A, CONTRACT_B])
        assert len(graph.graph.nodes) == 2
        has_edge = graph.graph.has_edge("orders-v1", "order-analytics-v1") or graph.graph.has_edge(
            "order-analytics-v1", "orders-v1"
        )
        assert has_edge

    def test_get_downstream(self):
        graph = self._build_graph([CONTRACT_A, CONTRACT_B, CONTRACT_C])
        all_downstream = set()
        for node in graph.graph.nodes:
            downstream = graph.get_downstream(node)
            all_downstream.update(downstream)
        assert len(graph.graph.nodes) == 3

    def test_get_downstream_nonexistent(self):
        graph = self._build_graph([CONTRACT_A])
        result = graph.get_downstream("nonexistent")
        assert result == []

    def test_impact_of_change(self):
        graph = self._build_graph([CONTRACT_A, CONTRACT_B, CONTRACT_C])
        for node in graph.graph.nodes:
            if graph.graph.out_degree(node) > 0:
                successors = list(graph.graph.successors(node))
                edge_data = graph.graph.edges[node, successors[0]]
                shared = edge_data.get("shared_fields", [])
                if shared:
                    impact = graph.get_impact_of_change(node, shared[:1])
                    assert len(impact["directly_affected"]) > 0
                    break

    def test_impact_no_change(self):
        graph = self._build_graph([CONTRACT_A])
        impact = graph.get_impact_of_change("orders-v1", ["nonexistent_field"])
        assert impact["directly_affected"] == []
        assert impact["severity"] == "low"

    def test_to_json(self):
        graph = self._build_graph([CONTRACT_A, CONTRACT_B])
        data = graph.to_json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 2
        node_ids = {n["id"] for n in data["nodes"]}
        assert "orders-v1" in node_ids
        assert "order-analytics-v1" in node_ids

    def test_explicit_edge_with_field_mapping(self):
        graph = self._build_graph([CONTRACT_A, CONTRACT_D])
        assert graph.graph.has_edge("orders-v1", "reporting-v1")
        edge = graph.graph.edges["orders-v1", "reporting-v1"]
        assert edge["edge_type"] == "explicit"
        assert edge["field_mapping"] == {
            "orders.customer_id": "daily_report.cust_id",
            "orders.order_total": "daily_report.total",
        }

    def test_impact_precision_mapped_field_triggers(self):
        """Changing a mapped upstream field should flag the downstream."""
        graph = self._build_graph([CONTRACT_A, CONTRACT_D])
        impact = graph.get_impact_of_change("orders-v1", ["orders.customer_id"])
        assert "reporting-v1" in impact["directly_affected"]

    def test_impact_precision_unmapped_field_does_not_trigger(self):
        """Changing an unmapped upstream field should NOT flag the downstream."""
        graph = self._build_graph([CONTRACT_A, CONTRACT_D])
        impact = graph.get_impact_of_change("orders-v1", ["orders.order_id"])
        assert "reporting-v1" not in impact["directly_affected"]

    def test_impact_precision_bare_column_match(self):
        """Bare column names (without table prefix) should still match."""
        graph = self._build_graph([CONTRACT_A, CONTRACT_D])
        impact = graph.get_impact_of_change("orders-v1", ["customer_id"])
        assert "reporting-v1" in impact["directly_affected"]

    def test_multi_upstream_creates_separate_edges(self):
        """Multiple depends_on entries for different upstreams create separate edges."""
        graph = self._build_graph([CONTRACT_A, CONTRACT_B, CONTRACT_E])
        assert graph.graph.has_edge("orders-v1", "unified-customers-v1")
        assert graph.graph.has_edge("order-analytics-v1", "unified-customers-v1")

    def test_multi_upstream_both_trigger_on_shared_field(self):
        """Changing a field on either upstream should flag the downstream."""
        graph = self._build_graph([CONTRACT_A, CONTRACT_B, CONTRACT_E])
        impact_a = graph.get_impact_of_change("orders-v1", ["orders.customer_id"])
        assert "unified-customers-v1" in impact_a["directly_affected"]

        impact_b = graph.get_impact_of_change("order-analytics-v1", ["orders.customer_id"])
        assert "unified-customers-v1" in impact_b["directly_affected"]

    def test_to_json_includes_field_mapping(self):
        graph = self._build_graph([CONTRACT_A, CONTRACT_D])
        data = graph.to_json()
        explicit_edges = [e for e in data["edges"] if e["edge_type"] == "explicit"]
        assert len(explicit_edges) == 1
        assert explicit_edges[0]["field_mapping"] == {
            "orders.customer_id": "daily_report.cust_id",
            "orders.order_total": "daily_report.total",
        }
        pairs = explicit_edges[0]["column_pairs"]
        assert any(p["upstream_ref"] == "orders.customer_id" for p in pairs)
        assert all(not p["inferred"] for p in pairs)

    def test_parse_contract_platform(self):
        cf = parse_contract(CONTRACT_A)
        assert cf.platform == "postgres"
        assert cf.platforms == ["postgres"]

    def test_lineage_node_set(self):
        graph = self._build_graph([CONTRACT_A, CONTRACT_B, CONTRACT_C])
        ns = graph.lineage_node_set("orders-v1", 2, 2)
        assert "orders-v1" in ns

    def test_to_json_node_platform(self):
        graph = self._build_graph([CONTRACT_A])
        data = graph.to_json()
        assert data["nodes"][0]["platform"] == "postgres"
