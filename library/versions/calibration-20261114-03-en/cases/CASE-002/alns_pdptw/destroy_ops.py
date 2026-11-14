# -*- coding: utf-8 -*-
"""
破坏算子集合。
每个算子从当前解中移除若干订单，返回被移除的订单 ID 列表。
"""

import random
import numpy as np
from config import NUM_ORDERS

def destroy_random(data, solution, num_remove, rng):
    """
    随机移除算子。
    从解中随机挑选 num_remove 个订单移除。
    """
    # 收集解中所有订单 ID
    all_orders = []
    for route in solution.routes:
        for node in route:
            if node == 0:
                continue
            if node <= NUM_ORDERS:  # 取货节点
                all_orders.append(node - 1)

    # 如果订单数量不够，全部移除
    num_remove = min(num_remove, len(all_orders))
    # removed = rng.sample(all_orders, num_remove)
    removed = rng.choice(all_orders, size=num_remove, replace=False).tolist()

    # 逐个从解中移除
    for oid in removed:
        solution.remove_order(oid)

    return removed


def destroy_shaw(data, solution, num_remove, rng):
    """
    Shaw 相关移除算子。
    优先移除地理上或时间上相近的订单（它们往往可以互相替换）。
    """
    # 收集所有订单
    all_orders = []
    for route in solution.routes:
        for node in route:
            if node == 0:
                continue
            if node <= NUM_ORDERS:
                all_orders.append(node - 1)

    if not all_orders:
        return []

    num_remove = min(num_remove, len(all_orders))

    # 随机选种子订单
    seed = rng.choice(all_orders)
    seed_pu = data.order_pickup(seed)

    # 计算所有订单与种子订单的相关度
    # 相关度 = 取货点距离 + 0.5 * 送货点距离 + 0.3 * 时间窗距离
    scored = []
    for oid in all_orders:
        if oid == seed:
            continue
        pu = data.order_pickup(oid)
        de = data.order_delivery(oid)
        de_seed = data.order_delivery(seed)

        d_pu = data.dist[seed_pu][pu]
        d_de = data.dist[de_seed][de]
        d_tw = abs(data.tw_start[pu] - data.tw_start[seed_pu])
        score = d_pu + 0.5 * d_de + 0.3 * d_tw
        scored.append((score, oid))

    # 按相关度升序，取前 num_remove - 1 个 + 种子
    scored.sort()
    removed = [seed] + [oid for _, oid in scored[:num_remove - 1]]

    # 从解中移除
    for oid in removed:
        solution.remove_order(oid)

    return removed


def destroy_worst(data, solution, num_remove, rng):
    """
    最差移除算子。
    移除对总成本贡献最大的订单。
    """
    from feasibility import check_route

    # 计算每个订单的移除收益 = 原路径成本 - 移除后路径成本
    order_saving = []
    for r_idx, route in enumerate(solution.routes):
        _, orig_cost, _ = check_route(data, route)

        # 收集路径内的订单
        orders_in_route = []
        for node in route:
            if node == 0:
                continue
            if node <= NUM_ORDERS:
                orders_in_route.append(node - 1)

        # 逐个试移除
        for oid in orders_in_route:
            pu = data.order_pickup(oid)
            de = data.order_delivery(oid)
            new_route = [n for n in route if n != pu and n != de]
            if len(new_route) <= 2:
                # 移除后路径为空，收益为原成本
                saving = orig_cost
            else:
                ok, new_cost, _ = check_route(data, new_route)
                saving = orig_cost - new_cost if ok else 0.0
            order_saving.append((saving, oid))

    # 按收益降序，移除收益最大的
    order_saving.sort(reverse=True)
    num_remove = min(num_remove, len(order_saving))
    removed = [oid for _, oid in order_saving[:num_remove]]

    for oid in removed:
        solution.remove_order(oid)

    return removed


def destroy_route(data, solution, num_remove, rng):
    """
    整条路径移除算子。
    随机选择一条路径，把整条路径上的订单全部移除。
    """
    if not solution.routes:
        return []

    # 随机选一条路径
    # r_idx = rng.randint(0, len(solution.routes) - 1)
    r_idx = rng.integers(0, len(solution.routes))
    route = solution.routes[r_idx]

    # 收集路径内订单
    removed = []
    for node in route:
        if node == 0:
            continue
        if node <= NUM_ORDERS:
            removed.append(node - 1)

    # 逐个移除
    for oid in removed:
        solution.remove_order(oid)

    return removed


# 破坏算子注册表：名字 -> 函数
DESTROY_OPS = {
    "random": destroy_random,
    "shaw": destroy_shaw,
    "worst": destroy_worst,
    "route": destroy_route,
}