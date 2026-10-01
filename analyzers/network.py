"""Conservative static flow investigation. No probing or appliance changes."""

import re
from dataclasses import asdict
from enum import Enum
from ipaddress import ip_address, ip_interface, ip_network

from analyzers.application import application_match, application_ports, isdb_match
from models.config import DeviceType


def network(value):
    value = value.strip()
    if " " in value:
        value = "/".join(value.split())
    return ip_network(value, strict=False)


class Resolver:
    def __init__(self, config):
        self.config = config
        self.indexes = {}
        self.address_cache = {}
        self.service_cache = {}
        self.cycle_counter = 0
        # A depth limit alone cannot bound a branching graph containing cycles.
        # Exhaustion propagates unknown, so it can never establish a mismatch.
        self.remaining_work = 20000
        for collection in (
            config.objects.addresses,
            config.objects.address_groups,
            config.objects.services,
            config.objects.service_groups,
        ):
            index = {}
            for obj in collection:
                index.setdefault((obj.vdom, obj.name), obj)
            self.indexes[id(collection)] = index

    def lookup(self, names, scope, collections):
        for owner in dict.fromkeys((scope, "shared")):
            for collection in collections:
                obj = self.indexes[id(collection)].get((owner, names))
                if obj is not None:
                    return obj
        return None

    def inherited_conflict(self, name, scope, origin_scope, collections):
        """Inherited references can depend on unparsed Panorama override settings."""
        if (
            self.config.device_info.device_type != DeviceType.PALOALTO
            or scope != "shared"
            or origin_scope == "shared"
        ):
            return False
        shared = self.lookup(name, "shared", collections)
        local = self.lookup(name, origin_scope, collections)
        if shared is None or local is None or local.vdom != origin_scope:
            return False
        fields = (
            "members",
            "dynamic_filter",
            "object_type",
            "value",
            "protocol",
            "port",
            "source_port",
        )
        return type(shared) is not type(local) or any(
            getattr(shared, field, None) != getattr(local, field, None) for field in fields
        )

    def address(self, name, scope, ip, seen=frozenset(), origin_scope=None):
        origin_scope = scope if origin_scope is None else origin_scope
        self.remaining_work -= 1
        if self.remaining_work < 0:
            self.cycle_counter += 1
            return None
        if (scope, name) in seen or len(seen) >= 128:
            self.cycle_counter += 1
            return None
        key = (origin_scope, scope, name, str(ip))
        if key in self.address_cache:
            return self.address_cache[key]
        before = self.cycle_counter
        result = self._address(name, scope, ip, seen, origin_scope)
        if result is not None or before == self.cycle_counter:
            self.address_cache[key] = result
        return result

    def _address(self, name, scope, ip, seen=frozenset(), origin_scope=None):
        if name.lower() in ("all", "any"):
            return True
        if self.inherited_conflict(
            name,
            scope,
            origin_scope,
            [self.config.objects.addresses, self.config.objects.address_groups],
        ):
            return None
        key = (scope, name)
        if key in seen or len(seen) >= 128:
            return None
        obj = self.lookup(
            name, scope, [self.config.objects.addresses, self.config.objects.address_groups]
        )
        if obj is None:
            try:
                return ip in network(name)
            except ValueError:
                return None
        if hasattr(obj, "members"):
            if obj.dynamic_filter:
                return None
            return self.union(
                [self.address(n, obj.vdom, ip, seen | {key}, origin_scope) for n in obj.members]
            )
        try:
            if obj.object_type == "iprange":
                start, end = obj.value.split("-", 1)
                return ip_address(start.strip()) <= ip <= ip_address(end.strip())
            if obj.object_type in ("subnet", "ip-netmask", "ipv6"):
                return ip in network(obj.value)
        except (ValueError, TypeError):
            pass
        return None

    @staticmethod
    def union(results):
        return True if True in results else None if not results or None in results else False

    def addresses(self, names, scope, ip, negate=False):
        result = self.union([self.address(n, scope, ip) for n in names])
        return not result if negate and result is not None else result

    def service(self, name, scope, protocol, port, seen=frozenset(), origin_scope=None):
        origin_scope = scope if origin_scope is None else origin_scope
        self.remaining_work -= 1
        if self.remaining_work < 0:
            self.cycle_counter += 1
            return None
        if (scope, name) in seen or len(seen) >= 128:
            self.cycle_counter += 1
            return None
        key = (origin_scope, scope, name, protocol, port)
        if key in self.service_cache:
            return self.service_cache[key]
        before = self.cycle_counter
        result = self._service(name, scope, protocol, port, seen, origin_scope)
        if result is not None or before == self.cycle_counter:
            self.service_cache[key] = result
        return result

    def _service(self, name, scope, protocol, port, seen=frozenset(), origin_scope=None):
        if name.lower() in ("all", "any"):
            return True
        if self.inherited_conflict(
            name,
            scope,
            origin_scope,
            [self.config.objects.services, self.config.objects.service_groups],
        ):
            return None
        key = (scope, name)
        if key in seen or len(seen) >= 128:
            return None
        obj = self.lookup(
            name, scope, [self.config.objects.services, self.config.objects.service_groups]
        )
        if obj is None:
            return None  # Builtins and application-default depend on vendor/version/App-ID.
        if hasattr(obj, "members"):
            return self.union(
                [
                    self.service(n, obj.vdom, protocol, port, seen | {key}, origin_scope)
                    for n in obj.members
                ]
            )
        if obj.protocol.upper() != protocol:
            return None if "/" in obj.protocol or obj.protocol.upper() == "IP" else False
        if getattr(obj, "source_port", "") or ":" in obj.port:
            return None
        try:
            ranges = re.split(r"[,\s]+", obj.port.strip())
            if not obj.port or any(not re.fullmatch(r"\d+(?:-\d+)?", p) for p in ranges):
                return None
            parsed = [(int(p.split("-")[0]), int(p.split("-")[-1])) for p in ranges]
            if any(start < 0 or end > 65535 or start > end for start, end in parsed):
                return None
            return any(start <= port <= end for start, end in parsed)
        except ValueError:
            return None


