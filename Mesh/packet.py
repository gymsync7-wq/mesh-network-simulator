import time
from routing import find_shortest_path
from topology import fail_node_in_path

def send_packet_with_failure(G, source, destination):

    path = find_shortest_path(G, source, destination)

    if path is None:
        print("No route available")
        return

    print("\nInitial Path:", path)

    i = 0
    failure_triggered = False

    while i < len(path) - 1:

        current = path[i]
        next_node = path[i + 1]

        print(f"Packet: {current} -> {next_node}")
        time.sleep(1)

        # Trigger failure once (midway)
        if not failure_triggered and len(path) > 3:

            failed_node = fail_node_in_path(
                G,
                path,
                exclude_nodes=[source, destination]
            )

            print("\n⚠ Node Failed:", failed_node)

            # Recalculate route
            new_path = find_shortest_path(G, current, destination)

            if new_path is None:
                print("No alternate path. Packet lost.")
                return

            print("🔁 New Path:", new_path)

            path = new_path
            i = 0
            failure_triggered = True
            continue

        i += 1

    print("\n✅ Packet Delivered Successfully\n")

    print("Simulation running...")