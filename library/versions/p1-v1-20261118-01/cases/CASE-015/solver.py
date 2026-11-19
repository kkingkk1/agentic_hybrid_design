"""Build a directional cycle cover and patch it into one TSP tour."""

from cycle_patching import patch_cycles
from hungarian import hungarian


def solve(distance):
    size = len(distance)
    if size < 2:
        return list(range(size))
    limit = (size + 1) * max(1, max(max(row) for row in distance))
    matrix = [
        [limit if a == b else distance[a][b] for b in range(size)]
        for a in range(size)
    ]
    _, successor = hungarian(matrix)
    return patch_cycles(distance, successor)
