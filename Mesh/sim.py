import networkx as nx
import matplotlib.pyplot as plt
import random
import math

plt.ion()

G = None
src = None
dst = None
current_path = None
selected_nodes = []


# -----------------------
# Create Network — retry until a 4+ node path exists
# -----------------------
def create_network(n=12, range_val=55):
    while True:
        G = nx.Graph()
        for i in range(n):
            G.add_node(i,
                       pos=(random.randint(0, 100), random.randint(0, 100)),
                       failed=False)

        nodes = list(G.nodes(data=True))
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                x1, y1 = nodes[i][1]['pos']
                x2, y2 = nodes[j][1]['pos']
                dist = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
                if dist <= range_val:
                    G.add_edge(nodes[i][0], nodes[j][0], weight=dist)

        # Find any src/dst pair with path length >= 4 nodes
        pair = find_long_path_pair(G, min_length=4)
        if pair:
            return G, pair[0], pair[1]
        # else retry with new random positions


# -----------------------
# Find a src/dst pair whose shortest path has >= min_length nodes
# -----------------------
def find_long_path_pair(G, min_length=4):
    nodes = list(G.nodes())
    random.shuffle(nodes)
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            s, d = nodes[i], nodes[j]
            try:
                path = nx.dijkstra_path(G, s, d)
                if len(path) >= min_length:
                    return s, d
            except:
                continue
    return None


# -----------------------
# Routing (skip failed nodes)
# -----------------------
def get_path(G, src, dst):
    G_copy = G.copy()
    for node in list(G_copy.nodes()):
        if G_copy.nodes[node]['failed']:
            G_copy.remove_node(node)
    try:
        return nx.dijkstra_path(G_copy, src, dst)
    except:
        return None


# -----------------------
# Fail a node strictly ON the current path (never src or dst)
# -----------------------
def fail_node_on_path(G, path):
    if not path or len(path) < 3:
        print("[!] Path too short to fail an intermediate node.")
        return None

    candidates = [n for n in path[1:-1] if not G.nodes[n]['failed']]

    if not candidates:
        print("[!] All intermediate nodes on the path are already failed.")
        return None

    node = random.choice(candidates)
    G.nodes[node]['failed'] = True
    return node


# -----------------------
# Fix all nodes
# -----------------------
def fix_nodes(G):
    for n in G.nodes():
        G.nodes[n]['failed'] = False


# -----------------------
# Find nearest node to click
# -----------------------
def find_nearest_node(G, click_x, click_y, threshold=5):
    pos = nx.get_node_attributes(G, 'pos')
    nearest, min_dist = None, float('inf')
    for node, (x, y) in pos.items():
        d = math.sqrt((x - click_x) ** 2 + (y - click_y) ** 2)
        if d < min_dist:
            min_dist = d
            nearest = node
    return nearest if min_dist <= threshold else None


# -----------------------
# Draw
# -----------------------
def draw(G, path=None, selected=None):
    plt.clf()
    pos = nx.get_node_attributes(G, 'pos')

    colors = []
    for n in G.nodes():
        if G.nodes[n]['failed']:
            colors.append('red')
        elif selected and n in selected:
            colors.append('orange')
        elif path and n == path[0]:
            colors.append('lime')       # SRC = green
        elif path and n == path[-1]:
            colors.append('gold')       # DST = yellow
        elif path and n in path:
            colors.append('deepskyblue') # on-path nodes
        else:
            colors.append('lightgray')  # off-path nodes

    nx.draw(G, pos, node_color=colors, with_labels=True, node_size=700,
            font_weight='bold')

    if path:
        edges = list(zip(path, path[1:]))
        nx.draw_networkx_edges(G, pos, edgelist=edges,
                               edge_color='green', width=4)

    node_count = len(path) if path else 0
    status = f"Path length: {node_count} nodes  |  " if path else "No active path  |  "
    status += "Green=SRC  Gold=DST  Blue=On-path  Gray=Off-path  Red=Failed"
    plt.title(status, fontsize=9)
    plt.draw()
    plt.pause(0.1)


