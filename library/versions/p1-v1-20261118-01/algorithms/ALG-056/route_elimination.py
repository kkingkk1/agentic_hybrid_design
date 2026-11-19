"""Try to eliminate a complete route using a caller-supplied feasible repair."""


def drop_route(distance, routes, rebuild):
    """Return the shortest one-fewer-route repair, or None on failure."""
    baseline = [list(route) for route in routes]
    best = None
    best_value = float("inf")
    for index, removed in enumerate(baseline):
        retained = [route[:] for j, route in enumerate(baseline) if j != index]
        trial = rebuild(retained, list(removed))
        if trial is None or len(trial) != len(baseline) - 1:
            continue
        value = 0
        for route in trial:
            closed = [0, *route, 0]
            value += sum(distance[a][b] for a, b in zip(closed, closed[1:]))
        if value < best_value:
            best, best_value = [list(route) for route in trial], value
    return best
