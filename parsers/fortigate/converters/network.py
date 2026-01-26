#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネットワーク設定コンバーター（インターフェース、ルート、DHCP、OSPF、BGP）
"""

from typing import Any, Dict, List

from models.config import (
    BGPNeighbor,
    BGPNetwork,
    BGPRedistribute,
    BGPSettings,
    ConfigModel,
    DHCPServer,
    Interface,
    OSPFArea,
    OSPFInterface,
    OSPFRedistribute,
    OSPFSettings,
    PolicyRoute,
    Route,
)
from parsers.utils import get_nested, ip_to_cidr


def convert_interfaces(config_model: ConfigModel, parsed_config: Dict) -> None:
    """インターフェースを変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    global_cfg = parsed_config.get("global", {})
    system_interface = get_nested(global_cfg, "system interface", default={})

    if isinstance(system_interface, dict):
        for iface_name, iface_data in system_interface.items():
            if isinstance(iface_data, dict):
                # VLAN IDがある場合は "vlan" タイプとする
                vlan_id = iface_data.get("vlanid", "")
                if vlan_id:
                    iface_type = "vlan"
                else:
                    iface_type = iface_data.get("type", "physical")

                iface = Interface(
                    name=iface_data.get("_name", iface_name),
                    alias=iface_data.get("alias", ""),
                    interface_type=iface_type,
                    vlan_id=str(vlan_id),
                    vdom=iface_data.get("vdom", "root"),
                    role=iface_data.get("role", ""),
                    status="up" if iface_data.get("status") != "down" else "down",
                    description=iface_data.get("description", ""),
                )

                # IP Address (IPv4/IPv6)
                ip4 = iface_data.get("ip", "")
                ip6 = iface_data.get("ip6-address", "") or iface_data.get("ip6", "")
                ips = []
                if ip4:
                    ips.append(ip_to_cidr(ip4))
                if ip6:
                    ips.append(ip_to_cidr(ip6))
                if ips:
                    # デュアルスタックの場合は併記（既存仕様を壊さないため区切りは ", "）
                    iface.ip_address = ", ".join([x for x in ips if x])

                # Allow access
                allowaccess = iface_data.get("allowaccess", "")
                if allowaccess:
                    if isinstance(allowaccess, list):
                        iface.allowed_access = allowaccess
                    else:
                        iface.allowed_access = [allowaccess]

                config_model.interfaces.append(iface)


def convert_routes(config_model: ConfigModel, parsed_config: Dict) -> None:
    """ルーティングを変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global routes
    global_cfg = parsed_config.get("global", {})
    router_static = get_nested(global_cfg, "router static", default={})
    _add_routes_from_config(config_model, router_static, "root")
    router_static6 = get_nested(global_cfg, "router static6", default={})
    if not router_static6:
        # FortiOSの表記揺れ対策
        router_static6 = get_nested(global_cfg, "router6 static", default={})
    _add_routes_from_config(config_model, router_static6, "root", route_type="static6")

    # VDOM routes
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        router_static = get_nested(vdom_cfg, "router static", default={})
        _add_routes_from_config(config_model, router_static, vdom_name)
        router_static6 = get_nested(vdom_cfg, "router static6", default={})
        if not router_static6:
            router_static6 = get_nested(vdom_cfg, "router6 static", default={})
        _add_routes_from_config(config_model, router_static6, vdom_name, route_type="static6")


def _add_routes_from_config(
    config_model: ConfigModel, router_static: Dict, vdom: str, route_type: str = "static"
) -> None:
    """ルート設定を追加"""
    if isinstance(router_static, dict):
        for route_id, route_data in router_static.items():
            if isinstance(route_data, dict):
                # 宛先ネットワークをCIDR表記に変換
                dst = route_data.get("dst", "")
                if dst:
                    dst = ip_to_cidr(dst)

                # Blackhole route (FortiOS: set blackhole enable)
                blackhole_val = str(route_data.get("blackhole", "")).strip().lower()
                is_blackhole = blackhole_val in ("enable", "enabled", "1", "yes", "true", "on")
                effective_route_type = (
                    "blackhole6"
                    if is_blackhole and route_type == "static6"
                    else "blackhole" if is_blackhole else route_type
                )

                route = Route(
                    name=route_data.get("_name", route_id),
                    destination=dst,
                    gateway=(
                        ""
                        if is_blackhole
                        else (route_data.get("gateway", "") or route_data.get("gateway6", ""))
                    ),
                    interface=route_data.get("device", ""),
                    distance=str(route_data.get("distance", "")),
                    vdom=vdom,
                    route_type=effective_route_type,
                )
                config_model.routes.append(route)


def convert_dhcp(config_model: ConfigModel, parsed_config: Dict) -> None:
    """DHCP設定を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global DHCP
    global_cfg = parsed_config.get("global", {})
    dhcp_server = get_nested(global_cfg, "system dhcp server", default={})
    _add_dhcp_from_config(config_model, dhcp_server, "root")

    # VDOM DHCP
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        dhcp_server = get_nested(vdom_cfg, "system dhcp server", default={})
        _add_dhcp_from_config(config_model, dhcp_server, vdom_name)


