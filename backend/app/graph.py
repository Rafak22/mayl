"""Project Graph: the shared map every agent reads and writes.

Impact analysis is graph traversal, not LLM guessing: a change to a node
affects every node reachable from it through `feeds` or `constrains` edges.
"""
import networkx as nx


def build_graph(product: dict) -> nx.DiGraph:
    g = nx.DiGraph()
    for node in product["nodes"]:
        g.add_node(node["id"], **node)
    for src, dst, kind in product["edges"]:
        g.add_edge(src, dst, kind=kind)
    return g


def affected_nodes(product: dict, node_id: str) -> list[dict]:
    """The changed node plus everything downstream of it, in dependency order."""
    g = build_graph(product)
    if node_id not in g:
        raise KeyError(node_id)
    reach = {node_id} | nx.descendants(g, node_id)
    order = [n for n in nx.topological_sort(g) if n in reach]
    return [g.nodes[n] for n in order]


def path_explanation(product: dict, start: str, end: str) -> list[str]:
    """Human-readable chain, e.g. ['Serving hardware', 'XGBoost model', 'Scoring service']."""
    g = build_graph(product)
    try:
        return [g.nodes[n]["label"] for n in nx.shortest_path(g, start, end)]
    except nx.NetworkXNoPath:
        return []
