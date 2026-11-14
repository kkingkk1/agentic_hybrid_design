# -*- coding: utf-8 -*-
"""
ALNS + CP-SAT 求解 PDPTW 的入口文件。
"""

import time
from data import PDPTWData
from alns import ALNS
from feasibility import check_route
from config import DEPOT, NUM_ORDERS


def print_solution(data, solution):
    """格式化输出最终解"""
    print("\n" + "=" * 60)
    print("最优解详情")
    print("=" * 60)

    total_distance = 0.0
    total_orders = 0

    for idx, route in enumerate(solution.routes):
        # 提取路径服务的订单
        orders = []
        for node in route:
            if node == DEPOT:
                continue
            # if node <= data.__class__.__module__ and False:
            #     pass
            oid = data.node_order(node)
            if oid >= 0 and node <= NUM_ORDERS:
                orders.append(oid)

        # 计算路径距离
        _, path_cost, _ = check_route(data, route)
        total_distance += path_cost
        total_orders += len(orders)

        print(f"\n路径 {idx + 1}:")
        print(f"  节点序列: {[int(n) for n in route]}")
        print(f"  服务订单: {[int(o) for o in orders]}")
        print(f"  路径成本: {path_cost:.2f}")

    print(f"\n总路径数（车辆数）: {len(solution.routes)}")
    print(f"总服务订单数: {total_orders} / {(len(data.coords) - 1) // 2}")
    print(f"纯行驶距离: {total_distance:.2f}")
    from config import VEHICLE_FIXED_COST
    print(f"车辆固定成本: {len(solution.routes) * VEHICLE_FIXED_COST:.2f}")
    print(f"总目标值: {solution.cost:.2f}")


if __name__ == "__main__":
    print("=" * 60)
    print("PDPTW ALNS + CP-SAT 求解")
    print("=" * 60)

    # 生成数据
    print("\n[步骤1] 生成数据...")
    data = PDPTWData(seed=42)

    # 运行 ALNS
    print("\n[步骤2] ALNS 求解...")
    start = time.time()
    alns = ALNS(data, seed=42)
    solution = alns.solve()
    elapsed = time.time() - start

    # 输出最终结果
    print_solution(data, solution)
    print(f"\n总耗时: {elapsed:.2f}s")