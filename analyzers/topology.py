"""Infer a logical topology from configured interfaces and routes, never from policy alone."""

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from ipaddress import ip_interface
from typing import List

from models.config import ConfigModel, PolicyAction


@dataclass(frozen=True)
class TopologyNode:
    id: str
    scope: str
    kind: str
    label: str
    details: List[str]
    status: str = "configured"


@dataclass(frozen=True)
class TopologyEdge:
    source: str
    target: str
    relation: str
    confidence: str
    evidence: str
    directed: bool = False


@dataclass(frozen=True)
class PolicyFlow:
    scope: str
    policy: str
    source: List[str]
    destination: List[str]
    conditions: str


@dataclass
class Topology:
    nodes: List[TopologyNode] = field(default_factory=list)
    edges: List[TopologyEdge] = field(default_factory=list)
    flows: List[PolicyFlow] = field(default_factory=list)
    limitations: List[str] = field(
        default_factory=lambda: [
            "論理構造の推定です。物理配線、隣接スイッチ、実通信・到達性は設定単体では確定できません。",
            "実線は設定上の IF 所属・ルート、破線は IF アドレスから推定した直結ネットワークです。",
            "VDOM 間リンクは設定にある論理接続です。ポリシー・NAT・経路・実機状態で通信可否は変わります。",
        ]
    )

    def to_dict(self):
        return asdict(self)


def _id(*parts):
    return "n" + sha256("\x00".join(parts).encode()).hexdigest()[:20]


def _interface_scope(iface):
    return iface.vdom if iface.vdom_assignment_known else "IF 所属未確定"


