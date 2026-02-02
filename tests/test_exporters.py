#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エクスポーターのテスト
"""

import tempfile
from pathlib import Path

import pytest

from exporters.html import HTMLExporter

try:
    import exporters.excel as excel_module  # type: ignore

    ExcelExporter = excel_module.ExcelExporter  # type: ignore[attr-defined]
    EXCEL_AVAILABLE = bool(getattr(excel_module, "OPENPYXL_AVAILABLE", True))
except ImportError:
    ExcelExporter = None  # type: ignore[assignment]
    EXCEL_AVAILABLE = False

try:
    from exporters.pdf import PDFExporter  # type: ignore

    PDF_AVAILABLE = True
except ImportError:
    PDFExporter = None  # type: ignore[assignment]
    PDF_AVAILABLE = False
from exporters.utils import CacheManager, HtmlFormatter


class TestHtmlFormatter:
    """HTMLフォーマッターのテスト"""

    def test_escape_html(self):
        """HTMLエスケープ"""
        assert HtmlFormatter.escape("<script>") == "&lt;script&gt;"
        assert HtmlFormatter.escape("&") == "&amp;"
        assert HtmlFormatter.escape('"') == "&quot;"
        assert HtmlFormatter.escape(None) == ""

    def test_list_to_str(self):
        """リストから文字列への変換"""
        assert HtmlFormatter.list_to_str(["a", "b", "c"]) == "a, b, c"
        assert HtmlFormatter.list_to_str(["a", "b"], " | ") == "a | b"
        assert HtmlFormatter.list_to_str([]) == ""

    def test_list_to_lines(self):
        """リストから改行区切りへの変換"""
        result = HtmlFormatter.list_to_lines(["a", "b"])
        assert "a<br>b" == result

    def test_with_default(self):
        """デフォルト値付き表示"""
        assert HtmlFormatter.with_default("value", "default") == "value"
        result = HtmlFormatter.with_default("", "default")
        assert "default" in result
        assert "text-muted" in result

    def test_to_badges(self):
        """バッジ変換"""
        color_map = {"http": "primary", "https": "success"}
        result = HtmlFormatter.to_badges(["http", "https"], color_map)
        assert "badge" in result
        assert "primary" in result
        assert "success" in result

    def test_with_default_annotation_is_default(self):
        """デフォルト値アノテーション（デフォルト時）"""
        result = HtmlFormatter.with_default_annotation("128", True)
        assert "128" in result
        assert "デフォルト値" in result
        assert "text-muted" in result

    def test_with_default_annotation_not_default(self):
        """デフォルト値アノテーション（非デフォルト時）"""
        result = HtmlFormatter.with_default_annotation("200", False)
        assert result == "200"
        assert "デフォルト値" not in result


class TestHTMLExporter:
    """HTMLエクスポーターのテスト"""

    def test_export_to_string(self, sample_config_model):
        """文字列として出力"""
        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        assert "<!DOCTYPE html>" in html
        assert sample_config_model.device_info.hostname in html
        assert "パラメータシート" in html

    def test_export_to_file(self, sample_config_model):
        """ファイルとして出力"""
        exporter = HTMLExporter(sample_config_model)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            output_path = f.name

        try:
            exporter.export(output_path)

            # ファイルが作成されていることを確認
            assert Path(output_path).exists()

            # 内容を確認
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "<!DOCTYPE html>" in content
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_contains_device_info(self, sample_config_model):
        """機器情報が含まれていることを確認"""
        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        assert sample_config_model.device_info.hostname in html
        assert sample_config_model.device_info.model in html
        assert sample_config_model.device_info.os_version in html

    def test_export_contains_interfaces(self, sample_config_model):
        """インターフェース情報が含まれていることを確認"""
        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        for iface in sample_config_model.interfaces:
            assert iface.name in html

    def test_export_contains_policies(self, sample_config_model):
        """ポリシー情報が含まれていることを確認"""
        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        for policy in sample_config_model.firewall_policies:
            assert policy.name in html

    def test_export_contains_blackhole_route(self, sample_config_model):
        """blackhole ルートがスタティックルートに明示されることを確認"""
        from models.config import Route

        sample_config_model.routes.append(
            Route(
                name="BH-TEST",
                destination="203.0.113.0/24",
                gateway="",  # blackholeはゲートウェイ空
                interface="",
                distance="10",
                vdom="root",
                route_type="blackhole",
            )
        )

        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        assert "BH-TEST" in html
        assert "blackhole" in html

    def test_export_for_pdf(self, sample_config_model):
        """PDF用出力（JavaScript削除）"""
        exporter = HTMLExporter(sample_config_model, for_pdf=True)
        html = exporter.export()

        # PDF用はscriptタグを含まない
        assert "<script>" not in html or "search" not in html.lower()

    def test_export_contains_nat_mode(self, sample_config_model):
        """NATモードが含まれていることを確認"""
        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        # デフォルトはPolicy Base NAT
        assert "Policy Base NAT" in html

    def test_export_contains_central_nat_mode(self, sample_config_model):
        """Central NATモードが含まれていることを確認"""
        sample_config_model.system_settings.central_nat = True
        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        assert "Central NAT" in html

    def test_export_contains_central_snat_section(self, sample_config_model):
        """Central SNAT Mapセクションが含まれていることを確認"""
        from models.config import NATPolicy

        sample_config_model.system_settings.central_nat = True
        sample_config_model.nat_policies.append(
            NATPolicy(
                name="1",
                nat_type="central-snat",
                original_source="10.0.0.0/24",
                original_destination="all",
                nat_ippool="SNAT-Pool-1",
                protocol="0",
                interface="port2 -> port1",
                vdom="root",
                enabled=True,
            )
        )

        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        assert "Central SNAT Map" in html
        assert "SNAT-Pool-1" in html
        assert "10.0.0.0/24" in html

    def test_export_default_annotation_in_ha(self, sample_config_model):
        """HA設定でデフォルト値アノテーションが表示されることを確認"""
        from models.config import HAMode, HASettings

        sample_config_model.ha = HASettings(
            mode=HAMode.ACTIVE_PASSIVE,
            group_id="1",
            priority="128",
            hb_interval="2",
            hb_lost_threshold="6",
        )
        sample_config_model.default_fields = {
            "ha.priority",
            "ha.hb_interval",
            "ha.hb_lost_threshold",
        }

        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        assert "デフォルト値" in html

    def test_escape_special_characters(self, sample_config_model):
        """特殊文字のエスケープ"""
        # ホスト名に特殊文字を含める
        sample_config_model.device_info.hostname = "<test>&hostname"
        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        # HTMLエスケープされていることを確認
        assert "&lt;test&gt;" in html
        assert "&amp;hostname" in html


class TestExcelExporter:
    """Excelエクスポーターのテスト"""

    def test_export_to_file(self, sample_config_model):
        """ファイルとして出力"""
        if not EXCEL_AVAILABLE or ExcelExporter is None:
            pytest.skip("openpyxl が未導入のため ExcelExporter テストをスキップ")
        exporter = ExcelExporter(sample_config_model)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            workbook = exporter.export(output_path)

            # ファイルが作成されていることを確認
            assert Path(output_path).exists()

            # ワークブックが返されることを確認
            assert workbook is not None
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_creates_sheets(self, sample_config_model):
        """必要なシートが作成されていることを確認"""
        if not EXCEL_AVAILABLE or ExcelExporter is None:
            pytest.skip("openpyxl が未導入のため ExcelExporter テストをスキップ")
        exporter = ExcelExporter(sample_config_model)
        workbook = exporter.export()

        sheet_names = workbook.sheetnames

        # 必須シートの存在確認
        assert "機器概要" in sheet_names
        assert "システム設定" in sheet_names
        assert "インターフェース" in sheet_names
        assert "ルーティング" in sheet_names
        assert "オブジェクト" in sheet_names
        assert "ファイアウォールポリシー" in sheet_names
        assert "NAT設定" in sheet_names
        assert "VPN設定" in sheet_names

    def test_overview_sheet_content(self, sample_config_model):
        """機器概要シートの内容確認"""
        if not EXCEL_AVAILABLE or ExcelExporter is None:
            pytest.skip("openpyxl が未導入のため ExcelExporter テストをスキップ")
        exporter = ExcelExporter(sample_config_model)
        workbook = exporter.export()

        overview_sheet = workbook["機器概要"]

        # シートにホスト名が含まれていることを確認
        found_hostname = False
        for row in overview_sheet.iter_rows(values_only=True):
            if sample_config_model.device_info.hostname in str(row):
                found_hostname = True
                break
        assert found_hostname

    def test_policies_sheet_content(self, sample_config_model):
        """ポリシーシートの内容確認"""
        if not EXCEL_AVAILABLE or ExcelExporter is None:
            pytest.skip("openpyxl が未導入のため ExcelExporter テストをスキップ")
        exporter = ExcelExporter(sample_config_model)
        workbook = exporter.export()

        policy_sheet = workbook["ファイアウォールポリシー"]

        # ヘッダー行の確認
        header_row = list(policy_sheet.iter_rows(min_row=1, max_row=1, values_only=True))[0]
        assert "ポリシー名" in header_row

        # ポリシーデータの存在確認
        found_policy = False
        for row in policy_sheet.iter_rows(min_row=2, values_only=True):
            if sample_config_model.firewall_policies[0].name in str(row):
                found_policy = True
                break
        assert found_policy

    def test_routes_sheet_contains_blackhole_gateway_label(self, sample_config_model):
        """blackhole ルートがゲートウェイ欄に明示されることを確認"""
        if not EXCEL_AVAILABLE or ExcelExporter is None:
            pytest.skip("openpyxl が未導入のため ExcelExporter テストをスキップ")
        from models.config import Route

        sample_config_model.routes.append(
            Route(
                name="BH-TEST",
                destination="203.0.113.0/24",
                gateway="",
                interface="",
                distance="10",
                vdom="root",
                route_type="blackhole",
            )
        )

        exporter = ExcelExporter(sample_config_model)
        workbook = exporter.export()

        ws = workbook["ルーティング"]
        # 2行目以降に BH-TEST があり、ゲートウェイ列(3)が blackhole になっていること
        found = False
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and str(row[0]) == "BH-TEST":
                found = True
                assert str(row[2]) == "blackhole"
                break
        assert found


class TestCacheManager:
    """キャッシュマネージャーのテスト"""

    def test_singleton(self):
        """シングルトンパターン"""
        cache1 = CacheManager()
        cache2 = CacheManager()
        assert cache1 is cache2

    def test_set_and_get(self):
        """値の設定と取得"""
        cache = CacheManager()
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"

    def test_get_nonexistent(self):
        """存在しないキーの取得"""
        cache = CacheManager()
        assert cache.get("nonexistent_key") is None

    def test_clear_specific_key(self):
        """特定キーのクリア"""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

        # クリーンアップ
        cache.clear()

    def test_internet_service_display(self, sample_config_model):
        """Internet Serviceの表示"""
        from models.config import FirewallPolicy, PolicyAction

        # Internet Service名を含むポリシーを追加
        policy = FirewallPolicy(
            policy_id="2",
            name="Internet-Service-Policy",
            source_address=["all"],
            destination_address=[],
            internet_service_name=["Google-Web", "Dropbox-Web"],
            action=PolicyAction.ALLOW,
            vdom="root",
        )
        sample_config_model.firewall_policies.append(policy)

        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        # Internet Serviceが表示されていることを確認
        assert "Google-Web" in html or "Web" in html
        assert "bg-info" in html  # Internet Service用のバッジ色

    def test_tooltip_generation(self, sample_config_model):
        """ツールチップの生成"""
        exporter = HTMLExporter(sample_config_model)

        # インターフェースツールチップ
        tooltip = exporter._get_interface_tooltip("port1", "root")
        assert len(tooltip) > 0

        # アドレストールチップ
        tooltip = exporter._get_address_tooltip("Server-A", "root")
        assert len(tooltip) > 0

        # サービストールチップ
        tooltip = exporter._get_service_tooltip("HTTP", "root")
        assert len(tooltip) > 0

    def test_tooltip_in_html(self, sample_config_model):
        """HTML出力にツールチップが含まれている"""
        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        # ツールチップ用のクラスが含まれていることを確認
        assert "has-tooltip" in html
        assert "data-tooltip" in html

    def test_sections_filtering(self, sample_config_model):
        """セクションのフィルタリング"""
        # 特定のセクションのみを出力
        exporter = HTMLExporter(sample_config_model, sections=["device_info", "policies"])
        html = exporter.export()

        # 指定したセクションが含まれていることを確認
        assert "機器概要" in html or "device_info" in html.lower()
        assert "ファイアウォールポリシー" in html or "policies" in html.lower()

    def test_pdf_exporter(self, sample_config_model):
        """PDFエクスポーターのテスト"""
        if not PDF_AVAILABLE or PDFExporter is None:
            pytest.skip("weasyprint が未導入のため PDFExporter テストをスキップ")
        exporter = PDFExporter(sample_config_model)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            exporter.export(output_path)

            # ファイルが作成されていることを確認
            assert Path(output_path).exists()
            # PDFファイルのサイズが0より大きいことを確認
            assert Path(output_path).stat().st_size > 0
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_pdf_exporter_header_css_with_cluster_config(self, sample_config_model):
        """ClusterConfig を渡してもヘッダーCSS生成で落ちないこと"""
        if not PDF_AVAILABLE or PDFExporter is None:
            pytest.skip("weasyprint が未導入のため PDFExporter テストをスキップ")
        from models.cluster import ClusterConfig, HAClusterInfo

        cluster = ClusterConfig(
            is_cluster=True,
            primary_config=sample_config_model,
            cluster_info=HAClusterInfo(
                cluster_name="CLUSTER-TEST",
                group_id="1",
                ha_mode=sample_config_model.ha.mode,
                members=[],
            ),
        )

        exporter = PDFExporter(cluster)
        css = exporter._generate_header_css()
        assert "CLUSTER-TEST" in css

    def test_excel_export_with_sections(self, sample_config_model):
        """セクション指定でのExcel出力"""
        if not EXCEL_AVAILABLE or ExcelExporter is None:
            pytest.skip("openpyxl が未導入のため ExcelExporter テストをスキップ")
        exporter = ExcelExporter(sample_config_model, sections=["device_info", "policies"])
        workbook = exporter.export()

        sheet_names = workbook.sheetnames
        # 指定したセクションが含まれていることを確認
        assert "機器概要" in sheet_names
        assert "ファイアウォールポリシー" in sheet_names
