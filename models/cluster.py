#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HAクラスタ構成データモデル
複数機器のHA構成を統合して表現する
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from models.config import ConfigModel, HAMode


class HARole(Enum):
    """HA役割"""
    PRIMARY = "Primary"
    SECONDARY = "Secondary"
    UNKNOWN = "Unknown"


@dataclass
class HAMemberInfo:
    """HAクラスタメンバー情報"""
    hostname: str = ""
    role: HARole = HARole.UNKNOWN
    priority: str = ""
    serial_number: str = ""
    config: Optional[ConfigModel] = None
    source_file: str = ""

    def get_display_role(self) -> str:
        """表示用の役割名を取得"""
        return self.role.value


@dataclass
class HAClusterInfo:
    """HAクラスタ全体情報"""
    cluster_name: str = ""
    group_id: str = ""
    ha_mode: HAMode = HAMode.STANDALONE
    members: List[HAMemberInfo] = field(default_factory=list)

    def get_primary(self) -> Optional[HAMemberInfo]:
        """Primaryメンバーを取得"""
        for member in self.members:
            if member.role == HARole.PRIMARY:
                return member
        return None

    def get_secondary(self) -> Optional[HAMemberInfo]:
        """Secondaryメンバーを取得"""
        for member in self.members:
            if member.role == HARole.SECONDARY:
                return member
        return None

    def get_member_count(self) -> int:
        """メンバー数を取得"""
        return len(self.members)


@dataclass
class ConfigDifference:
    """設定差分情報"""
    section: str = ""
    item: str = ""
    primary_value: str = ""
    secondary_value: str = ""
    description: str = ""


@dataclass
class ClusterConfig:
    """HAクラスタ統合設定

    複数のFortiGate/Palo Alto設定を統合し、
    クラスタ全体として1つのパラメータシートを生成するためのデータモデル
    """
    cluster_info: HAClusterInfo = field(default_factory=HAClusterInfo)
    primary_config: Optional[ConfigModel] = None
    config_differences: List[ConfigDifference] = field(default_factory=list)
    is_cluster: bool = False

    def get_config(self) -> Optional[ConfigModel]:
        """代表設定（Primary）を取得"""
        return self.primary_config

    def get_summary(self) -> Dict[str, Any]:
        """設定のサマリー情報を取得"""
        if self.primary_config:
            summary = self.primary_config.get_summary()
            summary["is_cluster"] = self.is_cluster
            summary["member_count"] = self.cluster_info.get_member_count()
            summary["ha_mode"] = self.cluster_info.ha_mode.value
            summary["group_id"] = self.cluster_info.group_id
            return summary
        return {
            "device_type": "Unknown",
            "hostname": "",
            "version": "",
            "is_cluster": self.is_cluster,
            "member_count": 0,
            "ha_mode": self.cluster_info.ha_mode.value,
            "group_id": self.cluster_info.group_id,
        }

    def has_differences(self) -> bool:
        """設定差分があるかどうか"""
        return len(self.config_differences) > 0
