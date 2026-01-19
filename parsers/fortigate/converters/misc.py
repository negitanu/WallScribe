#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
その他設定コンバーター（HA、ログ設定）
"""

from typing import Dict, List, Any

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


def _process_snmp_community(
    comm_data: Dict,
    comm_name: str,
    snmp_enabled: bool,
    config_model: ConfigModel
) -> None:
    """SNMPコミュニティ設定を処理"""
    # コミュニティ名を取得（_name属性を優先、なければキー名を使用）
    community_name = comm_data.get("_name", "")
    if not community_name:
        # _nameが存在しない場合、キー名を使用（引用符を除去）
        community_name = str(comm_name).strip('"')
    
    # ホストリストを処理
    hosts = _parse_hosts_list(comm_data.get("hosts", []))
    
    # トラップ送信先を取得（trap-statusがenableの場合）
    trap_hosts = []
    trap_status = comm_data.get("trap-status", "")
    if trap_status == "enable":
        trap_hosts = hosts if hosts else []

    snmp = SNMPSettings(
        enabled=snmp_enabled,
        community=community_name,
        hosts=hosts,
        trap_hosts=trap_hosts,
        version="v2c"
    )
    config_model.logging.snmp.append(snmp)


def _process_snmp_user(
    user_data: Dict,
    user_name: str,
    snmp_enabled: bool,
    config_model: ConfigModel
) -> None:
    """SNMP v3ユーザー設定を処理"""
    # ユーザー名を取得（_name属性を優先、なければキー名を使用）
    username = user_data.get("_name", "")
    if not username:
        # _nameが存在しない場合、キー名を使用（引用符を除去）
        username = str(user_name).strip('"')
    
    # ホストリストを処理
    hosts = _parse_hosts_list(user_data.get("hosts", []))
    
    # トラップ送信先を取得（trap-statusがenableの場合）
    trap_hosts = []
    trap_status = user_data.get("trap-status", "")
    if trap_status == "enable":
        trap_hosts = hosts if hosts else []

    snmp = SNMPSettings(
        enabled=snmp_enabled,
        username=username,
        hosts=hosts,
        trap_hosts=trap_hosts,
        version="v3"
    )
    config_model.logging.snmp.append(snmp)


def _parse_hosts_list(hosts: Any) -> List[str]:
    """ホストリストをパースして文字列リストに変換

    FortiGateのhosts設定は以下の形式でパースされる:
    {
        "1": {"_name": "1", "ip": "192.168.1.1 255.255.255.0"},
        "2": {"_name": "2", "ip": ["10.0.0.1", "255.255.255.0"]}
    }
    """
    if isinstance(hosts, str):
        # 単一の文字列の場合（スペース区切りの場合は最初の要素がIP）
        return [hosts.strip('"').split()[0]]
    elif isinstance(hosts, dict):
        # 辞書形式の場合、各エントリのipフィールドからIPアドレスを取得
        result = []
        for host_data in hosts.values():
            if isinstance(host_data, dict):
                ip_value = host_data.get("ip", "")
                if isinstance(ip_value, list) and ip_value:
                    # リスト形式の場合、最初の要素がIPアドレス
                    result.append(str(ip_value[0]).strip('"'))
                elif isinstance(ip_value, str) and ip_value:
                    # 文字列形式の場合、スペース区切りの最初がIPアドレス
                    result.append(ip_value.strip('"').split()[0])
        return result
    elif isinstance(hosts, list):
        # リストの各要素を処理
        result = []
        for item in hosts:
            if isinstance(item, dict):
                ip_value = item.get("ip", "")
                if isinstance(ip_value, list) and ip_value:
                    result.append(str(ip_value[0]).strip('"'))
                elif isinstance(ip_value, str) and ip_value:
                    result.append(ip_value.strip('"').split()[0])
            elif item:
                result.append(str(item).strip('"'))
        return result
    return []


def _add_snmp_settings(
    config_model: ConfigModel,
    global_cfg: Dict
) -> None:
    """SNMP設定を追加"""
    # SNMP有効化状態を取得
    snmp_sysinfo = get_nested(global_cfg, "system snmp sysinfo", default={})
    snmp_enabled = snmp_sysinfo.get("status", "") == "enable" if isinstance(snmp_sysinfo, dict) else False

    # SNMP v2c コミュニティ設定
    snmp_community = get_nested(global_cfg, "system snmp community", default={})
    
    # 辞書形式の場合
    if isinstance(snmp_community, dict):
        for comm_name, comm_data in snmp_community.items():
            if isinstance(comm_data, dict):
                _process_snmp_community(comm_data, comm_name, snmp_enabled, config_model)
            elif isinstance(comm_data, list):
                # リスト形式の場合（複数のエントリが同じキー名の場合）
                for item in comm_data:
                    if isinstance(item, dict):
                        _process_snmp_community(item, comm_name, snmp_enabled, config_model)
    # リスト形式の場合（直接リストとして保存されている場合）
    elif isinstance(snmp_community, list):
        for comm_data in snmp_community:
            if isinstance(comm_data, dict):
                comm_name = comm_data.get("_name", "")
                _process_snmp_community(comm_data, comm_name, snmp_enabled, config_model)

    # SNMP v3 ユーザー設定
    snmp_user = get_nested(global_cfg, "system snmp user", default={})
    
    # 辞書形式の場合
    if isinstance(snmp_user, dict):
        for user_name, user_data in snmp_user.items():
            if isinstance(user_data, dict):
                _process_snmp_user(user_data, user_name, snmp_enabled, config_model)
            elif isinstance(user_data, list):
                # リスト形式の場合（複数のエントリが同じキー名の場合）
                for item in user_data:
                    if isinstance(item, dict):
                        _process_snmp_user(item, user_name, snmp_enabled, config_model)
    # リスト形式の場合（直接リストとして保存されている場合）
    elif isinstance(snmp_user, list):
        for user_data in snmp_user:
            if isinstance(user_data, dict):
                user_name = user_data.get("_name", "")
                _process_snmp_user(user_data, user_name, snmp_enabled, config_model)


def _add_fortianalyzer_settings(
    config_model: ConfigModel,
    global_cfg: Dict
) -> None:
    """FortiAnalyzer設定を追加"""
    faz_setting = get_nested(global_cfg, "log fortianalyzer setting", default={})
    if isinstance(faz_setting, dict) and faz_setting:
        config_model.logging.fortianalyzer_server = faz_setting.get("server", "")
