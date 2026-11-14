"""矩形完全二分分配的最小费用 Hungarian 算法。"""

from fractions import Fraction
from math import isfinite


def _number(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or (isinstance(x, float) and not isfinite(x)):
        raise ValueError("费用须为有限数值")
    return Fraction(x)


def hungarian(costs):
    """每行分配一个不同列；要求行数不大于列数，返回费用和列下标。"""
    n = len(costs)
    if n == 0:
        return Fraction(0), []
    cols = len(costs[0])
    if cols < n or any(len(row) != cols for row in costs):
        raise ValueError("费用矩阵须为行数不大于列数的矩形矩阵")
    a = [[_number(x) for x in row] for row in costs]
    u, v = [Fraction(0)] * (n + 1), [Fraction(0)] * (cols + 1)
    p, way = [0] * (cols + 1), [0] * (cols + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minimum, used = [None] * (cols + 1), [False] * (cols + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], None, None
            for j in range(1, cols + 1):
                if not used[j]:
                    value = a[i0 - 1][j - 1] - u[i0] - v[j]
                    if minimum[j] is None or value < minimum[j]:
                        minimum[j], way[j] = value, j0
                    if delta is None or minimum[j] < delta:
                        delta, j1 = minimum[j], j
            for j in range(cols + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                elif j and minimum[j] is not None:
                    minimum[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    assigned = [None] * n
    for j in range(1, cols + 1):
        if p[j]:
            assigned[p[j] - 1] = j - 1
    return sum((a[i][assigned[i]] for i in range(n)), Fraction(0)), assigned
