#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
オブジェクト定義コンバーター（アドレス、サービス）
"""

from typing import Dict

from models.config import (
    ConfigModel, AddressObject, AddressGroup,
    ServiceObject, ServiceGroup
)
from parsers.utils import get_nested


def convert_objects(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
    """オブジェクト定義を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global objects
    global_cfg = parsed_config.get("global", {})
    _add_objects_from_config(config_model, global_cfg, "root")

    # VDOM objects
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        _add_objects_from_config(config_model, vdom_cfg, vdom_name)


def _add_objects_from_config(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """オブジェクトを追加"""
    _add_address_objects(config_model, config, vdom)
    _add_address_groups(config_model, config, vdom)
    _add_service_objects(config_model, config, vdom)
    _add_service_groups(config_model, config, vdom)


def _add_address_objects(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """アドレスオブジェクトを追加"""
    firewall_address = get_nested(config, "firewall address", default={})
    if isinstance(firewall_address, dict):
        for addr_name, addr_data in firewall_address.items():
            if isinstance(addr_data, dict):
                addr_type = addr_data.get("type", "subnet")
                if addr_type == "fqdn":
                    value = addr_data.get("fqdn", "")
                elif addr_type == "iprange":
                    start = addr_data.get("start-ip", "")
                    end = addr_data.get("end-ip", "")
                    value = f"{start}-{end}" if start and end else ""
                else:
                    value = addr_data.get("subnet", "")

                addr_obj = AddressObject(
                    name=addr_data.get("_name", addr_name),
                    object_type=addr_type,
                    value=value,
                    vdom=vdom,
                    description=addr_data.get("comment", "")
                )
                config_model.objects.addresses.append(addr_obj)


def _add_address_groups(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """アドレスグループを追加"""
    firewall_addrgrp = get_nested(config, "firewall addrgrp", default={})
    if isinstance(firewall_addrgrp, dict):
        for grp_name, grp_data in firewall_addrgrp.items():
            if isinstance(grp_data, dict):
                members = grp_data.get("member", [])
                if isinstance(members, str):
                    members = [members]
                grp_obj = AddressGroup(
                    name=grp_data.get("_name", grp_name),
                    members=members,
                    vdom=vdom,
                    description=grp_data.get("comment", "")
                )
                config_model.objects.address_groups.append(grp_obj)


def _normalize_port_value(value) -> str:
    """ポート値を正規化（リストの場合は結合、文字列の場合はそのまま）"""
    if not value:
        return ""
    if isinstance(value, list):
        # リストの場合は結合（空白や空文字列を除去）
        return ", ".join(str(v).strip() for v in value if v and str(v).strip())
    return str(value).strip()


def _normalize_protocol_value(value) -> str:
    """プロトコル値を正規化（リストの場合は最初の要素、文字列の場合はそのまま）"""
    if not value:
        return ""
    if isinstance(value, list):
        # リストの場合は最初の要素を使用
        return str(value[0]).strip().upper() if value else ""
    return str(value).strip().upper()


def _add_service_objects(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """サービスオブジェクトを追加"""
    firewall_service = get_nested(config, "firewall service custom", default={})
    if isinstance(firewall_service, dict):
        for svc_name, svc_data in firewall_service.items():
            if isinstance(svc_data, dict):
                # プロトコルとポート範囲を取得（リスト/文字列の両方に対応）
                protocol = _normalize_protocol_value(svc_data.get("protocol", ""))
                tcp_port = _normalize_port_value(svc_data.get("tcp-portrange", ""))
                udp_port = _normalize_port_value(svc_data.get("udp-portrange", ""))
                sctp_port = _normalize_port_value(svc_data.get("sctp-portrange", ""))
                icmp_code = _normalize_port_value(svc_data.get("icmpcode", ""))
                icmp_type = _normalize_port_value(svc_data.get("icmptype", ""))
                
                # プロトコルを推測（tcp-portrange/udp-portrangeから）
                protocols = []
                port_parts = []
                
                if tcp_port:
                    protocols.append("TCP")
                    port_parts.append(tcp_port)
                
                if udp_port:
                    protocols.append("UDP")
                    port_parts.append(udp_port)
                
                if sctp_port:
                    protocols.append("SCTP")
                    port_parts.append(sctp_port)
                
                # ICMPの処理
                if icmp_type or icmp_code:
                    protocols.append("ICMP")
                    icmp_value = ""
                    if icmp_type:
                        icmp_value = f"type={icmp_type}"
                    if icmp_code:
                        if icmp_value:
                            icmp_value += f",code={icmp_code}"
                        else:
                            icmp_value = f"code={icmp_code}"
                    port_parts.append(icmp_value)
                
                # 既存のprotocolフィールドがある場合、それを優先（ただし、ポート範囲から推測したものと統合）
                if protocol and protocol not in ["TCP", "UDP", "SCTP", "ICMP", "IP"]:
                    # 不明なプロトコルの場合は既存の値を保持
                    if not protocols:
                        protocols.append(protocol)
                
                # プロトコルが空の場合、ポート範囲から推測
                if not protocols:
                    if protocol:
                        protocols.append(protocol)
                    else:
                        protocols.append("IP")  # デフォルト
                
                # プロトコル文字列を生成（複数の場合は結合）
                protocol_str = "/".join(protocols) if len(protocols) > 1 else protocols[0]
                
                # ポート文字列を生成（プロトコル情報は含めない）
                if port_parts:
                    # 重複を除去して結合
                    unique_ports = []
                    for port in port_parts:
                        if port and port not in unique_ports:
                            unique_ports.append(port)
                    port_str = ", ".join(unique_ports)
                elif protocol_str in ["TCP", "UDP", "SCTP"]:
                    # プロトコルはあるがポートが指定されていない場合
                    port_str = ""
                else:
                    port_str = ""
                
                svc_obj = ServiceObject(
                    name=svc_data.get("_name", svc_name),
                    protocol=protocol_str,
                    port=port_str,
                    vdom=vdom,
                    description=svc_data.get("comment", "")
                )
                config_model.objects.services.append(svc_obj)


def _add_service_groups(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """サービスグループを追加"""
    firewall_svcgrp = get_nested(config, "firewall service group", default={})
    if isinstance(firewall_svcgrp, dict):
        for grp_name, grp_data in firewall_svcgrp.items():
            if isinstance(grp_data, dict):
                members = grp_data.get("member", [])
                if isinstance(members, str):
                    members = [members]
                grp_obj = ServiceGroup(
                    name=grp_data.get("_name", grp_name),
                    members=members,
                    vdom=vdom,
                    description=grp_data.get("comment", "")
                )
                config_model.objects.service_groups.append(grp_obj)