def _add_dhcp_from_config(config_model: ConfigModel, dhcp_server: Dict, vdom: str) -> None:
    """DHCP設定を追加"""
    if isinstance(dhcp_server, dict):
        for dhcp_id, dhcp_data in dhcp_server.items():
            if isinstance(dhcp_data, dict):
                dhcp = DHCPServer(
                    interface=dhcp_data.get("interface", ""),
                    netmask=dhcp_data.get("netmask", ""),
                    gateway=dhcp_data.get("default-gateway", ""),
                    lease_time=str(dhcp_data.get("lease-time", "")),
                    vdom=vdom,
                )

                # IP Range（ネストされた構造を処理）
                ip_range = dhcp_data.get("ip-range", {})
                if isinstance(ip_range, dict):
                    # ip-range は {"1": {"start-ip": ..., "end-ip": ...}, ...} の構造
                    for range_id, range_data in ip_range.items():
                        if isinstance(range_data, dict):
                            # 最初のレンジを使用（複数レンジは未対応）
                            if not dhcp.start_ip:
                                dhcp.start_ip = range_data.get("start-ip", "")
                                dhcp.end_ip = range_data.get("end-ip", "")

                # DNS
                for i in range(1, 4):
                    dns = dhcp_data.get(f"dns-server{i}", "")
                    if dns:
                        dhcp.dns_servers.append(dns)

                # Exclude IP Range
                exclude_range = dhcp_data.get("exclude-range", {})
                if isinstance(exclude_range, dict):
                    for ex_id, ex_data in exclude_range.items():
                        if isinstance(ex_data, dict):
                            start = ex_data.get("start-ip", "")
                            end = ex_data.get("end-ip", "")
                            if start and end:
                                dhcp.exclude_ips.append(f"{start}-{end}")
                            elif start:
                                dhcp.exclude_ips.append(start)

                config_model.dhcp_servers.append(dhcp)


