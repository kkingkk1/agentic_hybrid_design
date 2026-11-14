# -*- coding: utf-8 -*-
"""
ALNS 主循环。
流程：
    1. 构建初始解
    2. 循环：选破坏 + 选修复 -> 新解 -> 接受/拒绝
    3. 周期调用 CP-SAT 精修路径
    4. 自适应调整算子权重
"""

import time
import random
import numpy as np

from config import (ALNS_MAX_ITER, ALNS_TIME_LIMIT, ALNS_INIT_TEMP,
                    ALNS_COOLING_RATE, ALNS_MIN_TEMP,
                    DESTROY_MIN, DESTROY_MAX, SEGMENT_SIZE,
                    REACTION_FACTOR, SCORE_NEW_BEST, SCORE_IMPROVE,
                    SCORE_ACCEPT, WEIGHT_MIN,
                    SOLVER_CALL_INTERVAL)
from destroy_ops import DESTROY_OPS
from repair_ops import REPAIR_OPS
from acceptance import SimulatedAnnealing
from insertion import build_initial_solution
from route_optimizer import optimize_route_order
from feasibility import check_route


class ALNS:
    """ALNS 求解器"""

    def __init__(self, data, seed=42):
        self.data = data
        # 独立随机数生成器，便于复现
        self.rng = np.random.default_rng(seed)
        # 破坏和修复算子名字列表
        self.destroy_names = list(DESTROY_OPS.keys())
        self.repair_names = list(REPAIR_OPS.keys())
        # 算子权重初始化为 1
        self.destroy_weights = {n: 1.0 for n in self.destroy_names}
        self.repair_weights = {n: 1.0 for n in self.repair_names}
        # 分段得分与使用次数
        self.destroy_scores = {n: 0.0 for n in self.destroy_names}
        self.repair_scores = {n: 0.0 for n in self.repair_names}
        self.destroy_uses = {n: 0 for n in self.destroy_names}
        self.repair_uses = {n: 0 for n in self.repair_names}
        # 接受准则
        self.sa = SimulatedAnnealing(ALNS_INIT_TEMP, ALNS_COOLING_RATE, ALNS_MIN_TEMP)
        # 最优解记录
        self.best_solution = None
        self.best_cost = float('inf')
        # 求解历史
        self.history = []

    def _select_operator(self, weights):
        """按权重做轮盘赌选择算子"""
        names = list(weights.keys())
        ws = np.array([weights[n] for n in names], dtype=float)
        ws = ws / ws.sum()  # 归一化
        return self.rng.choice(names, p=ws)

    def _update_weights(self):
        """根据本段得分调整算子权重"""
        # 破坏算子
        for n in self.destroy_names:
            if self.destroy_uses[n] > 0:
                avg_score = self.destroy_scores[n] / self.destroy_uses[n]
                self.destroy_weights[n] = (
                    (1 - REACTION_FACTOR) * self.destroy_weights[n]
                    + REACTION_FACTOR * avg_score
                )
                self.destroy_weights[n] = max(self.destroy_weights[n], WEIGHT_MIN)
            # 清零本段统计
            self.destroy_scores[n] = 0.0
            self.destroy_uses[n] = 0
        # 修复算子
        for n in self.repair_names:
            if self.repair_uses[n] > 0:
                avg_score = self.repair_scores[n] / self.repair_uses[n]
                self.repair_weights[n] = (
                    (1 - REACTION_FACTOR) * self.repair_weights[n]
                    + REACTION_FACTOR * avg_score
                )
                self.repair_weights[n] = max(self.repair_weights[n], WEIGHT_MIN)
            self.repair_scores[n] = 0.0
            self.repair_uses[n] = 0

    def solve(self):
        """主循环"""
        start_time = time.time()

        # ---------- 初始解 ----------
        print("[ALNS] 构建初始解...")
        current = build_initial_solution(self.data)
        current.evaluate(self.data)
        # 记录最优
        self.best_solution = current.copy()
        self.best_cost = current.cost
        print(f"[ALNS] 初始解成本 = {current.cost:.2f}, 车辆数 = {len(current.routes)}")

        # ---------- 主循环 ----------
        for it in range(ALNS_MAX_ITER):
            # 时间检查
            if time.time() - start_time > ALNS_TIME_LIMIT:
                print(f"[ALNS] 时间限制达到，停止迭代")
                break

            # 每 SEGMENT_SIZE 轮更新一次权重
            if it > 0 and it % SEGMENT_SIZE == 0:
                self._update_weights()
                self.sa.cool()

            # ---------- 选择算子 ----------
            d_name = self._select_operator(self.destroy_weights)
            r_name = self._select_operator(self.repair_weights)
            d_op = DESTROY_OPS[d_name]
            r_op = REPAIR_OPS[r_name]

            # ---------- 复制解 ----------
            trial = current.copy()

            # ---------- 破坏 ----------
            num_remove = int(self.rng.integers(DESTROY_MIN, DESTROY_MAX + 1))
            removed = d_op(self.data, trial, num_remove, self.rng)
            if not removed:
                continue

            # ---------- 修复 ----------
            success = r_op(self.data, trial, removed, self.rng)
            if not success or not trial.is_feasible(self.data):
                # 修复失败，丢弃本次尝试
                self.destroy_uses[d_name] += 1
                self.repair_uses[r_name] += 1
                continue

            # ---------- 评估 ----------
            trial.evaluate(self.data)

            # ---------- 接受 / 拒绝 ----------
            accepted = self.sa.accept(current.cost, trial.cost, self.rng)

            # 得分判断
            if trial.cost < self.best_cost:
                # 更新全局最优
                self.best_solution = trial.copy()
                self.best_cost = trial.cost
                score = SCORE_NEW_BEST
                print(f"[ALNS] iter {it}: 新最优 {self.best_cost:.2f}, "
                      f"车辆数 = {len(self.best_solution.routes)}")
            elif trial.cost < current.cost:
                # 改进了当前解
                score = SCORE_IMPROVE
            elif accepted:
                # 差解被接受
                score = SCORE_ACCEPT
            else:
                score = 0.0

            # 更新算子统计
            self.destroy_scores[d_name] += score
            self.repair_scores[r_name] += score
            self.destroy_uses[d_name] += 1
            self.repair_uses[r_name] += 1

            # 接受则更新当前解
            if accepted:
                current = trial

            # 定期用 CP-SAT 精修路径
            if it > 0 and it % SOLVER_CALL_INTERVAL == 0:
                self._solver_refine(current)

            # 记录历史
            self.history.append(current.cost)

        # ---------- 输出 ----------
        elapsed = time.time() - start_time
        print(f"\n[ALNS] 结束，耗时 {elapsed:.1f}s")
        print(f"[ALNS] 最优成本 = {self.best_cost:.2f}")
        print(f"[ALNS] 车辆数 = {len(self.best_solution.routes)}")
        return self.best_solution

    def _solver_refine(self, current_solution):
        """用 CP-SAT 精修每条路径 (安全版本)"""
        print(f"  [Solver] 开始 CP-SAT 精修...")
        improved = 0
        
        # 1. 在临时副本上操作，绝不轻易触碰 current_solution
        trial_solution = current_solution.copy()
        
        for r_idx in range(len(trial_solution.routes)):
            old_route = trial_solution.routes[r_idx]
            new_route = optimize_route_order(self.data, old_route)
            if new_route != old_route:
                trial_solution.routes[r_idx] = new_route
                improved += 1

        if improved > 0:
            # 2. 评估精修后的临时解
            trial_solution.evaluate(self.data)
            
            # 3. 关键拦截：如果精修导致不可行（cost = inf），立即放弃本次精修
            if trial_solution.cost == float('inf'):
                print("  [Solver] 精修导致违反约束，解不可行，放弃本次精修。")
                return
                
            print(f"  [Solver] 精修 {improved} 条路径，新成本 {trial_solution.cost:.2f}")
            
            # 4. 确认变好了，才更新 current_solution 和全局最优
            current_solution.routes = trial_solution.routes
            current_solution.cost = trial_solution.cost
            
            if trial_solution.cost < self.best_cost:
                self.best_solution = trial_solution.copy()
                self.best_cost = trial_solution.cost
                print(f"  [Solver] 新全局最优 {self.best_cost:.2f}")