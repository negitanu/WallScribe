#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Palo Alto Networks設定ファイルパーサー
"""

import html
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

from models.config import (
    AddressGroup,
    AddressObject,
    AdminUser,
    ConfigModel,
    DeviceInfo,
    DeviceType,
    DHCPServer,
    FirewallPolicy,
    HAHeartbeatInterface,
    HAManagementInterface,
    HAMode,
    HASettings,
    Interface,
    IPSecPhase1,
    IPSecPhase2,
    LoggingSettings,
    NATPolicy,
    Objects,
    OperationMode,
    PolicyAction,
    Route,
    SecurityProfile,
    SecurityProfiles,
    ServiceGroup,
    ServiceObject,
    SNMPSettings,
    SSLInspectionProfile,
    SSLVPNSettings,
    SyslogServer,
    SystemSettings,
    VPNSettings,
)

from .base import BaseConfigParser
from .utils import ip_to_cidr

logger = logging.getLogger(__name__)


class PaloAltoParser(BaseConfigParser):
    """Palo Alto Networks設定ファイルパーサー"""

    def __init__(self):
        super().__init__()
        self.root: Optional[ET.Element] = None
        self.device: Optional[ET.Element] = None

    @staticmethod
    def detect_file_type(file_path: str) -> bool:
        """ファイル形式を判定"""
        path = Path(file_path)
        return path.suffix.lower() == ".xml"

    @staticmethod
    def detect_content_type(content: str) -> bool:
        """ファイル内容から形式を判定"""
        # Palo Altoの設定XMLの特徴を検出
        return "<config version=" in content or "<devices>" in content

    def parse(self, file_path: str) -> ConfigModel:
        """設定ファイルをパース"""
        content = self.read_file(file_path)
        if content is None:
            return self.config_model

        self.config_model.source_file = file_path
        return self.parse_content(content, Path(file_path).name)

    def parse_content(self, content: str, filename: str = "") -> ConfigModel:
        """設定ファイルの内容をパース"""
        self.config_model = ConfigModel()
        self.config_model.source_file = filename
        self.config_model.device_info.device_type = DeviceType.PALOALTO

        try:
            # XXE攻撃対策: defusedxmlを使用して安全にパース
            # xml.etree.ElementTreeはデフォルトで外部エンティティを解決しないが、
            # defusedxmlを使用することでより安全にパースできる
            try:
                from defusedxml.ElementTree import fromstring as safe_fromstring

                self.root = safe_fromstring(content)
            except ImportError:
                # defusedxmlがインストールされていない場合は標準ライブラリを使用
                # xml.etree.ElementTreeはデフォルトで外部エンティティを解決しないため比較的安全
                self.root = ET.fromstring(content)
        except ET.ParseError as e:
            self.add_error(f"XMLパースエラー: {e}")
            return self.config_model
        except Exception as e:
            # defusedxmlが検出したセキュリティ問題（XXE攻撃など）
            self.add_error(f"XMLセキュリティエラー: {e}")
            return self.config_model

        # デバイスエレメントを取得
        self.device = self.root.find('.//devices/entry[@name="localhost.localdomain"]')

        # 各セクションをパース
        self._parse_device_info()
        self._parse_system_settings()
        self._parse_interfaces()
        self._parse_routes()
        self._parse_dhcp()
        self._parse_objects()
        self._parse_policies()
        self._parse_nat()
        self._parse_vpn()
        self._parse_security_profiles()
        self._parse_ha()
        self._parse_logging()

        self.config_model.parse_errors = self.errors
        return self.config_model

    def _get_text(self, element: Optional[ET.Element], path: str, default: str = "") -> str:
        """要素からテキストを取得"""
        if element is None:
            return default
        found = element.find(path)
        if found is not None and found.text:
            return html.unescape(found.text)
        return default

    def _get_members(self, element: Optional[ET.Element], path: str) -> List[str]:
        """member要素のリストを取得"""
        if element is None:
            return []
        parent = element.find(path)
        if parent is None:
            return []
        return [m.text for m in parent.findall("member") if m.text]

    def _parse_device_info(self):
        """機器情報をパース"""
        if self.root is not None:
            self.config_model.device_info.os_version = self.root.get("version", "")

        if self.device is None:
            return

        system = self.device.find("deviceconfig/system")
        if system is not None:
            self.config_model.device_info.hostname = self._get_text(system, "hostname")
            self.config_model.device_info.model = "PA Series"

        # Operation mode (always NAT/Route for Palo Alto)
        self.config_model.device_info.operation_mode = OperationMode.NAT_ROUTE

        # vsys list
        vsys_list = self.device.findall(".//vsys/entry")
        for vsys in vsys_list:
            vsys_name = vsys.get("name", "")
            if vsys_name:
                self.config_model.device_info.vdom_list.append(vsys_name)

        if len(self.config_model.device_info.vdom_list) > 1:
            self.config_model.device_info.vdom_enabled = True

    def _parse_system_settings(self):
        """システム設定をパース"""
        if self.device is None:
            return

        system = self.device.find("deviceconfig/system")
        if system is None:
            return

        # Management IP
        self.config_model.system_settings.management_ip = self._get_text(system, "ip-address")
        self.config_model.system_settings.management_netmask = self._get_text(system, "netmask")

        # DNS
        self.config_model.system_settings.dns_primary = self._get_text(
            system, "dns-setting/servers/primary"
        )
        self.config_model.system_settings.dns_secondary = self._get_text(
            system, "dns-setting/servers/secondary"
        )

        # Timezone
        self.config_model.system_settings.timezone = self._get_text(system, "timezone")

        # NTP
        ntp_primary = system.find("ntp-servers/primary-ntp-server")
        if ntp_primary is not None:
            ntp_addr = self._get_text(ntp_primary, "ntp-server-address")
            if ntp_addr:
                self.config_model.system_settings.ntp_servers.append(ntp_addr)

        ntp_secondary = system.find("ntp-servers/secondary-ntp-server")
        if ntp_secondary is not None:
            ntp_addr = self._get_text(ntp_secondary, "ntp-server-address")
            if ntp_addr:
                self.config_model.system_settings.ntp_servers.append(ntp_addr)

        # Admin users
        mgt_config = self.root.find(".//mgt-config") if self.root is not None else None
        if mgt_config is not None:
            users = mgt_config.find("users")
            if users is not None:
                for user_entry in users.findall("entry"):
                    username = user_entry.get("name", "")
                    if username:
                        admin = AdminUser(
                            username=username,
                            profile=self._get_text(user_entry, "permissions/role-based/superuser"),
                        )
                        self.config_model.system_settings.admin_users.append(admin)

        # Permitted IPs
        permitted = system.find("permitted-ip")
        if permitted is not None:
            for entry in permitted.findall("entry"):
                ip = entry.get("name", "")
                if ip:
                    self.config_model.system_settings.allowed_protocols.append(ip)

    def _parse_interfaces(self):
        """インターフェースをパース"""
        if self.device is None:
            return

        network = self.device.find("network")
        if network is None:
            return

        # Physical interfaces (ethernet)
        ethernet = network.find("interface/ethernet")
        if ethernet is not None:
            for entry in ethernet.findall("entry"):
                iface = self._parse_interface_entry(entry, "physical")
                if iface:
                    self.config_model.interfaces.append(iface)

                    # Sub-interfaces (Layer3 units)
                    layer3 = entry.find("layer3")
                    if layer3 is not None:
                        units = layer3.find("units")
                        if units is not None:
                            for unit in units.findall("entry"):
                                sub_iface = self._parse_interface_entry(unit, "vlan")
                                if sub_iface:
                                    # Extract VLAN tag from name
                                    sub_name = unit.get("name", "")
                                    if "." in sub_name:
                                        sub_iface.vlan_id = sub_name.split(".")[-1]
                                    self.config_model.interfaces.append(sub_iface)

        # Aggregate interfaces
        aggregate = network.find("interface/aggregate-ethernet")
        if aggregate is not None:
            for entry in aggregate.findall("entry"):
                iface = self._parse_interface_entry(entry, "lag")
                if iface:
                    self.config_model.interfaces.append(iface)

        # Loopback interfaces
        loopback = network.find("interface/loopback")
        if loopback is not None:
            units = loopback.find("units")
            if units is not None:
                for entry in units.findall("entry"):
                    iface = self._parse_interface_entry(entry, "loopback")
                    if iface:
                        self.config_model.interfaces.append(iface)

        # Tunnel interfaces
        tunnel = network.find("interface/tunnel")
        if tunnel is not None:
            units = tunnel.find("units")
            if units is not None:
                for entry in units.findall("entry"):
                    iface = self._parse_interface_entry(entry, "tunnel")
                    if iface:
                        self.config_model.interfaces.append(iface)

        # Parse zones to associate with interfaces
        self._parse_zones()

    def _parse_interface_entry(self, entry: ET.Element, iface_type: str) -> Optional[Interface]:
        """インターフェースエントリをパース"""
        name = entry.get("name", "")
        if not name:
            return None

        iface = Interface(
            name=name, interface_type=iface_type, description=self._get_text(entry, "comment")
        )

        # IP address (Layer3)
        layer3 = entry.find("layer3")
        if layer3 is not None:
            ip_entry = layer3.find("ip/entry")
            if ip_entry is not None:
                iface.ip_address = ip_entry.get("name", "")
        else:
            # Direct IP (for units)
            ip_entry = entry.find("ip/entry")
            if ip_entry is not None:
                iface.ip_address = ip_entry.get("name", "")

        # Management profile
        mgmt_profile = self._get_text(entry, "layer3/interface-management-profile")
        if not mgmt_profile:
            mgmt_profile = self._get_text(entry, "interface-management-profile")
        if mgmt_profile:
            iface.allowed_access.append(mgmt_profile)

        return iface

    def _parse_zones(self):
        """ゾーン情報をパースしてインターフェースに関連付け"""
        if self.device is None:
            return

        vsys_entries = self.device.findall(".//vsys/entry")
        for vsys in vsys_entries:
            vsys_name = vsys.get("name", "vsys1")
            zone_entries = vsys.findall("zone/entry")

            for zone_entry in zone_entries:
                zone_name = zone_entry.get("name", "")
                network = zone_entry.find("network")
                if network is not None:
                    layer3 = network.find("layer3")
                    if layer3 is not None:
                        members = [m.text for m in layer3.findall("member") if m.text]
                        for member in members:
                            # インターフェースにゾーンを関連付け
                            for iface in self.config_model.interfaces:
                                if iface.name == member:
                                    iface.zone = zone_name
                                    iface.vdom = vsys_name

    def _parse_routes(self):
        """ルーティングをパース"""
        if self.device is None:
            return

        # Virtual routers
        vr_entries = self.device.findall("network/virtual-router/entry")
        for vr in vr_entries:
            vr_name = vr.get("name", "")

            # Static routes
            static_routes = vr.findall("routing-table/ip/static-route/entry")
            for route_entry in static_routes:
                # 宛先ネットワークをCIDR表記に変換
                destination = self._get_text(route_entry, "destination")
                if destination:
                    destination = ip_to_cidr(destination)

                # Nexthop: ip-address / discard / next-vr など
                route_type = "static"
                gateway = self._get_text(route_entry, "nexthop/ip-address")
                if route_entry.find("nexthop/discard") is not None:
                    route_type = "blackhole"
                    gateway = ""  # 破棄ルートなのでゲートウェイは空にする
                elif route_entry.find("nexthop/next-vr") is not None:
                    # 次の仮想ルータへ転送するタイプ（表示用に残す）
                    route_type = "next-vr"
                    gateway = self._get_text(route_entry, "nexthop/next-vr")

                route = Route(
                    name=route_entry.get("name", ""),
                    destination=destination,
                    gateway=gateway,
                    interface=self._get_text(route_entry, "interface"),
                    distance=self._get_text(route_entry, "metric"),
                    route_type=route_type,
                )
                self.config_model.routes.append(route)

    def _parse_dhcp(self):
        """DHCP設定をパース"""
        if self.device is None:
            return

        dhcp_entries = self.device.findall("network/dhcp/interface/entry")
        for dhcp_entry in dhcp_entries:
            interface_name = dhcp_entry.get("name", "")

            server = dhcp_entry.find("server")
            if server is not None:
                ip_pool = server.find("ip-pool/entry")
                start_ip = ""
                end_ip = ""
                if ip_pool is not None:
                    pool_name = ip_pool.get("name", "")
                    if "-" in pool_name:
                        start_ip, end_ip = pool_name.split("-", 1)

                dhcp = DHCPServer(
                    interface=interface_name,
                    start_ip=start_ip,
                    end_ip=end_ip,
                    gateway=self._get_text(server, "option/gateway"),
                    lease_time=self._get_text(server, "option/lease/timeout"),
                )

                # DNS servers
                dns_primary = self._get_text(server, "option/dns/primary")
                dns_secondary = self._get_text(server, "option/dns/secondary")
                if dns_primary:
                    dhcp.dns_servers.append(dns_primary)
                if dns_secondary:
                    dhcp.dns_servers.append(dns_secondary)

                self.config_model.dhcp_servers.append(dhcp)

    def _parse_objects(self):
        """オブジェクト定義をパース"""
        if self.device is None:
            return

        vsys_entries = self.device.findall(".//vsys/entry")
        for vsys in vsys_entries:
            vsys_name = vsys.get("name", "vsys1")
            self._parse_objects_for_vsys(vsys, vsys_name)

    def _parse_objects_for_vsys(self, vsys: ET.Element, vsys_name: str):
        """vsysごとのオブジェクトをパース"""
        # Address objects
        address_entries = vsys.findall("address/entry")
        for addr_entry in address_entries:
            name = addr_entry.get("name", "")
            addr_type = ""
            value = ""

            if addr_entry.find("ip-netmask") is not None:
                addr_type = "subnet"
                # CIDR表記に変換
                ip_netmask = self._get_text(addr_entry, "ip-netmask")
                value = ip_to_cidr(ip_netmask) if ip_netmask else ""
            elif addr_entry.find("ip-range") is not None:
                addr_type = "iprange"
                value = self._get_text(addr_entry, "ip-range")
            elif addr_entry.find("fqdn") is not None:
                addr_type = "fqdn"
                value = self._get_text(addr_entry, "fqdn")

            addr_obj = AddressObject(
                name=name,
                object_type=addr_type,
                value=value,
                vdom=vsys_name,
                description=self._get_text(addr_entry, "description"),
            )
            self.config_model.objects.addresses.append(addr_obj)

        # Address groups
        addrgrp_entries = vsys.findall("address-group/entry")
        for grp_entry in addrgrp_entries:
            members = self._get_members(grp_entry, "static")
            grp_obj = AddressGroup(
                name=grp_entry.get("name", ""),
                members=members,
                vdom=vsys_name,
                description=self._get_text(grp_entry, "description"),
            )
            self.config_model.objects.address_groups.append(grp_obj)

        # Service objects
        service_entries = vsys.findall("service/entry")
        for svc_entry in service_entries:
            name = svc_entry.get("name", "")
            protocol = ""
            port = ""

            tcp = svc_entry.find("protocol/tcp")
            udp = svc_entry.find("protocol/udp")

            if tcp is not None:
                protocol = "TCP"
                port = self._get_text(tcp, "port")
            elif udp is not None:
                protocol = "UDP"
                port = self._get_text(udp, "port")

            svc_obj = ServiceObject(
                name=name,
                protocol=protocol,
                port=port,
                vdom=vsys_name,
                description=self._get_text(svc_entry, "description"),
            )
            self.config_model.objects.services.append(svc_obj)

        # Service groups
        svcgrp_entries = vsys.findall("service-group/entry")
        for svc_grp_entry in svcgrp_entries:
            members = self._get_members(svc_grp_entry, "members")
            svc_grp_obj = ServiceGroup(
                name=svc_grp_entry.get("name", ""),
                members=members,
                vdom=vsys_name,
                description=self._get_text(svc_grp_entry, "description"),
            )
            self.config_model.objects.service_groups.append(svc_grp_obj)

    def _parse_policies(self):
        """ポリシーをパース"""
        if self.device is None:
            return

        vsys_entries = self.device.findall(".//vsys/entry")
        for vsys in vsys_entries:
            vsys_name = vsys.get("name", "vsys1")

            # Security rules
            rules = vsys.findall("rulebase/security/rules/entry")
            for idx, rule_entry in enumerate(rules, 1):
                # 仕様: action が未定義なら拒否(deny)として扱う
                action_str = self._get_text(rule_entry, "action", "deny")
                if action_str == "allow":
                    action = PolicyAction.ALLOW
                elif action_str == "deny":
                    action = PolicyAction.DENY
                elif action_str == "drop":
                    action = PolicyAction.DROP
                else:
                    action = PolicyAction.UNKNOWN

                policy = FirewallPolicy(
                    policy_id=str(idx),
                    name=rule_entry.get("name", ""),
                    source_interface=self._get_members(rule_entry, "from"),
                    destination_interface=self._get_members(rule_entry, "to"),
                    source_address=self._get_members(rule_entry, "source"),
                    destination_address=self._get_members(rule_entry, "destination"),
                    service=self._get_members(rule_entry, "service"),
                    application=self._get_members(rule_entry, "application"),
                    action=action,
                    log_enabled=self._get_text(rule_entry, "log-end", "no") == "yes",
                    vdom=vsys_name,
                    enabled=self._get_text(rule_entry, "disabled", "no") != "yes",
                    description=self._get_text(rule_entry, "description"),
                )

                # Security profiles
                profile_setting = rule_entry.find("profile-setting")
                if profile_setting is not None:
                    group = profile_setting.find("group")
                    if group is not None:
                        policy.security_profiles = self._get_members(profile_setting, "group")

                self.config_model.firewall_policies.append(policy)

    def _parse_nat(self):
        """NAT設定をパース"""
        if self.device is None:
            return

        vsys_entries = self.device.findall(".//vsys/entry")
        for vsys in vsys_entries:
            vsys_name = vsys.get("name", "vsys1")

            # NAT rules
            nat_rules = vsys.findall("rulebase/nat/rules/entry")
            for rule_entry in nat_rules:
                name = rule_entry.get("name", "")

                # Source translation
                src_translation = rule_entry.find("source-translation")
                dst_translation = rule_entry.find("destination-translation")

                nat_type = ""
                translated_src = ""
                translated_dst = ""

                if src_translation is not None:
                    nat_type = "snat"
                    # Dynamic IP/port
                    dynamic_ip = src_translation.find("dynamic-ip-and-port")
                    if dynamic_ip is not None:
                        interface_addr = dynamic_ip.find("interface-address")
                        if interface_addr is not None:
                            translated_src = self._get_text(interface_addr, "interface")

                if dst_translation is not None:
                    if nat_type:
                        nat_type = "static"
                    else:
                        nat_type = "dnat"
                    translated_dst = self._get_text(dst_translation, "translated-address")

                if nat_type:
                    original_src = self._get_members(rule_entry, "source")
                    original_dst = self._get_members(rule_entry, "destination")

                    nat = NATPolicy(
                        name=name,
                        nat_type=nat_type,
                        original_source=", ".join(original_src) if original_src else "",
                        original_destination=", ".join(original_dst) if original_dst else "",
                        translated_source=translated_src,
                        translated_destination=translated_dst,
                        vdom=vsys_name,
                        description=self._get_text(rule_entry, "description"),
                    )
                    self.config_model.nat_policies.append(nat)

    def _parse_vpn(self):
        """VPN設定をパース"""
        if self.device is None:
            return

        network = self.device.find("network")
        if network is None:
            return

        # IKE gateways
        ike_gateways = network.findall("ike/gateway/entry")
        for gw_entry in ike_gateways:
            name = gw_entry.get("name", "")
            peer_address = gw_entry.find("peer-address")
            remote_gw = ""
            if peer_address is not None:
                remote_gw = self._get_text(peer_address, "ip")

            p1 = IPSecPhase1(
                name=name,
                remote_gateway=remote_gw,
                interface=self._get_text(gw_entry, "local-address/interface"),
                ike_version=self._get_text(gw_entry, "protocol/ikev1/ike-crypto-profile"),
                psk=gw_entry.find("authentication/pre-shared-key") is not None,
            )
            self.config_model.vpn.ipsec_phase1.append(p1)

        # IPsec tunnels
        ipsec_tunnels = network.findall("tunnel/ipsec/entry")
        for tunnel_entry in ipsec_tunnels:
            # IKEゲートウェイのentry要素からname属性を取得
            ike_gw_entry = tunnel_entry.find("auto-key/ike-gateway/entry")
            phase1_name = ike_gw_entry.get("name", "") if ike_gw_entry is not None else ""

            p2 = IPSecPhase2(name=tunnel_entry.get("name", ""), phase1_name=phase1_name)
            self.config_model.vpn.ipsec_phase2.append(p2)

        # GlobalProtect (SSL VPN equivalent)
        gp_gateway = network.find("global-protect/global-protect-gateway")
        if gp_gateway is not None:
            for gw_entry in gp_gateway.findall("entry"):
                ssl_vpn = SSLVPNSettings(
                    listen_interface=self._get_text(gw_entry, "local-address/interface"),
                )

                # User groups
                agent_user = gw_entry.find("agent-user")
                if agent_user is not None:
                    groups = self._get_members(agent_user, "user-group-list")
                    ssl_vpn.user_groups = groups

                self.config_model.vpn.ssl_vpn.append(ssl_vpn)

    def _parse_security_profiles(self):
        """セキュリティプロファイルをパース"""
        if self.device is None:
            return

        vsys_entries = self.device.findall(".//vsys/entry")
        for vsys in vsys_entries:
            vsys_name = vsys.get("name", "vsys1")

            profile_types = [
                ("profiles/virus/entry", "antivirus"),
                ("profiles/url-filtering/entry", "webfilter"),
                ("profiles/vulnerability/entry", "ips"),
                ("profiles/decryption/entry", "ssl-inspection"),
            ]

            for path, profile_type in profile_types:
                entries = vsys.findall(path)
                for entry in entries:
                    profile = SecurityProfile(
                        name=entry.get("name", ""),
                        profile_type=profile_type,
                        vdom=vsys_name,
                        description=self._get_text(entry, "description"),
                    )
                    self.config_model.security_profiles.append(profile)

                    # SSLインスペクションプロファイルの詳細解析
                    if profile_type == "ssl-inspection":
                        mode = "certificate-inspection"  # デフォルト
                        profile_name = entry.get("name", "")

                        # プロファイル名で判定
                        if "deep" in profile_name.lower() or "full" in profile_name.lower():
                            mode = "deep-inspection"
                        else:
                            # ssl-forward-proxyの設定を確認
                            ssl_fp = entry.find("ssl-forward-proxy")
                            if ssl_fp is not None:
                                # ssl-forward-proxyが存在する場合はdeep-inspectionの可能性が高い
                                # ただし、設定内容を確認
                                cert_status = self._get_text(ssl_fp, "certificate-status")
                                if cert_status:
                                    # certificate-statusが設定されている場合はdeep-inspection
                                    mode = "deep-inspection"

                            # ssl-inbound-inspectionの設定を確認
                            ssl_inbound = entry.find("ssl-inbound-inspection")
                            if ssl_inbound is not None:
                                # ssl-inbound-inspectionが存在する場合はdeep-inspection
                                mode = "deep-inspection"

                        ssl_profile = SSLInspectionProfile(
                            name=profile_name, enabled=True, mode=mode, vdom=vsys_name
                        )
                        self.config_model.security_profiles_detail.ssl_inspection.append(
                            ssl_profile
                        )

    def _parse_ha(self):
        """HA設定をパース"""
        if self.device is None:
            return

        ha_config = self.device.find("deviceconfig/high-availability")
        if ha_config is None:
            return

        group = ha_config.find("group")
        if group is None:
            return

        # enabled 判定（未設定の場合は設定が存在する＝有効として扱う）
        enabled_raw = self._get_text(ha_config, "enabled", "").strip().lower()
        enabled = (
            True if enabled_raw == "" else enabled_raw in ("yes", "true", "1", "enable", "enabled")
        )

        # HA mode
        mode = HAMode.STANDALONE
        if enabled:
            mode_elem = group.find("mode")
            if mode_elem is not None:
                if mode_elem.find("active-passive") is not None:
                    mode = HAMode.ACTIVE_PASSIVE
                elif mode_elem.find("active-active") is not None:
                    mode = HAMode.ACTIVE_ACTIVE

        # group name / priority / preempt など
        group_name = (
            self._get_text(group, "group-description")
            or self._get_text(group, "group-name")
            or self._get_text(group, "name")
        )
        priority = self._get_text(group, "election-option/priority") or self._get_text(
            group, "election-option/device-priority"
        )
        preempt_raw = self._get_text(group, "election-option/preemptive", "no").strip().lower()
        preempt = preempt_raw in ("yes", "true", "1", "enable", "enabled")

        # 可能なら心拍系パラメータも拾う（PAN-OSの表記揺れ対策で複数候補）
        hb_interval = self._get_text(group, "election-option/hello-interval") or self._get_text(
            group, "election-option/heartbeat-interval"
        )
        hb_lost_threshold = self._get_text(group, "election-option/hold-time") or self._get_text(
            group, "election-option/heartbeat-missed"
        )

        self.config_model.ha = HASettings(
            mode=mode,
            group_id=self._get_text(group, "group-id"),
            group_name=group_name,
            priority=priority,
            preempt=preempt,
            hb_interval=hb_interval,
            hb_lost_threshold=hb_lost_threshold,
        )

        # Link/Path monitoring（監視対象インターフェース）
        monitor_set = set()
        for sec in (
            group.find("link-monitoring"),
            group.find("path-monitoring"),
            group.find("monitoring/link-monitoring"),
            group.find("monitoring/path-monitoring"),
        ):
            if sec is None:
                continue
            for m in sec.findall(".//member"):
                if m is not None and m.text:
                    val = m.text.strip()
                    if val:
                        monitor_set.add(val)
        if monitor_set:
            self.config_model.ha.monitor_interfaces = sorted(monitor_set)

        # HA1/HA2インターフェース・IP等
        iface_cfg = ha_config.find("interface")
        if iface_cfg is not None:
            hb_set = []
            seen = set()
            for key, label in (
                ("ha1", "HA1"),
                ("ha1-backup", "HA1-backup"),
                ("ha2", "HA2"),
                ("ha2-backup", "HA2-backup"),
                ("ha3", "HA3"),
                ("ha3-backup", "HA3-backup"),
            ):
                link = iface_cfg.find(key)
                if link is None:
                    continue

                port = self._get_text(link, "port") or self._get_text(link, "interface")
                ipaddr = self._get_text(link, "ip-address") or self._get_text(link, "ip")

                # 表示用：HAインターフェース（ラベル＋実インターフェース名）
                if port:
                    self.config_model.ha.ha_interfaces.append(f"{label}: {port}")
                else:
                    self.config_model.ha.ha_interfaces.append(label)

                # 表示用：ハートビートインターフェース（一覧/詳細）
                if port and port not in seen:
                    hb_set.append(port)
                    seen.add(port)
                    self.config_model.ha.heartbeat_interfaces_detail.append(
                        HAHeartbeatInterface(interface=port, priority="")
                    )

                # 表示用：HA管理/リンク情報（gateway欄にIPを載せる）
                if port or ipaddr:
                    self.config_model.ha.ha_mgmt_interfaces.append(
                        HAManagementInterface(
                            id=label, interface=port or label, gateway=ipaddr or ""
                        )
                    )

            if hb_set:
                self.config_model.ha.heartbeat_interfaces = hb_set

    def _parse_logging(self):
        """ログ設定をパース"""
        if self.device is None:
            return

        # Syslog - 複数のパスをサポート
        syslog_paths = [
            # deviceconfig/setting 配下
            ("deviceconfig/setting", "logging/logging-service-setting/syslog/entry"),
            # shared/log-settings 配下（PANOSの一般的な場所）
            ("..", "shared/log-settings/syslog/entry"),
        ]

        for base_path, syslog_path in syslog_paths:
            base_elem = self.device.find(base_path) if base_path != ".." else self.root
            if base_elem is not None:
                syslog_entries = base_elem.findall(syslog_path)
                for entry in syslog_entries:
                    server_addr = self._get_text(entry, "server")
                    # 重複チェック
                    if server_addr and not any(
                        s.server == server_addr for s in self.config_model.logging.syslog_servers
                    ):
                        server = SyslogServer(
                            server=server_addr,
                            port=self._get_text(entry, "port", "514"),
                            facility=self._get_text(entry, "facility", ""),
                            status="enabled",
                        )
                        self.config_model.logging.syslog_servers.append(server)

        # vsys配下のlog-settings/syslogも確認
        vsys_entries = self.device.findall(".//vsys/entry")
        for vsys in vsys_entries:
            syslog_profiles = vsys.findall("log-settings/syslog/entry")
            for entry in syslog_profiles:
                # syslog profileのserver設定を取得
                server_entries = entry.findall("server/entry")
                for server_entry in server_entries:
                    server_addr = server_entry.get("name", "")
                    if server_addr and not any(
                        s.server == server_addr for s in self.config_model.logging.syslog_servers
                    ):
                        server = SyslogServer(
                            server=server_addr,
                            port=self._get_text(server_entry, "port", "514"),
                            facility=self._get_text(server_entry, "facility", ""),
                            status="enabled",
                        )
                        self.config_model.logging.syslog_servers.append(server)

        # SNMP
        snmp_config = self.device.find("deviceconfig/system/snmp-setting")
        if snmp_config is not None:
            # SNMP有効化状態
            snmp_enabled = snmp_config.get("enabled", "no") == "yes"

            # SNMP v2c コミュニティ設定
            v2c = snmp_config.find("access-setting/version/v2c")
            if v2c is not None:
                for entry in v2c.findall("entry"):
                    community_name = entry.get("name", "")

                    # ホスト設定を取得
                    hosts = []
                    host_elem = entry.find("host")
                    if host_elem is not None:
                        host_text = host_elem.text
                        if host_text:
                            hosts = [host_text.strip()]

                    # トラップ送信先を取得
                    trap_hosts = []
                    trap_servers = snmp_config.find("trap-server")
                    if trap_servers is not None:
                        for trap_entry in trap_servers.findall("entry"):
                            trap_host = self._get_text(trap_entry, "server")
                            if trap_host:
                                trap_hosts.append(trap_host)

                    snmp = SNMPSettings(
                        enabled=snmp_enabled,
                        community=community_name,
                        hosts=hosts,
                        trap_hosts=trap_hosts,
                        version="v2c",
                    )
                    self.config_model.logging.snmp.append(snmp)

            # SNMP v3 ユーザー設定
            v3 = snmp_config.find("access-setting/version/v3")
            if v3 is not None:
                for entry in v3.findall("entry"):
                    username = entry.get("name", "")

                    # ホスト設定を取得
                    hosts = []
                    host_elem = entry.find("host")
                    if host_elem is not None:
                        host_text = host_elem.text
                        if host_text:
                            hosts = [host_text.strip()]

                    # トラップ送信先を取得
                    trap_hosts = []
                    trap_servers = snmp_config.find("trap-server")
                    if trap_servers is not None:
                        for trap_entry in trap_servers.findall("entry"):
                            trap_host = self._get_text(trap_entry, "server")
                            if trap_host:
                                trap_hosts.append(trap_host)

                    snmp = SNMPSettings(
                        enabled=snmp_enabled,
                        username=username,
                        hosts=hosts,
                        trap_hosts=trap_hosts,
                        version="v3",
                    )
                    self.config_model.logging.snmp.append(snmp)

        # Panorama
        panorama = self.root.find(".//panorama/panorama-server") if self.root is not None else None
        if panorama is not None:
            self.config_model.logging.panorama_server = panorama.text or ""
