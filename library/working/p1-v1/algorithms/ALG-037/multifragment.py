"""Join path fragments by cheap edges without forming an early cycle."""


def multifragment_tour(distance):
    """Construct an open tour from a complete symmetric distance matrix."""
    size = len(distance)
    if size <= 2:
        return list(range(size))
    parents = list(range(size))
    neighbors = [[] for _ in range(size)]

    def root(vertex):
        while parents[vertex] != vertex:
            parents[vertex] = parents[parents[vertex]]
            vertex = parents[vertex]
        return vertex

    edges = sorted(
        (distance[a][b], a, b) for a in range(size) for b in range(a + 1, size)
    )
    joined = 0
    for _, a, b in edges:
        if len(neighbors[a]) == 2 or len(neighbors[b]) == 2:
            continue
        a_root, b_root = root(a), root(b)
        if a_root == b_root:
            continue
        parents[b_root] = a_root
        neighbors[a].append(b)
        neighbors[b].append(a)
        joined += 1
        if joined == size - 1:
            break

    vertex = next(a for a, adjacent in enumerate(neighbors) if len(adjacent) == 1)
    path = [vertex]
    previous = -1
    while len(path) < size:
        following = next(a for a in neighbors[vertex] if a != previous)
        path.append(following)
        previous, vertex = vertex, following
    return path
