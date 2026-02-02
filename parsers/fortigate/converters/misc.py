#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
その他設定コンバーター（HA、ログ設定）
"""

from typing import Any, Dict, List, Tuple

from models.config import (
    ConfigModel,
    HAHeartbeatInterface,
    HAManagementInterface,
    HAMode,
    HASettings,
    SNMPSettings,
    SyslogServer,
)
from parsers.utils import get_nested


def convert_ha(config_model: ConfigModel, parsed_config: Dict) -> None:
    """HA設定を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ

    Note:
        FortiGate HA設定のデフォルト値（FortiOS 7.x）:
        - priority: 128
        - hb-interval: 2 (秒)
        - hb-lost-threshold: 6
        - override (preempt): disable
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

        # HA管理インターフェース有効化状態
        ha_mgmt_status = ha_config.get("ha-mgmt-status", "") == "enable"

        # セッション同期設定
        session_pickup = ha_config.get("session-pickup", "") == "enable"

        # ハートビート間隔と閾値（デフォルト値: 2秒, 6回）
        hb_interval_raw = ha_config.get("hb-interval", "")
        hb_lost_threshold_raw = ha_config.get("hb-lost-threshold", "")
        hb_interval = str(hb_interval_raw) if hb_interval_raw else "2"
        hb_lost_threshold = str(hb_lost_threshold_raw) if hb_lost_threshold_raw else "6"

        # 暗号化・認証設定
        encryption = ha_config.get("encryption", "") == "enable"
        authentication = ha_config.get("authentication", "") == "enable"
        password = ha_config.get("password", "")

        # 優先度（デフォルト値: 128）
        priority_raw = ha_config.get("priority", "")
        priority = str(priority_raw) if priority_raw else "128"

        config_model.ha = HASettings(
            mode=mode,
            group_id=str(ha_config.get("group-id", "")),
            group_name=str(ha_config.get("group-name", "")),
            priority=priority,
            monitor_interfaces=monitor,
            heartbeat_interfaces=hb_interfaces,
            heartbeat_interfaces_detail=hb_interfaces_detail,
            ha_mgmt_interfaces=ha_mgmt_interfaces,
            ha_mgmt_status=ha_mgmt_status,
            preempt=ha_config.get("override", "") == "enable",
            session_sync=True,  # FortiGateではデフォルト有効
            session_pickup=session_pickup,
            hb_interval=hb_interval,
            hb_lost_threshold=hb_lost_threshold,
            encryption=encryption,
            authentication=authentication,
            password=password if password else "",
        )

        # デフォルト値の追跡
        if not priority_raw:
            config_model.default_fields.add("ha.priority")
        if not hb_interval_raw:
            config_model.default_fields.add("ha.hb_interval")
        if not hb_lost_threshold_raw:
            config_model.default_fields.add("ha.hb_lost_threshold")
        if ha_config.get("override", "") != "enable":
            config_model.default_fields.add("ha.preempt")
        if ha_config.get("session-pickup", "") != "enable":
            config_model.default_fields.add("ha.session_pickup")


def _parse_hbdev(hbdev: Any) -> Tuple[List[str], List[HAHeartbeatInterface]]:
    """ハートビートデバイス設定をパース

    FortiGateのhbdev形式: "port3" 0 "port4" 1
    (インターフェース名 優先度のペア)

    Args:
        hbdev: hbdev設定文字列

    Returns:
        (インターフェース名リスト, HAHeartbeatInterfaceリスト)
    """
    interfaces: List[str] = []
    interfaces_detail: List[HAHeartbeatInterface] = []

    if not hbdev:
        return interfaces, interfaces_detail

    # hbdevは FortiOS の `set hbdev "port3" 0 "port4" 1` のような形式。
    # FortiGateParser._parse_value() はトークン数が複数の場合 list を返すため、
    # ここでは str / list の両方を受け取れるようにする。
    if isinstance(hbdev, list):
        parts = [str(x).replace('"', "") for x in hbdev if str(x).strip() != ""]
    else:
        # 例: '"port3" 0 "port4" 1' または 'port3 0 port4 1'
        parts = str(hbdev).replace('"', "").split()

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
        interfaces_detail.append(HAHeartbeatInterface(interface=iface_name, priority=priority))

    return interfaces, interfaces_detail


