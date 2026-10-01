"""Reject oversized, malformed or misleading test assumptions before evaluation."""

import json
from ipaddress import ip_address, ip_network

from analyzers.application import ports_match


def read_json(value, limit=256000):
    if len(value.encode("utf-8")) > limit:
        raise ValueError("補助データが大きすぎます")
    return json.loads(value) if value else {}


def catalogs(data):
    if not isinstance(data, dict) or set(data) - {
        "applications",
        "internet_services",
        "provenance",
    }:
        raise ValueError("補助 DB の形式が不正です")
    provenance = data.get("provenance", "")
    if data and (
        not isinstance(provenance, str) or not provenance.strip() or len(provenance) > 300
    ):
        raise ValueError("補助 DB に provenance（出典・DB バージョン・取得日時）を記入してください")
    apps, services = data.get("applications", {}), data.get("internet_services", {})
    for collection in (apps, services):
        if not isinstance(collection, dict) or len(collection) > 1000:
            raise ValueError("補助 DB は各 1000 項目以内にしてください")

    def specs(values):
        if (
            not isinstance(values, list)
            or not values
            or len(values) > 50
            or any(not isinstance(v, str) or len(v) > 200 for v in values)
        ):
            raise ValueError("ポート定義が不正です")
        for v in values:
            if (
                v.split("/")[0].upper() not in ("TCP", "UDP")
                or ports_match([v], v.split("/")[0].upper(), 443) is None
            ):
                raise ValueError("ポートは tcp/443 や udp/53-54 で指定してください")

    for name, values in apps.items():
        if not isinstance(name, str) or len(name) > 128:
            raise ValueError("App-ID 名が不正です")
        specs(values)
    for name, rows in services.items():
        if len(name) > 128 or not isinstance(rows, list) or not rows or len(rows) > 100:
            raise ValueError("ISDB レコードが不正です")
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"network", "ports"}:
                raise ValueError("ISDB は network と ports を指定してください")
            ip_network(row["network"], strict=False)
            specs(row["ports"])
    return apps, services, provenance


def validate_cases(cases, config):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 200:
        raise ValueError("ケースは 1〜200 件にしてください")
    scopes = (
        set(config.device_info.vdom_list)
        | {p.vdom for p in config.firewall_policies}
        | {i.vdom for i in config.interfaces}
    )
    contexts = {v.name for v in config.virtual_routers}
    ids = set()
    interface_names = {}
    for interface in config.interfaces:
        interface_names.setdefault(interface.vdom, set()).update((interface.name, interface.zone))
    for policy in config.firewall_policies:
        interface_names.setdefault(policy.vdom, set()).update(policy.source_interface + policy.destination_interface)
    for connection in config.vsys_connections:
        interface_names.setdefault(connection.source, set()).add(connection.zone)
    allowed = {
        "source",
        "destination",
        "protocol",
        "port",
        "scope",
        "source_interface",
        "destination_interface",
        "application",
        "routing_context",
    }
    for c in cases:
        if (
            not isinstance(c, dict)
            or not isinstance(c.get("id"), str)
            or not 1 <= len(c["id"]) <= 100
            or c["id"] in ids
        ):
            raise ValueError("ケース ID が不正または重複しています")
        ids.add(c["id"])
        if c.get("expected") not in ("allow", "block") or c.get("kind") not in (
            "policy",
            "boundary",
            "attack",
            "custom",
        ):
            raise ValueError("期待値・ケース種別が不正です")
        q = c.get("query")
        if (
            not isinstance(q, dict)
            or set(q) - allowed
            or not {"source", "destination", "scope", "protocol", "port"} <= set(q)
        ):
            raise ValueError("通信条件の形式が不正です")
        if any(not isinstance(v, str) or len(v) > 200 for k, v in q.items() if k != "port"):
            raise ValueError("通信条件は 200 文字以内の文字列で指定してください")
        src, dst = ip_address(q["source"]), ip_address(q["destination"])
        if (
            src.version != dst.version
            or q["protocol"] not in ("TCP", "UDP")
            or type(q["port"]) is not int
            or not 1 <= q["port"] <= 65535
        ):
            raise ValueError("IP・プロトコル・ポートが不正です")
        if q["scope"] not in scopes or (
            q.get("routing_context") and q["routing_context"] not in contexts
        ):
            raise ValueError("存在しない区画・仮想ルーターです")
        for field in ("source_interface", "destination_interface"):
            actual = q.get(field, "")
            if actual and (actual.lower() in ("any", "all") or actual not in interface_names.get(q["scope"], ())):
                raise ValueError("IF / ゾーンは指定区画に存在する名前で指定してください")
        if any(
            a.name == q.get("application")
            and a.vdom in (q["scope"], "shared")
            and (a.dynamic or a.members)
            for a in config.applications
        ):
            raise ValueError(
                "App-ID の仮定は具体的なアプリを指定してください。グループ・フィルターは識別値ではありません"
            )
        if q.get("routing_context") and q.get("source_interface"):
            entries = [
                i
                for i in config.interfaces
                if i.vdom == q["scope"]
                and i.vdom_assignment_known
                and q["source_interface"] in (i.name, i.zone)
            ]
            if entries and not any(i.routing_context == q["routing_context"] for i in entries):
                raise ValueError("入口 IF と仮想ルーターの所属が一致しません")
        # Client annotations do not affect outcomes and never become executable text.
        if not isinstance(c.get("name", ""), str) or len(c.get("name", "")) > 200:
            raise ValueError("ケース名が不正です")
        target = c.get("target", {})
        if not isinstance(target, dict) or set(target) - {"scope", "policy_id", "order", "name"}:
            raise ValueError("生成元ポリシーの形式が不正です")
        if any(
            not isinstance(target[k], str) for k in ("scope", "policy_id", "name") if k in target
        ):
            raise ValueError("生成元ポリシーの参照が不正です")
        if "order" in target and (
            type(target["order"]) is not int
            or not 1 <= target["order"] <= len(config.firewall_policies)
        ):
            raise ValueError("生成元ポリシーの順序が不正です")
    return cases
