import networkx as nx

def find_shortest_path(G, source, destination):

    # create a temporary graph without failed nodes
    G_copy = G.copy()

    for node in list(G_copy.nodes()):
        if G_copy.nodes[node].get('failed') == True:
            G_copy.remove_node(node)

    try:
        return nx.dijkstra_path(G_copy, source, destination, weight='weight')
    except:
        return None