#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ポリシー・NATコンバーター
"""

from typing import Dict

from models.config import ConfigModel, FirewallPolicy, LocalInPolicy, NATPolicy, PolicyAction
from parsers.utils import get_nested, to_list


def _merge_lists(*values) -> list:
    """FortiOS の IPv4/IPv6 など複数キーを重複なしで統合する。"""
    merged = []
    for value in values:
        for item in to_list(value):
            if item not in merged:
                merged.append(item)
    return merged


def convert_policies(config_model: ConfigModel, parsed_config: Dict) -> None:
    """ポリシーを変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global policies
    global_cfg = parsed_config.get("global", {})
    _add_policies_from_config(config_model, global_cfg, "root")

    # VDOM policies
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        _add_policies_from_config(config_model, vdom_cfg, vdom_name)


def _add_policies_from_config(config_model: ConfigModel, config: Dict, vdom: str) -> None:
    """ポリシーを追加"""
    firewall_policy = get_nested(config, "firewall policy", default={})
    if isinstance(firewall_policy, dict):
        for policy_id, policy_data in firewall_policy.items():
            if isinstance(policy_data, dict):
                action = _parse_action(policy_data.get("action", ""))

                # セキュリティプロファイル
                security_profiles = _extract_security_profiles(policy_data)

                policy = FirewallPolicy(
                    policy_id=str(policy_data.get("policyid", policy_id)),
                    name=policy_data.get("name", ""),
                    source_interface=to_list(policy_data.get("srcintf", [])),
                    destination_interface=to_list(policy_data.get("dstintf", [])),
                    source_address=_merge_lists(
                        policy_data.get("srcaddr", []),
                        policy_data.get("srcaddr6", []),
                    ),
                    destination_address=_merge_lists(
                        policy_data.get("dstaddr", []),
                        policy_data.get("dstaddr6", []),
                    ),
                    internet_service_name=_merge_lists(
                        policy_data.get("internet-service-name", []),
                        policy_data.get("internet-service-id", []),
                    ),
                    service=to_list(policy_data.get("service", [])),
                    application=to_list(policy_data.get("application", [])),
                    action=action,
                    nat_enabled=policy_data.get("nat", "") == "enable",
                    log_enabled=policy_data.get("logtraffic", "") in ("enable", "all", "utm"),
                    security_profiles=security_profiles,
                    vdom=vdom,
                    enabled=policy_data.get("status", "") != "disable",
                    description=policy_data.get("comments", ""),
                    tags=_merge_lists(policy_data.get("tag", []), policy_data.get("tags", [])),
                )

                config_model.firewall_policies.append(policy)


def _parse_action(action_str: str) -> PolicyAction:
    """アクション文字列をPolicyActionに変換

    仕様: action が未定義（キーなし/空）なら拒否(deny)として扱う。
    """
    action_str = (action_str or "").strip()
    if not action_str or action_str == "unset":
        return PolicyAction.DENY
    if action_str == "accept":
        return PolicyAction.ALLOW
    if action_str == "deny":
        return PolicyAction.DENY
    if action_str == "drop":
        return PolicyAction.DROP
    return PolicyAction.UNKNOWN


def _extract_security_profiles(policy_data: Dict) -> list:
    """ポリシーからセキュリティプロファイルを抽出"""
    security_profiles = []
    if policy_data.get("av-profile"):
        security_profiles.append(f"AV:{policy_data.get('av-profile')}")
    if policy_data.get("webfilter-profile"):
        security_profiles.append(f"Web:{policy_data.get('webfilter-profile')}")
    if policy_data.get("application-list"):
        security_profiles.append(f"App:{policy_data.get('application-list')}")
    if policy_data.get("ips-sensor"):
        security_profiles.append(f"IPS:{policy_data.get('ips-sensor')}")
    if policy_data.get("ssl-ssh-profile"):
        security_profiles.append(f"SSL:{policy_data.get('ssl-ssh-profile')}")
    return security_profiles


def convert_local_in_policies(config_model: ConfigModel, parsed_config: Dict) -> None:
    """Local-in ポリシーを変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global local-in policies
    global_cfg = parsed_config.get("global", {})
    _add_local_in_policies_from_config(config_model, global_cfg, "root")

    # VDOM local-in policies
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        _add_local_in_policies_from_config(config_model, vdom_cfg, vdom_name)


def _add_local_in_policies_from_config(config_model: ConfigModel, config: Dict, vdom: str) -> None:
    """Local-in ポリシーを追加"""
    local_in_policy = get_nested(config, "firewall local-in-policy", default={})
    if isinstance(local_in_policy, dict):
        for policy_id, policy_data in local_in_policy.items():
            if isinstance(policy_data, dict):
                action = _parse_action(policy_data.get("action", ""))

                policy = LocalInPolicy(
                    policy_id=str(policy_data.get("policyid", policy_id)),
                    source_interface=policy_data.get("intf", ""),
                    source_address=to_list(policy_data.get("srcaddr", [])),
                    destination_address=to_list(policy_data.get("dstaddr", [])),
                    service=to_list(policy_data.get("service", [])),
                    action=action,
                    schedule=policy_data.get("schedule", ""),
                    vdom=vdom,
                    enabled=policy_data.get("status", "") != "disable",
                    description=policy_data.get("comments", ""),
                )
                config_model.local_in_policies.append(policy)


def convert_nat(config_model: ConfigModel, parsed_config: Dict) -> None:
    """NAT設定を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global NAT
    global_cfg = parsed_config.get("global", {})
    _add_nat_from_config(config_model, global_cfg, "root")

    # VDOM NAT
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        _add_nat_from_config(config_model, vdom_cfg, vdom_name)


