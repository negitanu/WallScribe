"""Three-valued App-ID and ISDB matching; supplied observations are assumptions."""

from ipaddress import ip_network


def ports_match(specs, protocol, port):
    results = []
    for spec in specs:
        try:
            proto, ranges = spec.split("/", 1)
            if proto.upper() != protocol:
                results.append(False)
                continue
            for part in ranges.split(","):
                lo, _, hi = part.partition("-")
                lo, hi = int(lo), int(hi or lo)
                if not 1 <= lo <= hi <= 65535:
                    return None
                results.append(lo <= port <= hi)
        except (ValueError, TypeError, AttributeError):
            return None
    return True if True in results else False if results else None


def application_match(
    config, names, scope, actual, seen=frozenset(), budget=None, origin_scope=None
):
    origin_scope = scope if origin_scope is None else origin_scope
    if budget is None:
        budget = [512]
    budget[0] -= 1
    if budget[0] < 0:
        return None
    if "any" in names:
        return True
    if not actual:
        return None
    results = []
    for name in names:
        obj = next(
            (
                a
                for owner in (scope, "shared")
                for a in config.applications
                if a.vdom == owner and a.name == name
            ),
            None,
        )
        if scope == "shared" and origin_scope != "shared" and obj:
            local = next(
                (a for a in config.applications if a.vdom == origin_scope and a.name == name), None
            )
            if local and (local.members, local.dynamic, local.ports) != (
                obj.members,
                obj.dynamic,
                obj.ports,
            ):
                results.append(None)
                continue
        if name == actual:
            results.append(True)
            continue
        key = (obj.vdom, name) if obj else (scope, name)
        if obj and (obj.dynamic or key in seen or len(seen) >= 64):
            results.append(None)
        elif obj and obj.members:
            results.append(
                application_match(
                    config, obj.members, obj.vdom, actual, seen | {key}, budget, origin_scope
                )
            )
        elif obj is None:
            # A named application may be an unresolved filter/group.
            results.append(None)
        else:
            results.append(False)
    return True if True in results else None if not results or None in results else False


def application_ports(config, scope, actual, protocol, port, catalog):
    obj = next(
        (
            a
            for owner in (scope, "shared")
            for a in config.applications
            if a.vdom == owner and a.name == actual
        ),
        None,
    )
    return ports_match(obj.ports if obj and obj.ports else catalog.get(actual, []), protocol, port)


def isdb_match(names, ip, protocol, port, catalog, negate=False):
    results = []
    for name in names:
        records = catalog.get(name)
        if not records:
            results.append(None)
            continue
        values = [
            ip in ip_network(r["network"], strict=False) and ports_match(r["ports"], protocol, port)
            for r in records
        ]
        results.append(True if True in values else None if None in values else False)
    result = True if True in results else None if not results or None in results else False
    return not result if negate and result is not None else result
