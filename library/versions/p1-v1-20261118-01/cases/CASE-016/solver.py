"""Evolve random keys while ranking locally improved decoded tours."""

from random import Random

from random_keys import random_key_tour
from two_opt import two_opt


def solve(distance, seed=0, rounds=10):
    rng = Random(seed)
    size = len(distance)
    if size < 2:
        return list(range(size))

    def genotype():
        return tuple(rng.random() for _ in range(size))

    def decode(keys):
        cost, tour = two_opt(random_key_tour(keys), distance)
        return cost, keys, tour

    population = sorted(decode(genotype()) for _ in range(8))
    for _ in range(rounds):
        elites, others = population[:2], population[2:]
        next_population = elites[:]
        for _ in range(5):
            good = rng.choice(elites)[1]
            other = rng.choice(others)[1]
            keys = tuple(a if rng.random() < 0.7 else b for a, b in zip(good, other))
            next_population.append(decode(keys))
        next_population.append(decode(genotype()))
        population = sorted(next_population)
    return population[0][2]
