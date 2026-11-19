"""Reduce fleet size through complete route removal before distance improvement."""

from greedy_insertion import greedy_insert
from relocate import solution_length
from route_elimination import drop_route
from savings import savings_routes
from two_opt_star import two_opt_star


def solve(distance, demands, capacity):
    incumbent = savings_routes(distance, demands, capacity)

    def rebuild(routes, unserved):
        unserved.sort(key=lambda vertex: (-demands[vertex], vertex))
        return greedy_insert(distance, demands, capacity, routes, unserved, existing_only=True)

    while len(incumbent) > 1:
        candidate = drop_route(distance, incumbent, rebuild)
        if candidate is None:
            break
        incumbent = candidate
    polished = two_opt_star(distance, demands, capacity, incumbent)
    polished_score = len(polished), solution_length(distance, polished)
    incumbent_score = len(incumbent), solution_length(distance, incumbent)
    if polished_score < incumbent_score:
        return polished
    return incumbent
