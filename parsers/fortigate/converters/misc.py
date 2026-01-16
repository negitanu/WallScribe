#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
その他設定コンバーター（HA、ログ設定）
"""

from typing import Dict

from models.config import (
    ConfigModel, HASettings, HAMode,
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

        config_model.ha = HASettings(
            mode=mode,
            group_id=str(ha_config.get("group-id", "")),
            priority=str(ha_config.get("priority", "")),
            monitor_interfaces=monitor,
            preempt=ha_config.get("override", "") == "enable"
        )


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
