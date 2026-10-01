"""Deterministic, bounded, adversarial tabletop scenarios. Never sends packets."""

from dataclasses import asdict, replace
from ipaddress import ip_address, ip_interface

from analyzers.application import ports_match
from analyzers.network import Resolver, investigate_flow, network
from models.config import PolicyAction

MAX_CASES = 200
MAX_POLICIES = 5000


def sample_address(config, names, scope, fallback, seen=frozenset(), visited=None):
    if visited is None:
        visited = set()
    resolver = Resolver(config)
    for name in names:
        key = (scope, name)
        if key in visited:
            continue
        visited.add(key)
        if name in seen or len(seen) > 32:
            continue
        obj = resolver.lookup(
            name, scope, [config.objects.addresses, config.objects.address_groups]
        )
        if obj and hasattr(obj, "members") and not obj.dynamic_filter:
            found = sample_address(config, obj.members, obj.vdom, "", seen | {name}, visited)
            if found:
                return found
        raw = obj.value if obj and hasattr(obj, "value") else name
        try:
            if obj and getattr(obj, "object_type", "") == "iprange":
                return str(ip_address(raw.split("-")[0].strip()))
            net = network(raw)
            return str(net.network_address + (1 if net.num_addresses > 2 else 0))
        except ValueError:
            continue
    return fallback


def sample_service(config, names, scope, app, catalog, seen=frozenset()):
    resolver = Resolver(config)
    for name in names:
        if name in seen or len(seen) > 32:
            continue
        if name == "application-default":
            obj = next(
                (a for a in config.applications if a.name == app and a.vdom in (scope, "shared")),
                None,
            )
            specs = obj.ports if obj and obj.ports else catalog.get(app, [])
            for proto in ("TCP", "UDP"):
                for port in (443, 80, 53, 22, 8080, 8443):
                    if ports_match(specs, proto, port) is True:
                        return proto, port
            for spec in specs:
                try:
                    proto, raw = spec.split("/", 1)
                    port = int(raw.split(",")[0].split("-")[0])
                    if proto.upper() in ("TCP", "UDP") and 1 <= port <= 65535:
                        return proto.upper(), port
                except ValueError:
                    pass
        obj = resolver.lookup(name, scope, [config.objects.services, config.objects.service_groups])
        if obj and hasattr(obj, "members"):
            return sample_service(config, obj.members, obj.vdom, app, catalog, seen | {name})
        if obj and obj.protocol.upper() in ("TCP", "UDP"):
            try:
                port = int(obj.port.split(",")[0].split(" ")[0].split("-")[0])
                if 1 <= port <= 65535:
                    return obj.protocol.upper(), port
            except ValueError:
                pass
    return "TCP", 443


