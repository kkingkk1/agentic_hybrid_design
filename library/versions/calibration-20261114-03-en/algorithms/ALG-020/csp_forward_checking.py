"""有限二元 CSP：最小剩余域回溯与前向检查。"""


def solve_csp(domains, constraints):
    """返回一个满足二元允许值对的赋值，无解返回 None。"""
    current = {v: list(dict.fromkeys(values)) for v, values in domains.items()}
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

    def search(assignment, remaining):
        if len(assignment) == len(current):
            return assignment
        variable = min((v for v in current if v not in assignment), key=lambda v: len(remaining[v]))
        for value in remaining[variable]:
            next_domains = {v: choices[:] for v, choices in remaining.items()}
            valid = True
            for other in current:
                if other in assignment or other == variable or (variable, other) not in relations:
                    continue
                next_domains[other] = [b for b in next_domains[other] if (value, b) in relations[variable, other]]
                if not next_domains[other]:
                    valid = False
                    break
            if valid:
                result = search({**assignment, variable: value}, next_domains)
                if result is not None:
                    return result
        return None

    return search({}, current)
