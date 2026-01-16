#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPN設定コンバーター
"""

from typing import Dict

from models.config import ConfigModel, IPSecPhase1, IPSecPhase2, SSLVPNSettings
from parsers.utils import get_nested, parse_proposal


def convert_vpn(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
    """VPN設定を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global VPN
    global_cfg = parsed_config.get("global", {})
    _add_vpn_from_config(config_model, global_cfg, "root")

    # VDOM VPN
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        _add_vpn_from_config(config_model, vdom_cfg, vdom_name)


def _add_vpn_from_config(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """VPN設定を追加"""
    vpn_config = get_nested(config, "vpn", default={})

    _add_ipsec_phase1(config_model, vpn_config)
    _add_ipsec_phase2(config_model, vpn_config)
    _add_ssl_vpn_settings(config_model, vpn_config, vdom)
    _add_ssl_vpn_portal(config_model, vpn_config, vdom)


def _add_ipsec_phase1(
    config_model: ConfigModel,
    vpn_config: Dict
) -> None:
    """IPsec Phase1設定を追加"""
    phase1 = get_nested(vpn_config, "ipsec phase1-interface", default={})
    if isinstance(phase1, dict):
        for p1_name, p1_data in phase1.items():
            if isinstance(p1_data, dict):
                proposals = p1_data.get("proposal", [])
                if isinstance(proposals, list):
                    proposals = ", ".join(proposals)

                encryption, authentication = parse_proposal(proposals)

                p1 = IPSecPhase1(
                    name=p1_data.get("_name", p1_name),
                    remote_gateway=p1_data.get("remote-gw", ""),
                    interface=p1_data.get("interface", ""),
                    ike_version=str(p1_data.get("ike-version", "")),
                    proposal=proposals,
                    encryption=encryption,
                    authentication=authentication,
                    dh_group=str(p1_data.get("dhgrp", "")),
                    lifetime=str(p1_data.get("keylife", "")),
                    dpd=p1_data.get("dpd", ""),
                    psk=bool(p1_data.get("psksecret", "")),
                    local_id=p1_data.get("localid", ""),
                    remote_id=p1_data.get("peerid", "")
                )
                config_model.vpn.ipsec_phase1.append(p1)


def _add_ipsec_phase2(
    config_model: ConfigModel,
    vpn_config: Dict
) -> None:
    """IPsec Phase2設定を追加"""
    phase2 = get_nested(vpn_config, "ipsec phase2-interface", default={})
    if isinstance(phase2, dict):
        for p2_name, p2_data in phase2.items():
            if isinstance(p2_data, dict):
                proposals = p2_data.get("proposal", [])
                if isinstance(proposals, list):
                    proposals = ", ".join(proposals)

                encryption, authentication = parse_proposal(proposals)

                p2 = IPSecPhase2(
                    name=p2_data.get("_name", p2_name),
                    phase1_name=p2_data.get("phase1name", ""),
                    proposal=proposals,
                    encryption=encryption,
                    authentication=authentication,
                    pfs=str(p2_data.get("pfs", "")),
                    lifetime=str(p2_data.get("keylifeseconds", "")),
                    local_subnet=p2_data.get("src-subnet", ""),
                    remote_subnet=p2_data.get("dst-subnet", "")
                )
                config_model.vpn.ipsec_phase2.append(p2)


def _add_ssl_vpn_settings(
    config_model: ConfigModel,
    vpn_config: Dict,
    vdom: str
) -> None:
    """SSL-VPN設定を追加"""
    ssl_settings = get_nested(vpn_config, "ssl settings", default={})
    if isinstance(ssl_settings, dict) and ssl_settings:
        # トンネルIPプールの処理
        tunnel_pools = ssl_settings.get("tunnel-ip-pools", "")
        if isinstance(tunnel_pools, list):
            tunnel_pools = ", ".join(tunnel_pools)

        # 認証グループの処理
        auth_rule = get_nested(ssl_settings, "authentication-rule", default={})
        user_groups = []
        if isinstance(auth_rule, dict):
            for rule_id, rule_data in auth_rule.items():
                if isinstance(rule_data, dict):
                    groups = rule_data.get("groups", [])
                    if isinstance(groups, str):
                        groups = [groups]
                    user_groups.extend(groups)

        ssl_vpn = SSLVPNSettings(
            listen_port=str(ssl_settings.get("port", "443")),
            listen_interface=ssl_settings.get("source-interface", ""),
            tunnel_ip_pool=tunnel_pools,
            user_groups=user_groups,
            mode="tunnel",  # デフォルト
            vdom=vdom
        )
        config_model.vpn.ssl_vpn.append(ssl_vpn)


def _add_ssl_vpn_portal(
    config_model: ConfigModel,
    vpn_config: Dict,
    vdom: str
) -> None:
    """SSL-VPNポータル設定を追加"""
    ssl_portal = get_nested(vpn_config, "ssl web portal", default={})
    if isinstance(ssl_portal, dict):
        for portal_name, portal_data in ssl_portal.items():
            if isinstance(portal_data, dict):
                mode = "web"
                if portal_data.get("tunnel-mode") == "enable":
                    mode = "tunnel"
                elif portal_data.get("web-mode") == "enable":
                    mode = "web"

                ssl_vpn = SSLVPNSettings(
                    portal=portal_data.get("_name", portal_name),
                    mode=mode,
                    vdom=vdom
                )
                # ポータルごとに追加（設定がある場合のみ）
                if portal_data.get("tunnel-mode") or portal_data.get("web-mode"):
                    config_model.vpn.ssl_vpn.append(ssl_vpn)
