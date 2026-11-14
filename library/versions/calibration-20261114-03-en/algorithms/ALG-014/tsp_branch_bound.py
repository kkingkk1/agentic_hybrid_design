"""以出边下界剪枝的精确 TSP 深度优先分支定界。"""

from fractions import Fraction
from math import isfinite


def tsp_branch_bound(distances, start=0):
    """返回最短闭合回路及代价；适用于有限非负有向完全图。"""
    n = len(distances)
    if not n or any(len(row) != n for row in distances):
        raise ValueError("距离须为非空方阵")
    if isinstance(start, bool) or not isinstance(start, int) or not 0 <= start < n:
        raise ValueError("起点无效")
    d = []
    for row in distances:
        converted = []
        for x in row:
            if isinstance(x, bool) or not isinstance(x, (int, float)) or x < 0 or (isinstance(x, float) and not isfinite(x)):
                raise ValueError("边权须为有限非负数")
            converted.append(Fraction(x))
        d.append(converted)
    if n == 1:
        return Fraction(0), [start, start]
    best, best_path = None, None

    def search(path, remaining, cost):
        nonlocal best, best_path
        last = path[-1]
        if not remaining:
            total = cost + d[last][start]
            if best is None or total < best:
                best, best_path = total, [*path, start]
            return
        bound = cost + min(d[last][v] for v in remaining)
        for u in remaining:
            bound += min(d[u][v] for v in [*remaining, start] if v != u)
        if best is not None and bound >= best:
            return
        for v in sorted(remaining, key=lambda x: (d[last][x], x)):
            search([*path, v], remaining - {v}, cost + d[last][v])

    search([start], set(range(n)) - {start}, Fraction(0))
    return best, best_path