def generate_cases(config, catalog=None, feeds=()):
    if len(config.firewall_policies) > MAX_POLICIES:
        raise ValueError("ポリシーは 5000 件以内で指定してください")
    catalog = catalog or {}
    cases = []
    for index, p in enumerate(config.firewall_policies):
        if not p.enabled:
            continue
        app = next((a for a in p.application if a != "any"), "")
        group = next(
            (
                a
                for a in config.applications
                if a.name == app and a.members and a.vdom in (p.vdom, "shared")
            ),
            None,
        )
        if group:
            app = group.members[0]
        proto, port = sample_service(config, p.service, p.vdom, app, catalog)
        src = sample_address(config, p.source_address, p.vdom, "192.0.2.10")
        dst = sample_address(config, p.destination_address, p.vdom, "198.51.100.20")
        if ip_address(src).version != ip_address(dst).version:
            if ip_address(dst).version == 6:
                src = "2001:db8::10"
            else:
                dst = "2001:db8:1::20"
        source_if = next((n for n in p.source_interface if n not in ("any", "all")), "")
        destination_if = next((n for n in p.destination_interface if n not in ("any", "all")), "")
        vr = next(
            (
                i.routing_context
                for i in config.interfaces
                if i.vdom == p.vdom
                and i.vdom_assignment_known
                and source_if in (i.name, i.zone)
                and i.routing_context
            ),
            "",
        )
        base = {
            "source": src,
            "destination": dst,
            "protocol": proto,
            "port": port,
            "scope": p.vdom,
            "source_interface": source_if,
            "destination_interface": destination_if,
            "application": app,
            "routing_context": vr,
        }
        target = {"policy_id": p.policy_id, "name": p.name, "scope": p.vdom, "order": index + 1}
        expected = "allow" if p.action == PolicyAction.ALLOW else "block"
        variants = [
            ("policy", "ポリシー代表条件", base, expected),
            (
                "boundary",
                "宛先ポート境界・非標準ポート",
                base | {"port": 65535 if port != 65535 else 1},
                "block",
            ),
            (
                "attack",
                "管理・横展開の到達条件",
                base | {"port": 3389, "application": "unknown-tcp"},
                "block",
            ),
        ]
        for kind, name, query, want in variants:
            cases.append(
                {
                    "id": "case-" + str(len(cases) + 1),
                    "kind": kind,
                    "name": name,
                    "query": query,
                    "expected": want,
                    "target": target,
                    "reason": "代表条件はポリシーから生成。境界・攻撃ケースの期待値は検討用の拒否仮説で、業務要件に合わせて変更してください。",
                }
            )
        if len(cases) >= MAX_CASES - 20:
            break
    bases = [c for c in cases if c["kind"] == "policy"][:10]
    for feed in feeds:
        if feed.get("stale") or feed.get("status") != "ok":
            continue
        chosen_categories = set()
        for item in feed["items"][:30]:
            if feed["key"] == "cisa-kev":
                title = item["vulnerabilityName"].lower()
                category = (
                    "認証・権限境界"
                    if any(w in title for w in ("auth", "privilege", "credential"))
                    else (
                        "コード実行・入力検査"
                        if any(w in title for w in ("execution", "injection", "overflow"))
                        else "公開サービスの検査"
                    )
                )
                if category in chosen_categories or len(chosen_categories) >= 3:
                    continue
                chosen_categories.add(category)
                for base in bases[:1]:
                    cases.append(
                        {
                            "id": "case-" + str(len(cases) + 1),
                            "kind": "attack",
                            "name": "KEV " + category + " / " + item["cveID"],
                            "query": base["query"]
                            | {"port": 443, "protocol": "TCP", "application": "ssl"},
                            "expected": "block",
                            "target": base["target"],
                            "reason": item["cveID"]
                            + " / "
                            + item["vendorProject"]
                            + " / "
                            + item["vulnerabilityName"]
                            + "。関連製品・バージョンと検査プロファイルを確認。CVE の再現や機器の脆弱性判定ではありません。",
                            "feed": {
                                "name": feed["name"],
                                "url": feed["url"],
                                "fetched_at": feed["fetched_at"],
                                "indicator": item["cveID"],
                            },
                        }
                    )
            if feed["key"] == "feodo":
                for base in bases[:2]:
                    cases.append(
                        {
                            "id": "case-" + str(len(cases) + 1),
                            "kind": "attack",
                            "name": "C2 宛先への出口制御",
                            "query": base["query"]
                            | {
                                "destination": item["ip"],
                                "port": item["port"],
                                "protocol": "TCP",
                                "application": "unknown-tcp",
                            },
                            "expected": "block",
                            "target": base["target"],
                            "reason": "Feed に掲載された C2 通信条件。接続や攻撃は行いません。",
                            "feed": {
                                "name": feed["name"],
                                "url": feed["url"],
                                "fetched_at": feed["fetched_at"],
                                "indicator": item["ip"],
                            },
                        }
                    )
    return cases[:MAX_CASES]


