#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネットワーク設定コンバーター（インターフェース、ルート、DHCP）
"""

from typing import Dict

from models.config import ConfigModel, Interface, Route, DHCPServer
from parsers.utils import get_nested, ip_to_cidr


def convert_interfaces(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
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
                    description=iface_data.get("description", "")
                )

                # IP Address
                ip = iface_data.get("ip", "")
                if ip:
                    iface.ip_address = ip_to_cidr(ip)

                # Allow access
                allowaccess = iface_data.get("allowaccess", "")
                if allowaccess:
                    if isinstance(allowaccess, list):
                        iface.allowed_access = allowaccess
                    else:
                        iface.allowed_access = [allowaccess]

                config_model.interfaces.append(iface)


def convert_routes(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
    """ルーティングを変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global routes
    global_cfg = parsed_config.get("global", {})
    router_static = get_nested(global_cfg, "router static", default={})
    _add_routes_from_config(config_model, router_static, "root")

    # VDOM routes
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        router_static = get_nested(vdom_cfg, "router static", default={})
        _add_routes_from_config(config_model, router_static, vdom_name)


def _add_routes_from_config(
    config_model: ConfigModel,
    router_static: Dict,
    vdom: str
) -> None:
    """ルート設定を追加"""
    if isinstance(router_static, dict):
        for route_id, route_data in router_static.items():
            if isinstance(route_data, dict):
                route = Route(
                    name=route_data.get("_name", route_id),
                    destination=route_data.get("dst", ""),
                    gateway=route_data.get("gateway", ""),
                    interface=route_data.get("device", ""),
                    distance=str(route_data.get("distance", "")),
                    vdom=vdom,
                    route_type="static"
                )
                config_model.routes.append(route)


def convert_dhcp(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
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


def _add_dhcp_from_config(
    config_model: ConfigModel,
    dhcp_server: Dict,
    vdom: str
) -> None:
    """DHCP設定を追加"""
    if isinstance(dhcp_server, dict):
        for dhcp_id, dhcp_data in dhcp_server.items():
            if isinstance(dhcp_data, dict):
                dhcp = DHCPServer(
                    interface=dhcp_data.get("interface", ""),
                    netmask=dhcp_data.get("netmask", ""),
                    gateway=dhcp_data.get("default-gateway", ""),
                    lease_time=str(dhcp_data.get("lease-time", "")),
                    vdom=vdom
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
