#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
パーサーのテスト
"""

import pytest

from models.config import DeviceType, HAMode, OperationMode, PolicyAction
from parsers.base import detect_encoding, get_parser_for_content
from parsers.fortigate import FortiGateParser
from parsers.paloalto import PaloAltoParser


class TestDetectEncoding:
    """エンコーディング検出のテスト"""

    def test_detect_utf8(self):
        """UTF-8の検出"""
        data = "テスト文字列".encode("utf-8")
        content, encoding = detect_encoding(data)
        assert encoding == "utf-8"
        assert content == "テスト文字列"

    def test_detect_utf8_bom(self):
        """UTF-8 BOMの検出"""
        data = "テスト文字列".encode("utf-8-sig")
        content, encoding = detect_encoding(data)
        assert encoding in ("utf-8", "utf-8-sig")
        assert "テスト文字列" in content

    def test_detect_cp932(self):
        """Shift-JIS (CP932) の検出"""
        # CP932特有の文字列を使用
        data = "日本語テスト".encode("cp932")
        content, encoding = detect_encoding(data)
        # UTF-8で失敗した後にCP932で成功するはず
        assert "日本語テスト" in content

    def test_detect_ascii(self):
        """ASCII文字列の検出"""
        data = b"Hello World"
        content, encoding = detect_encoding(data)
        assert encoding == "utf-8"  # ASCIIはUTF-8互換
        assert content == "Hello World"


class TestGetParserForContent:
    """パーサー自動選択のテスト"""

    def test_fortigate_detection(self, sample_fortigate_config):
        """FortiGate設定の検出"""
        parser = get_parser_for_content(sample_fortigate_config)
        assert parser is not None
        assert isinstance(parser, FortiGateParser)

    def test_paloalto_detection(self, sample_paloalto_config):
        """Palo Alto設定の検出"""
        parser = get_parser_for_content(sample_paloalto_config)
        assert parser is not None
        assert isinstance(parser, PaloAltoParser)

    def test_unknown_format(self):
        """未知のフォーマット"""
        parser = get_parser_for_content("This is not a valid config file")
        assert parser is None


class TestFortiGateParser:
    """FortiGateパーサーのテスト"""

    def test_parse_content(self, sample_fortigate_config):
        """基本的なパース"""
        parser = FortiGateParser()
        config = parser.parse_content(sample_fortigate_config, "test.conf")

        assert config.device_info.device_type == DeviceType.FORTIGATE
        assert config.device_info.hostname == "FW-TEST-01"
        assert config.device_info.model == "FortiGate 60F"
        assert config.device_info.os_version == "7.2.5"

    def test_parse_model_compact_code(self):
        """省略形モデルコードの変換（例: 33E1 -> 3301E）"""
        config_content = """#config-version=FG33E1-7.4.8-FW-build2795-250523:opmode=0:vdom=0:user=admin
config system global
    set hostname "FW-TEST-02"
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert config.device_info.model == "FortiGate 3301E"

    def test_parse_interfaces(self, sample_fortigate_config):
        """インターフェースのパース"""
        parser = FortiGateParser()
        config = parser.parse_content(sample_fortigate_config, "test.conf")

        assert len(config.interfaces) >= 2
        port1 = next((i for i in config.interfaces if i.name == "port1"), None)
        assert port1 is not None
        # FortiGateは "IP MASK" をCIDR表記に正規化する
        assert port1.ip_address == "192.168.1.1/24"
        assert "https" in port1.allowed_access

    def test_parse_dns(self, sample_fortigate_config):
        """DNS設定のパース"""
        parser = FortiGateParser()
        config = parser.parse_content(sample_fortigate_config, "test.conf")

        assert config.system_settings.dns_primary == "8.8.8.8"
        assert config.system_settings.dns_secondary == "8.8.4.4"

    def test_parse_ha_hbdev_list(self):
        """HA hbdev が list でパースされても落ちないこと"""
        config_content = """#config-version=FGT60F-7.4.8-FW-build2795-250523:opmode=0:vdom=0:user=admin
config system global
    set hostname "FW-TEST-HA"
end
config system ha
    set mode a-p
    set group-id 1
    set group-name "CLUSTER-01"
    set priority 255
    set hbdev "port3" 0 "port4" 1
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert config.device_info.hostname == "FW-TEST-HA"
        assert config.ha.mode.value == "Active-Passive"
        assert config.ha.heartbeat_interfaces == ["port3", "port4"]
        assert [(x.interface, x.priority) for x in config.ha.heartbeat_interfaces_detail] == [
            ("port3", "0"),
            ("port4", "1"),
        ]

    def test_parse_addresses(self, sample_fortigate_config):
        """アドレスオブジェクトのパース"""
        parser = FortiGateParser()
        config = parser.parse_content(sample_fortigate_config, "test.conf")

        assert len(config.objects.addresses) >= 2
        server_a = next((a for a in config.objects.addresses if a.name == "Server-A"), None)
        assert server_a is not None
        assert "10.0.0.10" in server_a.value

    def test_parse_policies(self, sample_fortigate_config):
        """ポリシーのパース"""
        parser = FortiGateParser()
        config = parser.parse_content(sample_fortigate_config, "test.conf")

        assert len(config.firewall_policies) >= 1
        policy = config.firewall_policies[0]
        assert policy.name == "Allow-Outbound"
        assert policy.action == PolicyAction.ALLOW
        assert policy.nat_enabled is True

    def test_parse_policy_action_default_deny(self):
        """action 未定義のポリシーは deny 扱いになること"""
        config_content = """#config-version=FGT60F-7.4.8-FW-build2795-250523:opmode=0:vdom=0:user=admin
