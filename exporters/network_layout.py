"""Deterministic connection-aware placement for the offline SVG map."""

from collections import defaultdict, deque


def layout_topology(topology):
    """Place connected partitions together and fan out each partition by graph depth."""
    nodes = {node.id: node for node in topology.nodes}
    grouped, adjacent, scope_links = defaultdict(list), defaultdict(set), defaultdict(set)
    for node in topology.nodes:
        grouped[node.scope].append(node)
    for edge in topology.edges:
        left, right = nodes[edge.source], nodes[edge.target]
        if left.scope == right.scope:
            adjacent[left.id].add(right.id)
            adjacent[right.id].add(left.id)
        else:
            scope_links[left.scope].add(right.scope)
            scope_links[right.scope].add(left.scope)
    local, dimensions = {}, {}
    for scope, members in grouped.items():
        roots = sorted((n.id for n in members if n.kind in ("device", "router")))
        depth = dict.fromkeys(roots, 0)
        queue = deque(roots)
        while queue:
            node = queue.popleft()
            for peer in sorted(adjacent[node]):
                if peer not in depth:
                    depth[peer] = depth[node] + 1
                    queue.append(peer)
        layers = defaultdict(list)
        for node in members:
            layers[depth.get(node.id, 1)].append(node)
        # Ordering follows parent positions rather than configuration file order.
        order = {}
        levels = []
        for rank in sorted(layers):

            def key(node):
                parents = [
                    order[p] for p in adjacent[node.id] if p in order and depth.get(p, 1) < rank
                ]
                return (
                    sum(parents) / len(parents) if parents else 0,
                    node.kind,
                    node.label,
                    node.id,
                )

            layer = sorted(layers[rank], key=key)
            order.update((node.id, index) for index, node in enumerate(layer))
            levels.append(layer)
        columns = min(4, max(len(level) for level in levels))
        width = max(570, columns * 270 + 40)
        y = 80
        boxes = {}
        for level in levels:
            for index, node in enumerate(level):
                row, column = divmod(index, columns)
                count = min(columns, len(level) - row * columns)
                x = (width - count * 270 + 20) / 2 + column * 270
                boxes[node.id] = (x, y + row * 100, 250, 64)
            y += ((len(level) + columns - 1) // columns) * 100 + 28
        local[scope], dimensions[scope] = boxes, (width, y + 12)
    # A central partition anchors each connected component. Its peers occupy
    # following tiers; disconnected components start below the previous one.
    remaining = set(grouped)
    bounds, positions = {}, {}
    canvas_width, cursor = 0, 80
    while remaining:
        root = min(remaining, key=lambda s: (-len(scope_links[s]), s))
        depth = {root: 0}
        queue = deque([root])
        remaining.remove(root)
        while queue:
            scope = queue.popleft()
            for peer in sorted(scope_links[scope]):
                if peer in remaining:
                    remaining.remove(peer)
                    depth[peer] = depth[scope] + 1
                    queue.append(peer)
        tiers = defaultdict(list)
        for scope, rank in depth.items():
            tiers[rank].append(scope)
        rows = [
            sorted(tiers[rank])[start : start + 3]
            for rank in sorted(tiers)
            for start in range(0, len(tiers[rank]), 3)
        ]
        component_width = max(
            sum(dimensions[s][0] for s in row) + 100 * (len(row) - 1) for row in rows
        )
        canvas_width = max(canvas_width, component_width + 60)
        for row in rows:
            row_width = sum(dimensions[s][0] for s in row) + 100 * (len(row) - 1)
            x = 30 + (component_width - row_width) / 2
            for scope in row:
                width, height = dimensions[scope]
                bounds[scope] = (x, cursor, width, height)
                for node, (nx, ny, w, h) in local[scope].items():
                    positions[node] = (x + nx, cursor + ny, w, h)
                x += width + 100
            cursor += max(dimensions[s][1] for s in row) + 100
        cursor += 40
    return positions, bounds, max(630, canvas_width), cursor
