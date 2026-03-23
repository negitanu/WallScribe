#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HAクラスタパーサー
複数のFortiGate/Palo Alto設定ファイルを読み込み、クラスタ構成として統合する
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from models.cluster import ClusterConfig, ConfigDifference, HAClusterInfo, HAMemberInfo, HARole
from models.config import ConfigModel, DeviceType, HAMode
from parsers.base import detect_encoding, get_parser_for_content, get_parser_for_file

logger = logging.getLogger(__name__)


def parse_ha_cluster(file_paths: List[str]) -> ClusterConfig:
    """複数の設定ファイルからHAクラスタ構成をパース

    Args:
        file_paths: 設定ファイルパスのリスト

    Returns:
        ClusterConfig: クラスタ構成データ
    """
    if not file_paths:
        return ClusterConfig(is_cluster=False)

    # 単一ファイルの場合
    if len(file_paths) == 1:
        config = _parse_single_file(file_paths[0])
        if config is None:
            return ClusterConfig(is_cluster=False)

        # HA管理インターフェースからIPとインターフェース名を取得
        ha_mgmt_ip, ha_mgmt_interface = _get_ha_mgmt_info(config)

        return ClusterConfig(
            primary_config=config,
            is_cluster=False,
            cluster_info=HAClusterInfo(
                cluster_name=config.device_info.hostname,
                group_id=config.ha.group_id,
                ha_mode=config.ha.mode,
                members=[
                    HAMemberInfo(
                        hostname=config.device_info.hostname,
                        role=HARole.PRIMARY,
                        priority=config.ha.priority,
                        serial_number=config.device_info.serial_number,
                        model=config.device_info.model,
                        os_version=config.device_info.os_version,
                        ha_mgmt_ip=ha_mgmt_ip,
                        ha_mgmt_interface=ha_mgmt_interface,
                        config=config,
                        source_file=file_paths[0],
                    )
                ],
            ),
        )

    # 複数ファイルの場合：各ファイルをパース
    configs = []
    for file_path in file_paths:
        config = _parse_single_file(file_path)
        if config:
            configs.append((file_path, config))

    if not configs:
        return ClusterConfig(is_cluster=False)

    # HA構成を検出・構築
    return _build_cluster_config(configs)


def parse_ha_cluster_from_contents(contents: List[Tuple[str, str]]) -> ClusterConfig:
    """複数の設定ファイル内容からHAクラスタ構成をパース

    Args:
        contents: (ファイル名, ファイル内容)のタプルのリスト

    Returns:
        ClusterConfig: クラスタ構成データ
    """
    if not contents:
        return ClusterConfig(is_cluster=False)

    # 単一ファイルの場合
    if len(contents) == 1:
        filename, content = contents[0]
        config = _parse_single_content(content, filename)
        if config is None:
            return ClusterConfig(is_cluster=False)

        # HA管理インターフェースからIPとインターフェース名を取得
        ha_mgmt_ip, ha_mgmt_interface = _get_ha_mgmt_info(config)

        return ClusterConfig(
            primary_config=config,
            is_cluster=False,
            cluster_info=HAClusterInfo(
                cluster_name=config.device_info.hostname,
                group_id=config.ha.group_id,
                ha_mode=config.ha.mode,
                members=[
                    HAMemberInfo(
                        hostname=config.device_info.hostname,
                        role=HARole.PRIMARY,
                        priority=config.ha.priority,
                        serial_number=config.device_info.serial_number,
                        model=config.device_info.model,
                        os_version=config.device_info.os_version,
                        ha_mgmt_ip=ha_mgmt_ip,
                        ha_mgmt_interface=ha_mgmt_interface,
                        config=config,
                        source_file=filename,
                    )
                ],
            ),
        )

    # 複数ファイルの場合：各ファイルをパース
    configs = []
    for filename, content in contents:
        config = _parse_single_content(content, filename)
        if config:
            configs.append((filename, config))

    if not configs:
        return ClusterConfig(is_cluster=False)

    # HA構成を検出・構築
    return _build_cluster_config(configs)


