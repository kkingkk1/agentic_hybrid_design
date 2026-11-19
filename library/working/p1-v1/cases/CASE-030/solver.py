"""Adapt destroy and repair choices from outcomes of feasible CVRP trials."""

from random import Random

from adaptive_operators import choose_operator, score_outcome, update_weights
from annealing_acceptance import annealing_accept
from greedy_insertion import best_insertion, greedy_insert
from random_removal import uniform_remove
from regret_k import regret_k_insert
from relocate import solution_length
from savings import savings_routes
from shaw_removal import shaw_removal


def solve(distance, demands, capacity, seed=0, rounds=16):
    rng = Random(seed)
    current = best = savings_routes(distance, demands, capacity)
    current_value = best_value = solution_length(distance, current)
    customers = {v: v for v in range(1, len(distance))}
    if not customers:
        return best
    count = min(3, len(customers))
    weights = [[1.0, 1.0], [1.0, 1.0]]
    scores = [[0, 0], [0, 0]]
    uses = [[0, 0], [0, 0]]
    temperature = max(1.0, current_value / len(customers))
    seen = {tuple(tuple(route) for route in current)}

    def insertion(route, vertex):
        return best_insertion(distance, demands, capacity, route, vertex)

    for step in range(rounds):
        destroy, repair = [choose_operator(options, rng) for options in weights]
        if destroy == 0:
            partial, removed = uniform_remove(current, count, rng)
        else:
            partial, removed = shaw_removal(
                current, customers, count, 4, lambda a, b: distance[a][b], rng
            )
        if repair == 1:
            partial, removed = regret_k_insert(partial, removed, 2, insertion)
        trial = greedy_insert(distance, demands, capacity, partial, removed)
        value = solution_length(distance, trial)
        accepted = annealing_accept(current_value, value, temperature, rng)
        key = tuple(tuple(route) for route in trial)
        reward = score_outcome(value, current_value, best_value, accepted, key in seen, [5, 2, 1])
        for group, index in enumerate((destroy, repair)):
            scores[group][index] += reward
            uses[group][index] += 1
        if accepted:
            current, current_value = trial, value
            seen.add(key)
            if value < best_value:
                best, best_value = trial, value
        if (step + 1) % 4 == 0:
            weights = [update_weights(w, s, n, 0.25) for w, s, n in zip(weights, scores, uses)]
            scores = [[0, 0], [0, 0]]
            uses = [[0, 0], [0, 0]]
            temperature = max(1e-12, temperature * 0.8)
    return best
