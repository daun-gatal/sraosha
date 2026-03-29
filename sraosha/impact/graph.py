import networkx as nx

from sraosha.impact.parser import ContractFields, parse_contract


class ContractDependencyGraph:
    """
    Builds a directed graph of cross-contract dependencies.
    Nodes: contracts (keyed by contract_id)
    Edges: A -> B if B references tables/fields that A defines
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self._contract_fields: dict[str, ContractFields] = {}

    def add_contract(self, contract: dict) -> None:
        parsed = parse_contract(contract)
        self._contract_fields[parsed.contract_id] = parsed
        self.graph.add_node(
            parsed.contract_id,
            owner_team=parsed.owner_team,
            tables=list(parsed.tables.keys()),
        )

    def build_edges(self) -> None:
        contracts = list(self._contract_fields.values())

        table_owners: dict[str, str] = {}
        for cf in contracts:
            for table_name in cf.tables:
                table_owners[table_name] = cf.contract_id

        for cf in contracts:
            for ref_table in cf.server_tables:
                if ref_table in table_owners:
                    producer = table_owners[ref_table]
                    if producer != cf.contract_id:
                        producer_fields = set(
                            self._contract_fields[producer].tables.get(ref_table, [])
                        )
                        consumer_fields = set()
                        for table_name, fields in cf.tables.items():
                            consumer_fields.update(fields)

                        shared = producer_fields & consumer_fields
                        if shared:
                            self.graph.add_edge(
                                producer,
                                cf.contract_id,
                                shared_fields=list(shared),
                            )

            for table_name in cf.tables:
                if table_name in table_owners:
                    producer = table_owners[table_name]
                    if producer != cf.contract_id and not self.graph.has_edge(
                        producer, cf.contract_id
                    ):
                        producer_fields = set(
                            self._contract_fields[producer].tables.get(table_name, [])
                        )
                        consumer_fields = set(cf.tables.get(table_name, []))
                        shared = producer_fields & consumer_fields
                        if shared:
                            self.graph.add_edge(
                                producer,
                                cf.contract_id,
                                shared_fields=list(shared),
                            )

    def get_downstream(self, contract_id: str, depth: int = -1) -> list[str]:
        if contract_id not in self.graph:
            return []
        if depth == -1:
            return list(nx.descendants(self.graph, contract_id))
        downstream = set()
        current_level = {contract_id}
        for _ in range(depth):
            next_level = set()
            for node in current_level:
                for successor in self.graph.successors(node):
                    if successor not in downstream and successor != contract_id:
                        downstream.add(successor)
                        next_level.add(successor)
            current_level = next_level
            if not current_level:
                break
        return list(downstream)

    def get_impact_of_change(self, contract_id: str, changed_fields: list[str]) -> dict:
        if contract_id not in self.graph:
            return {
                "directly_affected": [],
                "transitively_affected": [],
                "severity": "low",
                "affected_pipelines": [],
            }

        directly_affected: list[str] = []
        for successor in self.graph.successors(contract_id):
            edge_data = self.graph.edges[contract_id, successor]
            shared = set(edge_data.get("shared_fields", []))
            if shared & set(changed_fields):
                directly_affected.append(successor)

        transitively_affected: list[str] = []
        for direct in directly_affected:
            downstream = self.get_downstream(direct)
            for d in downstream:
                if d not in directly_affected and d not in transitively_affected:
                    transitively_affected.append(d)

        total_affected = len(directly_affected) + len(transitively_affected)
        if total_affected == 0:
            severity = "low"
        elif total_affected <= 2:
            severity = "medium"
        else:
            severity = "high"

        return {
            "directly_affected": directly_affected,
            "transitively_affected": transitively_affected,
            "severity": severity,
            "affected_pipelines": [],
        }

    def to_json(self) -> dict:
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nodes.append(
                {
                    "id": node_id,
                    "label": node_id,
                    "owner_team": data.get("owner_team"),
                    "tables": data.get("tables", []),
                }
            )

        edges = []
        for source, target, data in self.graph.edges(data=True):
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "shared_fields": data.get("shared_fields", []),
                }
            )

        return {"nodes": nodes, "edges": edges}
