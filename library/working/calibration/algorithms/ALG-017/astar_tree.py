"""非负边权图的 A* 路径树搜索。"""

from fractions import Fraction
from heapq import heappop, heappush
from itertools import count
from math import isfinite


def _number(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x < 0 or (isinstance(x, float) and not isfinite(x)):
        raise ValueError("边权与启发值必须是有限非负数")
    return Fraction(x)


def astar_tree(graph, start, goal, heuristic):
    """返回代价和路径；调用方须提供可采纳启发函数且终点启发值为零。"""
    if _number(heuristic(goal)) != 0:
        raise ValueError("终点启发值必须为零")
    counter = count()
    frontier = [(_number(heuristic(start)), next(counter), Fraction(0), (start,))]
    while frontier:
        _, _, cost, path = heappop(frontier)
        node = path[-1]
        if node == goal:
            return cost, list(path)
        for nxt, weight in graph.get(node, ()):
            w = _number(weight)
            if nxt not in path:
                g = cost + w
                heappush(frontier, (g + _number(heuristic(nxt)), next(counter), g, (*path, nxt)))
    return None
