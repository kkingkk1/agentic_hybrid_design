# -*- coding: utf-8 -*-
"""
ALNS + CP-SAT 求解 PDPTW 的全局配置。
所有可调参数集中在这里，方便做对比实验。
"""

# ==================== 问题规模 ====================
NUM_ORDERS = 100                    # 订单数量
NUM_NODES = 2 * NUM_ORDERS + 1      # 总节点数 = 201（含仓库）
DEPOT = 0                           # 仓库节点编号

# ==================== 车辆参数 ====================
CAPACITY = 10                       # 车辆最大载重
MAX_ROUTE_DURATION = 10000          # 单条路径最大总时长（分钟）
MAX_ORDERS_PER_ROUTE = 5            # 单条路径最多服务订单数
VEHICLE_FIXED_COST = 1000           # 每启用一辆车的固定成本

# ==================== 地图参数 ====================
MAP_WIDTH = 40.0                    # 地图宽度
MAP_HEIGHT = 40.0                   # 地图高度

# ==================== ALNS 参数 ====================
ALNS_MAX_ITER = 3000                # ALNS 最大迭代次数
ALNS_TIME_LIMIT = 300.0             # ALNS 总时间限制（秒）
ALNS_INIT_TEMP = 50.0               # 初始温度（模拟退火）
ALNS_COOLING_RATE = 0.9997          # 冷却率
ALNS_MIN_TEMP = 0.1                 # 最低温度
DESTROY_MIN = 5                     # 每次破坏最少移除订单数
DESTROY_MAX = 20                    # 每次破坏最多移除订单数

# ==================== 自适应权重 ====================
SEGMENT_SIZE = 100                  # 每多少轮更新一次算子权重
REACTION_FACTOR = 0.2               # 权重反应系数
SCORE_NEW_BEST = 10.0               # 找到新全局最优的得分
SCORE_IMPROVE = 5.0                 # 改进当前解的得分
SCORE_ACCEPT = 2.0                  # 被接受的次优解的得分
WEIGHT_MIN = 0.05                   # 算子权重下限（防止归零）

# ==================== CP-SAT 求解器参数 ====================
SOLVER_CALL_INTERVAL = 50          # 每多少轮 ALNS 调用一次 CP-SAT
SOLVER_ROUTE_TIME_LIMIT = 1.0       # 单条路径 CP-SAT 时间限制（秒）