"""Clarke-Wright parallel savings for a single depot and symmetric costs."""


def savings_routes(distance, demands, capacity, customers=None):
    """Merge capacity-feasible route ends in descending positive savings order."""
    if customers is None:
        customers = list(range(1, len(distance)))
    else:
        customers = sorted(customers)
    if len(set(customers)) != len(customers):
        raise ValueError("customers must be distinct")
    if capacity < 0 or any(
        not 0 < v < len(distance) or not 0 <= demands[v] <= capacity for v in customers
    ):
        raise ValueError("customer cannot be served by a singleton route")

    owners = {v: v for v in customers}
    routes = {v: [v] for v in customers}
    loads = {v: demands[v] for v in customers}
    savings = sorted(
        (-(distance[0][a] + distance[0][b] - distance[a][b]), a, b)
        for index, a in enumerate(customers)
        for b in customers[index + 1:]
    )
    for negative_gain, a, b in savings:
        if negative_gain >= 0:
            break
        first, second = owners[a], owners[b]
        if first == second or loads[first] + loads[second] > capacity:
            continue
        left, right = routes[first], routes[second]
        if a not in (left[0], left[-1]) or b not in (right[0], right[-1]):
            continue
        if left[-1] != a:
            left.reverse()
        if right[0] != b:
            right.reverse()
        left.extend(right)
        for customer in right:
            owners[customer] = first
        loads[first] += loads.pop(second)
        del routes[second]
    return list(routes.values())
