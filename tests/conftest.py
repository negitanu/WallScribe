#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
テスト用共通フィクスチャ
"""

import pytest
from pathlib import Path

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
    DHCPServer,
    Objects,
    AddressObject,
    AddressGroup,
    ServiceObject,
    ServiceGroup,
    FirewallPolicy,
    NATPolicy,
    PolicyAction,
    VPNSettings,
    IPSecPhase1,
    IPSecPhase2,
    SSLVPNSettings,
    SecurityProfile,
    SecurityProfiles,
    HASettings,
    LoggingSettings,
    SyslogServer,
    SNMPSettings,
)


@pytest.fixture
def sample_fortigate_config():
    """FortiGateのサンプル設定ファイル内容"""
    return """#config-version=FGT60F-7.2.5-FW-build1517-230523:opmode=0:vdom=0:user=admin
#conf_file_ver=1234567890
#buildno=1517
#global_vdom=1
config system global
    set hostname "FW-TEST-01"
    set timezone "Asia/Tokyo"
end
config system interface
    edit "port1"
        set vdom "root"
        set ip 192.168.1.1 255.255.255.0
        set allowaccess ping https ssh
        set type physical
        set role wan
    next
    edit "port2"
        set vdom "root"
        set ip 10.0.0.1 255.255.255.0
        set allowaccess ping
        set type physical
        set role lan
    next
end
config system dns
    set primary 8.8.8.8
    set secondary 8.8.4.4
end
config firewall address
    edit "Server-A"
        set uuid 12345678-1234-1234-1234-123456789abc
        set subnet 10.0.0.10 255.255.255.255
    next
    edit "Network-Internal"
        set uuid 12345678-1234-1234-1234-123456789abd
        set subnet 10.0.0.0 255.255.255.0
    next
end
config firewall policy
    edit 1
        set name "Allow-Outbound"
        set srcintf "port2"
        set dstintf "port1"
        set srcaddr "all"
        set dstaddr "all"
        set action accept
        set schedule "always"
        set service "ALL"
        set nat enable
        set logtraffic all
    next
end
"""


@pytest.fixture
def sample_paloalto_config():
    """Palo Altoのサンプル設定ファイル内容"""
    return """<?xml version="1.0"?>
<config version="10.2.0">
  <devices>
    <entry name="localhost.localdomain">
      <deviceconfig>
        <system>
          <hostname>PA-TEST-01</hostname>
          <ip-address>192.168.1.1</ip-address>
          <netmask>255.255.255.0</netmask>
          <timezone>Asia/Tokyo</timezone>
          <dns-setting>
            <servers>
              <primary>8.8.8.8</primary>
              <secondary>8.8.4.4</secondary>
            </servers>
          </dns-setting>
        </system>
      </deviceconfig>
      <network>
        <interface>
          <ethernet>
            <entry name="ethernet1/1">
              <layer3>
                <ip>
                  <entry name="192.168.1.1/24"/>
                </ip>
              </layer3>
            </entry>
          </ethernet>
        </interface>
      </network>
      <vsys>
        <entry name="vsys1">
          <address>
            <entry name="Server-A">
              <ip-netmask>10.0.0.10/32</ip-netmask>
            </entry>
          </address>
          <rulebase>
            <security>
              <rules>
                <entry name="Allow-Outbound">
                  <from>
                    <member>trust</member>
                  </from>
                  <to>
                    <member>untrust</member>
                  </to>
                  <source>
                    <member>any</member>
                  </source>
                  <destination>
                    <member>any</member>
                  </destination>
                  <service>
                    <member>any</member>
                  </service>
                  <action>allow</action>
                  <log-end>yes</log-end>
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


