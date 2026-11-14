# -*- coding: utf-8 -*-
"""
解的表示。
一个解由一组路径组成，每条路径是一串节点序列。
"""

from feasibility import check_route, total_cost, all_orders_served
from config import NUM_ORDERS, DEPOT


class Solution:
    """
    PDPTW 解的封装。
    属性：
        routes: 路径列表，每条路径形如 [0, 5, 105, 0]
        cost  : 当前解的总成本（距离 + 车辆固定成本）
    """

    def __init__(self, routes=None):
        # 如果没传路径，初始化为空
        self.routes = routes if routes is not None else []
        self.cost = float('inf')   # 成本先置为无穷大

    def copy(self):
        """深拷贝：每条路径的列表也要复制，且需要保留 cost"""
        new_sol = Solution([list(r) for r in self.routes])
        new_sol.cost = self.cost
        return new_sol

    def evaluate(self, data):
        """计算当前解的总成本"""
        self.cost = total_cost(data, self.routes)
        return self.cost

    def is_feasible(self, data):
        """检查所有路径是否可行，且所有订单被服务"""
        # 每条路径逐一检查
        for r in self.routes:
            ok, _, _ = check_route(data, r)
            if not ok:
                return False
        # 所有订单是否被覆盖
        return all_orders_served(self.routes, NUM_ORDERS)

    def remove_order(self, order_id):
        """
        从解中移除指定订单。
        返回被移除的两个节点（取货、送货），用于后续重新插入。
        """
        pu = order_id + 1
        de = order_id + 1 + NUM_ORDERS

        # 遍历所有路径，找到包含该订单的路径
        for r_idx, route in enumerate(self.routes):
            if pu in route and de in route:
                # 移除这两个节点
                new_route = [n for n in route if n != pu and n != de]
                # 如果路径只剩仓库，直接删除这条路径
                if len(new_route) <= 2:
                    self.routes.pop(r_idx)
                else:
                    self.routes[r_idx] = new_route
                return pu, de

        # 理论上不会走到这里
        return pu, de

    def get_route_of_order(self, order_id):
        """返回订单所在的路径索引"""
        pu = order_id + 1
        for r_idx, route in enumerate(self.routes):
            if pu in route:
                return r_idx
        return -1