#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HAクラスタパーサー
複数のFortiGate/Palo Alto設定ファイルを読み込み、クラスタ構成として統合する
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from models.config import ConfigModel, HAMode
from models.cluster import (
    ClusterConfig, HAClusterInfo, HAMemberInfo, HARole, ConfigDifference
)
from parsers.base import get_parser_for_file, get_parser_for_content, detect_encoding

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

        return ClusterConfig(
            primary_config=config,
            is_cluster=False,
            cluster_info=HAClusterInfo(
                cluster_name=config.device_info.hostname,
                group_id=config.ha.group_id,
                ha_mode=config.ha.mode,
                members=[HAMemberInfo(
                    hostname=config.device_info.hostname,
                    role=HARole.PRIMARY,
                    priority=config.ha.priority,
                    serial_number=config.device_info.serial_number,
                    config=config,
                    source_file=file_paths[0]
                )]
            )
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


def parse_ha_cluster_from_contents(
    contents: List[Tuple[str, str]]
) -> ClusterConfig:
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

        return ClusterConfig(
            primary_config=config,
            is_cluster=False,
            cluster_info=HAClusterInfo(
                cluster_name=config.device_info.hostname,
                group_id=config.ha.group_id,
                ha_mode=config.ha.mode,
                members=[HAMemberInfo(
                    hostname=config.device_info.hostname,
                    role=HARole.PRIMARY,
                    priority=config.ha.priority,
                    serial_number=config.device_info.serial_number,
                    config=config,
                    source_file=filename
                )]
            )
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


def _build_cluster_config(
    configs: List[Tuple[str, ConfigModel]]
) -> ClusterConfig:
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
        return ClusterConfig(
            primary_config=config,
            is_cluster=False,
            cluster_info=HAClusterInfo(
                cluster_name=config.device_info.hostname,
                group_id=config.ha.group_id,
                ha_mode=config.ha.mode,
                members=[HAMemberInfo(
                    hostname=config.device_info.hostname,
                    role=HARole.PRIMARY,
                    priority=config.ha.priority,
                    serial_number=config.device_info.serial_number,
                    config=config,
                    source_file=file_path
                )]
            )
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

    # クラスタ情報を構築
    first_config = configs[0][1]
    cluster_info = HAClusterInfo(
        cluster_name=first_config.ha.group_name or first_config.device_info.hostname,
        group_id=first_config.ha.group_id,
        ha_mode=first_config.ha.mode,
        members=members
    )

    # 設定差分を検出
    differences = _detect_config_differences(members) if len(members) > 1 else []

    return ClusterConfig(
        cluster_info=cluster_info,
        primary_config=primary_member.config if primary_member else None,
        config_differences=differences,
        is_cluster=True
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
    if len(group_ids) == 1 and group_ids != {''}:
        return True

    # グループIDが設定されていなくても、同じHAモードであればクラスタとみなす
    if len(ha_modes) == 1 and HAMode.STANDALONE not in ha_modes:
        return True

    return False


def _determine_ha_roles(
    configs: List[Tuple[str, ConfigModel]]
) -> List[HAMemberInfo]:
    """各設定のHA役割を判定

    優先度(priority)が高い方がPrimary（FortiGateの場合、数値が大きいほど優先）

    Args:
        configs: (ファイルパス, ConfigModel)のタプルのリスト

    Returns:
        List[HAMemberInfo]: メンバー情報のリスト
    """
    members = []

    for file_path, config in configs:
        members.append(HAMemberInfo(
            hostname=config.device_info.hostname,
            role=HARole.UNKNOWN,
            priority=config.ha.priority,
            serial_number=config.device_info.serial_number,
            config=config,
            source_file=file_path
        ))

    # 優先度でソート（降順：高い方がPrimary）
    def get_priority(member: HAMemberInfo) -> int:
        try:
            return int(member.priority)
        except (ValueError, TypeError):
            return 0

    members.sort(key=get_priority, reverse=True)

    # 役割を割り当て
    if members:
        members[0].role = HARole.PRIMARY
        for i in range(1, len(members)):
            members[i].role = HARole.SECONDARY

    return members


def _detect_config_differences(
    members: List[HAMemberInfo]
) -> List[ConfigDifference]:
    """Primary/Secondary間の設定差分を検出

    Args:
        members: メンバー情報のリスト

    Returns:
        List[ConfigDifference]: 設定差分のリスト
    """
    differences = []

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
        differences.append(ConfigDifference(
            section="機器情報",
            item="ホスト名",
            primary_value=p_config.device_info.hostname,
            secondary_value=s_config.device_info.hostname,
            description="ホスト名はHA構成で異なることが想定されます"
        ))

    # HA設定の差分
    if p_config.ha.priority != s_config.ha.priority:
        differences.append(ConfigDifference(
            section="HA設定",
            item="優先度",
            primary_value=p_config.ha.priority,
            secondary_value=s_config.ha.priority,
            description="優先度はHA構成で異なることが想定されます"
        ))

    # 管理IPの差分（HA管理インターフェース）
    p_mgmt_ips = [mgmt.gateway for mgmt in p_config.ha.ha_mgmt_interfaces]
    s_mgmt_ips = [mgmt.gateway for mgmt in s_config.ha.ha_mgmt_interfaces]
    if p_mgmt_ips != s_mgmt_ips:
        differences.append(ConfigDifference(
            section="HA設定",
            item="HA管理インターフェース",
            primary_value=", ".join(p_mgmt_ips) if p_mgmt_ips else "-",
            secondary_value=", ".join(s_mgmt_ips) if s_mgmt_ips else "-",
            description="HA管理インターフェースの設定差分"
        ))

    # ポリシー数の差分（警告レベル）
    p_policy_count = len(p_config.firewall_policies)
    s_policy_count = len(s_config.firewall_policies)
    if p_policy_count != s_policy_count:
        differences.append(ConfigDifference(
            section="ポリシー",
            item="ファイアウォールポリシー数",
            primary_value=str(p_policy_count),
            secondary_value=str(s_policy_count),
            description="ポリシー数の不一致（設定同期の問題の可能性）"
        ))

    # オブジェクト数の差分
    p_addr_count = len(p_config.objects.addresses)
    s_addr_count = len(s_config.objects.addresses)
    if p_addr_count != s_addr_count:
        differences.append(ConfigDifference(
            section="オブジェクト",
            item="アドレスオブジェクト数",
            primary_value=str(p_addr_count),
            secondary_value=str(s_addr_count),
            description="オブジェクト数の不一致（設定同期の問題の可能性）"
        ))

    return differences