def flow_snapshot(config):
    """Small allowlist: never embed VPN secrets, users' passwords or raw input."""

    def serial(obj):
        return {k: v.value if isinstance(v, Enum) else v for k, v in asdict(obj).items()}

    return {
        "vendor": config.device_info.device_type.value,
        "policies": [serial(p) for p in config.firewall_policies],
        "addresses": [serial(p) for p in config.objects.addresses],
        "address_groups": [serial(p) for p in config.objects.address_groups],
        "services": [serial(p) for p in config.objects.services],
        "service_groups": [serial(p) for p in config.objects.service_groups],
        "routes": [serial(p) for p in config.routes],
        "interfaces": [serial(p) for p in config.interfaces],
        "nat": [serial(p) for p in config.nat_policies],
        "virtual_routers": [serial(p) for p in config.virtual_routers],
        "applications": [serial(p) for p in config.applications],
    }


LIMITATIONS = [
    "静的設定の候補照合です。通信の成功・失敗を確定しません。最終判断は担当者が行ってください。",
    "稼働中の経路、SD-WAN/PBR、VPN、戻り経路、隣接機器、セッション状態、上位/下位ルールを実機で確認してください。",
    "NAT は設定候補を示すだけです。適用順序、変換前後のアドレス/ゾーンとポートを人が確認してください。",
    "未一致も疎通不可の証明ではありません。暗黙ルールや未解析設定は元の設定と実機で確認してください。",
]


def nat_candidates(config, resolver, src, dst, scope):
    candidates = []
    for n in config.nat_policies:
        if not n.enabled or n.vdom != scope:
            continue
        checks = {}
        for label, raw, ip in [
            ("変換前送信元", n.original_source, src),
            ("変換前宛先", n.original_destination or n.external_ip, dst),
        ]:
            checks[label] = (
                resolver.addresses([value.strip() for value in raw.split(",")], scope, ip)
                if raw
                else None
            )
        if False in checks.values():
            continue
        item = asdict(n)
        item["evidence"] = [
            label + "アドレスが一致" for label, value in checks.items() if value is True
        ]
        item["unknown"] = [
            label + "の選択条件を確定できない" for label, value in checks.items() if value is None
        ]
        item["unknown"].append(
            "IF/ゾーン・サービス・ポート・適用順序・実効ルールを人が確認。アドレス照合だけでは適用を確定しません"
        )
        candidates.append(item)
    return candidates


