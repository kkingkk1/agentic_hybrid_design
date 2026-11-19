"""Apply record-based acceptance to capacity-feasible route moves."""

from random import Random

from record_travel import record_travel
from relocate import relocations, solution_length
from savings import savings_routes
from two_opt_star import tail_exchanges


def solve(distance, demands, capacity, seed=0, rounds=20):
    first = savings_routes(distance, demands, capacity)

    def cost(routes):
        return solution_length(distance, routes)

    def propose(routes, rng):
        left = (trial for trial, _ in relocations(demands, capacity, routes))
        right = tail_exchanges(demands, capacity, routes)
        neighborhoods = (left, right) if rng.random() < 0.5 else (right, left)
        for moves in neighborhoods:
            candidate = None
            for count, trial in enumerate(moves, 1):
                if rng.randrange(count) == 0:
                    candidate = trial
            if candidate is not None:
                return candidate
        return None

    return record_travel(first, propose, cost, rounds, 0.05 * cost(first), Random(seed))