def route_path(config, query):
    dst = ip_address(query["destination"])
    scope, context = query["scope"], query.get("routing_context", "")
    if config.virtual_routers and not context:
        return {
            "status": "unknown",
            "steps": [],
            "issues": ["入口 IF の仮想ルーターを指定してください"],
        }
    seen, steps = set(), []
    while True:
        if context in seen:
            return {"status": "cycle", "steps": steps, "issues": ["next-vr に循環があります"]}
        seen.add(context)
        candidates = []
        for r in config.routes:
            if (
                not r.enabled
                or (context and r.routing_context != context)
                or (not context and (r.vdom != scope or not r.vdom_assignment_known))
            ):
                continue
            try:
                net = network(r.destination)
                if dst in net:
                    candidates.append((net.prefixlen, r))
            except ValueError:
                return {
                    "status": "unknown",
                    "steps": steps,
                    "issues": ["解釈できない経路があります"],
                }
        for i in config.interfaces:
            if (
                i.status == "down"
                or not i.vdom_assignment_known
                or (context and i.routing_context != context)
                or (not context and i.vdom != scope)
            ):
                continue
            for raw in i.ip_address.split(","):
                try:
                    net = ip_interface(raw.strip()).network
                    if dst in net:
                        from models.config import Route

                        candidates.append(
                            (
                                net.prefixlen,
                                Route(
                                    destination=str(net),
                                    interface=i.name,
                                    route_type="connected",
                                    distance="0",
                                    routing_context=context,
                                ),
                            )
                        )
                except ValueError:
                    pass
        if not candidates:
            dynamic = any(
                v.name == context and v.dynamic_protocols for v in config.virtual_routers
            ) or bool(config.routing.ospf or config.routing.bgp)
            return {
                "status": "unknown" if dynamic else "missing",
                "steps": steps,
                "issues": [
                    "動的経路の実行時情報が必要" if dynamic else "設定上の宛先経路がありません"
                ],
            }
        prefix = max(n for n, _ in candidates)
        best = [r for n, r in candidates if n == prefix]

        def rank(r):
            try:
                return int(r.distance), int(r.metric or r.priority or "0")
            except ValueError:
                return None

        if len(best) > 1:
            ranks = [rank(r) for r in best]
            if None in ranks:
                return {
                    "status": "ambiguous",
                    "steps": steps,
                    "issues": ["同一プレフィックスの優先順位を確定できません"],
                }
            minimum = min(ranks)
            best = [r for r in best if rank(r) == minimum]
            if len(best) != 1:
                return {
                    "status": "ambiguous",
                    "steps": steps,
                    "issues": ["同順位の経路が複数あります（ECMP 等は実機確認）"],
                }
        r = best[0]
        steps.append(asdict(r))
        if r.route_type.startswith("blackhole"):
            return {"status": "drop", "steps": steps, "issues": ["より優先される破棄経路です"]}
        if r.route_type == "next-vr":
            if not any(v.name == r.gateway for v in config.virtual_routers):
                return {
                    "status": "missing",
                    "steps": steps,
                    "issues": ["next-vr の参照先がありません"],
                }
            context = r.gateway
            continue
        interfaces = [
            i
            for i in config.interfaces
            if i.name == r.interface
            and (i.routing_context == context if context else i.vdom == scope)
        ]
        if r.interface and not interfaces:
            return {
                "status": "missing",
                "steps": steps,
                "issues": ["経路の出口 IF が未定義または別の VR に所属しています"],
            }
        if interfaces and all(i.status == "down" for i in interfaces):
            return {"status": "drop", "steps": steps, "issues": ["出口 IF が管理上無効です"]}
        if not r.interface:
            return {
                "status": "unknown",
                "steps": steps,
                "issues": ["出口 IF がなく再帰経路の確認が必要です"],
            }
        issues = []
        if interfaces and any(i.vdom != scope for i in interfaces):
            issues.append(
                "出口 IF は別 vsys に所属しています。外部ゾーンと両側ポリシーを確認してください"
            )
        expected_exit = query.get("destination_interface", "")
        external_zone = any(
            c.source == scope
            and c.target in {i.vdom for i in interfaces}
            and c.zone == expected_exit
            and c.visible
            for c in config.vsys_connections
        )
        if (
            expected_exit
            and interfaces
            and not external_zone
            and not any(expected_exit in (i.name, i.zone) for i in interfaces)
        ):
            issues.append("指定した出口 IF/ゾーンと選択経路の出口が一致しません")
        if config.routing.policy_routes:
            issues.append("PBR の優先評価は未確定です")
        if r.gateway:
            try:
                gateway = ip_address(r.gateway)
                nets = [
                    ip_interface(raw.strip()).network
                    for i in interfaces
                    for raw in i.ip_address.split(",")
                    if raw.strip()
                ]
                if nets and not any(gateway in net for net in nets):
                    issues.append(
                        "next-hop が出口 IF のネットワーク外です。再帰経路・IP/マスクを確認してください"
                    )
            except ValueError:
                issues.append("next-hop または IF の IP/マスクを解釈できません")
        return {"status": "unknown" if issues else "found", "steps": steps, "issues": issues}