config firewall policy
    edit 1
        set name "No-Action"
        set srcintf "port2"
        set dstintf "port1"
        set srcaddr "all"
        set dstaddr "all"
        set schedule "always"
        set service "ALL"
        set nat enable
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.firewall_policies) == 1
        assert config.firewall_policies[0].action == PolicyAction.DENY

    def test_detect_file_type(self):
        """ファイル拡張子の検出"""
        assert FortiGateParser.detect_file_type("config.conf") is True
        assert FortiGateParser.detect_file_type("config.CONF") is True
        assert FortiGateParser.detect_file_type("config.xml") is False
        assert FortiGateParser.detect_file_type("config.txt") is False

    def test_detect_content_type(self, sample_fortigate_config):
        """内容からの形式検出"""
        assert FortiGateParser.detect_content_type(sample_fortigate_config) is True
        assert FortiGateParser.detect_content_type("<config>xml</config>") is False

    def test_parse_internet_service_name(self):
        """internet-service-nameのパース"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config firewall policy
    edit 53
        set name "test-policy"
        set internet-service enable
        set internet-service-name "Google-Web" "Dropbox-Web"
        set action accept
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.firewall_policies) == 1
        policy = config.firewall_policies[0]
        assert len(policy.internet_service_name) == 2
        assert "Google-Web" in policy.internet_service_name
        assert "Dropbox-Web" in policy.internet_service_name

    def test_parse_cidr_conversion_address(self):
        """アドレスオブジェクトのCIDR変換"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config firewall address
    edit "Server-A"
        set subnet 10.0.0.10 255.255.255.255
    next
    edit "Network-Internal"
        set subnet 192.168.1.0 255.255.255.0
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.objects.addresses) == 2
        server_a = next((a for a in config.objects.addresses if a.name == "Server-A"), None)
        assert server_a is not None
        assert server_a.value == "10.0.0.10/32"

        network = next((a for a in config.objects.addresses if a.name == "Network-Internal"), None)
        assert network is not None
        assert network.value == "192.168.1.0/24"

    def test_parse_cidr_conversion_interface(self):
        """インターフェースのCIDR変換"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config system interface
    edit "port1"
        set ip 192.168.1.1 255.255.255.0
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.interfaces) == 1
        port1 = config.interfaces[0]
        assert port1.ip_address == "192.168.1.1/24"

    def test_parse_cidr_conversion_route(self):
        """ルートのCIDR変換"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config router static
    edit 1
        set dst 10.0.0.0 255.255.0.0
        set gateway 192.168.1.254
        set device "port1"
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.routes) == 1
        route = config.routes[0]
        assert route.destination == "10.0.0.0/16"

    def test_parse_interface_ipv6(self):
        """インターフェースIPv6アドレスのパース"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config system interface
    edit "port1"
        set ip6-address 2001:db8::1/64
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.interfaces) == 1
        assert config.interfaces[0].ip_address == "2001:db8::1/64"

    def test_parse_interface_dual_stack(self):
        """インターフェースのデュアルスタック（IPv4+IPv6）"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config system interface
    edit "port1"
        set ip 192.168.1.1 255.255.255.0
        set ip6-address 2001:db8::1/64
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.interfaces) == 1
        assert config.interfaces[0].ip_address == "192.168.1.1/24, 2001:db8::1/64"

    def test_parse_route_static6(self):
        """IPv6静的ルート（router static6）のパース"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config router static6
    edit 1
        set dst 2001:db8:1::/64
        set gateway 2001:db8::fe
        set device "port1"
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.routes) == 1
        route = config.routes[0]
        assert route.destination == "2001:db8:1::/64"
        assert route.gateway == "2001:db8::fe"
        assert route.route_type == "static6"

    def test_parse_route_blackhole(self):
        """blackholeルート（router static / set blackhole enable）のパース"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config router static
    edit 1
        set dst 10.0.0.0 255.255.255.0
        set blackhole enable
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.routes) == 1
        route = config.routes[0]
        assert route.destination == "10.0.0.0/24"
        assert route.route_type == "blackhole"
        assert route.gateway == ""

    def test_parse_route_blackhole6(self):
        """blackhole IPv6ルート（router static6 / set blackhole enable）のパース"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config router static6
    edit 1
        set dst 2001:db8:dead::/64
        set blackhole enable
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        assert len(config.routes) == 1
        route = config.routes[0]
        assert route.destination == "2001:db8:dead::/64"
        assert route.route_type == "blackhole6"
        assert route.gateway == ""

    def test_parse_address6_object(self):
        """IPv6アドレスオブジェクト（firewall address6）のパース"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config firewall address6
    edit "NET6"
        set ip6 2001:db8:1::/64
    next
