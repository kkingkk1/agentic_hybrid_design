"""Ant System tour construction, evaporation, and all-ant reinforcement."""


def ant_system(distance, steps, ants, rng, improve=None):
    """Return the lowest-cost tour seen, optionally improving each ant's tour."""
    if steps < 1 or ants < 1:
        raise ValueError("steps and ants must be positive")
    size = len(distance)
    if size <= 1:
        return list(range(size))
    trail = [[1.0] * size for _ in range(size)]

    def edges(tour):
        return zip(tour, tour[1:] + tour[:1])

    best = None
    best_cost = float("inf")
    for _ in range(steps):
        population = []
        for _ in range(ants):
            tour = [rng.randrange(size)]
            remaining = set(range(size)) - set(tour)
            while remaining:
                last = tour[-1]
                nodes = sorted(remaining)
                weights = [trail[last][node] / (1.0 + distance[last][node]) ** 2 for node in nodes]
                vertex = rng.choices(nodes, weights=weights, k=1)[0]
                tour.append(vertex)
                remaining.remove(vertex)
            if improve is not None:
                tour = list(improve(tour))
            value = sum(distance[a][b] for a, b in edges(tour))
            population.append((tour, value))
            if value < best_cost:
                best, best_cost = tour, value

        for row in trail:
            for vertex in range(size):
                row[vertex] = max(1e-12, 0.8 * row[vertex])
        for tour, value in population:
            deposit = 1.0 / (1.0 + value)
            for a, b in edges(tour):
                trail[a][b] += deposit
                trail[b][a] += deposit
    return best
