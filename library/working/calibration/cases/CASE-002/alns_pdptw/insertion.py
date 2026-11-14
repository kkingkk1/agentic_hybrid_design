# -*- coding: utf-8 -*-
"""
插入启发式。
把订单（取货点 + 送货点）插入到现有路径中的最优位置。
"""

import numpy as np
from feasibility import check_route
from config import VEHICLE_FIXED_COST


def best_insertion_in_route(data, route, pu, de):
    """
    在指定路径中寻找最优插入位置。

    做法：
        尝试所有 (i, j) 组合，把 pu 插到位置 i，de 插到位置 j，且 i <= j。
        返回 (增量成本, 新路径)，如果不可行则返回 (inf, None)。

    参数：
        route: 当前路径节点序列，形如 [0, 5, 105, 0]
        pu   : 取货节点
        de   : 送货节点
    """
    best_delta = float('inf')
    best_route = None

    # 原路径行驶距离
    _, orig_cost, _ = check_route(data, route)

    # 枚举所有插入位置（i、j 为路径索引）
    for i in range(1, len(route)):
        for j in range(i, len(route)):
            # 构造新路径
            new_route = route[:i] + [pu] + route[i:j] + [de] + route[j:]
            # 可行性检查
            ok, new_cost, _ = check_route(data, new_route)
            if not ok:
                continue
            # 增量成本
            delta = new_cost - orig_cost
            if delta < best_delta:
                best_delta = delta
                best_route = new_route

    return best_delta, best_route


def best_insertion(data, solution, pu, de):
    """
    在解的所有路径中寻找最优插入位置。

    返回：
        (delta, r_idx, new_route)
        delta    : 插入的增量成本（如果新建路径，则为新路径成本 + 固定成本）
        r_idx    : 目标路径索引（-1 表示新建一条路径）
        new_route: 插入后的新路径
    """
    best_delta = float('inf')
    best_r_idx = -1
    best_route = None

    # 尝试插入现有路径
    for r_idx, route in enumerate(solution.routes):
        delta, new_route = best_insertion_in_route(data, route, pu, de)
        if new_route is not None and delta < best_delta:
            best_delta = delta
            best_r_idx = r_idx
            best_route = new_route

    # 尝试新建一条路径
    new_route = [0, pu, de, 0]
    ok, cost, _ = check_route(data, new_route)
    if ok:
        # 新路径的成本要加上车辆固定成本
        new_cost = cost + VEHICLE_FIXED_COST
        if new_cost < best_delta:
            best_delta = new_cost
            best_r_idx = -1
            best_route = new_route

    return best_delta, best_r_idx, best_route


def insert_order(data, solution, order_id):
    """
    把指定订单插入到解中。
    返回是否插入成功。
    """
    pu = data.order_pickup(order_id)
    de = data.order_delivery(order_id)

    delta, r_idx, new_route = best_insertion(data, solution, pu, de)
    if new_route is None:
        return False

    if r_idx == -1:
        # 新建路径
        solution.routes.append(new_route)
    else:
        # 替换原有路径
        solution.routes[r_idx] = new_route

    return True

def build_initial_solution(data):
    """构建初始解：按送货时间窗截止时间升序，逐个贪心插入。"""
    from solution import Solution
    from config import NUM_ORDERS

    solution = Solution([])

    # 按送货截止时间排序
    order_dl = []
    for oid in range(NUM_ORDERS):
        de = data.order_delivery(oid)
        order_dl.append((data.tw_end[de], oid))
    order_dl.sort()

    # 逐个插入
    for _, oid in order_dl:
        insert_order(data, solution, oid)

    solution.evaluate(data)
    return solution