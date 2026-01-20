#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統一設定データモデル
FortiGate と Palo Alto の設定を統一フォーマットで表現する
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class DeviceType(Enum):
    """機器タイプ"""
    FORTIGATE = "FortiGate"
    PALOALTO = "Palo Alto"
    UNKNOWN = "Unknown"


class OperationMode(Enum):
    """動作モード"""
    NAT_ROUTE = "NAT/Route"
    TRANSPARENT = "Transparent"
    UNKNOWN = "Unknown"


class HAMode(Enum):
    """HAモード"""
    STANDALONE = "Standalone"
    ACTIVE_PASSIVE = "Active-Passive"
    ACTIVE_ACTIVE = "Active-Active"
    UNKNOWN = "Unknown"


class PolicyAction(Enum):
    """ポリシーアクション"""
    ALLOW = "allow"
    DENY = "deny"
    DROP = "drop"
    UNKNOWN = "unknown"


@dataclass
class LicenseInfo:
    """ライセンス情報"""
    support_expiry: str = ""
    utm_expiry: str = ""
    av_expiry: str = ""
    webfilter_expiry: str = ""
    ips_expiry: str = ""


@dataclass
class DeviceInfo:
    """機器概要"""
    hostname: str = ""
    model: str = ""
    os_version: str = ""
    serial_number: str = ""
    operation_mode: OperationMode = OperationMode.UNKNOWN
    device_type: DeviceType = DeviceType.UNKNOWN
    vdom_enabled: bool = False
    vdom_list: List[str] = field(default_factory=list)
    license: LicenseInfo = field(default_factory=LicenseInfo)


@dataclass
class AdminUser:
    """管理者アカウント"""
    username: str = ""
    profile: str = ""
    vdom: str = ""
    trust_hosts: List[str] = field(default_factory=list)


@dataclass
class SystemSettings:
    """システム設定"""
    management_ip: str = ""
    management_netmask: str = ""
    management_interface: str = ""
    allowed_protocols: List[str] = field(default_factory=list)
    https_port: str = "443"
    ssh_port: str = "22"
    ntp_servers: List[str] = field(default_factory=list)
    dns_primary: str = ""
    dns_secondary: str = ""
    timezone: str = ""
    admin_users: List[AdminUser] = field(default_factory=list)


@dataclass
class Interface:
    """インターフェース"""
    name: str = ""
    alias: str = ""
    interface_type: str = ""  # physical, vlan, lag, loopback, tunnel
    ip_address: str = ""
    netmask: str = ""
    vlan_id: str = ""
    vdom: str = "root"
    zone: str = ""
    role: str = ""
    allowed_access: List[str] = field(default_factory=list)
    status: str = "up"
    description: str = ""


@dataclass
class Route:
    """ルーティング"""
    name: str = ""
    destination: str = ""
    gateway: str = ""
    interface: str = ""
    distance: str = ""
    vdom: str = "root"
    route_type: str = "static"  # static, connected, ospf, bgp


@dataclass
class DHCPServer:
    """DHCPサーバー設定"""
    interface: str = ""
    start_ip: str = ""
    end_ip: str = ""
    netmask: str = ""
    gateway: str = ""
    dns_servers: List[str] = field(default_factory=list)
    exclude_ips: List[str] = field(default_factory=list)
    lease_time: str = ""
    vdom: str = "root"


@dataclass
class AddressObject:
    """アドレスオブジェクト"""
    name: str = ""
    object_type: str = ""  # subnet, iprange, fqdn, wildcard
    value: str = ""
    vdom: str = "root"
    description: str = ""


@dataclass
class AddressGroup:
    """アドレスグループ"""
    name: str = ""
    members: List[str] = field(default_factory=list)
    vdom: str = "root"
    description: str = ""


@dataclass
class ServiceObject:
    """サービスオブジェクト"""
    name: str = ""
    protocol: str = ""  # TCP, UDP, ICMP, IP
    port: str = ""
    vdom: str = "root"
    description: str = ""


@dataclass
class ServiceGroup:
    """サービスグループ"""
    name: str = ""
    members: List[str] = field(default_factory=list)
    vdom: str = "root"
    description: str = ""


@dataclass
class Objects:
    """オブジェクト定義"""
    addresses: List[AddressObject] = field(default_factory=list)
    address_groups: List[AddressGroup] = field(default_factory=list)
    services: List[ServiceObject] = field(default_factory=list)
    service_groups: List[ServiceGroup] = field(default_factory=list)


