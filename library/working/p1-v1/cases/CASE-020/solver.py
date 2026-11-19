"""Use exact fixed-boundary reorderings to improve a greedy fragment tour."""

from fixed_path import fixed_path
from multifragment import multifragment_tour


def solve(distance, window=5, passes=2):
    if not 2 <= window <= 8:
        raise ValueError("window must be between 2 and 8")
    tour = multifragment_tour(distance)
    size = len(tour)
    if size < 4:
        return tour
    width = min(window, size - 2)

    def length(before, block, after):
        segment = [before, *block, after]
        return sum(distance[a][b] for a, b in zip(segment, segment[1:]))

    for _ in range(passes):
        changed = False
        for start in range(1, size - width):
            end = start + width
            before, after = tour[start - 1], tour[end]
            block = tour[start:end]
            better = fixed_path(distance, block, before, after)
            if length(before, better, after) < length(before, block, after):
                tour[start:end] = better
                changed = True
        if not changed:
            break
    return tour
