# -*- coding: utf-8 -*-
"""
接受准则：模拟退火。
"""

import math


class SimulatedAnnealing:
    """
    模拟退火接受准则。
    温度高时接受差解，温度低时只接受更好的解。
    """

    def __init__(self, init_temp, cooling_rate, min_temp):
        # 初始温度
        self.temp = init_temp
        # 冷却率（每轮乘以此系数）
        self.cooling_rate = cooling_rate
        # 最低温度
        self.min_temp = min_temp

    def accept(self, curr_cost, new_cost, rng):
        """
        判断是否接受新解。
        curr_cost: 当前解成本
        new_cost : 新解成本
        """
        # 新解更好，直接接受
        if new_cost < curr_cost:
            return True

        # 温度过低，不再接受差解
        if self.temp <= self.min_temp:
            return False

        # 概率接受差解：exp(-(new-curr)/T)
        delta = new_cost - curr_cost
        prob = math.exp(-delta / self.temp)
        return rng.random() < prob

    def cool(self):
        """温度下降一步"""
        self.temp = max(self.temp * self.cooling_rate, self.min_temp)