@dataclass
class FirewallPolicy:
    """ファイアウォールポリシー"""
    policy_id: str = ""
    name: str = ""
    source_interface: List[str] = field(default_factory=list)
    destination_interface: List[str] = field(default_factory=list)
    source_address: List[str] = field(default_factory=list)
    destination_address: List[str] = field(default_factory=list)
    internet_service_name: List[str] = field(default_factory=list)  # Internet Service名のリスト
    service: List[str] = field(default_factory=list)
    application: List[str] = field(default_factory=list)
    action: PolicyAction = PolicyAction.UNKNOWN
    nat_enabled: bool = False
    log_enabled: bool = False
    security_profiles: List[str] = field(default_factory=list)
    vdom: str = "root"
    enabled: bool = True
    description: str = ""


@dataclass
class NATPolicy:
    """NATポリシー"""
    name: str = ""
    nat_type: str = ""  # snat, dnat, static, vip
    original_source: str = ""
    original_destination: str = ""
    translated_source: str = ""
    translated_destination: str = ""
    external_interface: str = ""
    external_ip: str = ""
    internal_ip: str = ""
    interface: str = ""
    port_forward: bool = False
    original_port: str = ""
    translated_port: str = ""
    vdom: str = "root"
    description: str = ""


@dataclass
class LocalInPolicy:
    """Local-in ポリシー"""
    policy_id: str = ""
    name: str = ""
    source_interface: str = ""
    source_address: List[str] = field(default_factory=list)
    destination_address: List[str] = field(default_factory=list)
    service: List[str] = field(default_factory=list)
    action: PolicyAction = PolicyAction.UNKNOWN
    schedule: str = ""
    vdom: str = "root"
    enabled: bool = True
    description: str = ""


@dataclass
class IPSecPhase1:
    """IPsec Phase1設定"""
    name: str = ""
    remote_gateway: str = ""
    interface: str = ""
    ike_version: str = ""
    proposal: str = ""  # 暗号化/認証アルゴリズム
    encryption: str = ""
    authentication: str = ""
    dh_group: str = ""
    lifetime: str = ""
    dpd: str = ""
    psk: bool = False
    local_id: str = ""
    remote_id: str = ""


@dataclass
class IPSecPhase2:
    """IPsec Phase2設定"""
    name: str = ""
    phase1_name: str = ""
    proposal: str = ""  # 暗号化/認証アルゴリズム
    encryption: str = ""
    authentication: str = ""
    pfs: str = ""
    lifetime: str = ""
    local_subnet: str = ""
    remote_subnet: str = ""


@dataclass
class SSLVPNSettings:
    """SSL-VPN設定"""
    realm: str = ""
    portal: str = ""
    listen_port: str = ""
    listen_interface: str = ""
    tunnel_ip_pool: str = ""
    auth_method: str = ""  # local, radius, ldap
    user_groups: List[str] = field(default_factory=list)
    mode: str = ""  # tunnel, web
    vdom: str = "root"


@dataclass
class VPNSettings:
    """VPN設定"""
    ipsec_phase1: List[IPSecPhase1] = field(default_factory=list)
    ipsec_phase2: List[IPSecPhase2] = field(default_factory=list)
    ssl_vpn: List[SSLVPNSettings] = field(default_factory=list)


@dataclass
class AntivirusProfile:
    """アンチウイルスプロファイル"""
    name: str = ""
    enabled: bool = True
    scan_mode: str = ""
    protocols: List[str] = field(default_factory=list)  # http, ftp, smtp, imap, pop3
    action: str = ""
    vdom: str = "root"


@dataclass
class WebFilterProfile:
    """Webフィルタプロファイル"""
    name: str = ""
    enabled: bool = True
    categories: List[str] = field(default_factory=list)
    action: str = ""  # block, monitor, allow
    vdom: str = "root"


@dataclass
class AppControlEntry:
    """アプリケーションコントロールエントリ"""
    app_id: str = ""
    app_name: str = ""
    category: str = ""
    risk: str = ""
    action: str = ""


@dataclass
class AppControlProfile:
    """アプリケーションコントロールプロファイル"""
    name: str = ""
    enabled: bool = True
    categories: List[str] = field(default_factory=list)
    applications: List[AppControlEntry] = field(default_factory=list)
    action: str = ""
    vdom: str = "root"


@dataclass
class IPSProfile:
    """IPSプロファイル"""
    name: str = ""
    enabled: bool = True
    signatures: List[str] = field(default_factory=list)
    action: str = ""
    vdom: str = "root"