def _parse_single_file(file_path: str) -> Optional[ConfigModel]:
    """単一ファイルをパース"""
    try:
        parser = get_parser_for_file(file_path)
        if parser is None:
            logger.warning(f"サポートされていないファイル形式: {file_path}")
            return None

        config = parser.parse(file_path)
        return config
    except Exception as e:
        logger.error(f"ファイルパースエラー: {file_path}, {e}")
        return None


def _parse_single_content(content: str, filename: str) -> Optional[ConfigModel]:
    """ファイル内容をパース"""
    try:
        parser = get_parser_for_content(content)
        if parser is None:
            logger.warning(f"サポートされていないファイル形式: {filename}")
            return None

        config = parser.parse_content(content, filename)
        return config
    except Exception as e:
        logger.error(f"コンテンツパースエラー: {filename}, {e}")
        return None


def _get_ha_mgmt_info(config: ConfigModel) -> Tuple[str, str]:
    """HA管理インターフェースからIPアドレスとインターフェース名を取得

    FortiGateのha-mgmt-interfacesには複数のエントリが含まれることがあり、
    各エントリは各HAメンバーに対応しています。
    単一ファイルの場合は、すべてのHA管理IPを結合して表示します。

    Args:
        config: ConfigModel

    Returns:
        (HA管理IP, HA管理インターフェース名)のタプル
    """
    if not config.ha.ha_mgmt_interfaces:
        return "", ""

    # すべてのHA管理IPとインターフェースを収集
    ips = []
    interfaces = set()
    for mgmt in config.ha.ha_mgmt_interfaces:
        if mgmt.dst:
            ips.append(mgmt.dst)
        if mgmt.interface:
            interfaces.add(mgmt.interface)

    # IPは改行で結合、インターフェースは一意なものを結合
    ha_mgmt_ip = "\n".join(ips) if ips else ""
    ha_mgmt_interface = ", ".join(sorted(interfaces)) if interfaces else ""

    return ha_mgmt_ip, ha_mgmt_interface


def _build_cluster_config(configs: List[Tuple[str, ConfigModel]]) -> ClusterConfig:
    """パース済み設定からクラスタ構成を構築

    Args:
        configs: (ファイルパス, ConfigModel)のタプルのリスト

    Returns:
        ClusterConfig: クラスタ構成データ
    """
    if not configs:
        return ClusterConfig(is_cluster=False)

    # HA構成かどうかを判定
    is_ha_cluster = _detect_ha_cluster(configs)

    if not is_ha_cluster:
        # HAクラスタではない場合、最初のファイルをプライマリとして扱う
        file_path, config = configs[0]
        # HA管理インターフェースからIPとインターフェース名を取得
        ha_mgmt_ip, ha_mgmt_interface = _get_ha_mgmt_info(config)
        return ClusterConfig(
            primary_config=config,
            is_cluster=False,
            cluster_info=HAClusterInfo(
                cluster_name=config.device_info.hostname,
                group_id=config.ha.group_id,
                ha_mode=config.ha.mode,
                members=[
                    HAMemberInfo(
                        hostname=config.device_info.hostname,
                        role=HARole.PRIMARY,
                        priority=config.ha.priority,
                        serial_number=config.device_info.serial_number,
                        model=config.device_info.model,
                        os_version=config.device_info.os_version,
                        ha_mgmt_ip=ha_mgmt_ip,
                        ha_mgmt_interface=ha_mgmt_interface,
                        config=config,
                        source_file=file_path,
                    )
                ],
            ),
        )

    # HAクラスタの場合、Primary/Secondaryを判定
    members = _determine_ha_roles(configs)

    # Primaryを特定
    primary_member = None
    for member in members:
        if member.role == HARole.PRIMARY:
            primary_member = member
            break

    if primary_member is None and members:
        # Primaryが特定できない場合、最初のメンバーをPrimaryとして扱う
        members[0].role = HARole.PRIMARY
        primary_member = members[0]

    # クラスタ情報を構築（Primaryの設定を使用）
    primary_config = primary_member.config
    is_paloalto = primary_config.device_info.device_type == DeviceType.PALOALTO
    # Palo Altoの場合、クラスタ名は空にする（group_nameの概念がない）
    if is_paloalto:
        cluster_name = ""
    else:
        cluster_name = primary_config.ha.group_name or primary_config.device_info.hostname
    cluster_info = HAClusterInfo(
        cluster_name=cluster_name,
        group_id=primary_config.ha.group_id,
        ha_mode=primary_config.ha.mode,
        members=members,
    )

    # 設定差分を検出
    differences = _detect_config_differences(members) if len(members) > 1 else []

    return ClusterConfig(
        cluster_info=cluster_info,
        primary_config=primary_member.config if primary_member else None,
        config_differences=differences,
        is_cluster=True,
    )


