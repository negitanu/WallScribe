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
            "許可ポリシーは通信条件として別記し、物理接続として描画しません。デフォルトルートもインターネット接続の証明ではありません。",
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
    for route in config.routes:
        scope = (
            route.vdom
            if route.vdom_assignment_known
            else f"VR: {route.routing_context or '未確定'} (vsys 未確定)"
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
                "device",
                config.device_info.hostname or config.device_info.device_type.value,
                [scope, "同一機器内の論理区画"],
            )
        )
    for index, iface in enumerate(config.interfaces):
        scope = _interface_scope(iface)
        node_id = _id("interface", scope, iface.name, str(index))
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
    for index, route in enumerate(config.routes):
        if not route.enabled:
            continue
        scope = (
            route.vdom
            if route.vdom_assignment_known
            else f"VR: {route.routing_context or '未確定'} (vsys 未確定)"
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
                devices[scope],
                route_id,
                "破棄経路" if discard else "設定ルート",
                "configured",
                f"route={route.name}; type={route.route_type}; IF={route.interface}",
            )
        )
    for policy in config.firewall_policies:
        if not policy.enabled or policy.action != PolicyAction.ALLOW:
            continue
        conditions = (
            f"src={', '.join(policy.source_address)}; dst={', '.join(policy.destination_address)}; "
        )
        conditions += f"service={', '.join(policy.service)}; app={', '.join(policy.application) or '未指定'}; "
        conditions += f"src-negate={policy.source_negate}; dst-negate={policy.destination_negate}; "
        conditions += f"schedule={policy.schedule or '未指定'}; users={', '.join(policy.source_users)}; groups={', '.join(policy.source_groups)}"
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
