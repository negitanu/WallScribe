#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExcelExporter: VDOM/vsys 系シート生成（IF/ルート/オブジェクト/ポリシー/NAT/VPN/セキュリティ）
"""

from __future__ import annotations

from typing import Any

try:
    from openpyxl.styles import PatternFill  # type: ignore
    from openpyxl.worksheet.worksheet import Worksheet  # type: ignore
except ImportError:  # pragma: no cover
    from exporters.excel_styles import PatternFill  # type: ignore

    Worksheet = Any  # type: ignore


class ExcelVdomSheetsMixin:
    # ============================================================
    # VDOM単位のシート作成メソッド
    # ============================================================

    def _create_interfaces_sheet_for_vdom(self, vdom: str):
        """指定VDOMのインターフェースシートを作成"""
        interfaces = self._filter_by_vdom(self.config.interfaces, vdom)
        if not interfaces:
            return

        ws = self._create_sheet("IF", vdom)
        headers = [
            "インターフェース名",
            "タイプ",
            "役割",
            "IPアドレス",
            "VLAN ID",
            "ゾーン",
            "許可アクセス",
            "状態",
            "説明",
        ]
        self._set_header_row(ws, headers)

        for row_idx, iface in enumerate(interfaces, 2):
            self._set_cell(ws, row_idx, 1, iface.name)
            self._set_cell(ws, row_idx, 2, iface.interface_type, center=True)
            self._set_cell(ws, row_idx, 3, iface.role, center=True)
            self._set_cell(ws, row_idx, 4, iface.ip_address)
            self._set_cell(ws, row_idx, 5, iface.vlan_id, center=True)
            self._set_cell(ws, row_idx, 6, iface.zone, center=True)
            self._set_cell(ws, row_idx, 7, self._list_to_str(iface.allowed_access, ", "))
            status_enabled = iface.status and iface.status.lower() in (
                "up",
                "enable",
                "enabled",
                "有効",
            )
            self._set_status_cell(
                ws,
                row_idx,
                8,
                status_enabled,
                enabled_text=iface.status or "up",
                disabled_text=iface.status or "down",
            )
            self._set_cell(ws, row_idx, 9, iface.description)

        self._auto_column_width(ws)

    def _create_routes_sheet_for_vdom(self, vdom: str):
        """指定VDOMのルーティングシートを作成（スタティック、OSPF、BGP、ポリシールート）"""
        routes = self._filter_by_vdom(self.config.routes, vdom)
        ospf_list = self._filter_by_vdom(self.config.routing.ospf, vdom)
        ospf6_list = self._filter_by_vdom(self.config.routing.ospf6, vdom)
        bgp_list = self._filter_by_vdom(self.config.routing.bgp, vdom)
        policy_routes = self._filter_by_vdom(self.config.routing.policy_routes, vdom)

        if not any([routes, ospf_list, ospf6_list, bgp_list, policy_routes]):
            return

        ws = self._create_sheet("ルート", vdom)
        row_idx = 1

        if routes:
            self._set_section_title(ws, row_idx, 1, "スタティックルート", colspan=6)
            headers = [
                "ルート名",
                "宛先ネットワーク",
                "ゲートウェイ",
                "インターフェース",
                "ディスタンス",
                "タイプ",
            ]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2

            for route in routes:
                gateway_display = route.gateway
                if not gateway_display and getattr(route, "route_type", "") in (
                    "blackhole",
                    "blackhole6",
                ):
                    gateway_display = "blackhole"

                self._set_cell(ws, row_idx, 1, route.name)
                self._set_cell(ws, row_idx, 2, route.destination)
                self._set_cell(ws, row_idx, 3, gateway_display)
                self._set_cell(ws, row_idx, 4, route.interface or "-")
                self._set_cell(ws, row_idx, 5, route.distance, center=True)
                self._set_cell(ws, row_idx, 6, route.route_type, center=True)
                row_idx += 1
            row_idx += 1

        for ospf in ospf_list:
            row_idx = self._add_ospf_section(ws, row_idx, ospf, "OSPF")
        for ospf6 in ospf6_list:
            row_idx = self._add_ospf_section(ws, row_idx, ospf6, "OSPFv3")
        for bgp in bgp_list:
            row_idx = self._add_bgp_section(ws, row_idx, bgp)

        if policy_routes:
            self._set_section_title(ws, row_idx, 1, "ポリシールート", colspan=8)
            headers = [
                "Seq",
                "送信元",
                "宛先",
                "プロトコル",
                "入力IF",
                "出力IF",
                "ゲートウェイ",
                "状態",
            ]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2

            for pr in policy_routes:
                self._set_cell(ws, row_idx, 1, pr.seq_num, center=True)
                self._set_cell(ws, row_idx, 2, pr.src or "any")
                self._set_cell(ws, row_idx, 3, pr.dst or "any")
                self._set_cell(ws, row_idx, 4, pr.protocol or "any", center=True)
                self._set_cell(ws, row_idx, 5, pr.input_device or "-")
                self._set_cell(ws, row_idx, 6, pr.output_device or "-")
                self._set_cell(ws, row_idx, 7, pr.gateway or "-")
                self._set_status_cell(ws, row_idx, 8, pr.status)
                row_idx += 1

        self._auto_column_width(ws)

    def _add_ospf_section(self, ws: Worksheet, row_idx: int, ospf, title: str) -> int:
        """OSPFセクションを追加"""
        self._set_section_title(ws, row_idx, 1, f"{title}設定", colspan=4)
        row_idx += 1

        info_fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")
        basic_data = [
            ("Router ID", ospf.router_id or "-"),
            ("デフォルトルート生成", "有効" if ospf.default_information_originate else "無効"),
            ("デフォルトメトリック", ospf.default_metric or "-"),
            ("ディスタンス", ospf.distance or "-"),
        ]
        for label, value in basic_data:
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill
            label_cell.border = self.THIN_BORDER
            value_cell = ws.cell(row=row_idx, column=2, value=value)
            value_cell.font = self.CELL_FONT
            value_cell.fill = info_fill
            value_cell.border = self.THIN_BORDER
            row_idx += 1
        row_idx += 1

        if ospf.areas:
            self._set_section_title(ws, row_idx, 1, f"{title}エリア", colspan=4)
            headers = ["エリアID", "タイプ", "認証", "ネットワーク"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for area in ospf.areas:
                self._set_cell(ws, row_idx, 1, area.area_id)
                self._set_cell(ws, row_idx, 2, area.area_type, center=True)
                self._set_cell(ws, row_idx, 3, area.authentication or "-", center=True)
                self._set_cell(ws, row_idx, 4, ", ".join(area.networks) if area.networks else "-")
                row_idx += 1
            row_idx += 1

        if ospf.interfaces:
            self._set_section_title(ws, row_idx, 1, f"{title}インターフェース", colspan=6)
            headers = ["名前", "インターフェース", "エリア", "コスト", "優先度", "パッシブ"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for iface in ospf.interfaces:
                self._set_cell(ws, row_idx, 1, iface.name)
                self._set_cell(ws, row_idx, 2, iface.interface)
                self._set_cell(ws, row_idx, 3, iface.area)
                self._set_cell(ws, row_idx, 4, iface.cost or "-", center=True)
                self._set_cell(ws, row_idx, 5, iface.priority or "-", center=True)
                self._set_status_cell(ws, row_idx, 6, iface.passive)
                row_idx += 1
            row_idx += 1

        if ospf.redistributes:
            self._set_section_title(ws, row_idx, 1, f"{title}再配布", colspan=4)
            headers = ["プロトコル", "状態", "メトリック", "ルートマップ"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for redist in ospf.redistributes:
                self._set_cell(ws, row_idx, 1, redist.protocol)
                self._set_status_cell(ws, row_idx, 2, redist.status)
                self._set_cell(ws, row_idx, 3, redist.metric or "-", center=True)
                self._set_cell(ws, row_idx, 4, redist.routemap or "-")
                row_idx += 1
            row_idx += 1

        return row_idx

    def _add_bgp_section(self, ws: Worksheet, row_idx: int, bgp) -> int:
        """BGPセクションを追加"""
        self._set_section_title(ws, row_idx, 1, "BGP設定", colspan=4)
        row_idx += 1

        info_fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")
        basic_data = [("AS番号", bgp.as_number or "-"), ("Router ID", bgp.router_id or "-")]
        for label, value in basic_data:
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill
            label_cell.border = self.THIN_BORDER
            value_cell = ws.cell(row=row_idx, column=2, value=value)
            value_cell.font = self.CELL_FONT
            value_cell.fill = info_fill
            value_cell.border = self.THIN_BORDER
            row_idx += 1
        row_idx += 1

        if bgp.neighbors:
            self._set_section_title(ws, row_idx, 1, "BGPネイバー", colspan=6)
            headers = [
                "ネイバーIP",
                "リモートAS",
                "説明",
                "Next-Hop-Self",
                "ルートマップ(IN)",
                "ルートマップ(OUT)",
            ]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for neighbor in bgp.neighbors:
                self._set_cell(ws, row_idx, 1, neighbor.ip)
                self._set_cell(ws, row_idx, 2, neighbor.remote_as, center=True)
                self._set_cell(ws, row_idx, 3, neighbor.description or "-")
                self._set_status_cell(ws, row_idx, 4, neighbor.next_hop_self)
                self._set_cell(ws, row_idx, 5, neighbor.route_map_in or "-")
                self._set_cell(ws, row_idx, 6, neighbor.route_map_out or "-")
                row_idx += 1
            row_idx += 1

        if bgp.networks:
            self._set_section_title(ws, row_idx, 1, "BGPネットワーク", colspan=2)
            headers = ["プレフィックス", "ルートマップ"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for network in bgp.networks:
                self._set_cell(ws, row_idx, 1, network.prefix)
                self._set_cell(ws, row_idx, 2, network.route_map or "-")
                row_idx += 1
            row_idx += 1

        if bgp.redistributes:
            self._set_section_title(ws, row_idx, 1, "BGP再配布", colspan=3)
            headers = ["プロトコル", "状態", "ルートマップ"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for redist in bgp.redistributes:
                self._set_cell(ws, row_idx, 1, redist.protocol)
                self._set_status_cell(ws, row_idx, 2, redist.status)
                self._set_cell(ws, row_idx, 3, redist.route_map or "-")
                row_idx += 1
            row_idx += 1

        return row_idx

    def _create_objects_sheet_for_vdom(self, vdom: str):
        """指定VDOMのオブジェクト定義シートを作成"""
        addresses = self._filter_by_vdom(self.config.objects.addresses, vdom)
        address_groups = self._filter_by_vdom(self.config.objects.address_groups, vdom)
        services = self._filter_by_vdom(self.config.objects.services, vdom)
        service_groups = self._filter_by_vdom(self.config.objects.service_groups, vdom)

        if not any([addresses, address_groups, services, service_groups]):
            return

        ws = self._create_sheet("オブジェクト", vdom)
        row_idx = 1

        if addresses:
            self._set_section_title(ws, row_idx, 1, "アドレスオブジェクト", colspan=4)
            addr_headers = ["オブジェクト名", "タイプ", "値", "説明"]
            self._set_header_row(ws, addr_headers, row_idx + 1)
            row_idx += 2
            for addr in addresses:
                self._set_cell(ws, row_idx, 1, addr.name)
                self._set_cell(ws, row_idx, 2, addr.object_type, center=True)
                self._set_cell(ws, row_idx, 3, addr.value)
                self._set_cell(ws, row_idx, 4, addr.description)
                row_idx += 1
            row_idx += 1

        if address_groups:
            self._set_section_title(ws, row_idx, 1, "アドレスグループ", colspan=3)
            grp_headers = ["グループ名", "メンバー", "説明"]
            self._set_header_row(ws, grp_headers, row_idx + 1)
            row_idx += 2
            for grp in address_groups:
                self._set_cell(ws, row_idx, 1, grp.name)
                self._set_cell(ws, row_idx, 2, self._list_to_str(grp.members, ", "))
                self._set_cell(ws, row_idx, 3, grp.description)
                row_idx += 1
            row_idx += 1

        if services:
            self._set_section_title(ws, row_idx, 1, "サービスオブジェクト", colspan=4)
            svc_headers = ["オブジェクト名", "プロトコル", "ポート", "説明"]
            self._set_header_row(ws, svc_headers, row_idx + 1)
            row_idx += 2
            for svc in services:
                self._set_cell(ws, row_idx, 1, svc.name)
                self._set_cell(ws, row_idx, 2, svc.protocol, center=True)
                self._set_cell(ws, row_idx, 3, svc.port, center=True)
                self._set_cell(ws, row_idx, 4, svc.description)
                row_idx += 1
            row_idx += 1

        if service_groups:
            self._set_section_title(ws, row_idx, 1, "サービスグループ", colspan=3)
            sgrp_headers = ["グループ名", "メンバー", "説明"]
            self._set_header_row(ws, sgrp_headers, row_idx + 1)
            row_idx += 2
            for grp in service_groups:
                self._set_cell(ws, row_idx, 1, grp.name)
                self._set_cell(ws, row_idx, 2, self._list_to_str(grp.members, ", "))
                self._set_cell(ws, row_idx, 3, grp.description)
                row_idx += 1

        self._auto_column_width(ws)

    def _create_policies_sheet_for_vdom(self, vdom: str):
        """指定VDOMのファイアウォールポリシーシートを作成"""
        policies = self._filter_by_vdom(self.config.firewall_policies, vdom)
        local_in_policies = self._filter_by_vdom(self.config.local_in_policies, vdom)

        if not policies and not local_in_policies:
            return

        ws = self._create_sheet("ポリシー", vdom)
        row_idx = 1

        if policies:
            self._set_section_title(ws, row_idx, 1, "ファイアウォールポリシー", colspan=14)
            headers = [
                "No",
                "ID",
                "ポリシー名",
                "送信元IF",
                "宛先IF",
                "送信元アドレス",
                "宛先アドレス",
                "サービス",
                "アクション",
                "NAT",
                "ログ",
                "セキュリティ",
                "有効",
                "説明",
            ]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2

            for idx, policy in enumerate(policies, 1):
                self._set_cell(ws, row_idx, 1, idx, center=True)
                self._set_cell(ws, row_idx, 2, policy.policy_id, center=True)
                self._set_cell(ws, row_idx, 3, policy.name)
                self._set_cell(ws, row_idx, 4, self._list_to_str(policy.source_interface))
                self._set_cell(ws, row_idx, 5, self._list_to_str(policy.destination_interface))
                self._set_cell(ws, row_idx, 6, self._list_to_str(policy.source_address))
                self._set_cell(ws, row_idx, 7, self._list_to_str(policy.destination_address))
                self._set_cell(ws, row_idx, 8, self._list_to_str(policy.service))
                self._set_action_cell(ws, row_idx, 9, policy.action)
                self._set_status_cell(ws, row_idx, 10, policy.nat_enabled)
                self._set_status_cell(ws, row_idx, 11, policy.log_enabled)
                self._set_cell(ws, row_idx, 12, self._list_to_str(policy.security_profiles))
                self._set_status_cell(ws, row_idx, 13, policy.enabled)
                self._set_cell(ws, row_idx, 14, policy.description)
                row_idx += 1

            row_idx += 1

        if local_in_policies:
            self._set_section_title(ws, row_idx, 1, "Local-in ポリシー", colspan=10)
            headers = [
                "No",
                "ID",
                "ポリシー名",
                "送信元IF",
                "送信元アドレス",
                "宛先アドレス",
                "サービス",
                "アクション",
                "有効",
                "説明",
            ]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2

            for idx, policy in enumerate(local_in_policies, 1):
                src_if = policy.source_interface
                if isinstance(src_if, list):
                    src_if_str = self._list_to_str(src_if)
                else:
                    src_if_str = src_if or "-"

                self._set_cell(ws, row_idx, 1, idx, center=True)
                self._set_cell(ws, row_idx, 2, policy.policy_id, center=True)
                self._set_cell(ws, row_idx, 3, policy.name)
                self._set_cell(ws, row_idx, 4, src_if_str)
                self._set_cell(ws, row_idx, 5, self._list_to_str(policy.source_address))
                self._set_cell(ws, row_idx, 6, self._list_to_str(policy.destination_address))
                self._set_cell(ws, row_idx, 7, self._list_to_str(policy.service))
                self._set_action_cell(ws, row_idx, 8, policy.action)
                self._set_status_cell(ws, row_idx, 9, policy.enabled)
                self._set_cell(ws, row_idx, 10, policy.description)
                row_idx += 1

        self._auto_column_width(ws)

    def _create_nat_sheet_for_vdom(self, vdom: str):
        """指定VDOMのNAT設定シートを作成"""
        nat_policies = self._filter_by_vdom(self.config.nat_policies, vdom)
        if not nat_policies:
            return

        ws = self._create_sheet("NAT", vdom)
        headers = [
            "ルール名",
            "タイプ",
            "元送信元",
            "元宛先",
            "変換後送信元",
            "変換後宛先",
            "外部IF",
            "外部IP",
            "内部IP",
            "ポートFW",
            "元ポート",
            "変換後ポート",
            "説明",
        ]
        self._set_header_row(ws, headers)

        for row_idx, nat in enumerate(nat_policies, 2):
            self._set_cell(ws, row_idx, 1, nat.name)
            self._set_cell(ws, row_idx, 2, nat.nat_type, center=True)
            self._set_cell(ws, row_idx, 3, nat.original_source)
            self._set_cell(ws, row_idx, 4, nat.original_destination)
            self._set_cell(ws, row_idx, 5, nat.translated_source)
            self._set_cell(ws, row_idx, 6, nat.translated_destination)
            self._set_cell(ws, row_idx, 7, nat.external_interface)
            self._set_cell(ws, row_idx, 8, nat.external_ip)
            self._set_cell(ws, row_idx, 9, nat.internal_ip)
            self._set_status_cell(ws, row_idx, 10, nat.port_forward)
            self._set_cell(ws, row_idx, 11, nat.original_port, center=True)
            self._set_cell(ws, row_idx, 12, nat.translated_port, center=True)
            self._set_cell(ws, row_idx, 13, nat.description)

        self._auto_column_width(ws)

    def _create_vpn_sheet_for_vdom(self, vdom: str):
        """指定VDOMのVPN設定シートを作成"""
        ipsec_p1 = self.config.vpn.ipsec_phase1
        ipsec_p2 = self.config.vpn.ipsec_phase2
        ssl_vpn = [s for s in self.config.vpn.ssl_vpn if getattr(s, "vdom", "root") == vdom]

        if not any([ipsec_p1, ipsec_p2, ssl_vpn]):
            return

        ws = self._create_sheet("VPN", vdom)
        row_idx = 1

        if ipsec_p1:
            self._set_section_title(ws, row_idx, 1, "IPsec Phase1", colspan=9)
            p1_headers = [
                "VPN名",
                "リモートGW",
                "IF",
                "IKE",
                "暗号化",
                "認証",
                "DH",
                "ライフタイム",
                "PSK",
            ]
            self._set_header_row(ws, p1_headers, row_idx + 1)
            row_idx += 2
            for p1 in ipsec_p1:
                self._set_cell(ws, row_idx, 1, p1.name)
                self._set_cell(ws, row_idx, 2, p1.remote_gateway)
                self._set_cell(ws, row_idx, 3, p1.interface)
                self._set_cell(ws, row_idx, 4, p1.ike_version, center=True)
                self._set_cell(ws, row_idx, 5, p1.encryption, center=True)
                self._set_cell(ws, row_idx, 6, p1.authentication, center=True)
                self._set_cell(ws, row_idx, 7, p1.dh_group, center=True)
                self._set_cell(ws, row_idx, 8, p1.lifetime, center=True)
                self._set_status_cell(
                    ws, row_idx, 9, bool(p1.psk), enabled_text="有", disabled_text="無"
                )
                row_idx += 1
            row_idx += 1

        if ipsec_p2:
            self._set_section_title(ws, row_idx, 1, "IPsec Phase2", colspan=8)
            p2_headers = [
                "VPN名",
                "Phase1",
                "暗号化",
                "認証",
                "PFS",
                "ライフタイム",
                "ローカル",
                "リモート",
            ]
            self._set_header_row(ws, p2_headers, row_idx + 1)
            row_idx += 2
            for p2 in ipsec_p2:
                self._set_cell(ws, row_idx, 1, p2.name)
                self._set_cell(ws, row_idx, 2, p2.phase1_name)
                self._set_cell(ws, row_idx, 3, p2.encryption, center=True)
                self._set_cell(ws, row_idx, 4, p2.authentication, center=True)
                self._set_cell(ws, row_idx, 5, p2.pfs, center=True)
                self._set_cell(ws, row_idx, 6, p2.lifetime, center=True)
                self._set_cell(ws, row_idx, 7, p2.local_subnet)
                self._set_cell(ws, row_idx, 8, p2.remote_subnet)
                row_idx += 1
            row_idx += 1

        if ssl_vpn:
            self._set_section_title(ws, row_idx, 1, "SSL-VPN / GlobalProtect", colspan=8)
            ssl_headers = [
                "レルム",
                "ポータル",
                "ポート",
                "IF",
                "認証",
                "IPプール",
                "ユーザーグループ",
                "モード",
            ]
            self._set_header_row(ws, ssl_headers, row_idx + 1)
            row_idx += 2
            for ssl in ssl_vpn:
                self._set_cell(ws, row_idx, 1, ssl.realm)
                self._set_cell(ws, row_idx, 2, ssl.portal)
                self._set_cell(ws, row_idx, 3, ssl.listen_port, center=True)
                self._set_cell(ws, row_idx, 4, ssl.listen_interface)
                self._set_cell(ws, row_idx, 5, ssl.auth_method, center=True)
                self._set_cell(ws, row_idx, 6, ssl.tunnel_ip_pool)
                self._set_cell(ws, row_idx, 7, self._list_to_str(ssl.user_groups, ", "))
                self._set_cell(ws, row_idx, 8, ssl.mode, center=True)
                row_idx += 1

        self._auto_column_width(ws)

    def _create_security_profiles_sheet_for_vdom(self, vdom: str):
        """指定VDOMのセキュリティプロファイルシートを作成"""
        profiles = self._filter_by_vdom(self.config.security_profiles, vdom)
        if not profiles:
            return

        ws = self._create_sheet("セキュリティ", vdom)
        headers = ["プロファイル名", "タイプ", "有効/無効", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, profile in enumerate(profiles, 2):
            self._set_cell(ws, row_idx, 1, profile.name)
            self._set_cell(ws, row_idx, 2, profile.profile_type, center=True)
            self._set_status_cell(ws, row_idx, 3, profile.enabled)
            self._set_cell(ws, row_idx, 4, profile.description)

        self._auto_column_width(ws)

    def _create_dhcp_sheet_for_vdom(self, vdom: str):
        """指定VDOMのDHCPサーバーシートを作成"""
        dhcp_servers = self._filter_by_vdom(self.config.dhcp_servers, vdom)
        if not dhcp_servers:
            return

        ws = self._create_sheet("DHCP", vdom)
        headers = [
            "インターフェース",
            "開始IP",
            "終了IP",
            "サブネットマスク",
            "除外IP",
            "ゲートウェイ",
            "DNSサーバー",
            "リース時間",
            "状態",
        ]
        self._set_header_row(ws, headers)

        for row_idx, dhcp in enumerate(dhcp_servers, 2):
            self._set_cell(ws, row_idx, 1, dhcp.interface)
            self._set_cell(ws, row_idx, 2, dhcp.start_ip)
            self._set_cell(ws, row_idx, 3, dhcp.end_ip)
            self._set_cell(ws, row_idx, 4, dhcp.netmask)
            self._set_cell(
                ws,
                row_idx,
                5,
                self._list_to_str(dhcp.exclude_ips, ", ") if dhcp.exclude_ips else "-",
            )
            self._set_cell(ws, row_idx, 6, dhcp.gateway or "-")
            self._set_cell(
                ws,
                row_idx,
                7,
                self._list_to_str(dhcp.dns_servers, ", ") if dhcp.dns_servers else "-",
            )
            self._set_cell(ws, row_idx, 8, dhcp.lease_time or "-")
            self._set_status_cell(ws, row_idx, 9, dhcp.status if hasattr(dhcp, "status") else True)

        self._auto_column_width(ws)
