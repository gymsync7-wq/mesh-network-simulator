import matplotlib.pyplot as plt
import networkx as nx

def draw_network(G, path=None):

    pos = nx.get_node_attributes(G, 'pos')

    # Compute positions if not set
    if not pos:
        pos = nx.spring_layout(G)

    node_colors = []

    for node in G.nodes():

        if G.nodes[node].get('failed') == True:
            node_colors.append('red')   # 🔴 failed node
        else:
            node_colors.append('skyblue')

    nx.draw(G, pos, node_color=node_colors, with_labels=True)

    if path:
        edges = list(zip(path, path[1:]))
        nx.draw_networkx_edges(G, pos,
                               edgelist=edges,
                               edge_color='green',
                               width=3)

    plt.title("Mesh Network Failure Simulation")
    plt.show()