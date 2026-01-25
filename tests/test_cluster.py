#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HAクラスタパーサーのテスト
"""

import pytest
from unittest.mock import patch, MagicMock

from parsers.cluster import (
    parse_ha_cluster,
    parse_ha_cluster_from_contents,
    _get_ha_mgmt_info,
    _detect_ha_cluster,
    _determine_ha_roles,
    _detect_config_differences,
    _build_cluster_config,
)
from models.config import ConfigModel, HAMode, HASettings, DeviceInfo, HAManagementInterface
from models.cluster import ClusterConfig, HAClusterInfo, HAMemberInfo, HARole


class TestParseHaCluster:
    """parse_ha_cluster関数のテスト"""

    def test_empty_file_paths(self):
        """空のファイルリストの場合"""
        result = parse_ha_cluster([])
        assert result.is_cluster is False

    @patch("parsers.cluster._parse_single_file")
    def test_single_file_success(self, mock_parse):
        """単一ファイルのパース成功"""
        mock_config = ConfigModel()
        mock_config.device_info.hostname = "FW-01"
        mock_config.ha = HASettings(mode=HAMode.STANDALONE)
        mock_parse.return_value = mock_config

        result = parse_ha_cluster(["/path/to/config.conf"])

        assert result.is_cluster is False
        assert result.primary_config == mock_config
        assert result.cluster_info.cluster_name == "FW-01"
        assert len(result.cluster_info.members) == 1
        assert result.cluster_info.members[0].role == HARole.PRIMARY

    @patch("parsers.cluster._parse_single_file")
    def test_single_file_failure(self, mock_parse):
        """単一ファイルのパース失敗"""
        mock_parse.return_value = None

        result = parse_ha_cluster(["/path/to/config.conf"])

        assert result.is_cluster is False
        assert result.primary_config is None

    @patch("parsers.cluster._parse_single_file")
    def test_multiple_files_no_valid(self, mock_parse):
        """複数ファイルだが全てパース失敗"""
        mock_parse.return_value = None

        result = parse_ha_cluster(["/path/to/config1.conf", "/path/to/config2.conf"])

        assert result.is_cluster is False


class TestParseHaClusterFromContents:
    """parse_ha_cluster_from_contents関数のテスト"""

    def test_empty_contents(self):
        """空のコンテンツリストの場合"""
        result = parse_ha_cluster_from_contents([])
        assert result.is_cluster is False

    @patch("parsers.cluster._parse_single_content")
    def test_single_content_success(self, mock_parse):
        """単一コンテンツのパース成功"""
        mock_config = ConfigModel()
        mock_config.device_info.hostname = "FW-01"
        mock_config.ha = HASettings(mode=HAMode.STANDALONE)
        mock_parse.return_value = mock_config

        result = parse_ha_cluster_from_contents([("config.conf", "content")])

        assert result.is_cluster is False
        assert result.primary_config == mock_config
        assert len(result.cluster_info.members) == 1

    @patch("parsers.cluster._parse_single_content")
    def test_single_content_failure(self, mock_parse):
        """単一コンテンツのパース失敗"""
        mock_parse.return_value = None

        result = parse_ha_cluster_from_contents([("config.conf", "invalid content")])

        assert result.is_cluster is False
        assert result.primary_config is None

    @patch("parsers.cluster._parse_single_content")
    def test_multiple_contents_all_fail(self, mock_parse):
        """複数コンテンツだが全てパース失敗"""
        mock_parse.return_value = None

        result = parse_ha_cluster_from_contents(
            [
                ("config1.conf", "content1"),
                ("config2.conf", "content2"),
            ]
        )

        assert result.is_cluster is False


class TestGetHaMgmtInfo:
    """_get_ha_mgmt_info関数のテスト"""

    def test_no_ha_mgmt_interfaces(self):
        """HA管理インターフェースなしの場合"""
        config = ConfigModel()
        config.ha = HASettings(mode=HAMode.STANDALONE, ha_mgmt_interfaces=[])

        ip, interface = _get_ha_mgmt_info(config)

        assert ip == ""
        assert interface == ""

    def test_single_ha_mgmt_interface(self):
        """単一のHA管理インターフェース"""
        config = ConfigModel()
        config.ha = HASettings(
            mode=HAMode.ACTIVE_PASSIVE,
            ha_mgmt_interfaces=[
                HAManagementInterface(
                    id="1", interface="port1", dst="10.0.0.1/24", gateway="10.0.0.254"
                )
            ],
        )

        ip, interface = _get_ha_mgmt_info(config)

        assert ip == "10.0.0.1/24"
        assert interface == "port1"

    def test_multiple_ha_mgmt_interfaces(self):
        """複数のHA管理インターフェース"""
        config = ConfigModel()
        config.ha = HASettings(
            mode=HAMode.ACTIVE_PASSIVE,
            ha_mgmt_interfaces=[
                HAManagementInterface(
                    id="1", interface="port1", dst="10.0.0.1/24", gateway="10.0.0.254"
                ),
                HAManagementInterface(
                    id="2", interface="port1", dst="10.0.0.2/24", gateway="10.0.0.254"
                ),
            ],
        )

        ip, interface = _get_ha_mgmt_info(config)

        assert "10.0.0.1/24" in ip
        assert "10.0.0.2/24" in ip
        assert interface == "port1"


class TestDetectHaCluster:
    """_detect_ha_cluster関数のテスト"""

    def test_single_config(self):
        """単一設定はクラスタではない"""
        config = ConfigModel()
        config.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, group_id="1")

        result = _detect_ha_cluster([("/path/config.conf", config)])

        assert result is False

    def test_same_group_id(self):
        """同じグループIDを持つ場合はクラスタ"""
        config1 = ConfigModel()
        config1.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, group_id="1")

        config2 = ConfigModel()
        config2.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, group_id="1")

        result = _detect_ha_cluster(
            [
                ("/path/config1.conf", config1),
                ("/path/config2.conf", config2),
            ]
        )

        assert result is True

    def test_different_group_id_same_ha_mode(self):
        """異なるグループIDでも同じHAモードならクラスタとみなす"""
        config1 = ConfigModel()
        config1.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, group_id="1")

        config2 = ConfigModel()
        config2.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, group_id="2")

        result = _detect_ha_cluster(
            [
                ("/path/config1.conf", config1),
                ("/path/config2.conf", config2),
            ]
        )

        # 同じHAモードであればクラスタとみなす（グループIDが異なっても）
        assert result is True

    def test_mixed_ha_modes(self):
        """異なるHAモードの場合はクラスタではない"""
        config1 = ConfigModel()
        config1.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, group_id="1")

        config2 = ConfigModel()
        config2.ha = HASettings(mode=HAMode.ACTIVE_ACTIVE, group_id="2")

        result = _detect_ha_cluster(
            [
                ("/path/config1.conf", config1),
                ("/path/config2.conf", config2),
            ]
        )

        # 異なるHAモードはクラスタではない
        assert result is False

    def test_same_ha_mode_no_group_id(self):
        """グループIDなしでも同じHAモードならクラスタ"""
        config1 = ConfigModel()
        config1.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, group_id="")

        config2 = ConfigModel()
        config2.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, group_id="")

        result = _detect_ha_cluster(
            [
                ("/path/config1.conf", config1),
                ("/path/config2.conf", config2),
            ]
        )

        assert result is True

    def test_standalone_mode(self):
        """STANDALONEモードはクラスタではない"""
        config1 = ConfigModel()
        config1.ha = HASettings(mode=HAMode.STANDALONE)

        config2 = ConfigModel()
        config2.ha = HASettings(mode=HAMode.STANDALONE)

        result = _detect_ha_cluster(
            [
                ("/path/config1.conf", config1),
                ("/path/config2.conf", config2),
            ]
        )

        assert result is False


class TestDetermineHaRoles:
    """_determine_ha_roles関数のテスト"""

    def test_priority_based_role_assignment(self):
        """優先度に基づいて役割を割り当て"""
        config1 = ConfigModel()
        config1.device_info.hostname = "FW-01"
        config1.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, priority="200")

        config2 = ConfigModel()
        config2.device_info.hostname = "FW-02"
        config2.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, priority="100")

        members = _determine_ha_roles(
            [
                ("/path/config1.conf", config1),
                ("/path/config2.conf", config2),
            ]
        )

        # 優先度が高い方がPrimary
        assert len(members) == 2
        primary = [m for m in members if m.role == HARole.PRIMARY][0]
        secondary = [m for m in members if m.role == HARole.SECONDARY][0]

        assert primary.hostname == "FW-01"
        assert primary.priority == "200"
        assert secondary.hostname == "FW-02"
        assert secondary.priority == "100"

    def test_invalid_priority_handled(self):
        """無効な優先度の場合も処理"""
        config1 = ConfigModel()
        config1.device_info.hostname = "FW-01"
        config1.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, priority="invalid")

        config2 = ConfigModel()
        config2.device_info.hostname = "FW-02"
        config2.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, priority="100")

        members = _determine_ha_roles(
            [
                ("/path/config1.conf", config1),
                ("/path/config2.conf", config2),
            ]
        )

        # 無効な優先度は0として扱われる
        assert len(members) == 2


class TestDetectConfigDifferences:
    """_detect_config_differences関数のテスト"""

    def test_single_member(self):
        """単一メンバーの場合は差分なし"""
        config = ConfigModel()
        config.device_info.hostname = "FW-01"
        config.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, priority="200")

        member = HAMemberInfo(
            hostname="FW-01",
            role=HARole.PRIMARY,
            priority="200",
            config=config,
            source_file="/path/config.conf",
        )

        differences = _detect_config_differences([member])

        assert len(differences) == 0

    def test_hostname_difference(self):
        """ホスト名の差分を検出"""
        config1 = ConfigModel()
        config1.device_info.hostname = "FW-01"
        config1.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, priority="200")

        config2 = ConfigModel()
        config2.device_info.hostname = "FW-02"
        config2.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, priority="100")

        members = [
            HAMemberInfo(
                hostname="FW-01",
                role=HARole.PRIMARY,
                priority="200",
                config=config1,
                source_file="/path/config1.conf",
            ),
            HAMemberInfo(
                hostname="FW-02",
                role=HARole.SECONDARY,
                priority="100",
                config=config2,
                source_file="/path/config2.conf",
            ),
        ]

        differences = _detect_config_differences(members)

        # ホスト名と優先度の差分が検出される
        assert len(differences) >= 2
        hostname_diff = [d for d in differences if d.item == "ホスト名"]
        assert len(hostname_diff) == 1
        assert hostname_diff[0].primary_value == "FW-01"
        assert hostname_diff[0].secondary_value == "FW-02"

    def test_policy_count_difference(self):
        """ポリシー数の差分を検出"""
        config1 = ConfigModel()
        config1.device_info.hostname = "FW-01"
        config1.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, priority="200")
        # ポリシー数の差分を作成するために空のまま

        config2 = ConfigModel()
        config2.device_info.hostname = "FW-01"  # 同じホスト名
        config2.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, priority="200")  # 同じ優先度

        members = [
            HAMemberInfo(
                hostname="FW-01",
                role=HARole.PRIMARY,
                priority="200",
                config=config1,
                source_file="/path/config1.conf",
            ),
            HAMemberInfo(
                hostname="FW-01",
                role=HARole.SECONDARY,
                priority="200",
                config=config2,
                source_file="/path/config2.conf",
            ),
        ]

        differences = _detect_config_differences(members)

        # ポリシー数は同じなので差分はホスト名と優先度のみ（同じなので差分なし）
        # 差分がないはずだが、オブジェクト数やポリシー数で差分が出るかもしれない
        # 両方とも空なので差分はない
        policy_diff = [d for d in differences if d.item == "ファイアウォールポリシー数"]
        assert len(policy_diff) == 0


class TestBuildClusterConfig:
    """_build_cluster_config関数のテスト"""

    def test_empty_configs(self):
        """空の設定リスト"""
        result = _build_cluster_config([])

        assert result.is_cluster is False

    def test_non_ha_cluster(self):
        """HAクラスタではない場合"""
        config = ConfigModel()
        config.device_info.hostname = "FW-01"
        config.ha = HASettings(mode=HAMode.STANDALONE)

        result = _build_cluster_config([("/path/config.conf", config)])

        assert result.is_cluster is False
        assert result.primary_config == config

    def test_ha_cluster_with_two_members(self):
        """2メンバーのHAクラスタ"""
        config1 = ConfigModel()
        config1.device_info.hostname = "FW-01"
        config1.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, group_id="1", priority="200")

        config2 = ConfigModel()
        config2.device_info.hostname = "FW-02"
        config2.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, group_id="1", priority="100")

        result = _build_cluster_config(
            [
                ("/path/config1.conf", config1),
                ("/path/config2.conf", config2),
            ]
        )

        assert result.is_cluster is True
        assert len(result.cluster_info.members) == 2
        assert result.primary_config is not None
