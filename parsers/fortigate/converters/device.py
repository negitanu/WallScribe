#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
デバイス情報・システム設定コンバーター
"""

from typing import Dict, List

from models.config import ConfigModel, OperationMode, AdminUser
from parsers.utils import get_nested, ip_to_cidr


def convert_device_info(
    config_model: ConfigModel,
    parsed_config: Dict,
    vdoms: List[str]
) -> None:
    """機器情報を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
        vdoms: VDOMリスト
    """
    header = parsed_config.get("header", {})
    global_cfg = parsed_config.get("global", {})
    system_global = get_nested(global_cfg, "system global", default={})

    config_model.device_info.hostname = system_global.get("hostname", "").strip('"')
    config_model.device_info.model = header.get("model", "")
    config_model.device_info.os_version = header.get("version", "")
    config_model.device_info.serial_number = header.get("serial", "")

    opmode = header.get("opmode", "0")
    config_model.device_info.operation_mode = (
        OperationMode.NAT_ROUTE if opmode == "0" else OperationMode.TRANSPARENT
    )

    config_model.device_info.vdom_enabled = header.get("vdom_enabled", False)
    config_model.device_info.vdom_list = vdoms if vdoms else ["root"]


def convert_system_settings(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
    """システム設定を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    global_cfg = parsed_config.get("global", {})
    system_global = get_nested(global_cfg, "system global", default={})
    system_dns = get_nested(global_cfg, "system dns", default={})
    system_ntp = get_nested(global_cfg, "system ntp", default={})
    system_admin = get_nested(global_cfg, "system admin", default={})
    system_interface = get_nested(global_cfg, "system interface", default={})

    # DNS
    config_model.system_settings.dns_primary = system_dns.get("primary", "")
    config_model.system_settings.dns_secondary = system_dns.get("secondary", "")

    # Timezone
    config_model.system_settings.timezone = system_global.get("timezone", "")

    # 管理ポート番号
    admin_https_port = system_global.get("admin-https-port", "")
    admin_ssh_port = system_global.get("admin-ssh-port", "")
    config_model.system_settings.https_port = str(admin_https_port) if admin_https_port else "443"
    config_model.system_settings.ssh_port = str(admin_ssh_port) if admin_ssh_port else "22"

    # NTP
    if "ntpsync" in system_ntp:
        ntp_servers = system_ntp.get("ntpserver", {})
        if isinstance(ntp_servers, dict):
            for server_data in ntp_servers.values():
                if isinstance(server_data, dict) and "server" in server_data:
                    server_value = server_data["server"]
                    if isinstance(server_value, str):
                        config_model.system_settings.ntp_servers.append(
                            server_value.strip('"')
                        )
                    elif isinstance(server_value, list):
                        # リスト形式の場合（複数のサーバーが設定されている場合）
                        for svr in server_value:
                            if isinstance(svr, str):
                                config_model.system_settings.ntp_servers.append(svr.strip('"'))

    # 管理者アカウント
    if isinstance(system_admin, dict):
        for admin_name, admin_data in system_admin.items():
            if isinstance(admin_data, dict):
                admin_user = AdminUser(
                    username=admin_data.get("_name", admin_name),
                    profile=admin_data.get("accprofile", ""),
                    vdom=admin_data.get("vdom", "")
                )
                # Trust hosts
                for i in range(1, 11):
                    trusthost = admin_data.get(f"trusthost{i}", "")
                    if trusthost:
                        admin_user.trust_hosts.append(ip_to_cidr(trusthost))
                config_model.system_settings.admin_users.append(admin_user)

    # 管理インターフェースの検出
    if isinstance(system_interface, dict):
        for iface_name, iface_data in system_interface.items():
            if isinstance(iface_data, dict):
                allowaccess = iface_data.get("allowaccess", "")
                if allowaccess and "https" in str(allowaccess).lower():
                    ip = iface_data.get("ip", "")
                    if ip:
                        config_model.system_settings.management_interface = iface_data.get("_name", iface_name)
                        ip_parts = ip.split() if isinstance(ip, str) else ip
                        if ip_parts:
                            config_model.system_settings.management_ip = ip_parts[0] if isinstance(ip_parts, list) else ip_parts
                        # 許可プロトコル
                        if isinstance(allowaccess, str):
                            config_model.system_settings.allowed_protocols = allowaccess.split()
                        elif isinstance(allowaccess, list):
                            config_model.system_settings.allowed_protocols = allowaccess
                    break