end
"""
        parser = FortiGateParser()
        config = parser.parse_content(config_content, "test.conf")

        net6 = next((a for a in config.objects.addresses if a.name == "NET6"), None)
        assert net6 is not None
        assert net6.value == "2001:db8:1::/64"


class TestPaloAltoParser:
    """Palo Altoパーサーのテスト"""

    def test_parse_content(self, sample_paloalto_config):
        """基本的なパース"""
        parser = PaloAltoParser()
        config = parser.parse_content(sample_paloalto_config, "test.xml")

        assert config.device_info.device_type == DeviceType.PALOALTO
        assert config.device_info.hostname == "PA-TEST-01"
        assert config.device_info.os_version == "10.2.0"

    def test_parse_system_settings(self, sample_paloalto_config):
        """システム設定のパース"""
        parser = PaloAltoParser()
        config = parser.parse_content(sample_paloalto_config, "test.xml")

        assert config.system_settings.management_ip == "192.168.1.1"
        assert config.system_settings.dns_primary == "8.8.8.8"
        assert config.system_settings.dns_secondary == "8.8.4.4"

    def test_parse_interfaces(self, sample_paloalto_config):
        """インターフェースのパース"""
        parser = PaloAltoParser()
        config = parser.parse_content(sample_paloalto_config, "test.xml")

        assert len(config.interfaces) >= 1
        eth1 = next((i for i in config.interfaces if "ethernet1/1" in i.name), None)
        assert eth1 is not None

    def test_parse_addresses(self, sample_paloalto_config):
        """アドレスオブジェクトのパース"""
        parser = PaloAltoParser()
        config = parser.parse_content(sample_paloalto_config, "test.xml")

        assert len(config.objects.addresses) >= 1
        server_a = next((a for a in config.objects.addresses if a.name == "Server-A"), None)
        assert server_a is not None
        assert server_a.object_type == "subnet"

    def test_parse_policies(self, sample_paloalto_config):
        """ポリシーのパース"""
        parser = PaloAltoParser()
        config = parser.parse_content(sample_paloalto_config, "test.xml")

        assert len(config.firewall_policies) >= 1
        policy = config.firewall_policies[0]
        assert policy.name == "Allow-Outbound"
        assert policy.action == PolicyAction.ALLOW
        assert policy.log_enabled is True

    def test_parse_ha_more_details(self):
        """HA情報（group名/監視IF/HA1/HA2）を追加でパースできること"""
        config_content = """<?xml version="1.0"?>
