import networkx as nx

from sraosha.impact.parser import ContractFields, parse_contract


class ContractDependencyGraph:
    """
    Builds a directed graph of cross-contract dependencies.
    Nodes: contracts (keyed by contract_id)
    Edges: A -> B if B references tables/fields that A defines,
           or if B explicitly declares depends_on A with table.column mapping.
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
            platform=parsed.platform,
            platforms=list(parsed.platforms),
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
                                field_mapping={},
                                edge_type="inferred",
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
                                field_mapping={},
                                edge_type="inferred",
                            )

        # Explicit depends_on declarations with table.column mapping
        for cf in contracts:
            for dep in cf.depends_on:
                upstream_id = dep.contract_id
                if upstream_id not in self.graph or upstream_id == cf.contract_id:
                    continue

                if self.graph.has_edge(upstream_id, cf.contract_id):
                    edge = self.graph.edges[upstream_id, cf.contract_id]
                    edge["edge_type"] = "explicit"
                    existing_mapping = edge.get("field_mapping", {})
                    existing_mapping.update(dep.fields)
                    edge["field_mapping"] = existing_mapping
                    if dep.fields:
                        existing_shared = set(edge.get("shared_fields", []))
                        for k in dep.fields:
                            col = k.split(".")[-1] if "." in k else k
                            existing_shared.add(col)
                        edge["shared_fields"] = list(existing_shared)
                else:
                    explicit_shared_fields = (
                        [k.split(".")[-1] if "." in k else k for k in dep.fields]
                        if dep.fields
                        else []
                    )
                    self.graph.add_edge(
                        upstream_id,
                        cf.contract_id,
                        shared_fields=explicit_shared_fields,
                        field_mapping=dict(dep.fields),
                        edge_type="explicit",
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

        changed_set = set(changed_fields)

        directly_affected: list[str] = []
        for successor in self.graph.successors(contract_id):
            edge_data = self.graph.edges[contract_id, successor]
            fm = edge_data.get("field_mapping", {})
            shared = set(edge_data.get("shared_fields", []))
            is_explicit = edge_data.get("edge_type") == "explicit"

            if is_explicit and fm:
                # Precise match: check if any changed field matches a mapping key
                # Support both full dot-notation and bare column names
                if set(fm.keys()) & changed_set:
                    directly_affected.append(successor)
                else:
                    bare_keys = {k.split(".")[-1] if "." in k else k for k in fm}
                    bare_changed = {f.split(".")[-1] if "." in f else f for f in changed_set}
                    if bare_keys & bare_changed:
                        directly_affected.append(successor)
            elif is_explicit and not fm:
                directly_affected.append(successor)
            elif shared & changed_set:
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

    def lineage_node_set(
        self, focus_id: str, upstream_depth: int, downstream_depth: int
    ) -> set[str]:
        """Nodes within hop limits upstream and downstream of focus (includes focus)."""
        if focus_id not in self.graph:
            return set()
        nodes: set[str] = {focus_id}
        frontier: set[str] = {focus_id}
        for _ in range(max(0, upstream_depth)):
            nxt: set[str] = set()
            for n in frontier:
                for p in self.graph.predecessors(n):
                    nodes.add(p)
                    nxt.add(p)
            frontier = nxt
        frontier = {focus_id}
        for _ in range(max(0, downstream_depth)):
            nxt = set()
            for n in frontier:
                for s in self.graph.successors(n):
                    nodes.add(s)
                    nxt.add(s)
            frontier = nxt
        return nodes

    def to_json(self, node_ids: set[str] | None = None) -> dict:
        g = self.graph
        if node_ids is not None:
            node_ids = node_ids & set(g.nodes())
            if not node_ids:
                return {"nodes": [], "edges": []}
            g = self.graph.subgraph(node_ids).copy()

        nodes = []
        for node_id, data in g.nodes(data=True):
            nodes.append(
                {
                    "id": node_id,
                    "label": node_id,
                    "owner_team": data.get("owner_team"),
                    "tables": data.get("tables", []),
                    "platform": data.get("platform") or "",
                    "platforms": data.get("platforms") or [],
                    "upstream_count": g.in_degree(node_id),
                    "downstream_count": g.out_degree(node_id),
                    "degree": g.degree(node_id),
                }
            )

        edges = []
        for source, target, data in g.edges(data=True):
            edge_data = dict(data)
            column_pairs = self._build_column_pairs(source, target, edge_data)
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "shared_fields": data.get("shared_fields", []),
                    "field_mapping": data.get("field_mapping") or {},
                    "edge_type": data.get("edge_type", "inferred"),
                    "column_pairs": column_pairs,
                }
            )

        return {"nodes": nodes, "edges": edges}

    def _first_table_with_field(self, cf: ContractFields, col: str) -> str | None:
        for table, fields in cf.tables.items():
            if col in fields:
                return table
        return None

    def _build_column_pairs(self, source: str, target: str, edge_data: dict) -> list[dict]:
        """Upstream/downstream field refs for API and UI."""
        fm = edge_data.get("field_mapping") or {}
        et = edge_data.get("edge_type", "inferred")
        if et == "explicit" and fm:
            return [
                {"upstream_ref": str(k), "downstream_ref": str(v), "inferred": False}
                for k, v in fm.items()
            ]
        prod = self._contract_fields.get(source)
        cons = self._contract_fields.get(target)
        shared = edge_data.get("shared_fields") or []
        pairs: list[dict] = []
        if not prod or not cons:
            for col in shared:
                pairs.append({"upstream_ref": col, "downstream_ref": col, "inferred": True})
            return pairs
        for col in shared:
            up_tbl = self._first_table_with_field(prod, col)
            dn_tbl = self._first_table_with_field(cons, col)
            ur = f"{up_tbl}.{col}" if up_tbl else col
            dr = f"{dn_tbl}.{col}" if dn_tbl else col
            pairs.append({"upstream_ref": ur, "downstream_ref": dr, "inferred": True})
        return pairs
