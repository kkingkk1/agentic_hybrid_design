"""Recombine permutation tours and select offspring after local search."""

from random import Random

from edge_recombination import edge_recombine
from farthest_insertion import farthest_insertion
from nearest_tour import nearest_tour
from pmx import pmx
from three_opt import three_opt
from two_opt import two_opt


def solve(distance, seed=0, rounds=12):
    rng = Random(seed)
    size = len(distance)
    if size < 3:
        return list(range(size))

    def polish(tour):
        _, local = two_opt(tour, distance)
        return two_opt(three_opt(distance, local), distance)

    starters = [nearest_tour(distance), farthest_insertion(distance)]
    starters.extend(rng.sample(range(size), size) for _ in range(4))
    population = sorted(polish(tour) for tour in starters)
    for step in range(rounds):
        first, second = rng.sample(population, 2)
        if step % 2:
            lo, hi = sorted(rng.sample(range(size + 1), 2))
            child = pmx(first[1], second[1], lo, hi)
        else:
            child = edge_recombine(first[1], second[1], rng)
        candidate = polish(child)
        if candidate[0] < population[-1][0]:
            population[-1] = candidate
            population.sort()
    return population[0][1]