<config version="10.2.0">
  <devices>
    <entry name="localhost.localdomain">
      <deviceconfig>
        <system>
          <hostname>PA-HA-01</hostname>
        </system>
        <high-availability>
          <enabled>yes</enabled>
          <group>
            <group-id>10</group-id>
            <group-description>HA-GRP-01</group-description>
            <mode>
              <active-passive>
                <passive-link-state>auto</passive-link-state>
              </active-passive>
            </mode>
            <election-option>
              <priority>100</priority>
              <preemptive>yes</preemptive>
              <hello-interval>1000</hello-interval>
              <hold-time>3000</hold-time>
            </election-option>
            <link-monitoring>
              <enabled>yes</enabled>
              <link-group>
                <entry name="default">
                  <interface>
                    <member>ethernet1/1</member>
                  </interface>
                </entry>
              </link-group>
            </link-monitoring>
          </group>
          <interface>
            <ha1>
              <port>ethernet1/5</port>
              <ip-address>192.0.2.1</ip-address>
            </ha1>
            <ha2>
              <port>ethernet1/6</port>
              <ip-address>192.0.2.5</ip-address>
            </ha2>
          </interface>
        </high-availability>
      </deviceconfig>
    </entry>
  </devices>
</config>
"""
        parser = PaloAltoParser()
        config = parser.parse_content(config_content, "test.xml")

        assert config.device_info.hostname == "PA-HA-01"
        assert config.ha.mode == HAMode.ACTIVE_PASSIVE
        assert config.ha.group_id == "10"
        assert config.ha.group_name == "HA-GRP-01"
        assert config.ha.priority == "100"
        assert config.ha.preempt is True
        assert "ethernet1/1" in config.ha.monitor_interfaces
        assert config.ha.heartbeat_interfaces == ["ethernet1/5", "ethernet1/6"]
        assert any(
            x.id == "HA1" and x.interface == "ethernet1/5" and x.gateway == "192.0.2.1"
            for x in config.ha.ha_mgmt_interfaces
        )

    def test_parse_policy_action_default_deny(self):
        """action 未定義のポリシーは deny 扱いになること"""
        config_content = """<?xml version="1.0"?>
<config version="10.2.0">
  <devices>
    <entry name="localhost.localdomain">
      <vsys>
        <entry name="vsys1">
          <rulebase>
            <security>
              <rules>
                <entry name="No-Action">
                  <from><member>trust</member></from>
                  <to><member>untrust</member></to>
                  <source><member>any</member></source>
                  <destination><member>any</member></destination>
                  <service><member>any</member></service>
                  <!-- action 要素なし -->
                </entry>
              </rules>
            </security>
          </rulebase>
        </entry>
      </vsys>
    </entry>
  </devices>
</config>
"""
        parser = PaloAltoParser()
        config = parser.parse_content(config_content, "test.xml")

        assert len(config.firewall_policies) == 1
        assert config.firewall_policies[0].action == PolicyAction.DENY

    def test_detect_file_type(self):
        """ファイル拡張子の検出"""
        assert PaloAltoParser.detect_file_type("config.xml") is True
        assert PaloAltoParser.detect_file_type("config.XML") is True
        assert PaloAltoParser.detect_file_type("config.conf") is False
        assert PaloAltoParser.detect_file_type("config.txt") is False

    def test_detect_content_type(self, sample_paloalto_config):
        """内容からの形式検出"""
        assert PaloAltoParser.detect_content_type(sample_paloalto_config) is True
        assert PaloAltoParser.detect_content_type("#config-version=") is False

    def test_invalid_xml(self):
        """無効なXMLのハンドリング"""
        parser = PaloAltoParser()
        config = parser.parse_content("<invalid>xml", "test.xml")

        assert len(parser.errors) > 0
        assert config.device_info.device_type == DeviceType.PALOALTO

    def test_parse_cidr_conversion_address(self):
        """アドレスオブジェクトのCIDR変換"""
        config_content = """<?xml version="1.0"?>
<config version="10.2.0">
  <devices>
    <entry name="localhost.localdomain">
      <vsys>
        <entry name="vsys1">
          <address>
            <entry name="Server-A">
              <ip-netmask>10.0.0.10 255.255.255.255</ip-netmask>
            </entry>
            <entry name="Network-Internal">
              <ip-netmask>192.168.1.0 255.255.255.0</ip-netmask>
            </entry>
          </address>
        </entry>
      </vsys>
    </entry>
  </devices>
