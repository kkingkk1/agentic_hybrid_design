"""0/1 背包分支定界：用分数背包松弛作为上界。"""

from fractions import Fraction


def knapsack_branch_bound(weights, values, capacity):
    """返回最大价值及物品下标；重量为正整数，价值和容量非负。"""
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0 or len(weights) != len(values):
        raise ValueError("容量或输入长度无效")
    if any(isinstance(x, bool) or not isinstance(x, int) or x <= 0 for x in weights):
        raise ValueError("重量必须为正整数")
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in values):
        raise ValueError("价值必须为非负整数")
    order = sorted(range(len(weights)), key=lambda i: Fraction(values[i], weights[i]), reverse=True)
    best, selected = 0, []

    def upper(index, room, value):
        result = Fraction(value)
        for k in range(index, len(order)):
            i = order[k]
            if weights[i] <= room:
                room -= weights[i]
                result += values[i]
            else:
                result += Fraction(values[i] * room, weights[i])
                break
        return result

    def search(index, room, value, chosen):
        nonlocal best, selected
        if value > best:
            best, selected = value, chosen[:]
        if index == len(order) or upper(index, room, value) <= best:
            return
        i = order[index]
        if weights[i] <= room:
            search(index + 1, room - weights[i], value + values[i], [*chosen, i])
        search(index + 1, room, value, chosen)

    search(0, capacity, 0, [])
    return best, sorted(selected)