@pytest.fixture
def sample_config_model():
    """サンプルConfigModel"""
    config = ConfigModel()

    # Device Info
    config.device_info = DeviceInfo(
        hostname="TEST-FW-01",
        model="FortiGate-60F",
        os_version="7.2.5",
        serial_number="FGT60FXXXXXXXXXX",
        operation_mode=OperationMode.NAT_ROUTE,
        device_type=DeviceType.FORTIGATE,
        vdom_enabled=False,
        vdom_list=["root"],
    )

    # System Settings
    config.system_settings = SystemSettings(
        management_ip="192.168.1.1",
        management_netmask="255.255.255.0",
        management_interface="port1",
        allowed_protocols=["https", "ssh", "ping"],
        https_port="443",
        ssh_port="22",
        ntp_servers=["ntp.nict.jp"],
        dns_primary="8.8.8.8",
        dns_secondary="8.8.4.4",
        timezone="Asia/Tokyo",
        admin_users=[
            AdminUser(
                username="admin", profile="super_admin", vdom="root", trust_hosts=["0.0.0.0/0"]
            )
        ],
    )

    # Interfaces
    config.interfaces = [
        Interface(
            name="port1",
            interface_type="physical",
            ip_address="192.168.1.1/24",
            zone="WAN",
            vdom="root",
            role="wan",
            allowed_access=["https", "ssh", "ping"],
        ),
        Interface(
            name="port2",
            interface_type="physical",
            ip_address="10.0.0.1/24",
            zone="LAN",
            vdom="root",
            role="lan",
            allowed_access=["ping"],
        ),
    ]

    # Routes
    config.routes = [
        Route(
            name="default",
            destination="0.0.0.0/0",
            gateway="192.168.1.254",
            interface="port1",
            distance="10",
            vdom="root",
        )
    ]

    # Objects
    config.objects = Objects(
        addresses=[
            AddressObject(name="Server-A", object_type="subnet", value="10.0.0.10/32", vdom="root"),
            AddressObject(
                name="Network-Internal", object_type="subnet", value="10.0.0.0/24", vdom="root"
            ),
        ],
        address_groups=[
            AddressGroup(name="Internal-Servers", members=["Server-A"], vdom="root"),
        ],
        services=[
            ServiceObject(name="TCP-8080", protocol="TCP", port="8080", vdom="root"),
        ],
        service_groups=[
            ServiceGroup(name="Web-Services", members=["HTTP", "HTTPS", "TCP-8080"], vdom="root"),
        ],
    )

    # Policies
    config.firewall_policies = [
        FirewallPolicy(
            policy_id="1",
            name="Allow-Outbound",
            source_interface=["port2"],
            destination_interface=["port1"],
            source_address=["all"],
            destination_address=["all"],
            service=["ALL"],
            action=PolicyAction.ALLOW,
            nat_enabled=True,
            log_enabled=True,
            vdom="root",
            enabled=True,
        )
    ]

    # NAT
    config.nat_policies = [
        NATPolicy(
            name="VIP-Server-A",
            nat_type="vip",
            external_interface="port1",
            external_ip="192.168.1.100",
            internal_ip="10.0.0.10",
            port_forward=True,
            original_port="443",
            translated_port="443",
            vdom="root",
        )
    ]

    # VPN
    config.vpn = VPNSettings(
        ipsec_phase1=[
            IPSecPhase1(
                name="VPN-HQ",
                remote_gateway="203.0.113.1",
                interface="port1",
                ike_version="2",
                encryption="aes256",
                authentication="sha256",
                dh_group="14",
                lifetime="86400",
                psk=True,
            )
        ],
        ipsec_phase2=[
            IPSecPhase2(
                name="VPN-HQ-Phase2",
                phase1_name="VPN-HQ",
                encryption="aes256",
                authentication="sha256",
                pfs="14",
                lifetime="43200",
                local_subnet="10.0.0.0/24",
                remote_subnet="10.1.0.0/24",
            )
        ],
    )

    # HA
    config.ha = HASettings(mode=HAMode.STANDALONE)

    # Logging
    config.logging = LoggingSettings(
        syslog_servers=[SyslogServer(server="192.168.1.200", port="514", status="enabled")],
        local_logging=True,
    )

    config.source_file = "test_config.conf"

    return config
