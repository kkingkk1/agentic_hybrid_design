"""CVRP 两条路线之间的最佳 SWAP* 移动。"""

from fractions import Fraction
from heapq import nsmallest
from math import isfinite
from typing import Sequence


def _number(value: int | float) -> int | Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("距离、需求、容量和罚系数必须是数值")
    if value < 0 or (isinstance(value, float) and not isfinite(value)):
        raise ValueError("距离、需求、容量和罚系数必须是有限非负数")
    return Fraction(value) if isinstance(value, float) else value


def swap_star_pair(
    route_a: Sequence[int],
    route_b: Sequence[int],
    distances: Sequence[Sequence[int | float]],
    demands: Sequence[int | float],
    capacity: int | float,
    penalty_capacity: int | float | None = None,
) -> tuple[list[int], list[int], int | float] | None:
    """返回两条新路线及负的目标变化；不存在严格改善时返回 None。

    路线仅列客户，仓库节点为 0。每条路线移除一个客户，再把对方客户
    插入其最佳位置。默认检查硬容量；给出非负罚系数时以距离加容量
    超限罚项评价，输出可能超容量。本函数只搜索给定路线对，不筛选
    路线，也不检查时长、时间窗等其他约束。输入对象不被修改。
    """
    n = len(distances)
    if n == 0 or len(demands) != n or any(len(row) != n for row in distances):
        raise ValueError("需要含仓库的方阵及对应需求")
    a, b = list(route_a), list(route_b)
    customers = a + b
    if any(isinstance(v, bool) or not isinstance(v, int) or not 0 < v < n for v in customers):
        raise ValueError("路线必须使用矩阵中的非仓库客户编号")
    if len(set(customers)) != len(customers):
        raise ValueError("客户不能在路线中重复")
    matrix = [[_number(value) for value in row] for row in distances]
    demand = [_number(value) for value in demands]
    cap = _number(capacity)
    penalty = None if penalty_capacity is None else _number(penalty_capacity)
    if matrix[0][0] != 0 or demand[0] != 0:
        raise ValueError("仓库自距离和需求必须为零")
    load_a = sum(demand[v] for v in a)
    load_b = sum(demand[v] for v in b)
    if penalty is None and (load_a > cap or load_b > cap):
        raise ValueError("硬容量模式要求输入路线可行")
    if not a or not b:
        return None

    def edge(route, index):
        return (0 if index == 0 else route[index - 1],
                0 if index == len(route) else route[index])

    def insert_cost(customer, left, right):
        return matrix[left][customer] + matrix[customer][right] - matrix[left][right]

    def top_three(incoming, route):
        return {
            v: nsmallest(3, ((insert_cost(v, *edge(route, i)), i)
                             for i in range(len(route) + 1)))
            for v in incoming
        }

    def remove_cost(route, index):
        left = 0 if index == 0 else route[index - 1]
        right = 0 if index == len(route) - 1 else route[index + 1]
        v = route[index]
        return matrix[left][right] - matrix[left][v] - matrix[v][right]

    def best_after_removal(customer, route, removed, candidates):
        left = 0 if removed == 0 else route[removed - 1]
        right = 0 if removed == len(route) - 1 else route[removed + 1]
        options = [(insert_cost(customer, left, right), removed)]
        for delta, index in candidates:
            if index in (removed, removed + 1):
                continue
            options.append((delta, index if index < removed else index - 1))
        return min(options)

    insert_into_a = top_three(b, a)
    insert_into_b = top_three(a, b)
    old_excess = max(load_a - cap, 0) + max(load_b - cap, 0)
    best_delta: int | Fraction = 0
    best_move = None
    for ia, u in enumerate(a):
        for ib, v in enumerate(b):
            next_a = load_a - demand[u] + demand[v]
            next_b = load_b - demand[v] + demand[u]
            if penalty is None and (next_a > cap or next_b > cap):
                continue
            ins_a, pos_a = best_after_removal(v, a, ia, insert_into_a[v])
            ins_b, pos_b = best_after_removal(u, b, ib, insert_into_b[u])
            delta = remove_cost(a, ia) + ins_a + remove_cost(b, ib) + ins_b
            if penalty is not None:
                new_excess = max(next_a - cap, 0) + max(next_b - cap, 0)
                delta += penalty * (new_excess - old_excess)
            if delta < best_delta:
                best_delta = delta
                best_move = (ia, ib, pos_a, pos_b)

    if best_move is None:
        return None
    ia, ib, pos_a, pos_b = best_move
    new_a, new_b = a[:], b[:]
    u, v = new_a.pop(ia), new_b.pop(ib)
    new_a.insert(pos_a, v)
    new_b.insert(pos_b, u)
    values = [capacity, *demands, *(x for row in distances for x in row)]
    if penalty_capacity is not None:
        values.append(penalty_capacity)
    change = float(best_delta) if any(isinstance(x, float) for x in values) else best_delta
    return new_a, new_b, change
