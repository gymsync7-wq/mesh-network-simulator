import networkx as nx
import random


def create_nodes(n):
    """Create a graph with n nodes."""
    G = nx.Graph()
    G.add_nodes_from(range(n))
    return G


def connect_nodes(G, num_edges):
    """Connect nodes in the graph with random weighted edges."""
    nodes = list(G.nodes())
    edges_added = 0

    while edges_added < num_edges:
        u = random.choice(nodes)
        v = random.choice(nodes)

        if u != v and not G.has_edge(u, v):
            weight = random.randint(1, 10)
            G.add_edge(u, v, weight=weight)
            edges_added += 1

    return G


def fail_node_in_path(G, path, source, destination):

    candidates = [n for n in path if n != source and n != destination]

    if not candidates:
        return None

    failed_node = candidates[0]   # always fail first valid node

    # 🔥 MARK NODE AS FAILED (DO NOT REMOVE)
    G.nodes[failed_node]['failed'] = True

    return failed_node