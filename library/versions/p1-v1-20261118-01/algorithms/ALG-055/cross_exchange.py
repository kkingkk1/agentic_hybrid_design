"""Exchange two bounded contiguous customer chains across CVRP routes."""


def cross_exchange(distance, demands, capacity, routes, max_block=2):
    """Choose one best capacity-feasible, strictly improving exchange."""
    if max_block < 1:
        raise ValueError("max_block must be positive")

    def length(route):
        closed = [0, *route, 0]
        return sum(distance[a][b] for a, b in zip(closed, closed[1:]))

    routes = [list(route) for route in routes]
    loads = [sum(demands[v] for v in route) for route in routes]
    lengths = [length(route) for route in routes]
    best = routes
    best_delta = 0
    for i, left in enumerate(routes):
        for j in range(i + 1, len(routes)):
            right = routes[j]
            for start_a in range(len(left)):
                for end_a in range(start_a + 1, min(len(left), start_a + max_block) + 1):
                    chain_a = left[start_a:end_a]
                    load_a = sum(demands[v] for v in chain_a)
                    for start_b in range(len(right)):
                        for end_b in range(start_b + 1, min(len(right), start_b + max_block) + 1):
                            chain_b = right[start_b:end_b]
                            load_b = sum(demands[v] for v in chain_b)
                            if max(loads[i] - load_a + load_b, loads[j] - load_b + load_a) > capacity:
                                continue
                            a = left[:start_a] + chain_b + left[end_a:]
                            b = right[:start_b] + chain_a + right[end_b:]
                            delta = length(a) + length(b) - lengths[i] - lengths[j]
                            if delta < best_delta:
                                best = [route[:] for route in routes]
                                best[i], best[j] = a, b
                                best_delta = delta
    return best
