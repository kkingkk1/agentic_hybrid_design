"""有限二元约束网络的 AC-3 弧一致性传播。"""

from collections import deque


def ac3(domains, constraints):
    """constraints 为 (变量, 变量, 允许值对)；返回新域或 None。"""
    current = {v: set(values) for v, values in domains.items()}
    if any(not values for values in current.values()):
        return None
    relations = {}
    for x, y, pairs in constraints:
        if x not in current or y not in current or x == y:
            raise ValueError("约束变量必须存在且互不相同")
        allowed = {(a, b) for a, b in pairs}
        if (x, y) in relations:
            allowed &= relations[x, y]
        relations[x, y] = allowed
        relations[y, x] = {(b, a) for a, b in allowed}
    queue = deque(relations)
    while queue:
        x, y = queue.popleft()
        supported = {a for a in current[x] if any((a, b) in relations[x, y] for b in current[y])}
        if supported != current[x]:
            if not supported:
                return None
            current[x] = supported
            queue.extend((z, x) for z in current if z != y and (z, x) in relations)
    return current
