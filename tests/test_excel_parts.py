#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel パーツ（common, global_sheets, vdom_sheets）のテスト
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.cluster import ClusterConfig, HAClusterInfo, HAMemberInfo, HARole
from models.config import (
    ConfigModel,
    DeviceInfo,
    DeviceType,
    FirewallPolicy,
    HAManagementInterface,
    HAMode,
    HASettings,
    Interface,
    Objects,
    PolicyAction,
    SystemSettings,
)

# openpyxlが利用可能かチェック
try:
    import openpyxl

    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


@pytest.fixture
def sample_config():
    """サンプル設定モデル"""
    config = ConfigModel()
    config.device_info = DeviceInfo(
        hostname="FW-TEST-01",
        model="FortiGate-60F",
        os_version="7.2.5",
        device_type=DeviceType.FORTIGATE,
        serial_number="FGT60F123456789",
    )
    config.ha = HASettings(mode=HAMode.STANDALONE)
    config.system_settings = SystemSettings(management_ip="192.168.1.1", timezone="Asia/Tokyo")
    config.interfaces = [
        Interface(name="port1", ip_address="192.168.1.1/24", interface_type="physical")
    ]
    config.firewall_policies = [
        FirewallPolicy(
            policy_id="1",
            name="Allow-All",
            source_interface=["port1"],
            destination_interface=["port2"],
            action=PolicyAction.ALLOW,
        )
    ]
    config.source_file = "test.conf"
    return config


@pytest.fixture
def sample_cluster_config(sample_config):
    """サンプルクラスタ設定"""
    config1 = sample_config
    config2 = ConfigModel()
    config2.device_info = DeviceInfo(
        hostname="FW-TEST-02",
        model="FortiGate-60F",
        os_version="7.2.5",
        device_type=DeviceType.FORTIGATE,
    )
    config2.ha = HASettings(mode=HAMode.ACTIVE_PASSIVE, priority="100")
    config2.source_file = "test2.conf"

    return ClusterConfig(
        is_cluster=True,
        primary_config=config1,
        cluster_info=HAClusterInfo(
            cluster_name="HA-Cluster",
            group_id="1",
            ha_mode=HAMode.ACTIVE_PASSIVE,
            members=[
                HAMemberInfo(
                    hostname="FW-TEST-01",
                    role=HARole.PRIMARY,
                    priority="200",
                    model="FortiGate-60F",
                    os_version="7.2.5",
                    config=config1,
                    source_file="test1.conf",
                ),
                HAMemberInfo(
                    hostname="FW-TEST-02",
                    role=HARole.SECONDARY,
                    priority="100",
                    model="FortiGate-60F",
                    os_version="7.2.5",
                    config=config2,
                    source_file="test2.conf",
                ),
            ],
        ),
    )


@pytest.mark.skipif(not OPENPYXL_AVAILABLE, reason="openpyxl not installed")
class TestExcelCommonMixin:
    """ExcelCommonMixinのテスト"""

    def test_import_common(self):
        """common.pyのインポート"""
        from exporters.excel_parts.common import ExcelCommonMixin

        assert ExcelCommonMixin is not None

    def test_mixin_has_required_methods(self):
        """必要なメソッドが存在する"""
        from exporters.excel_parts.common import ExcelCommonMixin

        assert hasattr(ExcelCommonMixin, "_create_sheet")
        assert hasattr(ExcelCommonMixin, "_set_header_row")
        assert hasattr(ExcelCommonMixin, "_set_cell")


@pytest.mark.skipif(not OPENPYXL_AVAILABLE, reason="openpyxl not installed")
class TestExcelGlobalSheetsMixin:
    """ExcelGlobalSheetsMixinのテスト"""

    def test_import_global_sheets(self):
        """global_sheets.pyのインポート"""
        from exporters.excel_parts.global_sheets import ExcelGlobalSheetsMixin

        assert ExcelGlobalSheetsMixin is not None

    def test_mixin_has_required_methods(self):
        """必要なメソッドが存在する"""
        from exporters.excel_parts.global_sheets import ExcelGlobalSheetsMixin

        assert hasattr(ExcelGlobalSheetsMixin, "_create_cluster_overview_sheet")
        assert hasattr(ExcelGlobalSheetsMixin, "_create_overview_sheet")