def convert_ospf(config_model: ConfigModel, parsed_config: Dict) -> None:
    """OSPF設定を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global OSPF
    global_cfg = parsed_config.get("global", {})
    router_ospf = get_nested(global_cfg, "router ospf", default={})
    if router_ospf:
        ospf = _parse_ospf_config(router_ospf, "root")
        if ospf:
            config_model.routing.ospf.append(ospf)

    router_ospf6 = get_nested(global_cfg, "router ospf6", default={})
    if router_ospf6:
        ospf6 = _parse_ospf_config(router_ospf6, "root")
        if ospf6:
            config_model.routing.ospf6.append(ospf6)

    # VDOM OSPF
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        router_ospf = get_nested(vdom_cfg, "router ospf", default={})
        if router_ospf:
            ospf = _parse_ospf_config(router_ospf, vdom_name)
            if ospf:
                config_model.routing.ospf.append(ospf)

        router_ospf6 = get_nested(vdom_cfg, "router ospf6", default={})
        if router_ospf6:
            ospf6 = _parse_ospf_config(router_ospf6, vdom_name)
            if ospf6:
                config_model.routing.ospf6.append(ospf6)


def _parse_ospf_config(ospf_config: Dict, vdom: str) -> OSPFSettings:
    """OSPF設定をパース"""
    ospf = OSPFSettings(
        router_id=ospf_config.get("router-id", ""),
        default_information_originate=ospf_config.get("default-information-originate", "")
        == "enable",
        default_metric=str(ospf_config.get("default-metric", "")),
        distance=str(ospf_config.get("distance", "")),
        vdom=vdom,
    )

    # Areas
    areas = ospf_config.get("area", {})
    if isinstance(areas, dict):
        for area_id, area_data in areas.items():
            if isinstance(area_data, dict):
                area = OSPFArea(
                    area_id=area_data.get("_name", area_id),
                    area_type=area_data.get("stub-type", "normal"),
                    authentication=area_data.get("authentication", ""),
                )
                ospf.areas.append(area)

    # OSPF Interfaces
    ospf_interfaces = ospf_config.get("ospf-interface", {})
    if isinstance(ospf_interfaces, dict):
        for iface_name, iface_data in ospf_interfaces.items():
            if isinstance(iface_data, dict):
                iface = OSPFInterface(
                    name=iface_data.get("_name", iface_name),
                    interface=iface_data.get("interface", ""),
                    area=iface_data.get("area", "0.0.0.0"),
                    cost=str(iface_data.get("cost", "")),
                    priority=str(iface_data.get("priority", "")),
                    hello_interval=str(iface_data.get("hello-interval", "")),
                    dead_interval=str(iface_data.get("dead-interval", "")),
                    network_type=iface_data.get("network-type", ""),
                    authentication=iface_data.get("authentication", ""),
                    passive=iface_data.get("passive", "") == "enable",
                )
                ospf.interfaces.append(iface)

    # Networks
    networks = ospf_config.get("network", {})
    if isinstance(networks, dict):
        for net_id, net_data in networks.items():
            if isinstance(net_data, dict):
                prefix = net_data.get("prefix", "")
                if prefix:
                    prefix = ip_to_cidr(prefix)
                area_id = net_data.get("area", "0.0.0.0")
                # Areaに紐づけてネットワークを追加
                for area in ospf.areas:
                    if area.area_id == area_id:
                        area.networks.append(prefix)
                        break
                else:
                    # 該当Areaがない場合は新規作成
                    new_area = OSPFArea(area_id=area_id, networks=[prefix])
                    ospf.areas.append(new_area)

    # Redistributes
    for proto in ["connected", "static", "bgp", "rip", "isis"]:
        redistribute = (
            ospf_config.get("redistribute", {}).get(proto, {})
            if isinstance(ospf_config.get("redistribute"), dict)
            else {}
        )
        # 直接取得も試みる
        if not redistribute:
            redistribute_section = get_nested(ospf_config, f"redistribute {proto}", default={})
            if redistribute_section:
                redistribute = redistribute_section
        if isinstance(redistribute, dict):
            status = redistribute.get("status", "") == "enable"
            if status or redistribute:
                ospf.redistributes.append(
                    OSPFRedistribute(
                        protocol=proto,
                        status=status,
                        metric=str(redistribute.get("metric", "")),
                        metric_type=str(redistribute.get("metric-type", "")),
                        routemap=redistribute.get("routemap", ""),
                    )
                )

    # Passive interfaces
    passive_iface = ospf_config.get("passive-interface", [])
    if isinstance(passive_iface, str):
        ospf.passive_interfaces = [passive_iface]
    elif isinstance(passive_iface, list):
        ospf.passive_interfaces = passive_iface

    return ospf


def convert_bgp(config_model: ConfigModel, parsed_config: Dict) -> None:
    """BGP設定を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global BGP
    global_cfg = parsed_config.get("global", {})
    router_bgp = get_nested(global_cfg, "router bgp", default={})
    if router_bgp:
        bgp = _parse_bgp_config(router_bgp, "root")
        if bgp:
            config_model.routing.bgp.append(bgp)

    # VDOM BGP
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        router_bgp = get_nested(vdom_cfg, "router bgp", default={})
        if router_bgp:
            bgp = _parse_bgp_config(router_bgp, vdom_name)
            if bgp:
                config_model.routing.bgp.append(bgp)


