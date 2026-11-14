"""有限整数域求和等式的域一致性过滤。"""


def sum_equals_gac(domains, target):
    """过滤 x1 + ... + xn = target；无支持赋值则返回 None。"""
    if isinstance(target, bool) or not isinstance(target, int):
        raise ValueError("目标必须为整数")
    current = [set(values) for values in domains]
    if any(isinstance(x, bool) or not isinstance(x, int) for domain in current for x in domain):
        raise ValueError("域值必须为整数")
    if any(not domain for domain in current):
        return None
    prefix = [{0}]
    for domain in current:
        prefix.append({a + b for a in prefix[-1] for b in domain})
    if target not in prefix[-1]:
        return None
    suffix = [set() for _ in range(len(current) + 1)]
    suffix[-1] = {0}
    for i in range(len(current) - 1, -1, -1):
        suffix[i] = {a + b for a in suffix[i + 1] for b in current[i]}
    return [{value for value in current[i] if any(target - value - a in suffix[i + 1] for a in prefix[i])}
            for i in range(len(current))]
