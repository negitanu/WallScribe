#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
データモデルのテスト
"""

import pytest

from models.config import (
    ConfigModel,
    DeviceInfo,
    DeviceType,
    OperationMode,
    HAMode,
    SystemSettings,
    AdminUser,
    Interface,
    Route,
    Objects,
    AddressObject,
    AddressGroup,
    ServiceObject,
    ServiceGroup,
    FirewallPolicy,
    NATPolicy,
    PolicyAction,
    VPNSettings,
    HASettings,
    LoggingSettings,
)


class TestDeviceInfo:
    """DeviceInfoのテスト"""

    def test_default_values(self):
        """デフォルト値の確認"""
        info = DeviceInfo()

        assert info.hostname == ""
        assert info.model == ""
        assert info.os_version == ""
        assert info.device_type == DeviceType.UNKNOWN
        assert info.operation_mode == OperationMode.UNKNOWN
        assert info.vdom_enabled is False
        assert info.vdom_list == []

    def test_custom_values(self):
        """カスタム値の設定"""
        info = DeviceInfo(
            hostname="test-fw",
            model="FortiGate-100F",
            os_version="7.2.5",
            device_type=DeviceType.FORTIGATE,
            operation_mode=OperationMode.NAT_ROUTE,
            vdom_enabled=True,
            vdom_list=["root", "vdom1"],
        )

        assert info.hostname == "test-fw"
        assert info.model == "FortiGate-100F"
        assert info.device_type == DeviceType.FORTIGATE
        assert len(info.vdom_list) == 2


class TestPolicyAction:
    """PolicyActionのテスト"""

    def test_enum_values(self):
        """Enum値の確認"""
        assert PolicyAction.ALLOW.value == "allow"
        assert PolicyAction.DENY.value == "deny"
        assert PolicyAction.DROP.value == "drop"
        assert PolicyAction.UNKNOWN.value == "unknown"


class TestFirewallPolicy:
    """FirewallPolicyのテスト"""

    def test_default_values(self):
        """デフォルト値の確認"""
        policy = FirewallPolicy()

        assert policy.policy_id == ""
        assert policy.name == ""
        assert policy.source_interface == []
        assert policy.destination_interface == []
        assert policy.action == PolicyAction.UNKNOWN
        assert policy.nat_enabled is False
        assert policy.log_enabled is False
        assert policy.enabled is True
        assert policy.vdom == "root"

    def test_custom_policy(self):
        """カスタムポリシーの作成"""
        policy = FirewallPolicy(
            policy_id="1",
            name="Allow-Web",
            source_interface=["lan"],
            destination_interface=["wan"],
            source_address=["internal-network"],
            destination_address=["all"],
            service=["HTTP", "HTTPS"],
            action=PolicyAction.ALLOW,
            nat_enabled=True,
            log_enabled=True,
        )

        assert policy.policy_id == "1"
        assert policy.name == "Allow-Web"
        assert "lan" in policy.source_interface
        assert policy.action == PolicyAction.ALLOW
        assert policy.nat_enabled is True


class TestInterface:
    """Interfaceのテスト"""

    def test_default_values(self):
        """デフォルト値の確認"""
        iface = Interface()

        assert iface.name == ""
        assert iface.interface_type == ""
        assert iface.ip_address == ""
        assert iface.vdom == "root"
        assert iface.status == "up"
        assert iface.allowed_access == []

    def test_custom_interface(self):
        """カスタムインターフェースの作成"""
        iface = Interface(
            name="port1",
            interface_type="physical",
            ip_address="192.168.1.1/24",
            zone="WAN",
            role="wan",
            allowed_access=["https", "ssh", "ping"],
        )

        assert iface.name == "port1"
        assert iface.ip_address == "192.168.1.1/24"
        assert len(iface.allowed_access) == 3


class TestObjects:
    """Objectsのテスト"""

    def test_default_values(self):
        """デフォルト値の確認"""
        objects = Objects()

        assert objects.addresses == []
        assert objects.address_groups == []
        assert objects.services == []
        assert objects.service_groups == []

    def test_add_address_object(self):
        """アドレスオブジェクトの追加"""
        objects = Objects()
        addr = AddressObject(name="Server-A", object_type="subnet", value="10.0.0.10/32")
        objects.addresses.append(addr)

        assert len(objects.addresses) == 1
        assert objects.addresses[0].name == "Server-A"


class TestHASettings:
    """HASettingsのテスト"""

    def test_standalone(self):
        """スタンドアロンモード"""
        ha = HASettings()

        assert ha.mode == HAMode.STANDALONE
        assert ha.group_id == ""
        assert ha.priority == ""

    def test_active_passive(self):
        """Active-Passiveモード"""
        ha = HASettings(
            mode=HAMode.ACTIVE_PASSIVE,
            group_id="1",
            priority="100",
            preempt=True,
            monitor_interfaces=["port1", "port2"],
        )

        assert ha.mode == HAMode.ACTIVE_PASSIVE
        assert ha.group_id == "1"
        assert ha.preempt is True
        assert len(ha.monitor_interfaces) == 2


class TestConfigModel:
    """ConfigModelのテスト"""

    def test_default_values(self):
        """デフォルト値の確認"""
        config = ConfigModel()

        assert config.device_info is not None
        assert config.system_settings is not None
        assert config.interfaces == []
        assert config.firewall_policies == []
        assert config.source_file == ""
        assert config.parse_errors == []

    def test_get_summary(self, sample_config_model):
        """サマリーの取得"""
        summary = sample_config_model.get_summary()

        assert "device_type" in summary
        assert "hostname" in summary
        assert "version" in summary
        assert "interfaces" in summary
        assert "policies" in summary
        assert "objects" in summary

        assert summary["hostname"] == sample_config_model.device_info.hostname
        assert summary["interfaces"] == len(sample_config_model.interfaces)
        assert summary["policies"] == len(sample_config_model.firewall_policies)

    def test_summary_counts(self, sample_config_model):
        """サマリーのカウント値確認"""
        summary = sample_config_model.get_summary()

        expected_interfaces = len(sample_config_model.interfaces)
        expected_routes = len(sample_config_model.routes)
        expected_policies = len(sample_config_model.firewall_policies)
        expected_objects = len(sample_config_model.objects.addresses) + len(
            sample_config_model.objects.services
        )

        assert summary["interfaces"] == expected_interfaces
        assert summary["routes"] == expected_routes
        assert summary["policies"] == expected_policies
        assert summary["objects"] == expected_objects


class TestVPNSettings:
    """VPNSettingsのテスト"""

    def test_default_values(self):
        """デフォルト値の確認"""
        vpn = VPNSettings()

        assert vpn.ipsec_phase1 == []
        assert vpn.ipsec_phase2 == []
        assert vpn.ssl_vpn == []

    def test_with_ipsec(self, sample_config_model):
        """IPsec設定の確認"""
        vpn = sample_config_model.vpn

        assert len(vpn.ipsec_phase1) == 1
        assert len(vpn.ipsec_phase2) == 1

        p1 = vpn.ipsec_phase1[0]
        assert p1.name == "VPN-HQ"
        assert p1.psk is True

        p2 = vpn.ipsec_phase2[0]
        assert p2.phase1_name == "VPN-HQ"


class TestInternetService:
    """Internet Service関連のテスト"""

    def test_policy_with_internet_service(self):
        """Internet Service名を含むポリシー"""
        policy = FirewallPolicy(
            policy_id="53",
            name="Internet-Service-Policy",
            source_address=["all"],
            destination_address=[],
            internet_service_name=["Google-Web", "Google-RTMP", "Dropbox-Web"],
            action=PolicyAction.ALLOW,
            vdom="root",
        )

        assert policy.policy_id == "53"
        assert len(policy.internet_service_name) == 3
        assert "Google-Web" in policy.internet_service_name
        assert "Google-RTMP" in policy.internet_service_name
        assert "Dropbox-Web" in policy.internet_service_name

    def test_policy_default_internet_service(self):
        """デフォルト値の確認（internet_service_name）"""
        policy = FirewallPolicy()

        assert policy.internet_service_name == []


class TestCIDRNotation:
    """CIDR表記のテスト"""

    def test_address_object_cidr(self):
        """アドレスオブジェクトのCIDR表記"""
        addr = AddressObject(name="Server-A", object_type="subnet", value="10.0.0.10/32")
        assert addr.value == "10.0.0.10/32"
        assert "/" in addr.value

    def test_interface_cidr(self):
        """インターフェースのCIDR表記"""
        iface = Interface(name="port1", ip_address="192.168.1.1/24")
        assert iface.ip_address == "192.168.1.1/24"
        assert "/" in iface.ip_address

    def test_route_cidr(self):
        """ルートのCIDR表記"""
        route = Route(name="default", destination="0.0.0.0/0", gateway="192.168.1.254")
        assert route.destination == "0.0.0.0/0"
        assert "/" in route.destination
