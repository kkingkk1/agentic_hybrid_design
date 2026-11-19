"""Use tabu-controlled relocations and intensify after a new record."""

from relocate import relocations, solution_length
from savings import savings_routes
from tabu_memory import TabuMemory
from two_opt_star import two_opt_star


def solve(distance, demands, capacity, rounds=16, tenure=3):
    current = best = savings_routes(distance, demands, capacity)
    best_value = solution_length(distance, best)
    memory = TabuMemory(tenure)
    for step in range(rounds):
        choice = None
        for trial, vertex in relocations(demands, capacity, current):
            value = solution_length(distance, trial)
            if memory.permits(vertex, step, value, best_value):
                if choice is None or (value, vertex) < choice[:2]:
                    choice = value, vertex, trial
        if choice is None:
            break
        value, vertex, current = choice
        memory.forbid(vertex, step)
        if value < best_value:
            improved = two_opt_star(distance, demands, capacity, current)
            improved_value = solution_length(distance, improved)
            if improved_value < value:
                current, value = improved, improved_value
            best, best_value = current, value
    return best