def _detect_ha_cluster(configs: List[Tuple[str, ConfigModel]]) -> bool:
    """HAクラスタ構成かどうかを判定

    同じグループIDを持つかチェック

    Args:
        configs: (ファイルパス, ConfigModel)のタプルのリスト

    Returns:
        bool: HAクラスタならTrue
    """
    if len(configs) < 2:
        return False

    group_ids = set()
    ha_modes = set()

    for _, config in configs:
        if config.ha.mode != HAMode.STANDALONE:
            group_ids.add(config.ha.group_id)
            ha_modes.add(config.ha.mode)

    # 同じグループIDを持ち、HA構成が有効な場合
    if len(group_ids) == 1 and group_ids != {""}:
        return True

    # グループIDが設定されていなくても、同じHAモードであればクラスタとみなす
    if len(ha_modes) == 1 and HAMode.STANDALONE not in ha_modes:
        return True

    return False


def _determine_ha_roles(configs: List[Tuple[str, ConfigModel]]) -> List[HAMemberInfo]:
    """各設定のHA役割を判定

    優先度(priority)が高い方がPrimary（FortiGateの場合、数値が大きいほど優先）

    Args:
        configs: (ファイルパス, ConfigModel)のタプルのリスト

    Returns:
        List[HAMemberInfo]: メンバー情報のリスト
    """
    # まず優先度でソートするための一時リストを作成
    temp_members: List[Dict[str, Any]] = []

    for file_path, config in configs:
        temp_members.append(
            {
                "file_path": file_path,
                "config": config,
                "priority": config.ha.priority,
            }
        )

    # デバイスタイプを判定してソート順を決定
    # Palo Alto: 低い優先度がPrimary（昇順）
    # FortiGate: 高い優先度がPrimary（降順）
    is_paloalto = any(
        config.device_info.device_type == DeviceType.PALOALTO for _, config in configs
    )

    def get_priority(item: Dict[str, Any]) -> int:
        try:
            return int(item["priority"])
        except (ValueError, TypeError):
            return 0

    temp_members.sort(key=get_priority, reverse=not is_paloalto)

    # ソート後、各メンバーにHA管理インターフェースのエントリを順番に割り当て
    # FortiGateのha-mgmt-interfacesはID=1がprimary、ID=2がsecondaryに対応
    members: List[HAMemberInfo] = []
    for idx, item in enumerate(temp_members):
        member_config: ConfigModel = cast(ConfigModel, item["config"])
        member_file_path: str = cast(str, item["file_path"])

        # HA管理インターフェースからIPとインターフェース名を取得
        ha_mgmt_ip = ""
        ha_mgmt_interface = ""
        if member_config.ha.ha_mgmt_interfaces:
            # IDが(idx + 1)のエントリを探す（1-indexed）
            target_id = str(idx + 1)
            matched_entry = None
            for mgmt in member_config.ha.ha_mgmt_interfaces:
                if mgmt.id == target_id:
                    matched_entry = mgmt
                    break
            # 見つからない場合はインデックスで取得
            if matched_entry is None and idx < len(member_config.ha.ha_mgmt_interfaces):
                matched_entry = member_config.ha.ha_mgmt_interfaces[idx]
            if matched_entry:
                ha_mgmt_ip = matched_entry.dst  # 管理IPアドレス（dstフィールド）
                ha_mgmt_interface = matched_entry.interface

        # 役割を割り当て
        role = HARole.PRIMARY if idx == 0 else HARole.SECONDARY

        members.append(
            HAMemberInfo(
                hostname=member_config.device_info.hostname,
                role=role,
                priority=member_config.ha.priority,
                serial_number=member_config.device_info.serial_number,
                model=member_config.device_info.model,
                os_version=member_config.device_info.os_version,
                ha_mgmt_ip=ha_mgmt_ip,
                ha_mgmt_interface=ha_mgmt_interface,
                config=member_config,
                source_file=member_file_path,
            )
        )

    return members


