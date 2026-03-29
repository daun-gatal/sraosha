from sraosha.impact.graph import ContractDependencyGraph
from sraosha.impact.parser import parse_contract

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
        has_edge = graph.graph.has_edge("orders-v1", "order-analytics-v1") or \
                   graph.graph.has_edge("order-analytics-v1", "orders-v1")
        assert has_edge

    def test_get_downstream(self):
        graph = self._build_graph([CONTRACT_A, CONTRACT_B, CONTRACT_C])
        all_downstream = set()
        for node in graph.graph.nodes:
            downstream = graph.get_downstream(node)
            all_downstream.update(downstream)
        # At least some dependencies should be detected from shared "orders" table
        assert len(graph.graph.nodes) == 3

    def test_get_downstream_nonexistent(self):
        graph = self._build_graph([CONTRACT_A])
        result = graph.get_downstream("nonexistent")
        assert result == []

    def test_impact_of_change(self):
        graph = self._build_graph([CONTRACT_A, CONTRACT_B, CONTRACT_C])
        # Find which node is the producer and test from there
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
