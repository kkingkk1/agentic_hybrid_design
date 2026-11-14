# -*- coding: utf-8 -*-
"""
路径可行性检查与成本计算。
所有破坏/修复算子生成的候选路径，都要经过这里验证。
"""

from config import (CAPACITY, MAX_ROUTE_DURATION, DEPOT, NUM_ORDERS, MAX_ORDERS_PER_ROUTE)


def check_route(data, route):
    """
    检查一条路径是否满足所有约束，并返回行驶距离。

    参数：
        data : PDPTWData 对象
        route: 节点序列，形如 [0, 5, 105, 0]

    返回：
        (feasible, cost, msg)
        feasible: bool，是否可行
        cost    : float，路径行驶距离（不可行时为 0）
        msg     : str，错误提示（OK 表示可行）
    """
    # 路径非空检查
    if not route or len(route) < 2:
        return False, 0.0, "路径为空"

    # 必须以仓库开始和结束
    if route[0] != DEPOT or route[-1] != DEPOT:
        return False, 0.0, "路径必须以仓库开始和结束"

    # 只有一个仓库节点，视为空路径
    if len(route) == 2:
        return True, 0.0, "OK"

    load = 0            # 当前载重
    time = 0.0          # 当前时间
    cost = 0.0          # 累计距离
    visited = set()     # 已访问节点集合
    picked = set()      # 已取货订单
    delivered = set()   # 已送达订单
    order_count = 0

    # 遍历每一条边
    for i in range(len(route) - 1):
        cur = route[i]
        nxt = route[i + 1]

        # 非仓库节点不能重复访问
        if nxt != DEPOT and nxt in visited:
            return False, 0.0, f"节点 {nxt} 重复访问"

        # 计算行驶距离和到达时间
        travel = data.dist[cur][nxt]
        cost += travel
        arrival = time + travel

        # 时间窗上界检查
        if arrival > data.tw_end[nxt]:
            return False, 0.0, f"节点 {nxt} 超出时间窗"

        # 早到等待，计算离开时间
        start_service = max(arrival, data.tw_start[nxt])
        time = start_service + data.service_time[nxt]

        # 总时长检查
        if time > MAX_ROUTE_DURATION:
            return False, 0.0, f"路径总时长超限"

        # 更新载重
        load += data.demand[nxt]

        # 载重不能为负（不能配送未取货订单）
        if load < 0:
            return False, 0.0, f"节点 {nxt} 处载重为负"

        # 载重不能超过容量
        if load > CAPACITY:
            return False, 0.0, f"节点 {nxt} 处超载"

        # 取送配对约束
        order = data.node_order(nxt)
        if order >= 0:
            if nxt <= NUM_ORDERS:
                # 取货节点
                if order in picked:
                    return False, 0.0, f"订单 {order} 重复取货"
                picked.add(order)
                # 新增：订单数上限检查
                order_count += 1
                if order_count > MAX_ORDERS_PER_ROUTE:
                    return False, 0.0, f"单车订单数超限 {order_count} > {MAX_ORDERS_PER_ROUTE}"

            else:
                # 送货节点
                if order not in picked:
                    return False, 0.0, f"订单 {order} 未取货就配送"
                delivered.add(order)

        # 记录已访问
        visited.add(nxt)

    return True, cost, "OK"


def total_cost(data, routes):
    """
    计算整个解的加权总成本：
        总成本 = Σ 路径行驶距离 + 车辆数 × 固定成本
    """
    dist_sum = 0.0
    # 累加所有路径的行驶距离
    for route in routes:
        _, cost, _ = check_route(data, route)
        dist_sum += cost
    # 加上每辆车的固定成本
    from config import VEHICLE_FIXED_COST
    return dist_sum + len(routes) * VEHICLE_FIXED_COST


def all_orders_served(routes, num_orders):
    """
    检查所有订单是否都被服务且只被服务一次。
    """
    served = set()
    for route in routes:
        for node in route:
            if node == DEPOT:
                continue
            if node <= num_orders:
                # 取货节点代表一个订单
                served.add(node - 1)
    return len(served) == num_orders