# -*- coding: utf-8 -*-
"""
PDPTW 数据生成器。
"""

import numpy as np
from config import (NUM_ORDERS, NUM_NODES, DEPOT, MAP_WIDTH, MAP_HEIGHT,
                    CAPACITY, MAX_ROUTE_DURATION)


class PDPTWData:
    """
    PDPTW 问题数据容器。

    节点编号：
        0            -> 仓库
        1..NUM_ORDERS -> 取货点（订单 i 的取货点是 i+1）
        NUM_ORDERS+1..2*NUM_ORDERS -> 送货点（订单 i 的送货点是 i+1+NUM_ORDERS）
    """

    def __init__(self, seed=42):
        # 固定随机种子，保证结果可复现
        np.random.seed(seed)

        # ---------- 1. 生成坐标 ----------
        self.coords = np.zeros((NUM_NODES, 2))
        self.coords[DEPOT] = [MAP_WIDTH / 2, MAP_HEIGHT / 2]

        for order_id in range(NUM_ORDERS):
            px = np.random.uniform(5, MAP_WIDTH - 5)
            py = np.random.uniform(5, MAP_HEIGHT - 5)
            dx = px + np.random.uniform(-15, 15)
            dy = py + np.random.uniform(-15, 15)
            dx = np.clip(dx, 1, MAP_WIDTH - 1)
            dy = np.clip(dy, 1, MAP_HEIGHT - 1)

            pickup_node = order_id + 1
            delivery_node = order_id + 1 + NUM_ORDERS
            self.coords[pickup_node] = [px, py]
            self.coords[delivery_node] = [dx, dy]

        # ---------- 2. 距离矩阵 ----------
        self.dist = np.zeros((NUM_NODES, NUM_NODES))
        for i in range(NUM_NODES):
            for j in range(NUM_NODES):
                self.dist[i][j] = np.sqrt(
                    (self.coords[i][0] - self.coords[j][0]) ** 2 +
                    (self.coords[i][1] - self.coords[j][1]) ** 2
                )

        # ---------- 3. 订单需求 ----------
        self.demand = np.zeros(NUM_NODES, dtype=int)
        for order_id in range(NUM_ORDERS):
            d = np.random.randint(1, 4)
            self.demand[order_id + 1] = d
            self.demand[order_id + 1 + NUM_ORDERS] = -d

        # ---------- 4. 时间窗 ----------
        self.tw_start = np.zeros(NUM_NODES)
        self.tw_end = np.zeros(NUM_NODES)

        self.tw_start[DEPOT] = 0
        self.tw_end[DEPOT] = MAX_ROUTE_DURATION

        for order_id in range(NUM_ORDERS):
            p_start = np.random.uniform(0, 60)
            p_width = 120
            pickup_node = order_id + 1
            self.tw_start[pickup_node] = p_start
            self.tw_end[pickup_node] = p_start + p_width

            d_start = self.tw_end[pickup_node] + 30
            d_width = 200
            delivery_node = order_id + 1 + NUM_ORDERS
            self.tw_start[delivery_node] = d_start
            self.tw_end[delivery_node] = d_start + d_width

        # ---------- 5. 服务时间 ----------
        self.service_time = np.zeros(NUM_NODES)
        for i in range(1, NUM_NODES):
            self.service_time[i] = np.random.uniform(3, 8)

        print(f"[数据生成] {NUM_ORDERS} 个订单，{NUM_NODES} 个节点")
        print(f"[数据生成] 仓库坐标: ({self.coords[0][0]:.1f}, {self.coords[0][1]:.1f})")

    def order_pickup(self, order_id):
        """返回订单 order_id 的取货节点"""
        return order_id + 1

    def order_delivery(self, order_id):
        """返回订单 order_id 的送货节点"""
        return order_id + 1 + NUM_ORDERS

    def node_order(self, node):
        """返回节点 node 对应的订单 id，仓库返回 -1"""
        if node == DEPOT:
            return -1
        if node <= NUM_ORDERS:
            return node - 1
        return node - 1 - NUM_ORDERS

    def node_type(self, node):
        """返回节点类型"""
        if node == DEPOT:
            return 'depot'
        if node <= NUM_ORDERS:
            return 'pickup'
        return 'delivery'