def interface_identity(config, scope, actual):
    """Resolve interface input to its security zone without inventing membership."""
    if not actual or actual.lower() in ("any", "all"):
        return None
    interfaces = [i for i in config.interfaces if i.name == actual]
    if not interfaces:
        return actual  # The supplied value is a zone name.
    owned = [i for i in interfaces if i.vdom == scope and i.vdom_assignment_known]
    if not owned:
        return None
    identities = {
        i.zone or (i.name if config.device_info.device_type != DeviceType.PALOALTO else "")
        for i in owned
    }
    return next(iter(identities)) if len(identities) == 1 and "" not in identities else None


def interface_match(config, names, scope, actual):
    if any(n.lower() in ("any", "all") for n in names):
        return True
    identity = interface_identity(config, scope, actual)
    if identity is None:
        return None
    return identity in names or actual in names


def investigate_flow(
    config,
    source,
    destination,
    protocol="TCP",
    port=443,
    scope="root",
    source_interface="",
    destination_interface="",
    application="",
    application_catalog=None,
    internet_services=None,
    routing_context="",
    candidate_limit=None,
    include_excluded=False,
):
    src, dst = ip_address(source), ip_address(destination)
    protocol = protocol.upper()
    if protocol not in ("TCP", "UDP") or not 1 <= int(port) <= 65535:
        raise ValueError("TCP/UDP と 1〜65535 の宛先ポートを指定してください")
    if src.version != dst.version:
        raise ValueError("送信元と宛先の IP バージョンを合わせてください")
    resolver = Resolver(config)
    candidates, excluded = [], []
    for index, p in enumerate(config.firewall_policies):
        if p.vdom != scope or not p.enabled:
            continue
        if candidate_limit is not None and len(candidates) >= candidate_limit:
            break
        evidence, unknown = [], []
        checks = {
            "送信元アドレス": resolver.addresses(p.source_address, scope, src, p.source_negate),
            "宛先アドレス": resolver.addresses(
                p.destination_address, scope, dst, p.destination_negate
            ),
            "サービス": resolver.union(
                [resolver.service(n, scope, protocol, int(port)) for n in p.service]
            ),
        }
        for label, names, actual in [
            ("送信元 IF/ゾーン", p.source_interface, source_interface),
            ("宛先 IF/ゾーン", p.destination_interface, destination_interface),
        ]:
            checks[label] = interface_match(config, names, scope, actual)
        if p.internet_service_source_enabled:
            checks["送信元アドレス"] = isdb_match(
                p.internet_service_source_name,
                src,
                protocol,
                int(port),
                internet_services or {},
                p.internet_service_source_negate,
            )
        if p.internet_service_enabled:
            checks["宛先アドレス"] = isdb_match(
                p.internet_service_name,
                dst,
                protocol,
                int(port),
                internet_services or {},
                p.internet_service_negate,
            )
            checks["サービス"] = checks["宛先アドレス"]
        if application:
            checks["App-ID（仮定）"] = application_match(
                config, p.application or ["any"], scope, application
            )
            if "application-default" in p.service:
                checks["サービス"] = resolver.union(
                    [
                        (
                            application_ports(
                                config,
                                scope,
                                application,
                                protocol,
                                int(port),
                                application_catalog or {},
                            )
                            if n == "application-default"
                            else resolver.service(n, scope, protocol, int(port))
                        )
                        for n in p.service
                    ]
                )
        if p.rule_type in ("intrazone", "interzone"):
            source_zone = interface_identity(config, scope, source_interface)
            destination_zone = interface_identity(config, scope, destination_interface)
            same_zone = (
                source_zone == destination_zone if source_zone and destination_zone else None
            )
            checks["ゾーン種別"] = (
                (same_zone if p.rule_type == "intrazone" else not same_zone)
                if same_zone is not None
                else None
            )
            if p.rule_type == "intrazone":
                checks["宛先 IF/ゾーン"] = checks["ゾーン種別"]
        elif p.rule_type != "universal":
            checks["ゾーン種別"] = None
        if False in checks.values():
            if include_excluded and len(excluded) < 10:
                excluded.append(
                    {
                        "order": index + 1,
                        "scope": scope,
                        "policy_id": p.policy_id,
                        "name": p.name,
                        "action": p.action.value,
                        "mismatches": [
                            label + "が不一致" for label, value in checks.items() if value is False
                        ],
                    }
                )
            continue
        for label, result in checks.items():
            (evidence if result is True else unknown).append(
                label
                + (
                    "が一致"
                    if result is True
                    else "を確定できない（未解決参照・動的条件・入力不足）"
                )
            )
        if p.schedule and p.schedule != "always":
            unknown.append("スケジュールの実行時条件")
        if not application and any(n.lower() != "any" for n in p.application):
            unknown.append("App-ID の実通信判定")
        if any(n.lower() != "any" for n in p.source_users) or p.source_groups:
            unknown.append("ユーザー/グループの実行時情報")
        if any(n.lower() != "any" for n in p.url_categories):
            unknown.append("URL カテゴリの実通信判定")
        if (
            p.internet_service_name
            or p.internet_service_enabled
            or p.internet_service_source_enabled
        ):
            if not internet_services:
                unknown.append("Internet Service DB の実行時情報")
        unknown.extend(getattr(p, "unmodeled_fields", []))
        if config.parse_errors or config.unsupported_sections:
            unknown.append("未解析設定があり実効ルール順序は未保証")
        candidates.append(
            {
                "order": index + 1,
                "scope": scope,
                "policy_id": p.policy_id,
                "name": p.name,
                "action": p.action.value,
                "status": "needs_review" if unknown else "static_match",
                "evidence": evidence,
                "unknown": unknown,
                "nat_enabled": p.nat_enabled,
                "preceding_candidates": [c["policy_id"] for c in candidates],
            }
        )
    routes = []
    for r in config.routes:
        if (
            not r.enabled
            or (routing_context and r.routing_context != routing_context)
            or (not routing_context and r.vdom_assignment_known and r.vdom != scope)
        ):
            continue
        try:
            net = network(r.destination)
            if dst in net:
                routes.append(
                    {
                        "name": r.name,
                        "destination": r.destination,
                        "gateway": r.gateway,
                        "routing_context": r.routing_context,
                        "route_type": r.route_type,
                        "interface": r.interface,
                        "prefix_length": net.prefixlen,
                        "distance": r.distance,
                        "priority": r.priority,
                        "evidence": "宛先が設定プレフィックス内。稼働状態・優先度の確認が必要",
                        "scope_known": r.vdom_assignment_known,
                    }
                )
        except ValueError:
            routes.append(
                {
                    "name": r.name,
                    "destination": r.destination,
                    "evidence": "宛先形式を解釈できないため除外できない",
                    "prefix_length": -1,
                }
            )
    for iface in config.interfaces:
        if iface.status == "down" or not iface.vdom_assignment_known or iface.vdom != scope:
            continue
        for value in iface.ip_address.split(","):
            try:
                net = ip_interface(value.strip()).network
                if dst in net:
                    routes.append(
                        {
                            "name": "直結候補",
                            "destination": str(net),
                            "interface": iface.name,
                            "prefix_length": net.prefixlen,
                            "evidence": "IF 設定から推定。実際の IF/ARP/ND 状態を確認",
                        }
                    )
            except ValueError:
                pass
    result = {
        "query": {
            "source": str(src),
            "destination": str(dst),
            "protocol": protocol,
            "port": int(port),
            "scope": scope,
        },
        "verdict": "human_review_required",
        "policies": candidates,
        "routes": sorted(routes, key=lambda r: -r["prefix_length"]),
        "nat": nat_candidates(config, resolver, src, dst, scope),
        "limitations": LIMITATIONS,
    }

    if include_excluded:
        result["excluded"] = excluded
    return result
