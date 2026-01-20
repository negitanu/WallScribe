#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ポリシー・NATコンバーター
"""

from typing import Dict

from models.config import (
    ConfigModel, FirewallPolicy, LocalInPolicy, NATPolicy, PolicyAction
)
from parsers.utils import get_nested, to_list


def convert_policies(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
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


def _add_policies_from_config(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
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
                    source_address=to_list(policy_data.get("srcaddr", [])),
                    destination_address=to_list(policy_data.get("dstaddr", [])),
                    internet_service_name=to_list(policy_data.get("internet-service-name", [])),
                    service=to_list(policy_data.get("service", [])),
                    action=action,
                    nat_enabled=policy_data.get("nat", "") == "enable",
                    log_enabled=policy_data.get("logtraffic", "") in ("enable", "all"),
                    security_profiles=security_profiles,
                    vdom=vdom,
                    enabled=policy_data.get("status", "") != "disable",
                    description=policy_data.get("comments", "")
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


def convert_local_in_policies(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
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


def _add_local_in_policies_from_config(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
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
                    description=policy_data.get("comments", "")
                )
                config_model.local_in_policies.append(policy)


def convert_nat(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
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


def _add_nat_from_config(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """NAT設定を追加"""
    _add_vip_nat(config_model, config, vdom)
    _add_ippool_nat(config_model, config, vdom)


def _add_vip_nat(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
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
                    description=vip_data.get("comment", "")
                )
                config_model.nat_policies.append(nat)


def _add_ippool_nat(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """IP Pool (SNAT) を追加"""
    firewall_ippool = get_nested(config, "firewall ippool", default={})
    if isinstance(firewall_ippool, dict):
        for pool_name, pool_data in firewall_ippool.items():
            if isinstance(pool_data, dict):
                start_ip = pool_data.get("startip", "")
                end_ip = pool_data.get("endip", "")
                nat = NATPolicy(
                    name=pool_data.get("_name", pool_name),
                    nat_type="ippool",
                    translated_source=f"{start_ip}-{end_ip}" if start_ip else "",
                    interface=pool_data.get("associated-interface", ""),
                    vdom=vdom,
                    description=pool_data.get("comments", "")
                )
                config_model.nat_policies.append(nat)
