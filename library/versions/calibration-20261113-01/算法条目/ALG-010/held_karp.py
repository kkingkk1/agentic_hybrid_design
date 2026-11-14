"""Held–Karp 子集动态规划：有向完全图 TSP。"""

from fractions import Fraction
from math import isfinite


def held_karp(distances, start=0):
    """返回最小回路代价及含首尾起点的顶点列表；不修改输入。"""
    n = len(distances)
    if not n or any(len(row) != n for row in distances):
        raise ValueError("距离须为非空方阵")
    if isinstance(start, bool) or not isinstance(start, int) or not 0 <= start < n:
        raise ValueError("起点下标无效")
    matrix = []
    for row in distances:
        converted = []
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or (isinstance(value, float) and not isfinite(value)):
                raise ValueError("边权须为有限数值")
            converted.append(Fraction(value))
        matrix.append(converted)
    if n == 1:
        return Fraction(0), [start, start]
    nodes = [i for i in range(n) if i != start]
    dp = {}
    for j, node in enumerate(nodes):
        dp[1 << j, j] = (matrix[start][node], None)
    for mask in range(1, 1 << len(nodes)):
        for j, node in enumerate(nodes):
            if not mask & (1 << j):
                continue
            previous = mask ^ (1 << j)
            if previous:
                candidates = ((dp[previous, k][0] + matrix[nodes[k]][node], k)
                              for k in range(len(nodes)) if previous & (1 << k))
                dp[mask, j] = min(candidates)
    mask = (1 << len(nodes)) - 1
    cost, last = min((dp[mask, j][0] + matrix[node][start], j)
                     for j, node in enumerate(nodes))
    reverse = []
    while mask:
        reverse.append(nodes[last])
        previous = dp[mask, last][1]
        mask ^= 1 << last
        last = previous
    return cost, [start, *reversed(reverse), start]