def _parse_bgp_config(bgp_config: Dict, vdom: str) -> BGPSettings:
    """BGP設定をパース"""
    bgp = BGPSettings(
        as_number=str(bgp_config.get("as", "")),
        router_id=bgp_config.get("router-id", ""),
        vdom=vdom,
    )

    # Neighbors
    neighbors = bgp_config.get("neighbor", {})
    if isinstance(neighbors, dict):
        for neighbor_ip, neighbor_data in neighbors.items():
            if isinstance(neighbor_data, dict):
                neighbor = BGPNeighbor(
                    ip=neighbor_data.get("_name", neighbor_ip),
                    remote_as=str(neighbor_data.get("remote-as", "")),
                    description=neighbor_data.get("description", ""),
                    update_source=neighbor_data.get("update-source", ""),
                    ebgp_multihop=str(neighbor_data.get("ebgp-multihop", "")),
                    next_hop_self=neighbor_data.get("next-hop-self", "") == "enable",
                    soft_reconfiguration=neighbor_data.get("soft-reconfiguration", "") == "enable",
                    route_map_in=neighbor_data.get("route-map-in", ""),
                    route_map_out=neighbor_data.get("route-map-out", ""),
                    activate=neighbor_data.get("activate", "") != "disable",
                    shutdown=neighbor_data.get("shutdown", "") == "enable",
                )
                bgp.neighbors.append(neighbor)

    # Networks
    networks = bgp_config.get("network", {})
    if isinstance(networks, dict):
        for net_id, net_data in networks.items():
            if isinstance(net_data, dict):
                prefix = net_data.get("prefix", "")
                if prefix:
                    prefix = ip_to_cidr(prefix)
                network = BGPNetwork(prefix=prefix, route_map=net_data.get("route-map", ""))
                bgp.networks.append(network)

    # Redistributes
    for proto in ["connected", "static", "ospf", "rip", "isis"]:
        redistribute = get_nested(bgp_config, f"redistribute {proto}", default={})
        if isinstance(redistribute, dict):
            status = redistribute.get("status", "") == "enable"
            if status or redistribute:
                bgp.redistributes.append(
                    BGPRedistribute(
                        protocol=proto, status=status, route_map=redistribute.get("route-map", "")
                    )
                )

    return bgp


def convert_policy_routes(config_model: ConfigModel, parsed_config: Dict) -> None:
    """ポリシールートを変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global Policy routes
    global_cfg = parsed_config.get("global", {})
    policy_route = get_nested(global_cfg, "router policy", default={})
    _add_policy_routes(config_model, policy_route, "root")

    # VDOM Policy routes
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        policy_route = get_nested(vdom_cfg, "router policy", default={})
        _add_policy_routes(config_model, policy_route, vdom_name)


def _add_policy_routes(config_model: ConfigModel, policy_route: Dict, vdom: str) -> None:
    """ポリシールート設定を追加"""
    if isinstance(policy_route, dict):
        for route_id, route_data in policy_route.items():
            if isinstance(route_data, dict):
                # src/dstの処理
                src = route_data.get("src", "")
                if isinstance(src, list):
                    src = " ".join(str(x) for x in src)
                elif src:
                    src = ip_to_cidr(src)

                dst = route_data.get("dst", "")
                if isinstance(dst, list):
                    dst = " ".join(str(x) for x in dst)
                elif dst:
                    dst = ip_to_cidr(dst)

                # input-device / output-device
                input_dev = route_data.get("input-device", "")
                if isinstance(input_dev, list):
                    input_dev = ", ".join(input_dev)

                output_dev = route_data.get("output-device", "")
                if isinstance(output_dev, list):
                    output_dev = ", ".join(output_dev)

                policy = PolicyRoute(
                    seq_num=route_data.get("_name", route_id),
                    src=src,
                    src_negate=route_data.get("src-negate", "") == "enable",
                    dst=dst,
                    dst_negate=route_data.get("dst-negate", "") == "enable",
                    protocol=str(route_data.get("protocol", "")),
                    input_device=input_dev,
                    output_device=output_dev,
                    gateway=route_data.get("gateway", ""),
                    action=route_data.get("action", "permit"),
                    status=route_data.get("status", "") != "disable",
                    comments=route_data.get("comments", ""),
                    vdom=vdom,
                )
                config_model.routing.policy_routes.append(policy)