def _detect_config_differences(members: List[HAMemberInfo]) -> List[ConfigDifference]:
    """Primary/Secondary間の設定差分を検出

    Args:
        members: メンバー情報のリスト

    Returns:
        List[ConfigDifference]: 設定差分のリスト
    """
    differences: List[ConfigDifference] = []

    if len(members) < 2:
        return differences

    primary = None
    secondary = None

    for member in members:
        if member.role == HARole.PRIMARY:
            primary = member
        elif member.role == HARole.SECONDARY and secondary is None:
            secondary = member

    if primary is None or secondary is None:
        return differences

    p_config = primary.config
    s_config = secondary.config

    if p_config is None or s_config is None:
        return differences

    # 基本情報の差分
    if p_config.device_info.hostname != s_config.device_info.hostname:
        differences.append(
            ConfigDifference(
                section="機器情報",
                item="ホスト名",
                primary_value=p_config.device_info.hostname,
                secondary_value=s_config.device_info.hostname,
                description="ホスト名はHA構成で異なることが想定されます",
            )
        )

    # HA設定の差分
    if p_config.ha.priority != s_config.ha.priority:
        differences.append(
            ConfigDifference(
                section="HA設定",
                item="優先度",
                primary_value=p_config.ha.priority,
                secondary_value=s_config.ha.priority,
                description="優先度はHA構成で異なることが想定されます",
            )
        )

    # モデル名の差分（通常同一機種だが念のため）
    if p_config.device_info.model != s_config.device_info.model:
        differences.append(
            ConfigDifference(
                section="機器情報",
                item="モデル",
                primary_value=p_config.device_info.model,
                secondary_value=s_config.device_info.model,
                description="機種が異なります",
            )
        )

    # OSバージョンの差分
    if p_config.device_info.os_version != s_config.device_info.os_version:
        differences.append(
            ConfigDifference(
                section="機器情報",
                item="OSバージョン",
                primary_value=p_config.device_info.os_version,
                secondary_value=s_config.device_info.os_version,
                description="OSバージョンが異なります（HA構成では同一推奨）",
            )
        )

    # 管理IPの差分（HA管理インターフェース）
    # dstフィールドに管理IPアドレスが格納されている
    p_mgmt_ips = [mgmt.dst for mgmt in p_config.ha.ha_mgmt_interfaces if mgmt.dst]
    s_mgmt_ips = [mgmt.dst for mgmt in s_config.ha.ha_mgmt_interfaces if mgmt.dst]
    if p_mgmt_ips or s_mgmt_ips:
        differences.append(
            ConfigDifference(
                section="HA設定",
                item="HA管理IP",
                primary_value=", ".join(p_mgmt_ips) if p_mgmt_ips else "-",
                secondary_value=", ".join(s_mgmt_ips) if s_mgmt_ips else "-",
                description="HA管理インターフェースのIPアドレス（各機器固有）",
            )
        )

    # ポリシー数の差分（警告レベル）
    p_policy_count = len(p_config.firewall_policies)
    s_policy_count = len(s_config.firewall_policies)
    if p_policy_count != s_policy_count:
        differences.append(
            ConfigDifference(
                section="ポリシー",
                item="ファイアウォールポリシー数",
                primary_value=str(p_policy_count),
                secondary_value=str(s_policy_count),
                description="ポリシー数の不一致（設定同期の問題の可能性）",
            )
        )

    # オブジェクト数の差分
    p_addr_count = len(p_config.objects.addresses)
    s_addr_count = len(s_config.objects.addresses)
    if p_addr_count != s_addr_count:
        differences.append(
            ConfigDifference(
                section="オブジェクト",
                item="アドレスオブジェクト数",
                primary_value=str(p_addr_count),
                secondary_value=str(s_addr_count),
                description="オブジェクト数の不一致（設定同期の問題の可能性）",
            )
        )

    return differences
