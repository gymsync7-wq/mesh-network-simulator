from topology import create_nodes, connect_nodes, fail_node_in_path
from routing import find_shortest_path
from visualization import draw_network
import random

G = create_nodes(15)
G = connect_nodes(G, 80)

source = random.randint(0,14)
destination = random.randint(0,14)

while source == destination:
    destination = random.randint(0,14)

print("Source:", source)
print("Destination:", destination)

# Initial path
path = find_shortest_path(G, source, destination)
print("\nInitial Path:", path)

# Fail node
failed_node = fail_node_in_path(G, path, source, destination)
print("\n[!] FAILED NODE:", failed_node)

# New path
new_path = find_shortest_path(G, source, destination)
print("[->] NEW PATH:", new_path)

# Show graph
draw_network(G, new_path)