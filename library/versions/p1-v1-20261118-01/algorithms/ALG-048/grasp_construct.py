"""Cost-threshold restricted candidate list for TSP construction."""


def grasp_tour(distance, rng, alpha=0.25, start=0):
    """Sample an eligible outgoing edge at each step and return an open tour."""
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be in [0, 1]")
    if not distance:
        return []
    if not 0 <= start < len(distance):
        raise ValueError("start is outside the instance")
    order = [start]
    remaining = set(range(len(distance))) - {start}
    while remaining:
        row = distance[order[-1]]
        low = min(row[v] for v in remaining)
        high = max(row[v] for v in remaining)
        limit = low + alpha * (high - low)
        eligible = sorted(v for v in remaining if row[v] <= limit)
        selected = rng.choice(eligible)
        order.append(selected)
        remaining.remove(selected)
    return order
