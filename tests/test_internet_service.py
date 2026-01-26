#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Internet Service関連のテスト
"""

import pytest

from parsers.fortigate import FortiGateParser
from exporters.html import HTMLExporter
from exporters.utils import load_isdb
from models.config import ConfigModel, FirewallPolicy, PolicyAction


class TestInternetServiceParsing:
    """Internet Serviceのパーステスト"""

    def test_parse_internet_service_name(self):
        """internet-service-nameのパース"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config firewall policy
    edit 53
        set name "pref-0053"
        set srcintf "v1312-Internet"
        set dstintf "v930-SCO-WAN"
        set action accept
        set srcaddr "pref-172.21.0.0/16"
        set internet-service enable
        set internet-service-name "Google-Web" "Google-RTMP" "Google-Gmail"
        set schedule "always"
        set logtraffic all
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.firewall_policies) == 1
        policy = config.firewall_policies[0]
        assert policy.policy_id == "53"
        assert policy.name == "pref-0053"
        assert len(policy.internet_service_name) == 3
        assert "Google-Web" in policy.internet_service_name
        assert "Google-RTMP" in policy.internet_service_name
        assert "Google-Gmail" in policy.internet_service_name

    def test_parse_internet_service_with_dstaddr(self):
        """internet-service-nameとdstaddrの両方が指定されている場合"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config firewall policy
    edit 1
        set name "test-policy"
        set srcaddr "all"
        set dstaddr "all" "Server-A"
        set internet-service enable
        set internet-service-name "Dropbox-Web" "Box-Web"
        set action accept
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.firewall_policies) == 1
        policy = config.firewall_policies[0]
        assert len(policy.destination_address) == 2
        assert "all" in policy.destination_address
        assert "Server-A" in policy.destination_address
        assert len(policy.internet_service_name) == 2
        assert "Dropbox-Web" in policy.internet_service_name
        assert "Box-Web" in policy.internet_service_name


class TestInternetServiceDisplay:
    """Internet Serviceの表示テスト"""

    def test_internet_service_tooltip(self, sample_config_model):
        """Internet Serviceのツールチップ生成"""
        # Internet Service名を含むポリシーを追加
        policy = FirewallPolicy(
            policy_id="1",
            name="Internet-Service-Policy",
            source_address=["all"],
            destination_address=[],
            internet_service_name=["Google-Web", "Dropbox-Web"],
            action=PolicyAction.ALLOW,
            vdom="root",
        )
        sample_config_model.firewall_policies.append(policy)

        exporter = HTMLExporter(sample_config_model)

        # Internet Serviceの識別テスト
        assert exporter._is_internet_service("Google-Web") is True
        assert exporter._is_internet_service("12345") is True  # ISDB ID
        assert exporter._is_internet_service("Server-A") is False  # 通常のアドレス

        # ツールチップ生成テスト
        tooltip = exporter._get_internet_service_tooltip("Google-Web")
        assert "Internet Service" in tooltip
        assert "Google-Web" in tooltip or "Web" in tooltip

    def test_internet_service_display_in_html(self, sample_config_model):
        """HTML出力でのInternet Service表示"""
        # Internet Service名を含むポリシーを追加
        policy = FirewallPolicy(
            policy_id="1",
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

        # Internet Serviceがバッジ形式で表示されていることを確認
        assert "Google-Web" in html or "Web" in html
        assert "Dropbox-Web" in html or "Web" in html
        assert "bg-info" in html  # Internet Service用のバッジ色

    def test_internet_service_with_destination_address(self, sample_config_model):
        """Internet Serviceと宛先アドレスの両方が指定されている場合"""
        policy = FirewallPolicy(
            policy_id="1",
            name="Mixed-Policy",
            source_address=["all"],
            destination_address=["Server-A"],
            internet_service_name=["Google-Web"],
            action=PolicyAction.ALLOW,
            vdom="root",
        )
        sample_config_model.firewall_policies.append(policy)

        exporter = HTMLExporter(sample_config_model)
        html = exporter.export()

        # 両方が表示されていることを確認
        assert "Server-A" in html
        assert "Google-Web" in html or "Web" in html


class TestISDBData:
    """ISDBデータのテスト"""

    def test_load_isdb(self):
        """ISDBデータの読み込み"""
        isdb = load_isdb()

        # ISDBデータが読み込まれていることを確認
        assert isinstance(isdb, dict)
        # appid.csvからデータが読み込まれていることを確認（少なくとも1件以上）
        assert len(isdb) > 0

    def test_isdb_data_structure(self):
        """ISDBデータの構造確認"""
        isdb = load_isdb()

        # データがapp_id: app_nameの形式であることを確認
        for app_id, app_name in list(isdb.items())[:5]:  # 最初の5件をチェック
            assert isinstance(app_id, str)
            assert isinstance(app_name, str)
            assert len(app_id) > 0
            assert len(app_name) > 0
