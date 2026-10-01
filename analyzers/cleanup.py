"""Review-only cleanup candidates; never emits deletion commands."""

from dataclasses import asdict

from .network import Resolver


def analyze_cleanup(config):
    result = []

    def add(kind, scope, target, evidence):
        result.append(
            dict(
                kind=kind,
                scope=scope,
                target=target,
                evidence=evidence,
                suggestion="削除前に実効設定、未解析の参照、ログ/ヒット数、運用目的、復旧方法を人が確認してください",
            )
        )

    o = config.objects
    resolver = Resolver(config)
    referenced = set()
    # Service definitions may be vendor defaults; provenance is not modeled.
    # Do not turn their presence or equivalent ports into user review tasks.
    collections = [o.addresses, o.address_groups]

    def mark(name, scope, choices):
        pending = [(name, scope)]
        while pending:
            name, scope = pending.pop()
            obj = resolver.lookup(name, scope, choices)
            if obj is None:
                continue
            key = (type(obj).__name__, obj.vdom, obj.name)
            if key in referenced:
                continue
            referenced.add(key)
            if hasattr(obj, "members"):
                pending.extend((member, obj.vdom) for member in obj.members)

    for policies in (config.firewall_policies, config.local_in_policies):
        for p in policies:  # Disabled policies retain references.
            for name in p.source_address + p.destination_address:
                mark(name, p.vdom, [o.addresses, o.address_groups])
            for name in p.service:
                mark(name, p.vdom, [o.services, o.service_groups])
    for n in config.nat_policies:
        for field in (
            "original_source",
            "original_destination",
            "translated_source",
            "translated_destination",
        ):
            for name in getattr(n, field).split(","):
                mark(name.strip(), n.vdom, [o.addresses, o.address_groups])
    # Any group reference counts even if that group itself appears unused.
    for groups, choices in [
        (o.address_groups, [o.addresses, o.address_groups]),
        (o.service_groups, [o.services, o.service_groups]),
    ]:
        for group in groups:
            for name in group.members:
                mark(name, group.vdom, choices)
    for collection in collections:
        for obj in collection:
            if (type(obj).__name__, obj.vdom, obj.name) not in referenced:
                add(
                    "未参照候補",
                    obj.vdom,
                    obj.name,
                    "解析済みポリシー・NAT・グループ内で参照が見つからない。未解析設定からの参照は未確認",
                )
    previous = []
    fields = (
        "source_interface",
        "destination_interface",
        "source_address",
        "destination_address",
        "service",
        "application",
    )
    for p in config.firewall_policies:
        if not p.enabled:
            continue
        for q in previous:
            if p.vdom != q.vdom or any(
                f.startswith("未モデル化") for f in p.unmodeled_fields + q.unmodeled_fields
            ):
                continue
            matching = all(
                getattr(p, f) == getattr(q, f)
                for f in fields
                + (
                    "schedule",
                    "source_negate",
                    "destination_negate",
                    "source_users",
                    "source_groups",
                    "internet_service_name",
                    "internet_service_enabled",
                    "internet_service_source_enabled",
                    "rule_type",
                    "url_categories",
                )
            )
            if matching:
                a, b = asdict(p), asdict(q)
                for key in ("policy_id", "name", "description", "tags"):
                    a.pop(key)
                    b.pop(key)
                kind = "重複ルール候補" if a == b else "先行ルールに隠れる可能性"
                add(
                    kind,
                    p.vdom,
                    p.policy_id,
                    f"先行ルール {q.policy_id} とモデル内の全通信条件が一致。条件の実行時評価・省略設定の既定値・上位ルールは未確認",
                )
                break
            if (
                any(
                    getattr(q, f)
                    for f in ("source_users", "source_groups", "internet_service_name")
                )
                or q.internet_service_enabled
                or q.internet_service_source_enabled
                or q.rule_type != "universal"
                or any(n.lower() != "any" for n in q.url_categories)
                or q.schedule not in ("", "always")
                or q.source_negate
                or q.destination_negate
            ):
                continue
            if all(
                any(n.lower() in ("all", "any") for n in getattr(q, f))
                or set(getattr(p, f)).issubset(getattr(q, f))
                and bool(getattr(p, f))
                for f in fields
            ):
                add(
                    "先行ルールに隠れる可能性",
                    p.vdom,
                    p.policy_id,
                    f"先行ルール {q.policy_id} の名前ベースの条件集合が包含。動的評価、既定値、ルール種別を人が確認",
                )
                break
        previous.append(p)
    return {
        "candidates": result,
        "human_decision_required": True,
        "limitations": [
            "サービス・サービスグループは標準定義と独自定義を確実に区別できないため、整理候補の対象外です。設定一覧には掲載します。",
            "削除推奨ではなく調査候補です。ログ/利用実績は解析していません。部分設定・外部管理・VPN・PBR 等の未モデル化参照があり得ます。",
        ],
    }
