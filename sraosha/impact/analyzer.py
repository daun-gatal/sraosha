"""Impact analysis for proposed contract changes."""

from sraosha.impact.graph import ContractDependencyGraph


class ImpactAnalyzer:
    """Builds a graph from contracts and analyzes impact of proposed changes."""

    def __init__(self, contracts: list[dict]):
        self.graph = ContractDependencyGraph()
        for contract in contracts:
            self.graph.add_contract(contract)
        self.graph.build_edges()

    def analyze(self, contract_id: str, changed_fields: list[str]) -> dict:
        return self.graph.get_impact_of_change(contract_id, changed_fields)

    def get_downstream(self, contract_id: str) -> list[str]:
        return self.graph.get_downstream(contract_id)

    def to_json(self, node_ids: set[str] | None = None) -> dict:
        return self.graph.to_json(node_ids)

    def lineage_json(
        self, contract_id: str, upstream_depth: int, downstream_depth: int
    ) -> dict:
        ns = self.graph.lineage_node_set(contract_id, upstream_depth, downstream_depth)
        return self.graph.to_json(ns)