def _parse_ha_mgmt_interfaces(ha_config: Dict) -> List[HAManagementInterface]:
    """HA管理インターフェース設定をパース

    FortiGateのha-mgmt-interfacesセクションをパース:
    - id: エントリID（1, 2など、各HAメンバーに対応）
    - interface: 管理インターフェース名（例: port1）
    - dst: 管理IPアドレスとサブネットマスク（例: "10.0.0.10 255.255.255.0"）
    - gateway: デフォルトゲートウェイ

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
                dst = _format_dst_address(mgmt_data.get("dst", ""))
                result.append(
                    HAManagementInterface(
                        id=str(mgmt_id),
                        interface=mgmt_data.get("interface", ""),
                        dst=dst,
                        gateway=mgmt_data.get("gateway", ""),
                    )
                )
    elif isinstance(ha_mgmt_interfaces, list):
        for idx, mgmt_data in enumerate(ha_mgmt_interfaces):
            if isinstance(mgmt_data, dict):
                dst = _format_dst_address(mgmt_data.get("dst", ""))
                result.append(
                    HAManagementInterface(
                        id=str(idx + 1),
                        interface=mgmt_data.get("interface", ""),
                        dst=dst,
                        gateway=mgmt_data.get("gateway", ""),
                    )
                )

    return result


def _format_dst_address(dst_value) -> str:
    """dst値をCIDR形式のIPアドレスに変換

    FortiGateのdst設定は以下の形式:
    - "10.0.0.10 255.255.255.0" (IP + サブネットマスク)
    - ["10.0.0.10", "255.255.255.0"] (リスト形式)

    Returns:
        CIDR形式のIPアドレス（例: "10.0.0.10/24"）または空文字
    """
    if not dst_value:
        return ""

    ip_addr = ""
    netmask = ""

    if isinstance(dst_value, list) and len(dst_value) >= 2:
        ip_addr = dst_value[0]
        netmask = dst_value[1]
    elif isinstance(dst_value, str):
        parts = dst_value.split()
        if len(parts) >= 2:
            ip_addr = parts[0]
            netmask = parts[1]
        elif len(parts) == 1:
            return parts[0]  # IPアドレスのみの場合

    if ip_addr and netmask:
        # サブネットマスクをCIDRプレフィックスに変換
        prefix = _netmask_to_cidr(netmask)
        if prefix:
            return f"{ip_addr}/{prefix}"
        return ip_addr

    return ""


def _netmask_to_cidr(netmask: str) -> str:
    """サブネットマスクをCIDRプレフィックス長に変換

    Args:
        netmask: サブネットマスク（例: "255.255.255.0"）

    Returns:
        プレフィックス長（例: "24"）または空文字
    """
    try:
        octets = netmask.split(".")
        if len(octets) != 4:
            return ""
        binary = "".join(format(int(octet), "08b") for octet in octets)
        return str(binary.count("1"))
    except (ValueError, AttributeError):
        return ""


def _parse_ha_mode(mode_str: str) -> HAMode:
    """HAモード文字列をHAModeに変換"""
    if mode_str == "a-p":
        return HAMode.ACTIVE_PASSIVE
    elif mode_str == "a-a":
        return HAMode.ACTIVE_ACTIVE
    return HAMode.STANDALONE


def convert_logging(config_model: ConfigModel, parsed_config: Dict) -> None:
    """ログ設定を変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    global_cfg = parsed_config.get("global", {})

    _add_syslog_settings(config_model, global_cfg)
    _add_snmp_settings(config_model, global_cfg)
    _add_fortianalyzer_settings(config_model, global_cfg)


def _add_syslog_settings(config_model: ConfigModel, global_cfg: Dict) -> None:
    """Syslog設定を追加"""
    syslog_setting = get_nested(global_cfg, "log syslogd setting", default={})
    if isinstance(syslog_setting, dict) and syslog_setting:
        server = SyslogServer(
            server=syslog_setting.get("server", ""),
            port=str(syslog_setting.get("port", "514")),
            facility=syslog_setting.get("facility", ""),
            status="enabled" if syslog_setting.get("status") == "enable" else "disabled",
        )
        config_model.logging.syslog_servers.append(server)


def _process_snmp_community(
    comm_data: Dict, comm_name: str, snmp_enabled: bool, config_model: ConfigModel
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
        version="v2c",
    )
    config_model.logging.snmp.append(snmp)


def _process_snmp_user(
    user_data: Dict, user_name: str, snmp_enabled: bool, config_model: ConfigModel
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
        enabled=snmp_enabled, username=username, hosts=hosts, trap_hosts=trap_hosts, version="v3"
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


def _add_snmp_settings(config_model: ConfigModel, global_cfg: Dict) -> None:
    """SNMP設定を追加"""
    # SNMP有効化状態を取得
    snmp_sysinfo = get_nested(global_cfg, "system snmp sysinfo", default={})
    snmp_enabled = (
        snmp_sysinfo.get("status", "") == "enable" if isinstance(snmp_sysinfo, dict) else False
    )

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


def _add_fortianalyzer_settings(config_model: ConfigModel, global_cfg: Dict) -> None:
    """FortiAnalyzer設定を追加"""
    faz_setting = get_nested(global_cfg, "log fortianalyzer setting", default={})
    if isinstance(faz_setting, dict) and faz_setting:
        config_model.logging.fortianalyzer_server = faz_setting.get("server", "")