def run_case(config, case, catalog=None, internet_services=None):
    query = case["query"]
    flow = investigate_flow(
        config,
        **query,
        application_catalog=catalog,
        internet_services=internet_services,
        candidate_limit=11,
        include_excluded=True,
    )
    route = route_path(config, query)
    exclusions = flow["excluded"]
    target = case.get("target", {})
    original_target = next(
        (
            p
            for i, p in enumerate(config.firewall_policies)
            if p.vdom == target.get("scope")
            and p.policy_id == target.get("policy_id")
            and i + 1 == target.get("order")
        ),
        None,
    )
    if original_target:
        focus = investigate_flow(
            replace(config, firewall_policies=[original_target]),
            **query,
            application_catalog=catalog,
            internet_services=internet_services,
            include_excluded=True,
        )
        for ex in focus["excluded"]:
            ex["order"] = target["order"]
            if not any((e["scope"], e["order"]) == (ex["scope"], ex["order"]) for e in exclusions):
                exclusions.append(ex)
    boundary_policies = []
    if route["steps"]:
        exit_name = route["steps"][-1]["interface"]
        exit_context = route["steps"][-1]["routing_context"]
        terminal = next(
            (
                i
                for i in config.interfaces
                if i.name == exit_name
                and i.routing_context == exit_context
                and i.vdom_assignment_known
            ),
            None,
        )
        if terminal and terminal.vdom != query["scope"]:
            source_link = next(
                (
                    c
                    for c in config.vsys_connections
                    if c.source == query["scope"] and c.target == terminal.vdom and c.visible
                ),
                None,
            )
            reverse_link = next(
                (
                    c
                    for c in config.vsys_connections
                    if c.source == terminal.vdom and c.target == query["scope"] and c.visible
                ),
                None,
            )
            if source_link and reverse_link:
                peer_query = query | {
                    "scope": terminal.vdom,
                    "source_interface": reverse_link.zone,
                    "destination_interface": terminal.zone or terminal.name,
                    "routing_context": terminal.routing_context,
                }
                peer = investigate_flow(
                    config,
                    **peer_query,
                    application_catalog=catalog,
                    internet_services=internet_services,
                    candidate_limit=11,
                    include_excluded=True,
                )
                boundary_policies = peer["policies"][:10]
                exclusions.extend(peer["excluded"])
    policies = flow["policies"]
    first = policies[0] if policies else None
    issues = list(route["issues"])
    outcome = "review"
    if first and first["status"] == "static_match":
        if first["action"] in (
            "deny",
            "reject",
            "drop",
            "reset-client",
            "reset-server",
            "reset-both",
        ):
            outcome = "block"
        elif first["action"] == "allow":
            if route["status"] in ("drop", "missing", "cycle"):
                outcome = "route_failure"
            elif route["status"] == "found" and not first["nat_enabled"] and not flow["nat"]:
                outcome = "allow_candidate"
    if not first:
        issues.append("明示ポリシーが未一致。暗黙ルール・省略設定の確認が必要です")
    elif first["status"] != "static_match":
        issues.extend(first["unknown"])
    if first and (first["nat_enabled"] or flow["nat"]):
        issues.append("NAT 変換後の条件を再確認してください")
    if first and first["policy_id"] != case.get("target", {}).get("policy_id"):
        issues.append("生成元と異なる先行ポリシーが候補になっています")
    if case["kind"] == "attack":
        issues.append(
            "攻撃のペイロードや IPS 検知は模擬していません。到達条件と検査設定の確認ケースです"
        )
        if first:
            original = config.firewall_policies[first["order"] - 1]
            if original.action == PolicyAction.ALLOW and not original.security_profiles:
                issues.append("候補の許可ポリシーにセキュリティプロファイルの参照がありません")
    mismatch = (case["expected"] == "block" and outcome == "allow_candidate") or (
        case["expected"] == "allow" and outcome in ("block", "route_failure")
    )
    return {
        "id": case["id"],
        "outcome": outcome,
        "attention": mismatch,
        "issues": list(dict.fromkeys(issues)),
        "policies": policies[:10],
        "excluded": exclusions[:12],
        "boundary_policies": boundary_policies,
        "candidate_count": len(policies),
        "candidate_limit_reached": len(policies) >= 11,
        "route": route,
        "assumptions": [
            "App-ID と補助 DB は入力した仮定値です。実機の識別・DB バージョンと一致を確認してください",
            "許可候補は疎通・攻撃検知・戻り経路の保証ではありません",
        ],
    }


def audit_parameters(config):
    issues = []
    for i in config.interfaces:
        if not i.vdom_assignment_known:
            issues.append(
                {"scope": i.vdom, "target": i.name, "message": "IF の vsys 所属が未確定です"}
            )
        if (
            i.management_access_known
            and i.status != "down"
            and any(p in i.allowed_access for p in ("http", "telnet", "ssh", "https"))
            and not i.management_permitted_ips
        ):
            issues.append(
                {
                    "scope": i.vdom,
                    "target": i.name,
                    "message": "管理アクセスの送信元制限を確認してください（データプレーンの許可とは別です）",
                }
            )
    for r in config.routes:
        try:
            network(r.destination)
        except ValueError:
            issues.append(
                {
                    "scope": r.vdom,
                    "target": r.name,
                    "message": "経路の宛先 IP/マスクを解釈できません",
                }
            )
    for c in config.vsys_connections:
        if not c.visible:
            issues.append(
                {
                    "scope": c.source,
                    "target": c.zone,
                    "message": "外部ゾーンの接続先が visible-vsys にありません",
                }
            )
    return issues[:100]
