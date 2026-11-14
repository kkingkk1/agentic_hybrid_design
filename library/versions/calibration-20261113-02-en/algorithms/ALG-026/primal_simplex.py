"""原点可行的线性规划原始单纯形法。"""

from fractions import Fraction
from math import isfinite


def _number(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or (isinstance(x, float) and not isfinite(x)):
        raise ValueError("系数须为有限数值")
    return Fraction(x)


def primal_simplex(matrix, rhs, objective):
    """求 max c*x，A*x<=b，x>=0，要求 b>=0；返回状态、目标和解。"""
    m, n = len(rhs), len(objective)
    if len(matrix) != m or any(len(row) != n for row in matrix):
        raise ValueError("系数维度不一致")
    b, c = list(map(_number, rhs)), list(map(_number, objective))
    if any(x < 0 for x in b):
        raise ValueError("本实现要求原点可行，即 b 非负")
    rows = [[*map(_number, row), *(Fraction(int(i == j)) for j in range(m)), b[i]]
            for i, row in enumerate(matrix)]
    rows.append([-x for x in c] + [Fraction(0)] * (m + 1))
    basic = [n + i for i in range(m)]
    while True:
        entering = next((j for j in range(n + m) if rows[-1][j] < 0), None)
        if entering is None:
            solution = [Fraction(0)] * n
            for i, variable in enumerate(basic):
                if variable < n:
                    solution[variable] = rows[i][-1]
            return "optimal", rows[-1][-1], solution
        candidates = [(rows[i][-1] / rows[i][entering], basic[i], i)
                      for i in range(m) if rows[i][entering] > 0]
        if not candidates:
            return "unbounded", None, None
        _, _, leaving = min(candidates)
        pivot = rows[leaving][entering]
        rows[leaving] = [x / pivot for x in rows[leaving]]
        for i in range(m + 1):
            if i != leaving:
                factor = rows[i][entering]
                rows[i] = [a - factor * b for a, b in zip(rows[i], rows[leaving])]
        basic[leaving] = entering