</config>
"""
        parser = PaloAltoParser()
        config = parser.parse_content(config_content, "test.xml")

        assert len(config.objects.addresses) == 2
        server_a = next((a for a in config.objects.addresses if a.name == "Server-A"), None)
        assert server_a is not None
        assert server_a.value == "10.0.0.10/32"

        network = next((a for a in config.objects.addresses if a.name == "Network-Internal"), None)
        assert network is not None
        assert network.value == "192.168.1.0/24"

    def test_parse_cidr_conversion_route(self):
        """ルートのCIDR変換"""
        config_content = """<?xml version="1.0"?>
<config version="10.2.0">
  <devices>
    <entry name="localhost.localdomain">
      <network>
        <virtual-router>
          <entry name="default">
            <routing-table>
              <ip>
                <static-route>
                  <entry name="default">
                    <destination>0.0.0.0 0.0.0.0</destination>
                    <nexthop>
                      <ip-address>192.168.1.254</ip-address>
                    </nexthop>
                    <interface>ethernet1/1</interface>
                  </entry>
                </static-route>
              </ip>
            </routing-table>
          </entry>
        </virtual-router>
      </network>
    </entry>
  </devices>
</config>
"""
        parser = PaloAltoParser()
        config = parser.parse_content(config_content, "test.xml")

        assert len(config.routes) == 1
        route = config.routes[0]
        assert route.destination == "0.0.0.0/0"

    def test_parse_route_discard(self):
        """Palo Altoのdiscard(blackhole)ルートのパース"""
        config_content = """<?xml version="1.0"?>
<config version="10.2.0">
  <devices>
    <entry name="localhost.localdomain">
      <network>
        <virtual-router>
          <entry name="default">
            <routing-table>
              <ip>
                <static-route>
                  <entry name="discard-route">
                    <destination>10.10.10.0/24</destination>
                    <nexthop>
                      <discard/>
                    </nexthop>
                    <interface>ethernet1/1</interface>
                  </entry>
                </static-route>
              </ip>
            </routing-table>
          </entry>
        </virtual-router>
      </network>
    </entry>
  </devices>
</config>
"""
        parser = PaloAltoParser()
        config = parser.parse_content(config_content, "test.xml")

        assert len(config.routes) == 1
        route = config.routes[0]
        assert route.destination == "10.10.10.0/24"
        assert route.route_type == "blackhole"

    def test_parse_cidr_conversion_address(self):
        """アドレスオブジェクトのCIDR変換"""
        config_content = """<?xml version="1.0"?>
<config version="10.2.0">
  <devices>
    <entry name="localhost.localdomain">
      <vsys>
        <entry name="vsys1">
          <address>
            <entry name="Server-A">
              <ip-netmask>10.0.0.10 255.255.255.255</ip-netmask>
            </entry>
            <entry name="Network-Internal">
              <ip-netmask>192.168.1.0 255.255.255.0</ip-netmask>
            </entry>
          </address>
        </entry>
      </vsys>
    </entry>
  </devices>
</config>
"""
        parser = PaloAltoParser()
        config = parser.parse_content(config_content, "test.xml")

        assert len(config.objects.addresses) == 2
        server_a = next((a for a in config.objects.addresses if a.name == "Server-A"), None)
        assert server_a is not None
        assert server_a.value == "10.0.0.10/32"

        network = next((a for a in config.objects.addresses if a.name == "Network-Internal"), None)
        assert network is not None
        assert network.value == "192.168.1.0/24"

    def test_parse_cidr_conversion_route(self):
        """ルートのCIDR変換"""
        config_content = """<?xml version="1.0"?>
<config version="10.2.0">
  <devices>
    <entry name="localhost.localdomain">
      <network>
        <virtual-router>
          <entry name="default">
            <routing-table>
              <ip>
                <static-route>
                  <entry name="default">
                    <destination>0.0.0.0 0.0.0.0</destination>
                    <nexthop>
                      <ip-address>192.168.1.254</ip-address>
                    </nexthop>
                    <interface>ethernet1/1</interface>
                  </entry>
                </static-route>
              </ip>
            </routing-table>
          </entry>
        </virtual-router>
      </network>
    </entry>
  </devices>
</config>
"""
        parser = PaloAltoParser()
        config = parser.parse_content(config_content, "test.xml")

        assert len(config.routes) == 1
        route = config.routes[0]
        assert route.destination == "0.0.0.0/0"