def _add_nat_from_config(config_model: ConfigModel, config: Dict, vdom: str) -> None:
    """NAT設定を追加"""
    _add_vip_nat(config_model, config, vdom)
    _add_ippool_nat(config_model, config, vdom)
    _add_central_snat(config_model, config, vdom)


def _add_vip_nat(config_model: ConfigModel, config: Dict, vdom: str) -> None:
    """VIP (DNAT) を追加"""
    firewall_vip = get_nested(config, "firewall vip", default={})
    if isinstance(firewall_vip, dict):
        for vip_name, vip_data in firewall_vip.items():
            if isinstance(vip_data, dict):
                mappedip = vip_data.get("mappedip", "")
                if isinstance(mappedip, list):
                    mappedip = ", ".join(mappedip)

                nat = NATPolicy(
                    name=vip_data.get("_name", vip_name),
                    nat_type="vip",
                    external_interface=vip_data.get("extintf", ""),
                    external_ip=vip_data.get("extip", ""),
                    internal_ip=mappedip,
                    original_destination=vip_data.get("extip", ""),
                    translated_destination=mappedip,
                    interface=vip_data.get("extintf", ""),
                    port_forward=vip_data.get("portforward", "") == "enable",
                    original_port=vip_data.get("extport", ""),
                    translated_port=vip_data.get("mappedport", ""),
                    vdom=vdom,
                    description=vip_data.get("comment", ""),
                )
                config_model.nat_policies.append(nat)


def _add_ippool_nat(config_model: ConfigModel, config: Dict, vdom: str) -> None:
    """IP Pool (SNAT) を追加"""
    firewall_ippool = get_nested(config, "firewall ippool", default={})
    if isinstance(firewall_ippool, dict):
        for pool_name, pool_data in firewall_ippool.items():
            if isinstance(pool_data, dict):
                start_ip = pool_data.get("startip", "")
                end_ip = pool_data.get("endip", "")

                # translated_source の構築
                if start_ip and end_ip and start_ip != end_ip:
                    translated_source = f"{start_ip}-{end_ip}"
                elif start_ip:
                    translated_source = start_ip
                else:
                    translated_source = ""

                nat = NATPolicy(
                    name=pool_data.get("_name", pool_name),
                    nat_type="ippool",
                    pool_type=pool_data.get("type", "overload"),
                    translated_source=translated_source,
                    interface=pool_data.get("associated-interface", ""),
                    vdom=vdom,
                    description=pool_data.get("comments", ""),
                )
                config_model.nat_policies.append(nat)


def _add_central_snat(config_model: ConfigModel, config: Dict, vdom: str) -> None:
    """Central SNAT Map を追加"""
    central_snat = get_nested(config, "firewall central-snat-map", default={})
    if isinstance(central_snat, dict):
        for snat_id, snat_data in central_snat.items():
            if isinstance(snat_data, dict):
                # 送信元アドレス
                orig_addr = snat_data.get("orig-addr", "")
                if isinstance(orig_addr, list):
                    orig_addr = ", ".join(orig_addr)

                # 宛先アドレス
                dst_addr = snat_data.get("dst-addr", "")
                if isinstance(dst_addr, list):
                    dst_addr = ", ".join(dst_addr)

                # NAT IP Pool
                nat_ippool = snat_data.get("nat-ippool", "")
                if isinstance(nat_ippool, list):
                    nat_ippool = ", ".join(nat_ippool)

                # インターフェース
                srcintf = snat_data.get("srcintf", "")
                if isinstance(srcintf, list):
                    srcintf = ", ".join(srcintf)
                dstintf = snat_data.get("dstintf", "")
                if isinstance(dstintf, list):
                    dstintf = ", ".join(dstintf)

                # プロトコル番号（0=all, 6=TCP, 17=UDP など）
                protocol = snat_data.get("protocol", "0")

                nat = NATPolicy(
                    name=snat_data.get("_name", snat_id),
                    nat_type="central-snat",
                    original_source=orig_addr,
                    original_destination=dst_addr,
                    nat_ippool=nat_ippool,
                    interface=(
                        f"{srcintf} -> {dstintf}" if srcintf and dstintf
                        else srcintf or dstintf or ""
                    ),
                    protocol=str(protocol),
                    vdom=vdom,
                    enabled=snat_data.get("status", "") != "disable",
                    description=snat_data.get("comments", ""),
                )
                config_model.nat_policies.append(nat)