@dataclass
class SSLInspectionProfile:
    """SSLインスペクションプロファイル"""
    name: str = ""
    enabled: bool = True
    mode: str = ""  # certificate-inspection, deep-inspection
    vdom: str = "root"


@dataclass
class SecurityProfile:
    """セキュリティプロファイル（統合）"""
    name: str = ""
    profile_type: str = ""  # antivirus, webfilter, ips, ssl-inspection, app-control
    enabled: bool = True
    vdom: str = "root"
    description: str = ""


@dataclass
class SecurityProfiles:
    """セキュリティプロファイル（詳細）"""
    antivirus: List[AntivirusProfile] = field(default_factory=list)
    webfilter: List[WebFilterProfile] = field(default_factory=list)
    app_control: List[AppControlProfile] = field(default_factory=list)
    ips: List[IPSProfile] = field(default_factory=list)
    ssl_inspection: List[SSLInspectionProfile] = field(default_factory=list)


@dataclass
class HAHeartbeatInterface:
    """HAハートビートインターフェース"""
    interface: str = ""
    priority: str = ""


@dataclass
class HAManagementInterface:
    """HA管理インターフェース"""
    id: str = ""
    interface: str = ""
    gateway: str = ""


@dataclass
class HASettings:
    """高可用性設定"""
    mode: HAMode = HAMode.STANDALONE
    group_id: str = ""
    group_name: str = ""
    priority: str = ""
    monitor_interfaces: List[str] = field(default_factory=list)
    ha_interfaces: List[str] = field(default_factory=list)
    heartbeat_interfaces: List[str] = field(default_factory=list)
    heartbeat_interfaces_detail: List[HAHeartbeatInterface] = field(default_factory=list)
    ha_mgmt_interfaces: List[HAManagementInterface] = field(default_factory=list)
    preempt: bool = False
    session_sync: bool = True
    session_pickup: bool = False
    hb_interval: str = ""
    hb_lost_threshold: str = ""
    encryption: bool = False
    authentication: bool = False
    password: str = ""  # ハッシュ化されたパスワード（表示用）


@dataclass
class SyslogServer:
    """Syslogサーバー"""
    server: str = ""
    port: str = "514"
    facility: str = ""
    status: str = ""
    log_types: List[str] = field(default_factory=list)  # traffic, event, utm
    vdom: str = "root"


@dataclass
class SNMPSettings:
    """SNMP設定"""
    enabled: bool = False
    community: str = ""
    hosts: List[str] = field(default_factory=list)
    trap_hosts: List[str] = field(default_factory=list)
    version: str = ""  # v2c, v3
    username: str = ""  # for v3


@dataclass
class LoggingSettings:
    """ログ・監視設定"""
    syslog_servers: List[SyslogServer] = field(default_factory=list)
    snmp: List[SNMPSettings] = field(default_factory=list)
    fortianalyzer_server: str = ""
    fortianalyzer_status: str = ""
    panorama_server: str = ""
    local_logging: bool = True
    log_disk_quota: str = ""


@dataclass
class ConfigModel:
    """統一設定データモデル"""
    device_info: DeviceInfo = field(default_factory=DeviceInfo)
    system_settings: SystemSettings = field(default_factory=SystemSettings)
    interfaces: List[Interface] = field(default_factory=list)
    routes: List[Route] = field(default_factory=list)
    dhcp_servers: List[DHCPServer] = field(default_factory=list)
    objects: Objects = field(default_factory=Objects)
    firewall_policies: List[FirewallPolicy] = field(default_factory=list)
    local_in_policies: List[LocalInPolicy] = field(default_factory=list)
    nat_policies: List[NATPolicy] = field(default_factory=list)
    vpn: VPNSettings = field(default_factory=VPNSettings)
    security_profiles: List[SecurityProfile] = field(default_factory=list)
    security_profiles_detail: SecurityProfiles = field(default_factory=SecurityProfiles)
    ha: HASettings = field(default_factory=HASettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    # メタデータ
    source_file: str = ""
    parse_errors: List[str] = field(default_factory=list)

    def get_summary(self) -> Dict[str, Any]:
        """設定のサマリー情報を取得"""
        return {
            "device_type": self.device_info.device_type.value,
            "hostname": self.device_info.hostname,
            "version": self.device_info.os_version,
            "interfaces": len(self.interfaces),
            "routes": len(self.routes),
            "policies": len(self.firewall_policies),
            "objects": len(self.objects.addresses) + len(self.objects.services),
            "nat_rules": len(self.nat_policies),
        }
