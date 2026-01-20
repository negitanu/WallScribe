#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excelエクスポーター
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from models.config import (
    ConfigModel, PolicyAction, HAMode, DeviceType
)
from models.cluster import ClusterConfig, HARole

logger = logging.getLogger(__name__)


class ExcelExporter:
    """Excel形式でパラメータシートを出力"""

    # スタイル定義
    HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
    HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

    CELL_FONT = Font(size=9)
    CELL_ALIGNMENT = Alignment(vertical="top", wrap_text=True)

    THIN_BORDER = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # アクション色
    ACTION_FILLS = {
        PolicyAction.ALLOW: PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
        PolicyAction.DENY: PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
        PolicyAction.DROP: PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid"),
    }

    def __init__(self, config: Union[ConfigModel, ClusterConfig], sections: List[str] = None):
        """Excelエクスポーターを初期化

        Args:
            config: 設定データモデル（ConfigModelまたはClusterConfig）
            sections: 出力するセクションのリスト（Noneの場合は全セクション）
        """
        # ClusterConfigの場合、primary_configを使用
        if isinstance(config, ClusterConfig):
            self.cluster_config = config
            self.config = config.primary_config if config.primary_config else ConfigModel()
            self.is_cluster = config.is_cluster
        else:
            self.cluster_config = None
            self.config = config
            self.is_cluster = False

        self.sections = sections
        self.workbook = Workbook()
        # デフォルトシートを削除
        self.workbook.remove(self.workbook.active)

    def export(self, output_path: Optional[str] = None) -> Workbook:
        """Excelファイルを生成"""
        # クラスタ構成の場合、クラスタ概要シートを最初に作成
        if self.is_cluster:
            self._create_cluster_overview_sheet()

        self._create_overview_sheet()
        self._create_system_sheet()
        self._create_interfaces_sheet()
        self._create_routes_sheet()
        self._create_objects_sheet()
        self._create_policies_sheet()
        self._create_nat_sheet()
        self._create_vpn_sheet()
        self._create_security_profiles_sheet()
        self._create_ha_sheet()
        self._create_logging_sheet()

        if output_path:
            self.workbook.save(output_path)
            logger.info(f"Excelファイル出力完了: {output_path}")

        return self.workbook

    def _create_sheet(self, title: str) -> Worksheet:
        """シートを作成"""
        # シート名は31文字まで
        sheet_title = title[:31]
        ws = self.workbook.create_sheet(title=sheet_title)
        return ws

    def _set_header_row(self, ws: Worksheet, headers: List[str], row: int = 1):
        """ヘッダー行を設定"""
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = self.HEADER_ALIGNMENT
            cell.border = self.THIN_BORDER

    def _set_cell(self, ws: Worksheet, row: int, col: int, value: Any,
                  fill: PatternFill = None):
        """セルに値を設定"""
        cell = ws.cell(row=row, column=col, value=str(value) if value else "")
        cell.font = self.CELL_FONT
        cell.alignment = self.CELL_ALIGNMENT
        cell.border = self.THIN_BORDER
        if fill:
            cell.fill = fill
        return cell

    def _auto_column_width(self, ws: Worksheet, min_width: int = 8, max_width: int = 50):
        """列幅を自動調整"""
        from openpyxl.cell.cell import MergedCell
        
        for column_cells in ws.columns:
            max_length = 0
            # マージされていない最初のセルを見つける
            column_letter = None
            for cell in column_cells:
                if not isinstance(cell, MergedCell):
                    column_letter = cell.column_letter
                    break
            
            if column_letter is None:
                continue
                
            for cell in column_cells:
                # MergedCellはスキップ
                if isinstance(cell, MergedCell):
                    continue
                try:
                    if cell.value:
                        # 日本語文字は2文字分としてカウント
                        cell_length = sum(2 if ord(c) > 127 else 1 for c in str(cell.value))
                        max_length = max(max_length, cell_length)
                except:
                    pass
            adjusted_width = min(max(max_length + 2, min_width), max_width)
            ws.column_dimensions[column_letter].width = adjusted_width

    def _list_to_str(self, items: List[Any], separator: str = "\n") -> str:
        """リストを文字列に変換"""
        if not items:
            return "-"
        return separator.join(str(item) for item in items)

    def _create_cluster_overview_sheet(self):
        """クラスタ概要シートを作成（HAクラスタ時のみ）"""
        if not self.is_cluster or self.cluster_config is None:
            return

        ws = self._create_sheet("クラスタ概要")
        cluster_info = self.cluster_config.cluster_info

        # タイトル
        ws.merge_cells('A1:B1')
        title_cell = ws.cell(row=1, column=1, value="HAクラスタ概要")
        title_cell.font = Font(bold=True, size=14)

        # クラスタ情報
        data = [
            ("クラスタ名", cluster_info.cluster_name),
            ("グループID", cluster_info.group_id),
            ("HAモード", cluster_info.ha_mode.value),
            ("メンバー数", cluster_info.get_member_count()),
        ]

        for row_idx, (label, value) in enumerate(data, 3):
            ws.cell(row=row_idx, column=1, value=label).font = Font(bold=True)
            ws.cell(row=row_idx, column=2, value=value)

        # クラスタメンバー一覧
        member_start = len(data) + 5
        ws.cell(row=member_start, column=1, value="クラスタメンバー").font = Font(bold=True, size=12)

        member_headers = ["役割", "ホスト名", "優先度", "シリアル番号", "設定ファイル"]
        self._set_header_row(ws, member_headers, member_start + 1)

        for row_idx, member in enumerate(cluster_info.members, member_start + 2):
            self._set_cell(ws, row_idx, 1, member.role.value)
            self._set_cell(ws, row_idx, 2, member.hostname)
            self._set_cell(ws, row_idx, 3, member.priority)
            self._set_cell(ws, row_idx, 4, member.serial_number or "-")
            self._set_cell(ws, row_idx, 5, Path(member.source_file).name if member.source_file else "-")

        # 設定差分
        differences = self.cluster_config.config_differences
        if differences:
            diff_start = member_start + len(cluster_info.members) + 4
            ws.cell(row=diff_start, column=1, value="設定差分").font = Font(bold=True, size=12)

            diff_headers = ["セクション", "項目", "Primary", "Secondary", "備考"]
            self._set_header_row(ws, diff_headers, diff_start + 1)

            for row_idx, diff in enumerate(differences, diff_start + 2):
                self._set_cell(ws, row_idx, 1, diff.section)
                self._set_cell(ws, row_idx, 2, diff.item)
                self._set_cell(ws, row_idx, 3, diff.primary_value)
                self._set_cell(ws, row_idx, 4, diff.secondary_value)
                self._set_cell(ws, row_idx, 5, diff.description)

        self._auto_column_width(ws)

    def _create_overview_sheet(self):
        """機器概要シートを作成"""
        ws = self._create_sheet("機器概要")
        info = self.config.device_info
        today = datetime.now().strftime('%Y年%m月%d日')

        # タイトル
        ws.merge_cells('A1:B1')
        title_cell = ws.cell(row=1, column=1, value=f"{info.device_type.value} パラメータシート")
        title_cell.font = Font(bold=True, size=14)

        # 基本情報
        data = [
            ("作成日", today),
            ("ソースファイル", Path(self.config.source_file).name),
            ("", ""),
            ("ホスト名", info.hostname),
            ("モデル", info.model),
            ("シリアル番号", info.serial_number or "設定ファイルから取得不可"),
            ("OSバージョン", info.os_version),
            ("動作モード", info.operation_mode.value),
            ("VDOM/vsys", "有効" if info.vdom_enabled else "無効"),
            ("VDOM/vsysリスト", ", ".join(info.vdom_list) if info.vdom_list else "-"),
            ("", ""),
            ("インターフェース数", len(self.config.interfaces)),
            ("ルート数", len(self.config.routes)),
            ("ポリシー数", len(self.config.firewall_policies)),
            ("オブジェクト数", len(self.config.objects.addresses) + len(self.config.objects.services)),
            ("NAT数", len(self.config.nat_policies)),
        ]

        for row_idx, (label, value) in enumerate(data, 3):
            ws.cell(row=row_idx, column=1, value=label).font = Font(bold=True)
            ws.cell(row=row_idx, column=2, value=value)

        self._auto_column_width(ws)

    def _create_system_sheet(self):
        """システム設定シートを作成"""
        ws = self._create_sheet("システム設定")
        settings = self.config.system_settings

        # 管理設定
        ws.cell(row=1, column=1, value="管理アクセス設定").font = Font(bold=True, size=12)
        data = [
            ("管理用IPアドレス", settings.management_ip),
            ("サブネットマスク", settings.management_netmask),
            ("管理インターフェース", settings.management_interface),
            ("HTTPSポート", settings.https_port or "443"),
            ("SSHポート", settings.ssh_port or "22"),
            ("許可プロトコル", self._list_to_str(settings.allowed_protocols, ", ")),
        ]

        for row_idx, (label, value) in enumerate(data, 2):
            ws.cell(row=row_idx, column=1, value=label).font = Font(bold=True)
            ws.cell(row=row_idx, column=2, value=value)

        # DNS/NTP設定
        start_row = len(data) + 4
        ws.cell(row=start_row, column=1, value="DNS/NTP設定").font = Font(bold=True, size=12)
        dns_data = [
            ("プライマリDNS", settings.dns_primary or "-"),
            ("セカンダリDNS", settings.dns_secondary or "-"),
            ("NTPサーバー", self._list_to_str(settings.ntp_servers, ", ") or "-"),
            ("タイムゾーン", settings.timezone or "-"),
        ]

        for row_idx, (label, value) in enumerate(dns_data, start_row + 1):
            ws.cell(row=row_idx, column=1, value=label).font = Font(bold=True)
            ws.cell(row=row_idx, column=2, value=value)

        # 管理者アカウント
        admin_start = start_row + len(dns_data) + 3
        ws.cell(row=admin_start, column=1, value="管理者アカウント").font = Font(bold=True, size=12)

        if settings.admin_users:
            headers = ["ユーザー名", "権限プロファイル", "VDOM", "信頼ホスト"]
            self._set_header_row(ws, headers, admin_start + 1)

            for row_idx, admin in enumerate(settings.admin_users, admin_start + 2):
                self._set_cell(ws, row_idx, 1, admin.username)
                self._set_cell(ws, row_idx, 2, admin.profile)
                self._set_cell(ws, row_idx, 3, admin.vdom)
                self._set_cell(ws, row_idx, 4, self._list_to_str(admin.trust_hosts, ", "))

        self._auto_column_width(ws)

    def _create_interfaces_sheet(self):
        """インターフェースシートを作成"""
        ws = self._create_sheet("インターフェース")

        headers = ["インターフェース名", "タイプ", "役割", "IPアドレス", "VLAN ID",
                   "ゾーン", "VDOM/vsys", "許可アクセス", "状態", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, iface in enumerate(self.config.interfaces, 2):
            self._set_cell(ws, row_idx, 1, iface.name)
            self._set_cell(ws, row_idx, 2, iface.interface_type)
            self._set_cell(ws, row_idx, 3, iface.role)
            self._set_cell(ws, row_idx, 4, iface.ip_address)
            self._set_cell(ws, row_idx, 5, iface.vlan_id)
            self._set_cell(ws, row_idx, 6, iface.zone)
            self._set_cell(ws, row_idx, 7, iface.vdom)
            self._set_cell(ws, row_idx, 8, self._list_to_str(iface.allowed_access, ", "))
            self._set_cell(ws, row_idx, 9, iface.status)
            self._set_cell(ws, row_idx, 10, iface.description)

        self._auto_column_width(ws)

    def _create_routes_sheet(self):
        """ルーティングシートを作成"""
        ws = self._create_sheet("ルーティング")

        headers = ["ルート名", "宛先ネットワーク", "ゲートウェイ", "インターフェース",
                   "ディスタンス", "タイプ", "VDOM/vsys"]
        self._set_header_row(ws, headers)

        for row_idx, route in enumerate(self.config.routes, 2):
            gateway_display = route.gateway
            # blackhole/discard ルートはゲートウェイが空になるため、明示して記載する
            if not gateway_display and getattr(route, "route_type", "") in ("blackhole", "blackhole6"):
                gateway_display = "blackhole"

            self._set_cell(ws, row_idx, 1, route.name)
            self._set_cell(ws, row_idx, 2, route.destination)
            self._set_cell(ws, row_idx, 3, gateway_display)
            self._set_cell(ws, row_idx, 4, route.interface or "-")
            self._set_cell(ws, row_idx, 5, route.distance)
            self._set_cell(ws, row_idx, 6, route.route_type)
            self._set_cell(ws, row_idx, 7, route.vdom)

        self._auto_column_width(ws)

    def _create_objects_sheet(self):
        """オブジェクト定義シートを作成"""
        ws = self._create_sheet("オブジェクト")

        # アドレスオブジェクト
        ws.cell(row=1, column=1, value="アドレスオブジェクト").font = Font(bold=True, size=12)
        addr_headers = ["オブジェクト名", "タイプ", "値", "VDOM/vsys", "説明"]
        self._set_header_row(ws, addr_headers, 2)

        row_idx = 3
        for addr in self.config.objects.addresses:
            self._set_cell(ws, row_idx, 1, addr.name)
            self._set_cell(ws, row_idx, 2, addr.object_type)
            self._set_cell(ws, row_idx, 3, addr.value)
            self._set_cell(ws, row_idx, 4, addr.vdom)
            self._set_cell(ws, row_idx, 5, addr.description)
            row_idx += 1

        # アドレスグループ
        row_idx += 2
        ws.cell(row=row_idx, column=1, value="アドレスグループ").font = Font(bold=True, size=12)
        grp_headers = ["グループ名", "メンバー", "VDOM/vsys", "説明"]
        self._set_header_row(ws, grp_headers, row_idx + 1)
        row_idx += 2

        for grp in self.config.objects.address_groups:
            self._set_cell(ws, row_idx, 1, grp.name)
            self._set_cell(ws, row_idx, 2, self._list_to_str(grp.members, ", "))
            self._set_cell(ws, row_idx, 3, grp.vdom)
            self._set_cell(ws, row_idx, 4, grp.description)
            row_idx += 1

        # サービスオブジェクト
        row_idx += 2
        ws.cell(row=row_idx, column=1, value="サービスオブジェクト").font = Font(bold=True, size=12)
        svc_headers = ["オブジェクト名", "プロトコル", "ポート", "VDOM/vsys", "説明"]
        self._set_header_row(ws, svc_headers, row_idx + 1)
        row_idx += 2

        for svc in self.config.objects.services:
            self._set_cell(ws, row_idx, 1, svc.name)
            self._set_cell(ws, row_idx, 2, svc.protocol)
            self._set_cell(ws, row_idx, 3, svc.port)
            self._set_cell(ws, row_idx, 4, svc.vdom)
            self._set_cell(ws, row_idx, 5, svc.description)
            row_idx += 1

        # サービスグループ
        row_idx += 2
        ws.cell(row=row_idx, column=1, value="サービスグループ").font = Font(bold=True, size=12)
        sgrp_headers = ["グループ名", "メンバー", "VDOM/vsys", "説明"]
        self._set_header_row(ws, sgrp_headers, row_idx + 1)
        row_idx += 2

        for grp in self.config.objects.service_groups:
            self._set_cell(ws, row_idx, 1, grp.name)
            self._set_cell(ws, row_idx, 2, self._list_to_str(grp.members, ", "))
            self._set_cell(ws, row_idx, 3, grp.vdom)
            self._set_cell(ws, row_idx, 4, grp.description)
            row_idx += 1

        self._auto_column_width(ws)

    def _create_policies_sheet(self):
        """ファイアウォールポリシーシートを作成"""
        ws = self._create_sheet("ファイアウォールポリシー")

        headers = ["No", "ID", "ポリシー名", "送信元IF", "宛先IF", "送信元アドレス",
                   "宛先アドレス", "サービス", "アクション", "NAT", "ログ",
                   "セキュリティプロファイル", "VDOM/vsys", "有効", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, (idx, policy) in enumerate(enumerate(self.config.firewall_policies, 1), 2):
            action_fill = self.ACTION_FILLS.get(policy.action)

            self._set_cell(ws, row_idx, 1, idx)
            self._set_cell(ws, row_idx, 2, policy.policy_id)
            self._set_cell(ws, row_idx, 3, policy.name)
            self._set_cell(ws, row_idx, 4, self._list_to_str(policy.source_interface))
            self._set_cell(ws, row_idx, 5, self._list_to_str(policy.destination_interface))
            self._set_cell(ws, row_idx, 6, self._list_to_str(policy.source_address))
            self._set_cell(ws, row_idx, 7, self._list_to_str(policy.destination_address))
            self._set_cell(ws, row_idx, 8, self._list_to_str(policy.service))
            self._set_cell(ws, row_idx, 9, policy.action.value, fill=action_fill)
            self._set_cell(ws, row_idx, 10, "有効" if policy.nat_enabled else "無効")
            self._set_cell(ws, row_idx, 11, "有効" if policy.log_enabled else "無効")
            self._set_cell(ws, row_idx, 12, self._list_to_str(policy.security_profiles))
            self._set_cell(ws, row_idx, 13, policy.vdom)
            self._set_cell(ws, row_idx, 14, "有効" if policy.enabled else "無効")
            self._set_cell(ws, row_idx, 15, policy.description)

        self._auto_column_width(ws)

        # Local-in ポリシー（別シート）
        if self.config.local_in_policies:
            self._create_local_in_policies_sheet()

    def _create_local_in_policies_sheet(self):
        """Local-in ポリシーシートを作成"""
        ws = self._create_sheet("Local-in ポリシー")

        headers = ["No", "ID", "ポリシー名", "送信元IF", "送信元アドレス",
                   "宛先アドレス", "サービス", "アクション", "VDOM/vsys", "有効", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, (idx, policy) in enumerate(enumerate(self.config.local_in_policies, 1), 2):
            action_fill = self.ACTION_FILLS.get(policy.action)

            # source_interfaceが文字列の場合とリストの場合に対応
            src_if = policy.source_interface
            if isinstance(src_if, list):
                src_if_str = self._list_to_str(src_if)
            else:
                src_if_str = src_if or "-"

            self._set_cell(ws, row_idx, 1, idx)
            self._set_cell(ws, row_idx, 2, policy.policy_id)
            self._set_cell(ws, row_idx, 3, policy.name)
            self._set_cell(ws, row_idx, 4, src_if_str)
            self._set_cell(ws, row_idx, 5, self._list_to_str(policy.source_address))
            self._set_cell(ws, row_idx, 6, self._list_to_str(policy.destination_address))
            self._set_cell(ws, row_idx, 7, self._list_to_str(policy.service))
            self._set_cell(ws, row_idx, 8, policy.action.value, fill=action_fill)
            self._set_cell(ws, row_idx, 9, policy.vdom)
            self._set_cell(ws, row_idx, 10, "有効" if policy.enabled else "無効")
            self._set_cell(ws, row_idx, 11, policy.description)

        self._auto_column_width(ws)

    def _create_nat_sheet(self):
        """NAT設定シートを作成"""
        ws = self._create_sheet("NAT設定")

        headers = ["ルール名", "タイプ", "元送信元", "元宛先", "変換後送信元",
                   "変換後宛先", "外部IF", "外部IP", "内部IP", "ポートフォワード",
                   "元ポート", "変換後ポート", "VDOM/vsys", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, nat in enumerate(self.config.nat_policies, 2):
            self._set_cell(ws, row_idx, 1, nat.name)
            self._set_cell(ws, row_idx, 2, nat.nat_type)
            self._set_cell(ws, row_idx, 3, nat.original_source)
            self._set_cell(ws, row_idx, 4, nat.original_destination)
            self._set_cell(ws, row_idx, 5, nat.translated_source)
            self._set_cell(ws, row_idx, 6, nat.translated_destination)
            self._set_cell(ws, row_idx, 7, nat.external_interface)
            self._set_cell(ws, row_idx, 8, nat.external_ip)
            self._set_cell(ws, row_idx, 9, nat.internal_ip)
            self._set_cell(ws, row_idx, 10, "有効" if nat.port_forward else "無効")
            self._set_cell(ws, row_idx, 11, nat.original_port)
            self._set_cell(ws, row_idx, 12, nat.translated_port)
            self._set_cell(ws, row_idx, 13, nat.vdom)
            self._set_cell(ws, row_idx, 14, nat.description)

        self._auto_column_width(ws)

    def _create_vpn_sheet(self):
        """VPN設定シートを作成"""
        ws = self._create_sheet("VPN設定")

        # IPsec Phase1
        ws.cell(row=1, column=1, value="IPsec Phase1").font = Font(bold=True, size=12)
        p1_headers = ["VPN名", "リモートGW", "インターフェース", "IKEバージョン",
                      "暗号化", "認証", "DHグループ", "ライフタイム", "PSK"]
        self._set_header_row(ws, p1_headers, 2)

        row_idx = 3
        for p1 in self.config.vpn.ipsec_phase1:
            self._set_cell(ws, row_idx, 1, p1.name)
            self._set_cell(ws, row_idx, 2, p1.remote_gateway)
            self._set_cell(ws, row_idx, 3, p1.interface)
            self._set_cell(ws, row_idx, 4, p1.ike_version)
            self._set_cell(ws, row_idx, 5, p1.encryption)
            self._set_cell(ws, row_idx, 6, p1.authentication)
            self._set_cell(ws, row_idx, 7, p1.dh_group)
            self._set_cell(ws, row_idx, 8, p1.lifetime)
            self._set_cell(ws, row_idx, 9, "有" if p1.psk else "無")
            row_idx += 1

        # IPsec Phase2
        row_idx += 2
        ws.cell(row=row_idx, column=1, value="IPsec Phase2").font = Font(bold=True, size=12)
        p2_headers = ["VPN名", "Phase1名", "暗号化", "認証", "PFS",
                      "ライフタイム", "ローカルセグメント", "リモートセグメント"]
        self._set_header_row(ws, p2_headers, row_idx + 1)
        row_idx += 2

        for p2 in self.config.vpn.ipsec_phase2:
            self._set_cell(ws, row_idx, 1, p2.name)
            self._set_cell(ws, row_idx, 2, p2.phase1_name)
            self._set_cell(ws, row_idx, 3, p2.encryption)
            self._set_cell(ws, row_idx, 4, p2.authentication)
            self._set_cell(ws, row_idx, 5, p2.pfs)
            self._set_cell(ws, row_idx, 6, p2.lifetime)
            self._set_cell(ws, row_idx, 7, p2.local_subnet)
            self._set_cell(ws, row_idx, 8, p2.remote_subnet)
            row_idx += 1

        # SSL-VPN
        row_idx += 2
        ws.cell(row=row_idx, column=1, value="SSL-VPN / GlobalProtect").font = Font(bold=True, size=12)
        ssl_headers = ["レルム", "ポータル", "ポート", "インターフェース",
                       "認証方式", "IPプール", "ユーザーグループ", "モード", "VDOM/vsys"]
        self._set_header_row(ws, ssl_headers, row_idx + 1)
        row_idx += 2

        for ssl in self.config.vpn.ssl_vpn:
            self._set_cell(ws, row_idx, 1, ssl.realm)
            self._set_cell(ws, row_idx, 2, ssl.portal)
            self._set_cell(ws, row_idx, 3, ssl.listen_port)
            self._set_cell(ws, row_idx, 4, ssl.listen_interface)
            self._set_cell(ws, row_idx, 5, ssl.auth_method)
            self._set_cell(ws, row_idx, 6, ssl.tunnel_ip_pool)
            self._set_cell(ws, row_idx, 7, self._list_to_str(ssl.user_groups, ", "))
            self._set_cell(ws, row_idx, 8, ssl.mode)
            self._set_cell(ws, row_idx, 9, ssl.vdom)
            row_idx += 1

        self._auto_column_width(ws)

    def _create_security_profiles_sheet(self):
        """セキュリティプロファイルシートを作成"""
        ws = self._create_sheet("セキュリティプロファイル")

        headers = ["プロファイル名", "タイプ", "有効/無効", "VDOM/vsys", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, profile in enumerate(self.config.security_profiles, 2):
            self._set_cell(ws, row_idx, 1, profile.name)
            self._set_cell(ws, row_idx, 2, profile.profile_type)
            self._set_cell(ws, row_idx, 3, "有効" if profile.enabled else "無効")
            self._set_cell(ws, row_idx, 4, profile.vdom)
            self._set_cell(ws, row_idx, 5, profile.description)

        self._auto_column_width(ws)

    def _create_ha_sheet(self):
        """HA設定シートを作成"""
        ws = self._create_sheet("HA設定")
        ha = self.config.ha

        if ha.mode == HAMode.STANDALONE:
            ws.cell(row=1, column=1, value="HA設定なし（スタンドアロン）")
            return

        # HA基本設定
        ws.cell(row=1, column=1, value="HA基本設定").font = Font(bold=True, size=12)
        data = [
            ("HAモード", ha.mode.value),
            ("グループID", ha.group_id),
            ("グループ名", ha.group_name or "-"),
            ("優先度", ha.priority),
            ("プリエンプト", "有効" if ha.preempt else "無効"),
            ("", ""),
            ("セッション同期", "有効" if ha.session_sync else "無効"),
            ("セッションピックアップ", "有効" if ha.session_pickup else "無効"),
            ("ハートビート間隔", ha.hb_interval if ha.hb_interval else "-"),
            ("ハートビート損失閾値", ha.hb_lost_threshold if ha.hb_lost_threshold else "-"),
            ("", ""),
            ("暗号化", "有効" if ha.encryption else "無効"),
            ("認証", "有効" if ha.authentication else "無効"),
            ("", ""),
            ("監視インターフェース", self._list_to_str(ha.monitor_interfaces, ", ")),
            ("HAインターフェース", self._list_to_str(ha.ha_interfaces, ", ")),
        ]

        for row_idx, (label, value) in enumerate(data, 2):
            ws.cell(row=row_idx, column=1, value=label).font = Font(bold=True)
            ws.cell(row=row_idx, column=2, value=value)

        # ハートビートインターフェース詳細
        row_idx = len(data) + 4
        if ha.heartbeat_interfaces_detail:
            ws.cell(row=row_idx, column=1, value="ハートビートインターフェース").font = Font(bold=True, size=12)
            hb_headers = ["インターフェース", "優先度"]
            self._set_header_row(ws, hb_headers, row_idx + 1)
            row_idx += 2

            for hb in ha.heartbeat_interfaces_detail:
                self._set_cell(ws, row_idx, 1, hb.interface)
                self._set_cell(ws, row_idx, 2, hb.priority if hb.priority else "-")
                row_idx += 1
        elif ha.heartbeat_interfaces:
            ws.cell(row=row_idx, column=1, value="ハートビートインターフェース").font = Font(bold=True, size=12)
            row_idx += 1
            ws.cell(row=row_idx, column=1, value=self._list_to_str(ha.heartbeat_interfaces, ", "))
            row_idx += 1

        # HA管理インターフェース
        if ha.ha_mgmt_interfaces:
            row_idx += 2
            ws.cell(row=row_idx, column=1, value="HA管理インターフェース").font = Font(bold=True, size=12)
            mgmt_headers = ["ID", "インターフェース", "ゲートウェイ"]
            self._set_header_row(ws, mgmt_headers, row_idx + 1)
            row_idx += 2

            for mgmt in ha.ha_mgmt_interfaces:
                self._set_cell(ws, row_idx, 1, mgmt.id)
                self._set_cell(ws, row_idx, 2, mgmt.interface)
                self._set_cell(ws, row_idx, 3, mgmt.gateway)
                row_idx += 1

        self._auto_column_width(ws)

    def _create_logging_sheet(self):
        """ログ・監視設定シートを作成"""
        ws = self._create_sheet("ログ・監視設定")
        logging_config = self.config.logging

        # Syslog
        ws.cell(row=1, column=1, value="Syslogサーバー").font = Font(bold=True, size=12)
        syslog_headers = ["サーバー", "ポート", "ファシリティ", "状態", "ログ種別", "VDOM/vsys"]
        self._set_header_row(ws, syslog_headers, 2)

        row_idx = 3
        for syslog in logging_config.syslog_servers:
            self._set_cell(ws, row_idx, 1, syslog.server)
            self._set_cell(ws, row_idx, 2, syslog.port)
            self._set_cell(ws, row_idx, 3, syslog.facility)
            self._set_cell(ws, row_idx, 4, syslog.status)
            self._set_cell(ws, row_idx, 5, self._list_to_str(syslog.log_types, ", "))
            self._set_cell(ws, row_idx, 6, syslog.vdom)
            row_idx += 1

        # SNMP
        row_idx += 2
        ws.cell(row=row_idx, column=1, value="SNMP設定").font = Font(bold=True, size=12)
        snmp_headers = ["有効", "バージョン", "コミュニティ/ユーザー", "ホスト", "トラップ送信先"]
        self._set_header_row(ws, snmp_headers, row_idx + 1)
        row_idx += 2

        for snmp in logging_config.snmp:
            self._set_cell(ws, row_idx, 1, "有効" if snmp.enabled else "無効")
            self._set_cell(ws, row_idx, 2, snmp.version)
            self._set_cell(ws, row_idx, 3, snmp.community or snmp.username)
            self._set_cell(ws, row_idx, 4, self._list_to_str(snmp.hosts, ", "))
            self._set_cell(ws, row_idx, 5, self._list_to_str(snmp.trap_hosts, ", "))
            row_idx += 1

        # 集中管理
        row_idx += 2
        ws.cell(row=row_idx, column=1, value="集中管理").font = Font(bold=True, size=12)
        row_idx += 1

        if logging_config.fortianalyzer_server:
            ws.cell(row=row_idx, column=1, value="FortiAnalyzer").font = Font(bold=True)
            ws.cell(row=row_idx, column=2, value=logging_config.fortianalyzer_server)
            row_idx += 1
            ws.cell(row=row_idx, column=1, value="状態").font = Font(bold=True)
            ws.cell(row=row_idx, column=2, value=logging_config.fortianalyzer_status)

        if logging_config.panorama_server:
            ws.cell(row=row_idx, column=1, value="Panorama").font = Font(bold=True)
            ws.cell(row=row_idx, column=2, value=logging_config.panorama_server)

        self._auto_column_width(ws)
