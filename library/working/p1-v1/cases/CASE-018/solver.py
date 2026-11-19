"""Use an elite GRASP tour as the target of a relinking path."""

from random import Random

from grasp_construct import grasp_tour
from path_relinking import path_relink
from two_opt import two_opt


def solve(distance, seed=0, rounds=12):
    rng = Random(seed)
    if rounds < 1:
        raise ValueError("rounds must be positive")

    def cost(tour):
        return sum(distance[a][b] for a, b in zip(tour, tour[1:] + tour[:1]))

    elite = {}
    for _ in range(rounds):
        value, tour = two_opt(grasp_tour(distance, rng), distance)
        elite_tours = list(elite)
        if elite_tours:
            guide = max(elite_tours, key=lambda target: sum(a != b for a, b in zip(target, tour)))
            candidate = min(path_relink(tour, guide), key=cost, default=tour)
            improved, linked = two_opt(candidate, distance)
            if improved < value:
                value, tour = improved, linked
        elite[tuple(tour)] = value
        elite = dict(sorted(elite.items(), key=lambda entry: (entry[1], entry[0]))[:4])
    return list(min(elite, key=elite.get))
