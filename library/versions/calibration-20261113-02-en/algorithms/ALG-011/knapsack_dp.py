"""0/1 背包的容量状态动态规划。"""


def knapsack_dp(weights, values, capacity):
    """返回最大价值及物品下标；重量、价值和容量均为非负整数。"""
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
        raise ValueError("容量必须为非负整数")
    if len(weights) != len(values):
        raise ValueError("重量与价值长度不一致")
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in [*weights, *values]):
        raise ValueError("重量与价值必须为非负整数")
    rows = [[0] * (capacity + 1)]
    for weight, value in zip(weights, values):
        previous = rows[-1]
        rows.append([max(previous[c], previous[c - weight] + value) if weight <= c else previous[c]
                     for c in range(capacity + 1)])
    selected = []
    remaining = capacity
    for i in range(len(weights), 0, -1):
        if rows[i][remaining] > rows[i - 1][remaining]:
            selected.append(i - 1)
            remaining -= weights[i - 1]
    selected.reverse()
    return rows[-1][capacity], selected