# -----------------------
# Click handler
# -----------------------
def on_click(event):
    global src, dst, current_path, selected_nodes

    if event.inaxes is None:
        return

    clicked = find_nearest_node(G, event.xdata, event.ydata)
    if clicked is None:
        return

    selected_nodes.append(clicked)

    if len(selected_nodes) == 1:
        print(f"\n[CLICK] SRC = Node {clicked}. Now click DESTINATION node.")
        draw(G, current_path, selected_nodes)

    elif len(selected_nodes) == 2:
        s, d = selected_nodes[0], selected_nodes[1]
        selected_nodes = []

        if s == d:
            print("[!] Same node clicked twice. Pick again.")
            draw(G, current_path)
            return

        path = get_path(G, s, d)
        if not path or len(path) < 4:
            print(f"[!] Path between {s} and {d} has only {len(path) if path else 0} nodes. Pick a farther pair.")
            draw(G, current_path)
            return

        src, dst, current_path = s, d, path
        print(f"[CLICK] SRC={src}  DST={dst}  Path ({len(path)} nodes): {path}")
        draw(G, current_path)


# -----------------------
# Auto-reroute
# -----------------------
def reroute_if_needed(G, src, dst, current_path):
    if not current_path:
        return get_path(G, src, dst)

    if any(G.nodes[n]['failed'] for n in current_path):
        print("[REROUTE] Failure detected on active path — searching alternate route...")
        new_path = get_path(G, src, dst)
        if new_path:
            print(f"[REROUTE] Alternate path ({len(new_path)} nodes): {new_path}")
        else:
            print("[REROUTE] No alternate path available! Network is partitioned.")
        return new_path

    return current_path


# -----------------------
# MAIN
# -----------------------
print("Building network with a guaranteed 4+ node path...")
G, src, dst = create_network(n=12, range_val=55)

current_path = get_path(G, src, dst)
original_path = current_path[:]
print(f"Ready!  SRC={src}  DST={dst}")
print(f"Original path ({len(current_path)} nodes): {current_path}")
print("Tip: You can also click two nodes on the plot to pick your own SRC/DST.\n")

fig = plt.gcf()
fig.canvas.mpl_connect('button_press_event', on_click)
draw(G, current_path)

while True:
    print("\n1. Show Network")
    print("2. Fail a node on the current path")
    print("3. Reroute (find alternate path)")
    print("4. Fix all nodes")
    print("5. Exit")

    choice = input("Enter choice: ").strip()

    if choice == "1":
        if current_path:
            print(f"Active path ({len(current_path)} nodes): {current_path}")
        else:
            print("[!] No active path.")
        draw(G, current_path)

    elif choice == "2":
        if not current_path:
            current_path = get_path(G, src, dst)

        if not current_path:
            print("[!] No active path exists.")
        else:
            node = fail_node_on_path(G, current_path)
            if node is not None:
                print(f"[FAILED NODE]: {node}")
                print(f"Path broken: {current_path}")
                print("Press 3 to reroute.")
                draw(G, current_path)

    elif choice == "3":
        failed_on_path = any(G.nodes[n]['failed'] for n in (current_path or []))
        if not failed_on_path:
            print("[!] No failure on current path. Use option 2 first to fail a node.")
            draw(G, current_path)
        else:
            old_path = current_path[:]
            current_path = get_path(G, src, dst)
            if current_path:
                print(f"[REROUTE] Old path : {old_path}")
                print(f"[REROUTE] New path : {current_path}")
            else:
                print("[REROUTE] No alternate path available! Network is partitioned.")
            draw(G, current_path)

    elif choice == "4":
        fix_nodes(G)
        print("\n[NODE FIXED] Failed node is back online (turns blue).")
        print(f"Original path was : {original_path}")
        print(f"Still using       : {current_path}  <-- rerouted path, NOT reverted")
        draw(G, current_path)

    elif choice == "5":
        break

plt.ioff()
plt.show()