# -*- coding: utf-8 -*-
"""
CP-SAT 路径内优化器。
给定一条路径上的节点序列，重新排列以获得更短的行驶距离。
"""

import numpy as np
from ortools.sat.python import cp_model
from config import (NUM_ORDERS, DEPOT, CAPACITY, MAX_ROUTE_DURATION,
                    SOLVER_ROUTE_TIME_LIMIT)


def optimize_route_order(data, route, time_limit=SOLVER_ROUTE_TIME_LIMIT):
    """
    用 CP-SAT 重新优化一条路径上的节点顺序。

    参数：
        data     : PDPTWData
        route    : 现有路径节点序列 [0, pu1, de1, pu2, de2, ..., 0]
        time_limit: 求解时间限制

    返回：
        新的最优路径（如果求解失败，返回原路径）
    """
    # 提取路径上的订单
    orders = []
    seen = set()
    for node in route:
        if node == DEPOT:
            continue
        oid = data.node_order(node)
        if oid >= 0 and oid not in seen:
            orders.append(oid)
            seen.add(oid)

    M = len(orders)
    if M <= 1:
        # 少于 2 个订单无法优化
        return route

    # 构造局部节点映射：0=仓库，1..M=取货，M+1..2M=送货
    local_to_actual = {0: DEPOT}
    for idx, oid in enumerate(orders):
        local_to_actual[idx + 1] = data.order_pickup(oid)
        local_to_actual[idx + M + 1] = data.order_delivery(oid)

    # 计算局部距离矩阵和时间窗
    num_local = 2 * M + 1
    loc_dist = np.zeros((num_local, num_local), dtype=int)
    loc_tw_start = np.zeros(num_local, dtype=int)
    loc_tw_end = np.zeros(num_local, dtype=int)
    loc_service = np.zeros(num_local, dtype=int)
    loc_demand = np.zeros(num_local, dtype=int)

    SCALE = 1000
    for i in range(num_local):
        node_i = local_to_actual[i]
        loc_tw_start[i] = int(data.tw_start[node_i] * SCALE)
        loc_tw_end[i] = int(data.tw_end[node_i] * SCALE)
        loc_service[i] = int(data.service_time[node_i] * SCALE)
        loc_demand[i] = int(data.demand[node_i])
        for j in range(num_local):
            node_j = local_to_actual[j]
            loc_dist[i][j] = int(data.dist[node_i][node_j] * SCALE)  # 缩放为整数

    # ---------- CP-SAT 建模 ----------
    model = cp_model.CpModel()

    # 弧变量
    arcs = []
    x = {}
    for i in range(num_local):
        for j in range(num_local):
            if i == j:
                continue
            var = model.NewBoolVar(f"x_{i}_{j}")
            x[(i, j)] = var
            arcs.append([i, j, var])

    # 用 AddCircuit 强制单回路（即从仓库出发回到仓库的完整路径）
    model.AddCircuit(arcs)

    # ========== 时间变量 ==========
    horizon = int(max(loc_tw_end))
    start = {}
    for i in range(num_local):
        start[i] = model.NewIntVar(0, horizon, f"start_{i}")
        model.Add(start[i] >= loc_tw_start[i])
        model.Add(start[i] <= loc_tw_end[i])

    # ========== 时间推进约束 ==========
    BIG_M = horizon
    for (i, j), var in x.items():
        if j == 0:
            # 跳过进入仓库的弧，避免"start[0] 既是最小又是最大"的循环矛盾
            continue
        model.Add(
            start[j] >= start[i] + loc_service[i] + loc_dist[i][j]
        ).OnlyEnforceIf(var)   # 只在弧选中时生效

    # 取货必须在送货之前
    for idx in range(M):
        pu_local = idx + 1
        de_local = idx + M + 1
        model.Add(start[pu_local] <= start[de_local])

    # ========== 容量约束 ==========
    load = {}
    for i in range(num_local):
        load[i] = model.NewIntVar(0, CAPACITY, f"load_{i}")
    # 仓库出发时载重 = 0
    model.Add(load[0] == 0)
    # 载重推进：走 i→j 时，load[j] = load[i] + demand[j]
    for (i, j), var in x.items():
        if j == 0:
            continue    # 跳过返回仓库的弧（载重已归 0，不需要推进）
        model.Add(load[j] == load[i] + loc_demand[j]).OnlyEnforceIf(var)


    # 目标函数：最小化总距离
    obj_terms = [loc_dist[i][j] * x[(i, j)] for (i, j) in x]
    model.Minimize(sum(obj_terms))

    # ---------- 求解 ----------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"求解失败！回退原路径")
        return route   # 求解失败，回退原路径

    # ---------- 提取新路径 ----------
    # 从局部节点 0（仓库）出发，依次追踪后继节点
    new_route_local = [0]
    cur = 0
    # 最多走 num_local 步
    for _ in range(num_local):
        # 找到 cur 的出边
        found = False
        for j in range(num_local):
            if j == cur:
                continue
            if (cur, j) in x and solver.Value(x[(cur, j)]) == 1:
                new_route_local.append(j)
                cur = j
                found = True
                break
        if not found:
            break
        if cur == 0:
            break

    # 转换成实际节点序列
    new_route = []
    for i in new_route_local:
        new_route.append(int(local_to_actual[i]))

    # 检查可行性
    from feasibility import check_route
    ok, _, _ = check_route(data, new_route)
    if not ok:
        print(f"新路径不可行！")
        return route
    print(f"求解成功，优化后路线：{new_route}")
    return new_route