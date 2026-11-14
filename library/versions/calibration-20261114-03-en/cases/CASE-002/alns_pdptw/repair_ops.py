# -*- coding: utf-8 -*-
"""
修复算子集合。
每个算子把若干被移除的订单重新插回解中，返回是否全部插入成功。
"""

import random
import numpy as np
from insertion import best_insertion, best_insertion_in_route


def repair_greedy(data, solution, removed_orders, rng):
    """
    贪心插入算子。
    按顺序逐个把订单插入到当前最优位置。
    """
    # 按时间窗截止时间升序
    removed_sorted = sorted(
        removed_orders,
        key=lambda oid: data.tw_end[data.order_delivery(oid)]
    )

    # 逐个尝试插入
    for oid in removed_sorted:
        pu = data.order_pickup(oid)
        de = data.order_delivery(oid)
        delta, r_idx, new_route = best_insertion(data, solution, pu, de)
        if new_route is None:
            return False   # 插不进去，修复失败
        if r_idx == -1:
            solution.routes.append(new_route)
        else:
            solution.routes[r_idx] = new_route

    return True


def repair_regret(data, solution, removed_orders, rng):
    """
    后悔插入算子。
    每次选择“次优插入成本 - 最优插入成本”差值最大的订单先插入。
    思想：让“选择余地小”的订单先占位。
    """
    pending = list(removed_orders)
    # 最多尝试 len(pending) 轮
    for _ in range(len(pending)):
        if not pending:
            break

        # 计算每个订单在所有路径上的最优 + 次优增量
        best_choice = None
        best_regret = -1.0

        for oid in pending:
            pu = data.order_pickup(oid)
            de = data.order_delivery(oid)

            deltas = []
            # 尝试所有现有路径
            for r_idx, route in enumerate(solution.routes):
                d, new_route = best_insertion_in_route(data, route, pu, de)
                if new_route is not None:
                    deltas.append((d, r_idx, new_route))
            # 尝试新建路径
            from feasibility import check_route
            from config import VEHICLE_FIXED_COST
            new_route_new = [0, pu, de, 0]
            ok, cost, _ = check_route(data, new_route_new)
            if ok:
                deltas.append((cost + VEHICLE_FIXED_COST, -1, new_route_new))

            # 排序取最优和次优
            deltas.sort(key=lambda x: x[0])
            if len(deltas) == 0:
                # 完全无法插入，直接退出
                return False
            if len(deltas) == 1:
                regret = float('inf')  # 只有一种选择，优先插
            else:
                regret = deltas[1][0] - deltas[0][0]

            # 记录后悔值最大的订单
            if regret > best_regret:
                best_regret = regret
                best_choice = (oid, deltas[0])

        # 插入后悔值最大的订单
        oid, (delta, r_idx, new_route) = best_choice
        if r_idx == -1:
            solution.routes.append(new_route)
        else:
            solution.routes[r_idx] = new_route
        pending.remove(oid)

    return True


def repair_noise(data, solution, removed_orders, rng, noise_factor=0.1):
    """
    带噪声的贪心插入。
    在增量成本上加入随机扰动，避免陷入固定模式。
    """
    removed_sorted = sorted(
        removed_orders,
        key=lambda oid: data.tw_end[data.order_delivery(oid)]
    )

    for oid in removed_sorted:
        pu = data.order_pickup(oid)
        de = data.order_delivery(oid)

        # 遍历所有路径，收集带噪声的候选
        candidates = []
        for r_idx, route in enumerate(solution.routes):
            delta, new_route = best_insertion_in_route(data, route, pu, de)
            if new_route is not None:
                noise = rng.uniform(-noise_factor, noise_factor) * abs(delta + 1)
                candidates.append((delta + noise, r_idx, new_route))

        # 新建路径也加入候选
        from feasibility import check_route
        from config import VEHICLE_FIXED_COST
        new_route_new = [0, pu, de, 0]
        ok, cost, _ = check_route(data, new_route_new)
        if ok:
            noise = rng.uniform(-noise_factor, noise_factor) * (cost + 1)
            candidates.append((cost + VEHICLE_FIXED_COST + noise, -1, new_route_new))

        if not candidates:
            return False

        # 选带噪声后成本最小的
        candidates.sort(key=lambda x: x[0])
        _, r_idx, new_route = candidates[0]
        if r_idx == -1:
            solution.routes.append(new_route)
        else:
            solution.routes[r_idx] = new_route

    return True


# 修复算子注册表
REPAIR_OPS = {
    "greedy": repair_greedy,
    "regret": repair_regret,
    "noise": repair_noise,
}