def infer_topology(config: ConfigModel) -> Topology:
    topology = Topology()
    scopes = dict.fromkeys(config.device_info.vdom_list)
    for iface in config.interfaces:
        scopes[_interface_scope(iface)] = None
    for vr in config.virtual_routers:
        scopes["VR: " + vr.name] = None
    for route in config.routes:
        scope = (
            "VR: " + route.routing_context
            if config.virtual_routers and route.routing_context
            else (
                route.vdom
                if route.vdom_assignment_known
                else f"VR: {route.routing_context or '未確定'} (vsys 未確定)"
            )
        )
        scopes[scope] = None
    if not scopes:
        scopes["root"] = None
    devices = {}
    for scope in scopes:
        node_id = _id("device", scope)
        devices[scope] = node_id
        topology.nodes.append(
            TopologyNode(
                node_id,
                scope,
                "router" if scope.startswith("VR: ") else "device",
                (
                    scope[4:]
                    if scope.startswith("VR: ")
                    else config.device_info.hostname or config.device_info.device_type.value
                ),
                [scope, "同一機器内の論理区画"],
            )
        )
    interface_nodes = {}
    for index, iface in enumerate(config.interfaces):
        scope = _interface_scope(iface)
        node_id = _id("interface", scope, iface.name, str(index))
        interface_nodes[(scope, iface.name)] = node_id
        details = [
            text
            for text in (
                iface.ip_address,
                f"ゾーン: {iface.zone}" if iface.zone else "",
                f"VLAN: {iface.vlan_id}" if iface.vlan_id else "",
                f"種別: {iface.interface_type}",
            )
            if text
        ]
        topology.nodes.append(
            TopologyNode(node_id, scope, "interface", iface.name, details, iface.status)
        )
        topology.edges.append(
            TopologyEdge(
                node_id,
                devices[scope],
                "IF 所属",
                "configured",
                f"interface={iface.name}; scope={scope}; status={iface.status}",
            )
        )
        networks = []
        for raw in iface.ip_address.split(","):
            try:
                address = ip_interface(raw.strip())
                if address.ip.is_unspecified:
                    continue
                network = str(address.network)
                if network not in networks:
                    networks.append(network)
            except ValueError:
                if raw.strip():
                    topology.limitations.append(
                        f"{iface.vdom}/{iface.name}: IP 表記を解釈できません。"
                    )
        if networks:
            subnet_id = _id("subnet", node_id)
            topology.nodes.append(
                TopologyNode(subnet_id, scope, "subnet", "直結ネットワーク（推定）", networks)
            )
            topology.edges.append(
                TopologyEdge(
                    subnet_id,
                    node_id,
                    "IP から推定",
                    "inferred",
                    f"IF {iface.name} のアドレス: {iface.ip_address}",
                )
            )
    for vr in config.virtual_routers:
        router_id = devices["VR: " + vr.name]
        for iface in config.interfaces:
            if iface.name in vr.interfaces:
                topology.edges.append(
                    TopologyEdge(
                        interface_nodes[(_interface_scope(iface), iface.name)],
                        router_id,
                        "VR 所属",
                        "configured",
                        f"IF={iface.name}; VR={vr.name}",
                    )
                )
    zones = {}
    for conn in config.vsys_connections:
        if conn.source not in devices:
            continue
        key = (conn.source, conn.zone)
        if key not in zones:
            zones[key] = _id("external-zone", *key)
            topology.nodes.append(
                TopologyNode(
                    zones[key],
                    conn.source,
                    "interface",
                    conn.zone,
                    ["外部ゾーン", "接続先: " + conn.target, "visible-vsys: " + str(conn.visible)],
                )
            )
            topology.edges.append(
                TopologyEdge(
                    devices[conn.source], zones[key], "外部ゾーン所属", "configured", conn.zone
                )
            )
    for conn in config.vsys_connections:
        if not conn.visible or conn.target not in devices or (conn.source, conn.zone) not in zones:
            continue
        reverse = next(
            (
                c
                for c in config.vsys_connections
                if c.source == conn.target and c.target == conn.source and c.visible
            ),
            None,
        )
        target = zones.get((reverse.source, reverse.zone)) if reverse else devices[conn.target]
        topology.edges.append(
            TopologyEdge(
                zones[(conn.source, conn.zone)],
                target,
                "vsys 間接続",
                "configured",
                f"external zone={conn.zone}; visible-vsys={conn.target}; 経路と両側ポリシーの確認が必要",
                True,
            )
        )
    seen_pairs = set()
    interfaces = {iface.name: iface for iface in config.interfaces}
    for iface in config.interfaces:
        peer = interfaces.get(iface.vdom_link_peer)
        if (
            not peer
            or peer.vdom_link_peer != iface.name
            or not iface.vdom_assignment_known
            or not peer.vdom_assignment_known
        ):
            continue
        pair = tuple(sorted((iface.name, peer.name)))
        if pair in seen_pairs or iface.vdom == peer.vdom:
            continue
        seen_pairs.add(pair)
        topology.edges.append(
            TopologyEdge(
                interface_nodes[(_interface_scope(iface), iface.name)],
                interface_nodes[(_interface_scope(peer), peer.name)],
                "VDOM 間リンク",
                "configured",
                iface.vdom_link_evidence,
            )
        )
    for index, route in enumerate(config.routes):
        if not route.enabled:
            continue
        scope = (
            "VR: " + route.routing_context
            if config.virtual_routers and route.routing_context
            else (
                route.vdom
                if route.vdom_assignment_known
                else f"VR: {route.routing_context or '未確定'} (vsys 未確定)"
            )
        )
        route_id = _id("route", scope, route.name, str(index))
        discard = route.route_type.startswith("blackhole")
        details = [
            f"種別: {route.route_type}",
            f"IF: {route.interface or '未指定'}",
            f"next-hop: {route.gateway or ('破棄' if discard else '未指定')}",
        ]
        if route.routing_context:
            details.append(f"VR: {route.routing_context}")
        topology.nodes.append(
            TopologyNode(
                route_id,
                scope,
                "discard" if discard else "route",
                route.destination or "宛先未指定",
                details,
            )
        )
        topology.edges.append(
            TopologyEdge(
                interface_nodes.get((scope, route.interface), devices[scope]),
                route_id,
                "破棄経路" if discard else "設定ルート",
                "configured",
                f"route={route.name}; type={route.route_type}; IF={route.interface}",
            )
        )
    for route in config.routes:
        if (
            route.enabled
            and route.route_type == "next-vr"
            and "VR: " + route.routing_context in devices
            and "VR: " + route.gateway in devices
        ):
            topology.edges.append(
                TopologyEdge(
                    devices["VR: " + route.routing_context],
                    devices["VR: " + route.gateway],
                    "next-vr",
                    "configured",
                    "宛先: " + route.destination,
                    True,
                )
            )
    for policy in config.firewall_policies:
        if not policy.enabled or policy.action != PolicyAction.ALLOW:
            continue

        def names(values):
            return ", ".join(values) or "未指定"

        source = (
            "Internet Service DB（実行時に判定）"
            if policy.internet_service_source_enabled
            else names(policy.source_address)
        )
        destination = (
            "Internet Service DB（実行時に判定）"
            if policy.internet_service_enabled
            else names(policy.destination_address)
        )
        conditions = f"送信元: {source}{' 以外' if policy.source_negate else ''} → 宛先: {destination}{' 以外' if policy.destination_negate else ''}。"
        conditions += f" サービス: {'Internet Service DB' if policy.internet_service_enabled else names(policy.service)}。"
        if policy.application:
            conditions += f" アプリ: {names(policy.application)}。"
        if policy.url_categories:
            conditions += f" URL カテゴリ: {names(policy.url_categories)}。"
        if policy.rule_type != "universal":
            conditions += f" ゾーン条件: {policy.rule_type}。"
        if policy.schedule:
            conditions += f" 時間: {policy.schedule}。"
        if policy.source_users or policy.source_groups:
            conditions += f" 利用者: {names(policy.source_users + policy.source_groups)}。"
        topology.flows.append(
            PolicyFlow(
                policy.vdom,
                f"{policy.policy_id}: {policy.name}",
                policy.source_interface,
                policy.destination_interface,
                conditions,
            )
        )
    if config.parse_errors:
        topology.limitations.append(
            f"解析エラー／未対応行が {len(config.parse_errors)} 件あり、構造に欠落がある可能性があります。"
        )
    return topology
