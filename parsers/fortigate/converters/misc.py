#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
その他設定コンバーター（HA、ログ設定）
"""

from typing import Any, Dict, List, Tuple

from models.config import (
    ConfigModel, HASettings, HAMode,
    HAHeartbeatInterface, HAManagementInterface,
    SyslogServer, SNMPSettings
)
from parsers.utils import get_nested


def convert_ha(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
    """HA設定を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    global_cfg = parsed_config.get("global", {})
    ha_config = get_nested(global_cfg, "system ha", default={})

    if isinstance(ha_config, dict) and ha_config:
        mode = _parse_ha_mode(ha_config.get("mode", "standalone"))

        monitor = ha_config.get("monitor", [])
        if isinstance(monitor, str):
            monitor = [monitor]

        # ハートビートインターフェースをパース
        hbdev = ha_config.get("hbdev", "")
        hb_interfaces, hb_interfaces_detail = _parse_hbdev(hbdev)

        # HA管理インターフェースをパース
        ha_mgmt_interfaces = _parse_ha_mgmt_interfaces(ha_config)

        # セッション同期設定
        session_pickup = ha_config.get("session-pickup", "") == "enable"

        # ハートビート間隔と閾値
        hb_interval = str(ha_config.get("hb-interval", ""))
        hb_lost_threshold = str(ha_config.get("hb-lost-threshold", ""))

        # 暗号化・認証設定
        encryption = ha_config.get("encryption", "") == "enable"
        authentication = ha_config.get("authentication", "") == "enable"
        password = ha_config.get("password", "")

        config_model.ha = HASettings(
            mode=mode,
            group_id=str(ha_config.get("group-id", "")),
            group_name=str(ha_config.get("group-name", "")),
            priority=str(ha_config.get("priority", "")),
            monitor_interfaces=monitor,
            heartbeat_interfaces=hb_interfaces,
            heartbeat_interfaces_detail=hb_interfaces_detail,
            ha_mgmt_interfaces=ha_mgmt_interfaces,
            preempt=ha_config.get("override", "") == "enable",
            session_sync=True,  # FortiGateではデフォルト有効
            session_pickup=session_pickup,
            hb_interval=hb_interval,
            hb_lost_threshold=hb_lost_threshold,
            encryption=encryption,
            authentication=authentication,
            password=password if password else ""
        )


def _parse_hbdev(hbdev: Any) -> Tuple[List[str], List[HAHeartbeatInterface]]:
    """ハートビートデバイス設定をパース

    FortiGateのhbdev形式: "port3" 0 "port4" 1
    (インターフェース名 優先度のペア)

    Args:
        hbdev: hbdev設定文字列

    Returns:
        (インターフェース名リスト, HAHeartbeatInterfaceリスト)
    """
    interfaces = []
    interfaces_detail = []

    if not hbdev:
        return interfaces, interfaces_detail

    # hbdevは FortiOS の `set hbdev "port3" 0 "port4" 1` のような形式。
    # FortiGateParser._parse_value() はトークン数が複数の場合 list を返すため、
    # ここでは str / list の両方を受け取れるようにする。
    if isinstance(hbdev, list):
        parts = [str(x).replace('"', '') for x in hbdev if str(x).strip() != ""]
    else:
        # 例: '"port3" 0 "port4" 1' または 'port3 0 port4 1'
        parts = str(hbdev).replace('"', '').split()

    i = 0
    while i < len(parts):
        iface_name = parts[i]
        priority = ""

        # 次の要素が数字なら優先度
        if i + 1 < len(parts) and parts[i + 1].isdigit():
            priority = parts[i + 1]
            i += 2
        else:
            i += 1

        interfaces.append(iface_name)
        interfaces_detail.append(HAHeartbeatInterface(
            interface=iface_name,
            priority=priority
        ))

    return interfaces, interfaces_detail


def _parse_ha_mgmt_interfaces(ha_config: Dict) -> List[HAManagementInterface]:
    """HA管理インターフェース設定をパース

    Args:
        ha_config: HA設定辞書

    Returns:
        HAManagementInterfaceのリスト
    """
    result = []

    ha_mgmt_interfaces = ha_config.get("ha-mgmt-interfaces", {})
    if isinstance(ha_mgmt_interfaces, dict):
        for mgmt_id, mgmt_data in ha_mgmt_interfaces.items():
            if isinstance(mgmt_data, dict):
                result.append(HAManagementInterface(
                    id=str(mgmt_id),
                    interface=mgmt_data.get("interface", ""),
                    gateway=mgmt_data.get("gateway", "")
                ))
    elif isinstance(ha_mgmt_interfaces, list):
        for idx, mgmt_data in enumerate(ha_mgmt_interfaces):
            if isinstance(mgmt_data, dict):
                result.append(HAManagementInterface(
                    id=str(idx + 1),
                    interface=mgmt_data.get("interface", ""),
                    gateway=mgmt_data.get("gateway", "")
                ))

    return result


def _parse_ha_mode(mode_str: str) -> HAMode:
    """HAモード文字列をHAModeに変換"""
    if mode_str == "a-p":
        return HAMode.ACTIVE_PASSIVE
    elif mode_str == "a-a":
        return HAMode.ACTIVE_ACTIVE
    return HAMode.STANDALONE


def convert_logging(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
    """ログ設定を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    global_cfg = parsed_config.get("global", {})

    _add_syslog_settings(config_model, global_cfg)
    _add_snmp_settings(config_model, global_cfg)
    _add_fortianalyzer_settings(config_model, global_cfg)


def _add_syslog_settings(
    config_model: ConfigModel,
    global_cfg: Dict
) -> None:
    """Syslog設定を追加"""
    syslog_setting = get_nested(global_cfg, "log syslogd setting", default={})
    if isinstance(syslog_setting, dict) and syslog_setting:
        server = SyslogServer(
            server=syslog_setting.get("server", ""),
            port=str(syslog_setting.get("port", "514")),
            facility=syslog_setting.get("facility", ""),
            status="enabled" if syslog_setting.get("status") == "enable" else "disabled"
        )
        config_model.logging.syslog_servers.append(server)


def _add_snmp_settings(
    config_model: ConfigModel,
    global_cfg: Dict
) -> None:
    """SNMP設定を追加"""
    snmp_community = get_nested(global_cfg, "system snmp community", default={})
    if isinstance(snmp_community, dict):
        for comm_name, comm_data in snmp_community.items():
            if isinstance(comm_data, dict):
                hosts = comm_data.get("hosts", [])
                if isinstance(hosts, str):
                    hosts = [hosts]
                elif isinstance(hosts, dict):
                    hosts = list(hosts.keys())

                snmp = SNMPSettings(
                    community=comm_data.get("_name", comm_name),
                    hosts=hosts,
                    version="v2c"
                )
                config_model.logging.snmp.append(snmp)


def _add_fortianalyzer_settings(
    config_model: ConfigModel,
    global_cfg: Dict
) -> None:
    """FortiAnalyzer設定を追加"""
    faz_setting = get_nested(global_cfg, "log fortianalyzer setting", default={})
    if isinstance(faz_setting, dict) and faz_setting:
        config_model.logging.fortianalyzer_server = faz_setting.get("server", "")