@pytest.mark.skipif(not OPENPYXL_AVAILABLE, reason="openpyxl not installed")
class TestExcelVdomSheetsMixin:
    """ExcelVdomSheetsMixinのテスト"""

    def test_import_vdom_sheets(self):
        """vdom_sheets.pyのインポート"""
        from exporters.excel_parts.vdom_sheets import ExcelVdomSheetsMixin

        assert ExcelVdomSheetsMixin is not None

    def test_mixin_has_required_methods(self):
        """必要なメソッドが存在する"""
        from exporters.excel_parts.vdom_sheets import ExcelVdomSheetsMixin

        # VDOMシート生成メソッドが存在することを確認
        assert hasattr(ExcelVdomSheetsMixin, "_create_vdom_sheets")


@pytest.mark.skipif(not OPENPYXL_AVAILABLE, reason="openpyxl not installed")
class TestExcelExporterIntegration:
    """ExcelExporter統合テスト"""

    def test_exporter_import(self):
        """ExcelExporterのインポート"""
        from exporters.excel import ExcelExporter

        assert ExcelExporter is not None

    def test_exporter_initialization(self, sample_config):
        """ExcelExporterの初期化"""
        from exporters.excel import ExcelExporter

        exporter = ExcelExporter(sample_config)
        assert exporter.config == sample_config
        assert exporter.is_cluster is False

    def test_exporter_with_cluster(self, sample_config, sample_cluster_config):
        """クラスタ設定でのExcelExporter初期化"""
        from exporters.excel import ExcelExporter

        exporter = ExcelExporter(sample_config, cluster_config=sample_cluster_config)
        assert exporter.is_cluster is True
        assert exporter.cluster_config == sample_cluster_config

    def test_export_to_file(self, sample_config, tmp_path):
        """ファイルへのエクスポート"""
        from exporters.excel import ExcelExporter

        exporter = ExcelExporter(sample_config)

        output_path = tmp_path / "test_output.xlsx"
        exporter.export(str(output_path))

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_export_with_sections(self, sample_config, tmp_path):
        """セクション指定でのエクスポート"""
        from exporters.excel import ExcelExporter

        exporter = ExcelExporter(sample_config)

        output_path = tmp_path / "test_output_sections.xlsx"
        exporter.export(str(output_path), sections=["device", "network"])

        assert output_path.exists()

    def test_export_cluster(self, sample_config, sample_cluster_config, tmp_path):
        """クラスタ設定のエクスポート"""
        from exporters.excel import ExcelExporter

        exporter = ExcelExporter(sample_config, cluster_config=sample_cluster_config)

        output_path = tmp_path / "test_cluster_output.xlsx"
        exporter.export(str(output_path))

        assert output_path.exists()


class TestExcelStylesIntegration:
    """Excel スタイル統合テスト"""

    def test_import_styles(self):
        """excel_styles.pyのインポート"""
        from exporters.excel_styles import GLOBAL_COLOR, VDOM_COLORS

        assert VDOM_COLORS is not None
        assert GLOBAL_COLOR is not None

    def test_vdom_colors_count(self):
        """VDOMカラーの数"""
        from exporters.excel_styles import VDOM_COLORS

        assert len(VDOM_COLORS) == 10  # 10色定義

    def test_color_structure(self):
        """カラー構造の確認"""
        from exporters.excel_styles import GLOBAL_COLOR, VDOM_COLORS

        # 各カラーに必要なキーが存在
        for color in VDOM_COLORS:
            assert "header_bg" in color
            assert "header_text" in color
            assert "tab_color" in color

        assert "header_bg" in GLOBAL_COLOR
        assert "header_text" in GLOBAL_COLOR
        assert "tab_color" in GLOBAL_COLOR
