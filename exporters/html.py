#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTMLエクスポーター
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from models.config import (
    ConfigModel, PolicyAction, HAMode, DeviceType, FirewallPolicy
)
from models.cluster import ClusterConfig, HARole
from exporters.utils import (
    STATIC_DIR, load_isdb, load_css, load_css_for_pdf, load_search_js, load_tooltip_js, HtmlFormatter
)

logger = logging.getLogger(__name__)


class HTMLExporter:
    """HTML形式でパラメータシートを出力（VDOM/vsys単位）"""

    # グローバルセクション定義（VDOM横断の設定）
    GLOBAL_SECTIONS = [
        ('cluster_overview', 'クラスタ概要', '_generate_cluster_overview_section'),
        ('device_info', '機器概要', '_generate_device_info_section'),
        ('system_settings', 'システム設定', '_generate_system_settings_section'),
        ('ha', 'HA設定', '_generate_ha_section'),
        ('logging', 'ログ・監視設定', '_generate_logging_section'),
    ]

    # VDOM単位セクション定義
    VDOM_SECTIONS = [
        ('network', 'ネットワーク設定', '_generate_network_section'),
        ('objects', 'オブジェクト定義', '_generate_objects_section'),
        ('policies', 'ファイアウォールポリシー', '_generate_policies_section'),
        ('nat', 'NAT設定', '_generate_nat_section'),
        ('vpn', 'VPN設定', '_generate_vpn_section'),
        ('security_profiles', 'セキュリティプロファイル', '_generate_security_profiles_section'),
    ]

    def __init__(self, config: Union[ConfigModel, ClusterConfig], sections: List[str] = None, for_pdf: bool = False):
        """HTMLエクスポーターを初期化

        Args:
            config: 設定データモデル（ConfigModelまたはClusterConfig）
            sections: 出力するセクションのリスト（Noneの場合は全セクション）
            for_pdf: PDF用に最適化する場合True（JavaScript削除など）
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

        # セクション指定は現在未使用（将来の拡張用に保持）
        self.sections = sections
        self.for_pdf = for_pdf
        # ISDBデータをキャッシュ（ループ内での関数呼び出し削減）
        self._isdb_cache = load_isdb()
        # ツールチップ生成キャッシュ（同じオブジェクトの重複生成を防止）
        self._tooltip_cache: Dict[tuple, str] = {}
        # オブジェクト辞書を構築（ツールチップ用）
        self._build_object_lookups()

    # FortiGateデフォルト値
    DEFAULTS = {
        'timezone': '(GMT+0:00) UTC',
        'ntp_servers': 'FortiGuard NTP',
        'ntp_sync_interval': '60分',
        'dns_primary': 'FortiGuard DNS',
        'dns_secondary': '-',
        'https_port': '443',
        'ssh_port': '22',
        'idle_timeout': '5分',
        'auth_timeout': '5分',
        'ha_hb_interval': '200ms',
        'ha_hb_lost_threshold': '6',
        'dhcp_lease_time': '604800秒 (7日)',
        'dhcp_dns': 'システムDNS設定',
    }

    # フォーマッター（委譲）
    escape = staticmethod(HtmlFormatter.escape)
    _list_to_str = staticmethod(HtmlFormatter.list_to_str)
    _list_to_lines = staticmethod(HtmlFormatter.list_to_lines)

    def _with_default(self, value: Optional[str], default_key: str) -> str:
        """値が空の場合はデフォルト値を表示（グレー表示）"""
        default = self.DEFAULTS.get(default_key, '-')
        return HtmlFormatter.with_default(value, default)

    def _list_with_default(self, items: List[Any], default_key: str) -> str:
        """リストが空の場合はデフォルト値を表示"""
        default = self.DEFAULTS.get(default_key, '-')
        return HtmlFormatter.list_with_default(items, default)

    def _resolve_isdb_name(self, isdb_id: str) -> str:
        """ISDB IDからアプリケーション名を解決"""
        # IDをそのまま検索（キャッシュ使用）
        if isdb_id in self._isdb_cache:
            return self._isdb_cache[isdb_id]
        # 数字のみの場合もそのまま検索
        id_str = str(isdb_id).strip()
        if id_str in self._isdb_cache:
            return self._isdb_cache[id_str]
        # 見つからない場合は元の値を返す
        return isdb_id

    def _resolve_isdb_names(self, items: List[str]) -> List[str]:
        """リスト内のISDB IDをアプリケーション名に解決"""
        return [self._resolve_isdb_name(item) for item in items]

    # バッジ色マッピング
    SECURITY_PROFILE_COLORS = {
        "av": "danger", "antivirus": "danger",
        "ips": "warning",
        "ssl": "info", "ssl-ssh-profile": "info",
        "webfilter": "primary", "web-filter": "primary",
        "application": "success", "app-ctrl": "success",
        "dlp": "secondary",
        "emailfilter": "dark",
        "dns": "light", "dnsfilter": "light",
    }

    SERVICE_COLORS = {
        "all": "danger",
        "http": "primary", "https": "primary", "web access": "primary",
        "ssh": "dark", "telnet": "dark", "rdp": "dark", "vnc": "dark",
        "dns": "info", "ntp": "info", "snmp": "info", "syslog": "info", "icmp": "info", "ping": "info",
        "smtp": "warning", "smtps": "warning", "pop3": "warning", "pop3s": "warning", "imap": "warning", "imaps": "warning",
        "ftp": "success", "tftp": "success", "smb": "success", "nfs": "success",
    }

    def _security_profiles_to_badges(self, profiles: List[str]) -> str:
        """セキュリティプロファイルをBootstrapバッジで表示"""
        return HtmlFormatter.to_badges(profiles, self.SECURITY_PROFILE_COLORS, extract_key=True)

    def _services_to_badges(self, services: List[str]) -> str:
        """サービスをBootstrapバッジで表示"""
        return HtmlFormatter.to_badges(services, self.SERVICE_COLORS)

    def _get_vdom_list(self) -> List[str]:
        """出力対象のVDOM/vsysリストを取得"""
        if self.config.device_info.vdom_list:
            return self.config.device_info.vdom_list
        return ["root"]  # デフォルト

    def _filter_by_vdom(self, items: List[Any], vdom: str) -> List[Any]:
        """指定VDOMの項目のみをフィルタリング"""
        return [item for item in items if getattr(item, 'vdom', 'root') == vdom]

    def _build_object_lookups(self) -> None:
        """オブジェクト名から詳細情報を引くための辞書を構築"""
        # アドレスオブジェクト辞書: {(vdom, name): AddressObject}
        self._address_lookup: Dict[tuple, Any] = {}
        for addr in self.config.objects.addresses:
            key = (addr.vdom, addr.name)
            self._address_lookup[key] = addr

        # アドレスグループ辞書: {(vdom, name): AddressGroup}
        self._address_group_lookup: Dict[tuple, Any] = {}
        for addr_grp in self.config.objects.address_groups:
            key = (addr_grp.vdom, addr_grp.name)
            self._address_group_lookup[key] = addr_grp

        # サービスオブジェクト辞書: {(vdom, name): ServiceObject}
        self._service_lookup: Dict[tuple, Any] = {}
        for svc in self.config.objects.services:
            key = (svc.vdom, svc.name)
            self._service_lookup[key] = svc

        # サービスグループ辞書: {(vdom, name): ServiceGroup}
        self._service_group_lookup: Dict[tuple, Any] = {}
        for svc_grp in self.config.objects.service_groups:
            key = (svc_grp.vdom, svc_grp.name)
            self._service_group_lookup[key] = svc_grp

        # インターフェース辞書: {(vdom, name): Interface}
        self._interface_lookup: Dict[tuple, Any] = {}
        for iface in self.config.interfaces:
            key = (iface.vdom, iface.name)
            self._interface_lookup[key] = iface

        # セキュリティプロファイル辞書を構築
        self._security_profile_lookup: Dict[tuple, Any] = {}
        detail = self.config.security_profiles_detail

        # アンチウイルス
        for av in detail.antivirus:
            self._security_profile_lookup[(av.vdom, "av", av.name)] = av
            self._security_profile_lookup[(av.vdom, "antivirus", av.name)] = av

        # Webフィルタ
        for wf in detail.webfilter:
            self._security_profile_lookup[(wf.vdom, "webfilter", wf.name)] = wf
            self._security_profile_lookup[(wf.vdom, "web-filter", wf.name)] = wf

        # アプリケーションコントロール
        for app_ctrl in detail.app_control:
            self._security_profile_lookup[(app_ctrl.vdom, "application", app_ctrl.name)] = app_ctrl
            self._security_profile_lookup[(app_ctrl.vdom, "app-ctrl", app_ctrl.name)] = app_ctrl

        # IPS
        for ips in detail.ips:
            self._security_profile_lookup[(ips.vdom, "ips", ips.name)] = ips

        # SSLインスペクション
        for ssl in detail.ssl_inspection:
            self._security_profile_lookup[(ssl.vdom, "ssl", ssl.name)] = ssl
            self._security_profile_lookup[(ssl.vdom, "ssl-ssh-profile", ssl.name)] = ssl

    def _format_tooltip_table(self, rows: List[tuple]) -> str:
        """ツールチップ用の表形式HTMLを生成
        
        Args:
            rows: (項目, 値)のタプルのリスト。最初の行はヘッダーとして扱われる
        
        Returns:
            表形式のHTML文字列
        """
        if not rows or len(rows) < 2:
            return ""
        
        html = ['<table class="tooltip-table">']
        # ヘッダー行
        html.append('<thead><tr>')
        html.append(f'<th>{self.escape(rows[0][0])}</th>')
        html.append(f'<th>{self.escape(rows[0][1])}</th>')
        html.append('</tr></thead>')
        # データ行
        html.append('<tbody>')
        for key, value in rows[1:]:
            html.append('<tr>')
            html.append(f'<td class="tooltip-key">{self.escape(str(key))}</td>')
            html.append(f'<td class="tooltip-value">{self.escape(str(value))}</td>')
            html.append('</tr>')
        html.append('</tbody>')
        html.append('</table>')
        return ''.join(html)

    def _get_interface_tooltip(self, name: str, vdom: str = "root") -> str:
        """インターフェース名からツールチップ用の詳細情報を取得（表形式）"""
        # キャッシュチェック
        cache_key = ("interface", vdom, name)
        if cache_key in self._tooltip_cache:
            return self._tooltip_cache[cache_key]

        # インターフェースを検索
        iface = self._interface_lookup.get((vdom, name))
        if iface:
            rows = []
            rows.append(("項目", "値"))
            rows.append(("タイプ", iface.interface_type or "-"))
            if iface.ip_address:
                rows.append(("IPアドレス", iface.ip_address))
            if iface.vlan_id:
                rows.append(("VLAN ID", str(iface.vlan_id)))
            if iface.zone:
                rows.append(("ゾーン", iface.zone))
            if iface.role:
                rows.append(("役割", iface.role))
            if iface.allowed_access:
                rows.append(("許可アクセス", ", ".join(iface.allowed_access)))
            if iface.description:
                rows.append(("説明", iface.description))
            if iface.status:
                rows.append(("状態", iface.status))

            # 表形式のHTMLを生成してキャッシュ
            result = self._format_tooltip_table(rows)
            self._tooltip_cache[cache_key] = result
            return result

        self._tooltip_cache[cache_key] = ""
        return ""

    def _is_internet_service(self, name: str) -> bool:
        """Internet Serviceかどうかを判定"""
        name_lower = name.lower()
        # Internet Serviceの一般的な形式をチェック
        if name_lower.startswith("internet-service") or name_lower.startswith("internet_service"):
            return True
        # 数字のみのID（ISDB IDの可能性）
        if name.strip().isdigit():
            return True
        # ISDBデータに存在するかチェック（キャッシュ使用）
        if name in self._isdb_cache or name.strip() in self._isdb_cache:
            return True
        return False

    def _get_internet_service_tooltip(self, name: str) -> str:
        """Internet Serviceのツールチップを取得（表形式）"""
        # キャッシュチェック
        cache_key = ("internet_service", name)
        if cache_key in self._tooltip_cache:
            return self._tooltip_cache[cache_key]

        rows = [("項目", "値")]
        rows.append(("タイプ", "Internet Service"))

        # Internet Service名の形式を処理（キャッシュ使用）
        # "Google-Web"のような形式の場合、サービス名を表示
        service_name = name
        isdb_id = None

        if "-" in name:
            # "Google-Web"のような形式
            parts = name.split("-", 1)
            if len(parts) > 1:
                service_name = parts[1]
                # サービス名からISDB IDを検索（逆引き）
                for app_id, app_name in self._isdb_cache.items():
                    if app_name == service_name or app_name.lower() == service_name.lower():
                        isdb_id = app_id
                        break
        elif name.strip().isdigit():
            # 数字のみの場合はISDB IDとして扱う
            isdb_id = name.strip()
            if isdb_id in self._isdb_cache:
                service_name = self._isdb_cache[isdb_id]
            elif str(isdb_id) in self._isdb_cache:
                service_name = self._isdb_cache[str(isdb_id)]
        else:
            # その他の形式からIDを抽出を試みる
            isdb_id = name.strip()
            parts = isdb_id.split("-")
            for part in reversed(parts):
                if part.isdigit():
                    isdb_id = part
                    if isdb_id in self._isdb_cache:
                        service_name = self._isdb_cache[isdb_id]
                    break

        rows.append(("サービス名", service_name))
        if isdb_id:
            rows.append(("ISDB ID", isdb_id))
        else:
            rows.append(("Internet Service名", name))

        result = self._format_tooltip_table(rows)
        self._tooltip_cache[cache_key] = result
        return result

    def _get_address_tooltip(self, name: str, vdom: str = "root") -> str:
        """アドレスオブジェクト名からツールチップ用の詳細情報を取得（表形式）"""
        # キャッシュチェック
        cache_key = ("address", vdom, name)
        if cache_key in self._tooltip_cache:
            return self._tooltip_cache[cache_key]

        # 特殊なアドレス名
        if name.lower() in ("all", "any"):
            rows = [("項目", "値")]
            rows.append(("タイプ", "特殊アドレス"))
            rows.append(("値", "すべてのアドレス (0.0.0.0/0)"))
            result = self._format_tooltip_table(rows)
            self._tooltip_cache[cache_key] = result
            return result

        # Internet Serviceかどうかをチェック
        if self._is_internet_service(name):
            result = self._get_internet_service_tooltip(name)
            self._tooltip_cache[cache_key] = result
            return result

        # アドレスオブジェクトを検索
        addr = self._address_lookup.get((vdom, name))
        if addr:
            rows = [("項目", "値")]
            rows.append(("タイプ", addr.object_type or "-"))
            rows.append(("値", addr.value or "-"))
            if addr.description:
                rows.append(("説明", addr.description))

            result = self._format_tooltip_table(rows)
            self._tooltip_cache[cache_key] = result
            return result

        # アドレスグループを検索
        grp = self._address_group_lookup.get((vdom, name))
        if grp:
            rows = [("項目", "値")]
            rows.append(("タイプ", "アドレスグループ"))
            members = ", ".join(grp.members[:10])
            if len(grp.members) > 10:
                members += f" ... (他{len(grp.members) - 10}件)"
            rows.append(("メンバー", members))
            if grp.description:
                rows.append(("説明", grp.description))

            result = self._format_tooltip_table(rows)
            self._tooltip_cache[cache_key] = result
            return result

        self._tooltip_cache[cache_key] = ""
        return ""

    def _get_service_tooltip(self, name: str, vdom: str = "root") -> str:
        """サービスオブジェクト名からツールチップ用の詳細情報を取得（表形式）"""
        # キャッシュチェック
        cache_key = ("service", vdom, name)
        if cache_key in self._tooltip_cache:
            return self._tooltip_cache[cache_key]

        # 特殊なサービス名
        name_lower = name.lower()
        if name_lower == "all":
            rows = [("項目", "値")]
            rows.append(("タイプ", "特殊サービス"))
            rows.append(("値", "すべてのサービス"))
            result = self._format_tooltip_table(rows)
            self._tooltip_cache[cache_key] = result
            return result
        if name_lower in ("http", "https", "ssh", "telnet", "ftp", "dns", "smtp", "ping", "icmp"):
            rows = [("項目", "値")]
            rows.append(("タイプ", "組み込みサービス"))
            rows.append(("サービス名", name.upper()))
            result = self._format_tooltip_table(rows)
            self._tooltip_cache[cache_key] = result
            return result

        # サービスオブジェクトを検索
        svc = self._service_lookup.get((vdom, name))
        if svc:
            rows = [("項目", "値")]
            rows.append(("プロトコル", svc.protocol.upper() if svc.protocol else "-"))
            if svc.port:
                rows.append(("ポート", svc.port))
            if svc.description:
                rows.append(("説明", svc.description))

            result = self._format_tooltip_table(rows)
            self._tooltip_cache[cache_key] = result
            return result

        # サービスグループを検索
        grp = self._service_group_lookup.get((vdom, name))
        if grp:
            rows = [("項目", "値")]
            rows.append(("タイプ", "サービスグループ"))
            members = ", ".join(grp.members[:10])
            if len(grp.members) > 10:
                members += f" ... (他{len(grp.members) - 10}件)"
            rows.append(("メンバー", members))
            if grp.description:
                rows.append(("説明", grp.description))

            result = self._format_tooltip_table(rows)
            self._tooltip_cache[cache_key] = result
            return result

        self._tooltip_cache[cache_key] = ""
        return ""

    def _with_tooltip(self, text: str, tooltip: str) -> str:
        """ツールチップ付きのHTML要素を生成"""
        if not tooltip:
            return self.escape(text)
        return f'<span class="has-tooltip" data-tooltip="{self.escape(tooltip)}">{self.escape(text)}</span>'

    def _interface_with_tooltip(self, name: str, vdom: str = "root") -> str:
        """インターフェース名をツールチップ付きで表示"""
        tooltip = self._get_interface_tooltip(name, vdom)
        return self._with_tooltip(name, tooltip)

    def _address_with_tooltip(self, name: str, vdom: str = "root") -> str:
        """アドレス名をツールチップ付きで表示"""
        tooltip = self._get_address_tooltip(name, vdom)
        return self._with_tooltip(name, tooltip)

    def _service_with_tooltip(self, name: str, vdom: str = "root") -> str:
        """サービス名をツールチップ付きで表示"""
        tooltip = self._get_service_tooltip(name, vdom)
        return self._with_tooltip(name, tooltip)

    def _interfaces_to_lines_with_tooltip(self, interfaces: List[str], vdom: str = "root") -> str:
        """インターフェースリストをツールチップ付きで改行表示"""
        if not interfaces:
            return "-"
        lines = [self._interface_with_tooltip(iface, vdom) for iface in interfaces]
        return "<br>".join(lines)

    def _addresses_to_lines_with_tooltip(self, addresses: List[str], vdom: str = "root") -> str:
        """アドレスリストをツールチップ付きで改行表示"""
        if not addresses:
            return "-"
        lines = []
        for addr in addresses:
            # Internet Serviceの場合は特別な表示
            if self._is_internet_service(addr):
                # Internet Serviceをバッジ形式で表示（キャッシュ使用）
                isdb_id = addr.strip()
                if not isdb_id.isdigit():
                    parts = isdb_id.split("-")
                    for part in reversed(parts):
                        if part.isdigit():
                            isdb_id = part
                            break

                app_name = self._isdb_cache.get(isdb_id) or self._isdb_cache.get(str(isdb_id))
                display_name = app_name if app_name else f"Internet Service ({isdb_id})"
                tooltip = self._get_internet_service_tooltip(addr)
                lines.append(f'<span class="badge bg-info has-tooltip" data-tooltip="{self.escape(tooltip)}">{self.escape(display_name)}</span>')
            else:
                lines.append(self._address_with_tooltip(addr, vdom))
        return "<br>".join(lines)

    def _services_to_badges_with_tooltip(self, services: List[str], vdom: str = "root") -> str:
        """サービスをツールチップ付きBootstrapバッジで表示"""
        if not services:
            return '<span class="badge bg-secondary">-</span>'
        badges = []
        for svc in services:
            color = self.SERVICE_COLORS.get(svc.lower(), "secondary")
            tooltip = self._get_service_tooltip(svc, vdom)
            if tooltip:
                badges.append(f'<span class="badge bg-{color} has-tooltip" data-tooltip="{self.escape(tooltip)}">{self.escape(svc)}</span>')
            else:
                badges.append(f'<span class="badge bg-{color}">{self.escape(svc)}</span>')
        return " ".join(badges)

    def _get_security_profile_tooltip(self, profile_str: str, vdom: str = "root") -> str:
        """セキュリティプロファイル名からツールチップ用の詳細情報を取得

        Args:
            profile_str: "type:name" 形式のプロファイル文字列（例: "av:default", "ips:sensor1"）
            vdom: VDOM名

        Returns:
            ツールチップ用の文字列
        """
        # キャッシュチェック
        cache_key = ("security_profile", vdom, profile_str)
        if cache_key in self._tooltip_cache:
            return self._tooltip_cache[cache_key]

        # プロファイル文字列をパース
        if ":" in profile_str:
            profile_type, profile_name = profile_str.split(":", 1)
        else:
            profile_type = profile_str.lower()
            profile_name = profile_str

        profile_type_lower = profile_type.lower()

        # プロファイルタイプのフレンドリー名マッピング
        type_names = {
            "av": "アンチウイルス",
            "antivirus": "アンチウイルス",
            "webfilter": "Webフィルタ",
            "web-filter": "Webフィルタ",
            "application": "アプリケーションコントロール",
            "app-ctrl": "アプリケーションコントロール",
            "ips": "IPS（侵入防止）",
            "ssl": "SSLインスペクション",
            "ssl-ssh-profile": "SSLインスペクション",
            "dlp": "DLP（情報漏洩防止）",
            "emailfilter": "メールフィルタ",
            "dnsfilter": "DNSフィルタ",
            "dns": "DNSフィルタ",
        }
        type_friendly = type_names.get(profile_type_lower, profile_type)

        # 辞書から詳細を検索
        key = (vdom, profile_type_lower, profile_name)
        profile = self._security_profile_lookup.get(key)

        rows = [("項目", "値")]
        rows.append(("タイプ", type_friendly))
        rows.append(("名前", profile_name))

        if profile is None:
            # プロファイルが見つからない場合、基本情報のみを返す
            result = self._format_tooltip_table(rows)
            self._tooltip_cache[cache_key] = result
            return result

        # プロファイルタイプに応じた詳細情報を生成
        if hasattr(profile, 'scan_mode') and profile.scan_mode:
            # アンチウイルス
            rows.append(("スキャンモード", profile.scan_mode))
            if hasattr(profile, 'protocols') and profile.protocols:
                protocols_str = ', '.join(profile.protocols[:3])
                if len(profile.protocols) > 3:
                    protocols_str += f" ... (他{len(profile.protocols) - 3}件)"
                rows.append(("対象プロトコル", protocols_str))
            if hasattr(profile, 'action') and profile.action:
                rows.append(("アクション", profile.action))
        elif hasattr(profile, 'categories') and profile.categories:
            # Webフィルタ / アプリコントロール
            cat_count = len(profile.categories)
            rows.append(("カテゴリ", f"{cat_count}件設定"))
            if hasattr(profile, 'action') and profile.action:
                rows.append(("アクション", profile.action))
        elif hasattr(profile, 'signatures'):
            # IPS
            sig_count = len(profile.signatures) if profile.signatures else 0
            rows.append(("シグネチャ", f"{sig_count}件"))
            if hasattr(profile, 'action') and profile.action:
                rows.append(("アクション", profile.action))
        elif hasattr(profile, 'mode') and profile.mode:
            # SSLインスペクション
            rows.append(("モード", profile.mode))

        result = self._format_tooltip_table(rows)
        self._tooltip_cache[cache_key] = result
        return result

    def _security_profiles_to_badges_with_tooltip(self, profiles: List[str], vdom: str = "root") -> str:
        """セキュリティプロファイルをツールチップ付きBootstrapバッジで表示"""
        if not profiles:
            return "-"

        badges = []
        for profile in profiles:
            # プロファイルタイプを取得してカラーを決定
            if ":" in profile:
                profile_type = profile.lower().split(":")[0]
            else:
                profile_type = profile.lower()

            color = self.SECURITY_PROFILE_COLORS.get(profile_type, "secondary")
            tooltip = self._get_security_profile_tooltip(profile, vdom)

            badge_html = f'<span class="badge badge-outline badge-outline-{color} has-tooltip" data-tooltip="{self.escape(tooltip)}">{self.escape(profile)}</span>'
            badges.append(badge_html)

        return " ".join(badges)

    def _get_vdom_label(self) -> str:
        """デバイスタイプに応じたラベルを返す（VDOM/vsys）"""
        if self.config.device_info.device_type == DeviceType.PALOALTO:
            return "vsys"
        return "VDOM"

    def export(self, output_path: Optional[str] = None) -> str:
        """HTMLを生成"""
        html_content = self._generate_html()

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

        return html_content

    def _generate_toc(self) -> str:
        """階層的目次を生成（グローバル設定 → 各VDOM/vsys）"""
        toc = []
        vdom_label = self._get_vdom_label()

        # 1. グローバル設定セクション
        toc.append('                <li><a href="#global">1. グローバル設定</a>')
        toc.append('                    <ul>')
        section_num = 1
        for key, title, _ in self.GLOBAL_SECTIONS:
            # クラスタ概要はクラスタ構成時のみ表示
            if key == 'cluster_overview' and not self.is_cluster:
                continue
            toc.append(f'                        <li><a href="#global-{key}">1.{section_num} {title}</a></li>')
            section_num += 1
        toc.append('                    </ul>')
        toc.append('                </li>')

        # 2. 各VDOM/vsysセクション
        vdom_list = self._get_vdom_list()
        for vdom_idx, vdom in enumerate(vdom_list, 2):
            toc.append(f'                <li><a href="#vdom-{self.escape(vdom)}">{vdom_idx}. {vdom_label}: {self.escape(vdom)}</a>')
            toc.append('                    <ul>')
            for i, (key, title, _) in enumerate(self.VDOM_SECTIONS, 1):
                toc.append(f'                        <li><a href="#vdom-{self.escape(vdom)}-{key}">{vdom_idx}.{i} {title}</a></li>')
            toc.append('                    </ul>')
            toc.append('                </li>')

        return '\n'.join(toc)

    def _generate_sections(self) -> str:
        """グローバル設定とVDOM単位セクションを生成"""
        sections_html = []
        vdom_label = self._get_vdom_label()

        # 1. グローバル設定セクション
        sections_html.append(f'''
        <section id="global" class="vdom-section global-section">
            <h2>1. グローバル設定</h2>''')

        section_num = 1
        for key, title, method_name in self.GLOBAL_SECTIONS:
            # クラスタ概要はクラスタ構成時のみ表示
            if key == 'cluster_overview' and not self.is_cluster:
                continue
            method = getattr(self, method_name)
            section_html = method(section_num=f"1.{section_num}", section_id=f"global-{key}")
            sections_html.append(section_html)
            section_num += 1

        sections_html.append('        </section>')

        # 2. 各VDOM/vsysセクション
        vdom_list = self._get_vdom_list()
        for vdom_idx, vdom in enumerate(vdom_list, 2):
            sections_html.append(f'''
        <section id="vdom-{self.escape(vdom)}" class="vdom-section">
            <h2>{vdom_idx}. {vdom_label}: {self.escape(vdom)}</h2>''')

            for i, (key, title, method_name) in enumerate(self.VDOM_SECTIONS, 1):
                method = getattr(self, method_name)
                section_html = method(
                    section_num=f"{vdom_idx}.{i}",
                    section_id=f"vdom-{self.escape(vdom)}-{key}",
                    vdom=vdom
                )
                sections_html.append(section_html)

            sections_html.append('        </section>')

        return '\n'.join(sections_html)

    def _generate_html(self) -> str:
        """HTML全体を生成"""
        device_info = self.config.device_info
        today = datetime.now().strftime('%Y年%m月%d日')
        
        # 検索ボックス（PDF用の場合は非表示）
        search_box = '' if self.for_pdf else f'''            <div class="search-box">
                <input type="text" id="searchInput" placeholder="検索..." autocomplete="off">
                <button type="button" id="searchBtn" onclick="performSearch()">検索</button>
                <button type="button" id="clearBtn" onclick="clearSearch()" style="display:none;">クリア</button>
                <span id="searchResults" class="search-results"></span>
            </div>'''
        
        # JavaScript（PDF用の場合は削除）
        script_tag = '' if self.for_pdf else f'''    <script>
{load_search_js()}
{load_tooltip_js()}
    </script>'''

        # PDF用は軽量CSS（Bootstrap除外）を使用して高速化
        css_content = load_css_for_pdf() if self.for_pdf else load_css()

        return f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.escape(device_info.device_type.value)} パラメータシート - {self.escape(device_info.hostname)}</title>
    <style>
{css_content}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{self.escape(device_info.model or device_info.device_type.value)} パラメータシート</h1>
            <div class="meta">
                <strong>ファイル名:</strong> {self.escape(Path(self.config.source_file).name)} |
                <strong>バージョン:</strong> {self.escape(device_info.os_version)} |
                <strong>作成日:</strong> {today}
            </div>
{search_box}
        </header>

        <nav class="toc">
            <h2>目次</h2>
            <ul>
{self._generate_toc()}
            </ul>
        </nav>

{self._generate_sections()}

        <footer>
            <p>{self.escape(device_info.device_type.value)} Version: {self.escape(device_info.os_version)} | Device: {self.escape(device_info.hostname)}</p>
        </footer>
    </div>
{script_tag}
</body>
</html>'''

    def _generate_device_info_section(self, section_num: str = "1.1", section_id: str = "global-device_info") -> str:
        """機器概要セクション（グローバル）"""
        info = self.config.device_info
        license = info.license
        vdom_label = self._get_vdom_label()

        ha_status = "未設定"
        if self.config.ha.mode != HAMode.STANDALONE:
            ha_status = f"{self.config.ha.mode.value} (Group: {self.config.ha.group_id}, Priority: {self.config.ha.priority})"

        # ライセンス情報
        license_rows = ""
        if license.support_expiry or license.utm_expiry or license.av_expiry:
            if license.support_expiry:
                license_rows += f'<tr><td>サポート有効期限</td><td>{self.escape(license.support_expiry)}</td></tr>'
            if license.utm_expiry:
                license_rows += f'<tr><td>UTM Bundle有効期限</td><td>{self.escape(license.utm_expiry)}</td></tr>'
            if license.av_expiry:
                license_rows += f'<tr><td>アンチウイルス有効期限</td><td>{self.escape(license.av_expiry)}</td></tr>'
            if license.webfilter_expiry:
                license_rows += f'<tr><td>Webフィルタ有効期限</td><td>{self.escape(license.webfilter_expiry)}</td></tr>'
            if license.ips_expiry:
                license_rows += f'<tr><td>IPS有効期限</td><td>{self.escape(license.ips_expiry)}</td></tr>'
        else:
            license_rows = '<tr><td colspan="2">ライセンス情報は設定ファイルから取得できません（別途確認が必要）</td></tr>'

        # VDOM/vsysリスト
        vdom_list = self._get_vdom_list()
        vdom_list_display = ', '.join(vdom_list) if vdom_list else '-'

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} 機器概要</h3>
                <div class="info-grid">
                    <div class="info-card">
                        <h4>基本情報</h4>
                        <table class="table table-sm table-bordered">
                            <tr><th>項目</th><th>設定値</th></tr>
                            <tr><td>ホスト名</td><td><strong>{self.escape(info.hostname)}</strong></td></tr>
                            <tr><td>モデル名</td><td>{self.escape(info.model)}</td></tr>
                            <tr><td>シリアル番号</td><td>{self.escape(info.serial_number) if info.serial_number else '設定ファイルから取得不可'}</td></tr>
                            <tr><td>OSバージョン</td><td>{self.escape(info.os_version)}</td></tr>
                            <tr><td>動作モード</td><td>{self.escape(info.operation_mode.value)}</td></tr>
                            <tr><td>{vdom_label}</td><td>{'有効' if info.vdom_enabled else '無効'} ({vdom_list_display})</td></tr>
                        </table>
                    </div>
                    <div class="info-card">
                        <h4>ライセンス情報</h4>
                        <table class="table table-sm table-bordered">
                            {license_rows}
                        </table>
                    </div>
                    <div class="info-card">
                        <h4>サマリー</h4>
                        <table class="table table-sm table-bordered">
                            <tr><th>項目</th><th>数量</th></tr>
                            <tr><td>インターフェース数</td><td>{len(self.config.interfaces)}</td></tr>
                            <tr><td>ルート数</td><td>{len(self.config.routes)}</td></tr>
                            <tr><td>ポリシー数</td><td>{len(self.config.firewall_policies)}</td></tr>
                            <tr><td>オブジェクト数</td><td>{len(self.config.objects.addresses) + len(self.config.objects.services)}</td></tr>
                            <tr><td>HA状態</td><td>{self.escape(ha_status)}</td></tr>
                        </table>
                    </div>
                </div>
            </div>'''

    def _generate_system_settings_section(self, section_num: str = "1.2", section_id: str = "global-system_settings") -> str:
        """システム設定セクション（グローバル）"""
        settings = self.config.system_settings
        vdom_label = self._get_vdom_label()

        admin_rows = ""
        for admin in settings.admin_users:
            trust_hosts = self._list_to_str(admin.trust_hosts)
            admin_rows += f'''<tr>
                <td>{self.escape(admin.username)}</td>
                <td>{self.escape(admin.profile)}</td>
                <td>{self.escape(admin.vdom)}</td>
                <td><code>{self.escape(trust_hosts)}</code></td>
            </tr>'''

        # 管理アクセス情報
        mgmt_ip_display = self.escape(settings.management_ip)
        if settings.management_netmask:
            mgmt_ip_display += f" / {self.escape(settings.management_netmask)}"
        elif "/" not in settings.management_ip:
            mgmt_ip_display += " / -"

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} システム設定</h3>

                <h4>管理アクセス</h4>
                <div class="info-grid">
                    <div class="info-card">
                        <h5>管理インターフェース</h5>
                        <table class="table table-sm table-bordered">
                            <tr><th>項目</th><th>設定値</th></tr>
                            <tr><td>管理用IPアドレス</td><td><code>{mgmt_ip_display}</code></td></tr>
                            <tr><td>管理インターフェース</td><td>{self.escape(settings.management_interface) or '<span class="text-muted">-</span>'}</td></tr>
                            <tr><td>許可プロトコル</td><td>{self._format_allowed_access(settings.allowed_protocols)}</td></tr>
                            <tr><td>HTTPSポート</td><td>{self._with_default(settings.https_port, 'https_port')}</td></tr>
                            <tr><td>SSHポート</td><td>{self._with_default(settings.ssh_port, 'ssh_port')}</td></tr>
                        </table>
                    </div>
                </div>

                <h4>基本設定</h4>
                <div class="info-grid">
                    <div class="info-card">
                        <h5>DNS設定</h5>
                        <table class="table table-sm table-bordered">
                            <tr><th>順位</th><th>IPアドレス</th></tr>
                            <tr><td>プライマリ</td><td><code>{self._with_default(settings.dns_primary, 'dns_primary')}</code></td></tr>
                            <tr><td>セカンダリ</td><td><code>{self._with_default(settings.dns_secondary, 'dns_secondary')}</code></td></tr>
                        </table>
                    </div>
                    <div class="info-card">
                        <h5>その他</h5>
                        <table class="table table-sm table-bordered">
                            <tr><th>項目</th><th>設定値</th></tr>
                            <tr><td>タイムゾーン</td><td>{self._with_default(settings.timezone, 'timezone')}</td></tr>
                            <tr><td>NTPサーバー</td><td>{self._list_with_default(settings.ntp_servers, 'ntp_servers')}</td></tr>
                        </table>
                    </div>
                </div>

                <h4>管理者アカウント</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>ユーザー名</th><th>権限プロファイル</th><th>{vdom_label}</th><th>信頼ホスト</th></tr>
                        {admin_rows if admin_rows else '<tr><td colspan="4">管理者アカウント設定なし</td></tr>'}
                    </table>
                </div>
                <div class="warning-box">
                    <strong>注意:</strong> パスワードはセキュリティ上の理由により設定ファイルに含まれていません。管理台帳などで別途管理してください。
                </div>
            </div>'''

    def _generate_network_section(self, section_num: str = "2.1", section_id: str = "vdom-root-network", vdom: str = None) -> str:
        """ネットワーク設定セクション（VDOM単位）"""
        # VDOMでフィルタリング
        interfaces = self._filter_by_vdom(self.config.interfaces, vdom) if vdom else self.config.interfaces
        routes = self._filter_by_vdom(self.config.routes, vdom) if vdom else self.config.routes
        dhcp_servers = self._filter_by_vdom(self.config.dhcp_servers, vdom) if vdom else self.config.dhcp_servers

        # ルーティング設定
        ospf_settings = self._filter_by_vdom(self.config.routing.ospf, vdom) if vdom else self.config.routing.ospf
        bgp_settings = self._filter_by_vdom(self.config.routing.bgp, vdom) if vdom else self.config.routing.bgp
        policy_routes = self._filter_by_vdom(self.config.routing.policy_routes, vdom) if vdom else self.config.routing.policy_routes

        # インターフェース
        iface_rows = ""
        for iface in interfaces:
            zone_tag = ""
            if iface.zone:
                zone_class = self._get_zone_class(iface.zone)
                zone_tag = f'<span class="tag {zone_class}">{self.escape(iface.zone)}</span>'

            # VLAN ID表示
            vlan_display = ""
            if iface.vlan_id:
                vlan_display = f"VLAN {self.escape(iface.vlan_id)}"

            iface_rows += f'''<tr>
                <td>{self.escape(iface.name)}</td>
                <td>{self.escape(iface.interface_type)}</td>
                <td>{self.escape(iface.role) if iface.role else '-'}</td>
                <td><code>{self.escape(iface.ip_address)}</code></td>
                <td>{vlan_display}</td>
                <td>{zone_tag}</td>
                <td>{self._format_allowed_access(iface.allowed_access)}</td>
            </tr>'''

        # ルーティング
        route_rows = ""
        for route in routes:
            gateway_display = route.gateway or ""
            # blackhole/discard ルートはゲートウェイが空になるため、明示して記載する
            if not gateway_display and getattr(route, "route_type", "") in ("blackhole", "blackhole6"):
                gateway_display = "blackhole"

            interface_display = route.interface or "-"
            name_display = route.name or "-"
            destination_display = route.destination or "-"

            route_rows += f'''<tr>
                <td>{self.escape(name_display)}</td>
                <td><code>{self.escape(destination_display)}</code></td>
                <td><code>{self.escape(gateway_display) if gateway_display else '-'}</code></td>
                <td>{self.escape(interface_display)}</td>
            </tr>'''

        # DHCP
        dhcp_cards = ""
        for dhcp in dhcp_servers:
            exclude_ips_display = self._list_to_str(dhcp.exclude_ips) if dhcp.exclude_ips else "なし"
            dhcp_cards += f'''
                <div class="info-card">
                    <h5>{self.escape(dhcp.interface)}</h5>
                    <table class="table table-sm table-bordered">
                        <tr><td>IP払い出し範囲</td><td><code>{self.escape(dhcp.start_ip)} - {self.escape(dhcp.end_ip)}</code></td></tr>
                        <tr><td>サブネットマスク</td><td><code>{self.escape(dhcp.netmask)}</code></td></tr>
                        <tr><td>除外IP</td><td><code>{exclude_ips_display}</code></td></tr>
                        <tr><td>デフォルトゲートウェイ</td><td><code>{self.escape(dhcp.gateway)}</code></td></tr>
                        <tr><td>DNSサーバー</td><td>{self._list_with_default(dhcp.dns_servers, 'dhcp_dns')}</td></tr>
                        <tr><td>リース時間</td><td>{self._with_default(dhcp.lease_time, 'dhcp_lease_time')}</td></tr>
                    </table>
                </div>'''

        # OSPF設定
        ospf_html = self._generate_ospf_html(ospf_settings)

        # BGP設定
        bgp_html = self._generate_bgp_html(bgp_settings)

        # ポリシールート
        policy_route_rows = ""
        for pr in policy_routes:
            src_display = self._list_to_str(pr.src_addresses) if pr.src_addresses else "any"
            dst_display = self._list_to_str(pr.dst_addresses) if pr.dst_addresses else "any"
            gateway_display = pr.gateway or "-"
            interface_display = pr.output_interface or "-"
            policy_route_rows += f'''<tr>
                <td>{self.escape(str(pr.sequence_number))}</td>
                <td>{self.escape(pr.name) if pr.name else '-'}</td>
                <td>{self.escape(src_display)}</td>
                <td>{self.escape(dst_display)}</td>
                <td>{self.escape(interface_display)}</td>
                <td><code>{self.escape(gateway_display)}</code></td>
            </tr>'''

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} ネットワーク設定</h3>

                <h4>インターフェース（物理・VLAN・LAG）</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>インターフェース名</th><th>タイプ</th><th>役割</th><th>IPアドレス</th><th>VLAN ID</th><th>ゾーン</th><th>許可アクセス</th></tr>
                        {iface_rows if iface_rows else '<tr><td colspan="7">インターフェース設定なし</td></tr>'}
                    </table>
                </div>

                <h4>スタティックルート</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>名前</th><th>宛先ネットワーク</th><th>ゲートウェイ</th><th>デバイス（インターフェース）</th></tr>
                        {route_rows if route_rows else '<tr><td colspan="4">スタティックルート設定なし</td></tr>'}
                    </table>
                </div>

                <h4>DHCPサーバー</h4>
                <div class="info-grid">
                    {dhcp_cards if dhcp_cards else '<p>DHCPサーバー設定なし</p>'}
                </div>

                {ospf_html}

                {bgp_html}

                <h4>ポリシールート</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>シーケンス</th><th>名前</th><th>送信元</th><th>宛先</th><th>出力インターフェース</th><th>ゲートウェイ</th></tr>
                        {policy_route_rows if policy_route_rows else '<tr><td colspan="6">ポリシールート設定なし</td></tr>'}
                    </table>
                </div>
            </div>'''

    def _generate_ospf_html(self, ospf_settings: list) -> str:
        """OSPF設定のHTML生成"""
        if not ospf_settings:
            return '''
                <h4>OSPF設定</h4>
                <p>OSPF設定なし</p>
            '''

        ospf_html = '<h4>OSPF設定</h4>'

        for ospf in ospf_settings:
            # 基本情報
            ospf_html += f'''
                <div class="info-card mb-3">
                    <h5>OSPF基本設定</h5>
                    <table class="table table-sm table-bordered">
                        <tr><td>ルーターID</td><td><code>{self.escape(ospf.router_id) if ospf.router_id else '-'}</code></td></tr>
                        <tr><td>デフォルトルート配布</td><td>{'有効' if ospf.default_information_originate else '無効'}</td></tr>
                        <tr><td>デフォルトメトリック</td><td>{self.escape(ospf.default_metric) if ospf.default_metric else '-'}</td></tr>
                        <tr><td>距離</td><td>{self.escape(ospf.distance) if ospf.distance else '-'}</td></tr>
                    </table>
                </div>'''

            # エリア
            if ospf.areas:
                area_rows = ""
                for area in ospf.areas:
                    area_rows += f'''<tr>
                        <td>{self.escape(area.area_id)}</td>
                        <td>{self.escape(area.area_type) if area.area_type else 'normal'}</td>
                        <tr><td colspan="2">認証: {self.escape(area.authentication) if area.authentication else 'なし'}</td></tr>
                    </tr>'''
                ospf_html += f'''
                    <div class="table-responsive">
                        <h5>OSPFエリア</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>エリアID</th><th>タイプ</th></tr>
                            {area_rows}
                        </table>
                    </div>'''

            # インターフェース
            if ospf.interfaces:
                iface_rows = ""
                for iface in ospf.interfaces:
                    iface_rows += f'''<tr>
                        <td>{self.escape(iface.name)}</td>
                        <td>{self.escape(iface.area) if iface.area else '-'}</td>
                        <td>{self.escape(str(iface.cost)) if iface.cost else '-'}</td>
                        <td>{self.escape(str(iface.priority)) if iface.priority else '-'}</td>
                        <td>{self.escape(iface.network_type) if iface.network_type else '-'}</td>
                    </tr>'''
                ospf_html += f'''
                    <div class="table-responsive">
                        <h5>OSPFインターフェース</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>インターフェース</th><th>エリア</th><th>コスト</th><th>優先度</th><th>ネットワークタイプ</th></tr>
                            {iface_rows}
                        </table>
                    </div>'''

            # 再配布
            if ospf.redistributes:
                redist_rows = ""
                for redist in ospf.redistributes:
                    redist_rows += f'''<tr>
                        <td>{self.escape(redist.source)}</td>
                        <td>{'有効' if redist.status else '無効'}</td>
                        <td>{self.escape(str(redist.metric)) if redist.metric else '-'}</td>
                        <td>{self.escape(redist.metric_type) if redist.metric_type else '-'}</td>
                        <td>{self.escape(redist.routemap) if redist.routemap else '-'}</td>
                    </tr>'''
                ospf_html += f'''
                    <div class="table-responsive">
                        <h5>OSPF再配布</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>ソース</th><th>ステータス</th><th>メトリック</th><th>メトリックタイプ</th><th>ルートマップ</th></tr>
                            {redist_rows}
                        </table>
                    </div>'''

            # パッシブインターフェース
            if ospf.passive_interfaces:
                passive_list = ', '.join(ospf.passive_interfaces)
                ospf_html += f'''
                    <div class="info-card mb-3">
                        <h5>パッシブインターフェース</h5>
                        <p>{self.escape(passive_list)}</p>
                    </div>'''

        return ospf_html

    def _generate_bgp_html(self, bgp_settings: list) -> str:
        """BGP設定のHTML生成"""
        if not bgp_settings:
            return '''
                <h4>BGP設定</h4>
                <p>BGP設定なし</p>
            '''

        bgp_html = '<h4>BGP設定</h4>'

        for bgp in bgp_settings:
            # 基本情報
            bgp_html += f'''
                <div class="info-card mb-3">
                    <h5>BGP基本設定</h5>
                    <table class="table table-sm table-bordered">
                        <tr><td>AS番号</td><td><code>{self.escape(bgp.as_number) if bgp.as_number else '-'}</code></td></tr>
                        <tr><td>ルーターID</td><td><code>{self.escape(bgp.router_id) if bgp.router_id else '-'}</code></td></tr>
                    </table>
                </div>'''

            # ネイバー
            if bgp.neighbors:
                neighbor_rows = ""
                for neighbor in bgp.neighbors:
                    neighbor_rows += f'''<tr>
                        <td><code>{self.escape(neighbor.ip)}</code></td>
                        <td>{self.escape(neighbor.remote_as)}</td>
                        <td>{self.escape(neighbor.description) if neighbor.description else '-'}</td>
                        <td>{'有効' if neighbor.activate else '無効'}</td>
                        <td>{self.escape(neighbor.route_map_in) if neighbor.route_map_in else '-'}</td>
                        <td>{self.escape(neighbor.route_map_out) if neighbor.route_map_out else '-'}</td>
                    </tr>'''
                bgp_html += f'''
                    <div class="table-responsive">
                        <h5>BGPネイバー</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>IPアドレス</th><th>リモートAS</th><th>説明</th><th>有効</th><th>ルートマップIn</th><th>ルートマップOut</th></tr>
                            {neighbor_rows}
                        </table>
                    </div>'''

            # ネットワーク
            if bgp.networks:
                network_rows = ""
                for network in bgp.networks:
                    network_rows += f'''<tr>
                        <td><code>{self.escape(network.prefix)}</code></td>
                        <td>{self.escape(network.route_map) if network.route_map else '-'}</td>
                    </tr>'''
                bgp_html += f'''
                    <div class="table-responsive">
                        <h5>BGPネットワーク</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>プレフィックス</th><th>ルートマップ</th></tr>
                            {network_rows}
                        </table>
                    </div>'''

            # 再配布
            if bgp.redistributes:
                redist_rows = ""
                for redist in bgp.redistributes:
                    redist_rows += f'''<tr>
                        <td>{self.escape(redist.source)}</td>
                        <td>{'有効' if redist.status else '無効'}</td>
                        <td>{self.escape(redist.routemap) if redist.routemap else '-'}</td>
                    </tr>'''
                bgp_html += f'''
                    <div class="table-responsive">
                        <h5>BGP再配布</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>ソース</th><th>ステータス</th><th>ルートマップ</th></tr>
                            {redist_rows}
                        </table>
                    </div>'''

        return bgp_html

    def _get_zone_class(self, zone: str) -> str:
        """ゾーン名からCSSクラスを取得"""
        zone_lower = zone.lower()
        if 'trust' in zone_lower and 'untrust' not in zone_lower:
            return 'tag-trust'
        elif 'untrust' in zone_lower:
            return 'tag-untrust'
        elif 'dmz' in zone_lower:
            return 'tag-dmz'
        return ''

    def _format_allowed_access(self, allowed_access: List[str]) -> str:
        """許可アクセスをBootstrapアウトラインボタンで表示"""
        if not allowed_access:
            return '<span class="btn btn-outline-secondary btn-sm disabled">なし</span>'

        # プロトコルごとのボタン色を定義
        btn_classes = {
            'https': 'btn-outline-success',      # セキュア（緑）
            'ssh': 'btn-outline-success',        # セキュア（緑）
            'http': 'btn-outline-warning',       # 非セキュア（黄）
            'telnet': 'btn-outline-danger',      # 非セキュア（赤）
            'ping': 'btn-outline-info',          # 診断（青）
            'snmp': 'btn-outline-info',          # 監視（青）
            'fmg-access': 'btn-outline-primary', # FortiManager（紫）
            'capwap': 'btn-outline-primary',     # 無線AP管理（紫）
            'radius-acct': 'btn-outline-secondary',  # RADIUS（グレー）
            'ftm': 'btn-outline-secondary',      # FortiToken（グレー）
        }

        buttons = []
        for access in allowed_access:
            access_lower = access.lower()
            btn_class = btn_classes.get(access_lower, 'btn-outline-secondary')
            buttons.append(f'<span class="btn {btn_class} btn-sm me-1 mb-1">{self.escape(access)}</span>')

        return ' '.join(buttons)

    def _generate_objects_section(self, section_num: str = "2.2", section_id: str = "vdom-root-objects", vdom: str = None) -> str:
        """オブジェクト定義セクション（VDOM単位）"""
        # VDOMでフィルタリング
        addresses = self._filter_by_vdom(self.config.objects.addresses, vdom) if vdom else self.config.objects.addresses
        services = self._filter_by_vdom(self.config.objects.services, vdom) if vdom else self.config.objects.services

        # アドレスオブジェクト（最初の100件）
        addr_rows = ""
        for addr in addresses[:100]:
            addr_rows += f'''<tr>
                <td>{self.escape(addr.name)}</td>
                <td>{self.escape(addr.object_type)}</td>
                <td><code>{self.escape(addr.value)}</code></td>
            </tr>'''

        # サービスオブジェクト（最初の100件）
        svc_rows = ""
        for svc in services[:100]:
            svc_rows += f'''<tr>
                <td>{self.escape(svc.name)}</td>
                <td>{self.escape(svc.protocol)}</td>
                <td>{self.escape(svc.port)}</td>
            </tr>'''

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} オブジェクト定義</h3>

                <div class="summary-box">
                    <strong>オブジェクト数:</strong> アドレス {len(addresses)} 件、サービス {len(services)} 件
                </div>

                <h4>アドレスオブジェクト</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>オブジェクト名</th><th>タイプ</th><th>値</th></tr>
                        {addr_rows if addr_rows else '<tr><td colspan="3">アドレスオブジェクト設定なし</td></tr>'}
                    </table>
                </div>

                <h4>サービスオブジェクト</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>オブジェクト名</th><th>プロトコル</th><th>ポート</th></tr>
                        {svc_rows if svc_rows else '<tr><td colspan="3">サービスオブジェクト設定なし</td></tr>'}
                    </table>
                </div>
            </div>'''

    def _generate_policies_section(self, section_num: str = "2.3", section_id: str = "vdom-root-policies", vdom: str = None) -> str:
        """ポリシーセクション（VDOM単位）"""
        # VDOMでフィルタリング
        firewall_policies = self._filter_by_vdom(self.config.firewall_policies, vdom) if vdom else self.config.firewall_policies
        local_in_policies = self._filter_by_vdom(self.config.local_in_policies, vdom) if vdom else self.config.local_in_policies
        current_vdom = vdom or "root"

        policy_rows = []
        for idx, policy in enumerate(firewall_policies, 1):
            # 宛先アドレスの表示（Internet Service名がある場合はそれも含める）
            destination_display = self._addresses_to_lines_with_tooltip(policy.destination_address, current_vdom)
            if policy.internet_service_name:
                # Internet Service名を追加
                internet_services = []
                for is_name in policy.internet_service_name:
                    tooltip = self._get_internet_service_tooltip(is_name)
                    # "Google-Web"のような形式からサービス名を抽出
                    service_name = is_name
                    if "-" in is_name:
                        parts = is_name.split("-", 1)
                        if len(parts) > 1:
                            service_name = parts[1]
                    internet_services.append(f'<span class="badge bg-info has-tooltip" data-tooltip="{self.escape(tooltip)}">{self.escape(service_name)}</span>')
                
                if destination_display and destination_display != "-":
                    destination_display += "<br>" + " ".join(internet_services)
                else:
                    destination_display = " ".join(internet_services)
            
            policy_rows.append(f'''<tr class="policy-row">
                <td>{idx}</td>
                <td>{self.escape(policy.policy_id)}</td>
                <td>{self.escape(policy.name)} {"" if policy.enabled else '<span class="disabled">(無効)</span>'}</td>
                <td>{self._interfaces_to_lines_with_tooltip(policy.source_interface, current_vdom)}</td>
                <td>{self._interfaces_to_lines_with_tooltip(policy.destination_interface, current_vdom)}</td>
                <td>{self._addresses_to_lines_with_tooltip(policy.source_address, current_vdom)}</td>
                <td>{destination_display}</td>
                <td>{self._services_to_badges_with_tooltip(policy.service, current_vdom)}</td>
                <td class="{self._get_action_class(policy.action)}">{self.escape(policy.action.value)}</td>
                <td>{"有効" if policy.nat_enabled else "無効"}</td>
                <td>{self._security_profiles_to_badges_with_tooltip(policy.security_profiles, current_vdom)}</td>
                <td>{"有効" if policy.log_enabled else "無効"}</td>
                <td>{self.escape(policy.description)}</td>
            </tr>''')

        # Local-in ポリシー
        local_in_rows = []
        for idx, policy in enumerate(local_in_policies, 1):
            # source_interfaceは文字列の場合とリストの場合がある
            source_if_display = ""
            if isinstance(policy.source_interface, list):
                source_if_display = self._interfaces_to_lines_with_tooltip(policy.source_interface, current_vdom)
            elif policy.source_interface:
                source_if_display = self._interface_with_tooltip(policy.source_interface, current_vdom)
            else:
                source_if_display = "-"
            
            local_in_rows.append(f'''<tr class="policy-row">
                <td>{idx}</td>
                <td>{self.escape(policy.policy_id)}</td>
                <td>{self.escape(policy.name)} {"" if policy.enabled else '<span class="disabled">(無効)</span>'}</td>
                <td>{source_if_display}</td>
                <td>{self._addresses_to_lines_with_tooltip(policy.source_address, current_vdom)}</td>
                <td>{self._addresses_to_lines_with_tooltip(policy.destination_address, current_vdom)}</td>
                <td>{self._services_to_badges_with_tooltip(policy.service, current_vdom)}</td>
                <td class="{self._get_action_class(policy.action)}">{self.escape(policy.action.value)}</td>
                <td>{self.escape(policy.description)}</td>
            </tr>''')

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} ファイアウォールポリシー</h3>

                <div class="summary-box">
                    <strong>ポリシー数:</strong> {len(firewall_policies)} ルール
                </div>

                <h4>ポリシー一覧</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <thead>
                            <tr>
                                <th>No</th>
                                <th>ID</th>
                                <th>ポリシー名</th>
                                <th>送信元IF</th>
                                <th>宛先IF</th>
                                <th>送信元アドレス</th>
                                <th>宛先アドレス</th>
                                <th>サービス</th>
                                <th>アクション</th>
                                <th>NAT</th>
                                <th>セキュリティプロファイル</th>
                                <th>ログ</th>
                                <th>備考</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(policy_rows) if policy_rows else '<tr><td colspan="13">ポリシー設定なし</td></tr>'}
                        </tbody>
                    </table>
                </div>

                <h4>Local-in ポリシー</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <thead>
                            <tr>
                                <th>No</th>
                                <th>ID</th>
                                <th>ポリシー名</th>
                                <th>送信元IF</th>
                                <th>送信元アドレス</th>
                                <th>宛先アドレス</th>
                                <th>サービス</th>
                                <th>アクション</th>
                                <th>備考</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(local_in_rows) if local_in_rows else '<tr><td colspan="9">Local-in ポリシー設定なし</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>'''

    def _get_action_class(self, action: PolicyAction) -> str:
        """アクションからCSSクラスを取得"""
        if action == PolicyAction.ALLOW:
            return 'allow'
        elif action == PolicyAction.DENY:
            return 'deny'
        elif action == PolicyAction.DROP:
            return 'drop'
        return ''


    def _generate_nat_section(self, section_num: str = "2.4", section_id: str = "vdom-root-nat", vdom: str = None) -> str:
        """NAT設定セクション（VDOM単位）"""
        # VDOMでフィルタリング
        nat_policies = self._filter_by_vdom(self.config.nat_policies, vdom) if vdom else self.config.nat_policies

        # VIP/DNAT
        vip_rows = ""
        # SNAT/IP Pool
        snat_rows = ""

        for nat in nat_policies:
            if nat.nat_type in ("vip", "dnat"):
                port_forward_display = ""
                if nat.port_forward:
                    port_forward_display = f"{self.escape(nat.original_port)} → {self.escape(nat.translated_port)}"
                else:
                    port_forward_display = "なし"

                vip_rows += f'''<tr>
                    <td>{self.escape(nat.name)}</td>
                    <td>{self.escape(nat.external_interface)}</td>
                    <td><code>{self.escape(nat.external_ip)}</code></td>
                    <td><code>{self.escape(nat.internal_ip)}</code></td>
                    <td>{port_forward_display}</td>
                    <td>{self.escape(nat.description)}</td>
                </tr>'''
            elif nat.nat_type in ("snat", "ippool"):
                snat_rows += f'''<tr>
                    <td>{self.escape(nat.name)}</td>
                    <td><code>{self.escape(nat.translated_source)}</code></td>
                    <td>{self.escape(nat.interface)}</td>
                    <td>{self.escape(nat.description)}</td>
                </tr>'''

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} NAT設定</h3>

                <h4>VIP / DNAT（サーバー公開用）</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>ルール名</th><th>外部インターフェース</th><th>外部IP（Global IP）</th><th>内部IP（Private IP）</th><th>ポートフォワーディング</th><th>備考</th></tr>
                        {vip_rows if vip_rows else '<tr><td colspan="6">VIP/DNAT設定なし</td></tr>'}
                    </table>
                </div>

                <h4>SNAT / IP Pool</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>ルール名</th><th>変換後送信元</th><th>インターフェース</th><th>備考</th></tr>
                        {snat_rows if snat_rows else '<tr><td colspan="4">SNAT/IP Pool設定なし</td></tr>'}
                    </table>
                </div>
            </div>'''

    def _generate_vpn_section(self, section_num: str = "2.5", section_id: str = "vdom-root-vpn", vdom: str = None) -> str:
        """VPN設定セクション（VDOM単位）"""
        # VDOMでフィルタリング
        ipsec_phase1 = self._filter_by_vdom(self.config.vpn.ipsec_phase1, vdom) if vdom else self.config.vpn.ipsec_phase1
        ipsec_phase2 = self._filter_by_vdom(self.config.vpn.ipsec_phase2, vdom) if vdom else self.config.vpn.ipsec_phase2
        ssl_vpn = self._filter_by_vdom(self.config.vpn.ssl_vpn, vdom) if vdom else self.config.vpn.ssl_vpn

        # IPsec Phase1
        p1_rows = ""
        for p1 in ipsec_phase1:
            p1_rows += f'''<tr>
                <td>{self.escape(p1.name)}</td>
                <td><code>{self.escape(p1.remote_gateway)}</code></td>
                <td>{self.escape(p1.interface)}</td>
                <td>{self.escape(p1.encryption)} / {self.escape(p1.authentication)}</td>
                <td>{self.escape(p1.dh_group)}</td>
                <td>{self.escape(p1.lifetime)}</td>
                <td>{'有' if p1.psk else '無'}</td>
            </tr>'''

        # IPsec Phase2
        p2_rows = ""
        for p2 in ipsec_phase2:
            p2_rows += f'''<tr>
                <td>{self.escape(p2.name)}</td>
                <td>{self.escape(p2.phase1_name)}</td>
                <td><code>{self.escape(p2.local_subnet)}</code></td>
                <td><code>{self.escape(p2.remote_subnet)}</code></td>
                <td>{self.escape(p2.encryption)} / {self.escape(p2.authentication)}</td>
                <td>{self.escape(p2.pfs)}</td>
                <td>{self.escape(p2.lifetime)}</td>
            </tr>'''

        # SSL-VPN
        ssl_rows = ""
        for ssl in ssl_vpn:
            auth_method_display = self.escape(ssl.auth_method) if ssl.auth_method else "ローカル"
            mode_display = self.escape(ssl.mode) if ssl.mode else "-"
            realm_display = self.escape(ssl.realm) if ssl.realm else "-"
            portal_display = self.escape(ssl.portal) if ssl.portal else "-"

            ssl_rows += f'''<tr>
                <td>{realm_display} / {portal_display}</td>
                <td>{self.escape(ssl.listen_port)}</td>
                <td>{self.escape(ssl.listen_interface)}</td>
                <td>{auth_method_display}</td>
                <td><code>{self.escape(ssl.tunnel_ip_pool)}</code></td>
                <td>{self.escape(self._list_to_str(ssl.user_groups))}</td>
                <td>{mode_display}</td>
            </tr>'''

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} VPN設定</h3>

                <h4>IPsec-VPN Phase1</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>VPN名</th><th>対向機器IP（ピア）</th><th>インターフェース</th><th>暗号化/認証</th><th>DHグループ</th><th>ライフタイム</th><th>事前共有鍵</th></tr>
                        {p1_rows if p1_rows else '<tr><td colspan="7">IPsec Phase1設定なし</td></tr>'}
                    </table>
                </div>

                <h4>IPsec-VPN Phase2</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>VPN名</th><th>Phase1名</th><th>ローカルセグメント</th><th>リモートセグメント</th><th>暗号化/認証</th><th>PFS</th><th>ライフタイム</th></tr>
                        {p2_rows if p2_rows else '<tr><td colspan="7">IPsec Phase2設定なし</td></tr>'}
                    </table>
                </div>

                <h4>SSL-VPN / GlobalProtect</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>レルム/ポータル名</th><th>リスニングポート</th><th>インターフェース</th><th>認証</th><th>払い出しIPプール</th><th>許可ユーザーグループ</th><th>モード</th></tr>
                        {ssl_rows if ssl_rows else '<tr><td colspan="7">SSL-VPN設定なし</td></tr>'}
                    </table>
                </div>
            </div>'''

    def _generate_security_profiles_section(self, section_num: str = "2.6", section_id: str = "vdom-root-security_profiles", vdom: str = None) -> str:
        """セキュリティプロファイルセクション（VDOM単位）"""
        # VDOMでフィルタリング
        security_profiles = self._filter_by_vdom(self.config.security_profiles, vdom) if vdom else self.config.security_profiles
        antivirus = self._filter_by_vdom(self.config.security_profiles_detail.antivirus, vdom) if vdom else self.config.security_profiles_detail.antivirus
        webfilter = self._filter_by_vdom(self.config.security_profiles_detail.webfilter, vdom) if vdom else self.config.security_profiles_detail.webfilter
        app_control = self._filter_by_vdom(self.config.security_profiles_detail.app_control, vdom) if vdom else self.config.security_profiles_detail.app_control
        ips = self._filter_by_vdom(self.config.security_profiles_detail.ips, vdom) if vdom else self.config.security_profiles_detail.ips
        ssl_inspection = self._filter_by_vdom(self.config.security_profiles_detail.ssl_inspection, vdom) if vdom else self.config.security_profiles_detail.ssl_inspection

        # プロファイル一覧
        profile_rows = ""
        for profile in security_profiles:
            profile_rows += f'''<tr>
                <td>{self.escape(profile.name)}</td>
                <td>{self.escape(profile.profile_type)}</td>
                <td>{'有効' if profile.enabled else '無効'}</td>
                <td>{self.escape(profile.description)}</td>
            </tr>'''

        # 詳細プロファイル - アンチウイルス
        av_rows = ""
        for av in antivirus:
            protocols_display = self._list_to_str(av.protocols) if av.protocols else "-"
            av_rows += f'''<tr>
                <td>{self.escape(av.name)}</td>
                <td>{'有効' if av.enabled else '無効'}</td>
                <td>{self.escape(av.scan_mode)}</td>
                <td>{protocols_display}</td>
                <td>{self.escape(av.action)}</td>
            </tr>'''

        # 詳細プロファイル - Webフィルタ
        wf_rows = ""
        for wf in webfilter:
            categories_display = self._list_to_str(wf.categories[:10]) if wf.categories else "-"
            if len(wf.categories) > 10:
                categories_display += f" ... (他{len(wf.categories) - 10}件)"
            wf_rows += f'''<tr>
                <td>{self.escape(wf.name)}</td>
                <td>{'有効' if wf.enabled else '無効'}</td>
                <td>{categories_display}</td>
                <td>{self.escape(wf.action)}</td>
            </tr>'''

        # 詳細プロファイル - アプリケーションコントロール
        app_rows = ""
        for app in app_control:
            categories_display = self._list_to_str(app.categories[:10]) if app.categories else "-"
            if len(app.categories) > 10:
                categories_display += f" ... (他{len(app.categories) - 10}件)"
            app_rows += f'''<tr>
                <td>{self.escape(app.name)}</td>
                <td>{'有効' if app.enabled else '無効'}</td>
                <td>{categories_display}</td>
                <td>{self.escape(app.action)}</td>
            </tr>'''

        # 詳細プロファイル - IPS
        ips_rows = ""
        for i in ips:
            signatures_display = f"{len(i.signatures)}件" if i.signatures else "-"
            ips_rows += f'''<tr>
                <td>{self.escape(i.name)}</td>
                <td>{'有効' if i.enabled else '無効'}</td>
                <td>{signatures_display}</td>
                <td>{self.escape(i.action)}</td>
            </tr>'''

        # 詳細プロファイル - SSLインスペクション
        ssl_rows = ""
        for ssl in ssl_inspection:
            ssl_rows += f'''<tr>
                <td>{self.escape(ssl.name)}</td>
                <td>{'有効' if ssl.enabled else '無効'}</td>
                <td>{self.escape(ssl.mode)}</td>
            </tr>'''

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} セキュリティプロファイル（UTM）</h3>

                <h4>プロファイル一覧</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>プロファイル名</th><th>タイプ</th><th>有効/無効</th><th>説明</th></tr>
                        {profile_rows if profile_rows else '<tr><td colspan="4">プロファイル設定なし</td></tr>'}
                    </table>
                </div>

                <h4>アンチウイルスプロファイル</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>プロファイル名</th><th>有効/無効</th><th>スキャンモード</th><th>スキャン対象プロトコル</th><th>アクション</th></tr>
                        {av_rows if av_rows else '<tr><td colspan="5">アンチウイルスプロファイル設定なし</td></tr>'}
                    </table>
                </div>

                <h4>Webフィルタプロファイル</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>プロファイル名</th><th>有効/無効</th><th>適用カテゴリ</th><th>アクション</th></tr>
                        {wf_rows if wf_rows else '<tr><td colspan="4">Webフィルタプロファイル設定なし</td></tr>'}
                    </table>
                </div>

                <h4>アプリケーションコントロールプロファイル</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>プロファイル名</th><th>有効/無効</th><th>適用カテゴリ/シグネチャ</th><th>アクション</th></tr>
                        {app_rows if app_rows else '<tr><td colspan="4">アプリケーションコントロールプロファイル設定なし</td></tr>'}
                    </table>
                </div>

                <h4>IPSプロファイル</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>プロファイル名</th><th>有効/無効</th><th>適用シグネチャ</th><th>アクション</th></tr>
                        {ips_rows if ips_rows else '<tr><td colspan="4">IPSプロファイル設定なし</td></tr>'}
                    </table>
                </div>

                <h4>SSLインスペクションプロファイル</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>プロファイル名</th><th>有効/無効</th><th>モード</th></tr>
                        {ssl_rows if ssl_rows else '<tr><td colspan="3">SSLインスペクションプロファイル設定なし</td></tr>'}
                    </table>
                </div>
            </div>'''

    def _generate_cluster_overview_section(self, section_num: str = "1.1", section_id: str = "global-cluster_overview") -> str:
        """クラスタ概要セクション（HAクラスタ時のみ表示）"""
        if not self.is_cluster or self.cluster_config is None:
            return ""  # クラスタ構成でない場合は何も出力しない

        cluster_info = self.cluster_config.cluster_info
        differences = self.cluster_config.config_differences

        # メンバー一覧テーブル
        member_rows = ""
        for member in cluster_info.members:
            role_class = "primary" if member.role == HARole.PRIMARY else "secondary"
            role_badge = f'<span class="badge bg-{"success" if member.role == HARole.PRIMARY else "info"}">{member.role.value}</span>'
            member_rows += f'''<tr>
                <td>{role_badge}</td>
                <td><strong>{self.escape(member.hostname)}</strong></td>
                <td>{self.escape(member.model) if member.model else "-"}</td>
                <td>{self.escape(member.os_version) if member.os_version else "-"}</td>
                <td>{self.escape(member.priority) if member.priority else "-"}</td>
                <td><code>{self.escape(member.ha_mgmt_ip) if member.ha_mgmt_ip else "-"}</code></td>
                <td><code>{self.escape(member.serial_number) if member.serial_number else "-"}</code></td>
                <td>{self.escape(Path(member.source_file).name)}</td>
            </tr>'''

        # 設定差分テーブル
        diff_rows = ""
        if differences:
            for diff in differences:
                diff_rows += f'''<tr>
                    <td>{self.escape(diff.section)}</td>
                    <td>{self.escape(diff.item)}</td>
                    <td><code>{self.escape(diff.primary_value)}</code></td>
                    <td><code>{self.escape(diff.secondary_value)}</code></td>
                    <td>{self.escape(diff.description)}</td>
                </tr>'''

        diff_section = ""
        if diff_rows:
            diff_section = f'''
                <h4>設定差分</h4>
                <div class="warning-box">
                    <strong>注意:</strong> Primary/Secondary間で以下の設定差分が検出されました。
                </div>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>セクション</th><th>項目</th><th>Primary</th><th>Secondary</th><th>備考</th></tr>
                        {diff_rows}
                    </table>
                </div>'''

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} クラスタ概要</h3>

                <div class="info-grid">
                    <div class="info-card">
                        <h4>クラスタ情報</h4>
                        <table class="table table-sm table-bordered">
                            <tr><td>クラスタ名</td><td><strong>{self.escape(cluster_info.cluster_name)}</strong></td></tr>
                            <tr><td>グループID</td><td>{self.escape(cluster_info.group_id)}</td></tr>
                            <tr><td>HAモード</td><td>{self.escape(cluster_info.ha_mode.value)}</td></tr>
                            <tr><td>メンバー数</td><td>{cluster_info.get_member_count()}</td></tr>
                        </table>
                    </div>
                </div>

                <h4>クラスタメンバー</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>役割</th><th>ホスト名</th><th>モデル</th><th>OS Ver</th><th>優先度</th><th>HA管理IP</th><th>シリアル番号</th><th>設定ファイル</th></tr>
                        {member_rows if member_rows else '<tr><td colspan="8">メンバー情報なし</td></tr>'}
                    </table>
                </div>
                {diff_section}
            </div>'''

    def _generate_ha_section(self, section_num: str = "1.4", section_id: str = "global-ha") -> str:
        """HA設定セクション（グローバル）"""
        ha = self.config.ha

        if ha.mode == HAMode.STANDALONE:
            return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} HA設定</h3>
                <p>HA設定なし（スタンドアロン）</p>
            </div>'''

        # ハートビートインターフェース
        hb_rows = ""
        if ha.heartbeat_interfaces_detail:
            for hb in ha.heartbeat_interfaces_detail:
                hb_rows += f'''<tr>
                    <td>{self.escape(hb.interface)}</td>
                    <td>{self.escape(hb.priority) if hb.priority else "-"}</td>
                </tr>'''
        else:
            # 詳細情報がない場合はシンプルなリスト表示
            for iface in ha.heartbeat_interfaces:
                hb_rows += f'''<tr>
                    <td>{self.escape(iface)}</td>
                    <td>-</td>
                </tr>'''

        hb_section = ""
        if hb_rows:
            hb_section = f'''
                <h4>ハートビートインターフェース</h4>
                <div class="table-responsive">
                    <table class="table table-sm table-bordered">
                        <tr><th>インターフェース</th><th>優先度</th></tr>
                        {hb_rows}
                    </table>
                </div>'''

        # HA管理インターフェース
        mgmt_rows = ""
        if ha.ha_mgmt_interfaces:
            for mgmt in ha.ha_mgmt_interfaces:
                mgmt_rows += f'''<tr>
                    <td>{self.escape(mgmt.id)}</td>
                    <td>{self.escape(mgmt.interface)}</td>
                    <td><code>{self.escape(mgmt.dst) if mgmt.dst else '-'}</code></td>
                    <td><code>{self.escape(mgmt.gateway) if mgmt.gateway else '-'}</code></td>
                </tr>'''

        mgmt_section = ""
        if mgmt_rows:
            mgmt_section = f'''
                <h4>HA管理インターフェース</h4>
                <div class="table-responsive">
                    <table class="table table-sm table-bordered">
                        <tr><th>ID</th><th>インターフェース</th><th>管理IPアドレス</th><th>ゲートウェイ</th></tr>
                        {mgmt_rows}
                    </table>
                </div>'''

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} HA設定</h3>

                <div class="info-grid">
                    <div class="info-card">
                        <h4>HA基本設定</h4>
                        <table class="table table-sm table-bordered">
                            <tr><td>HAモード</td><td><strong>{self.escape(ha.mode.value)}</strong></td></tr>
                            <tr><td>グループID</td><td>{self.escape(ha.group_id)}</td></tr>
                            <tr><td>グループ名</td><td>{self.escape(ha.group_name) if ha.group_name else "-"}</td></tr>
                            <tr><td>優先度</td><td>{self.escape(ha.priority) if ha.priority else "-"}</td></tr>
                            <tr><td>プリエンプト</td><td>{'有効' if ha.preempt else '無効'}</td></tr>
                            <tr><td>HA管理ステータス</td><td>{'有効' if ha.ha_mgmt_status else '無効'}</td></tr>
                        </table>
                    </div>
                    <div class="info-card">
                        <h4>監視設定</h4>
                        <table class="table table-sm table-bordered">
                            <tr><td>監視インターフェース</td><td>{self.escape(self._list_to_str(ha.monitor_interfaces))}</td></tr>
                            <tr><td>HAインターフェース</td><td>{self.escape(self._list_to_str(ha.ha_interfaces))}</td></tr>
                        </table>
                    </div>
                    <div class="info-card">
                        <h4>同期・セキュリティ</h4>
                        <table class="table table-sm table-bordered">
                            <tr><td>セッション同期</td><td>{'有効' if ha.session_sync else '無効'}</td></tr>
                            <tr><td>セッションピックアップ</td><td>{'有効' if ha.session_pickup else '無効'}</td></tr>
                            <tr><td>ハートビート間隔</td><td>{self._with_default(ha.hb_interval, 'ha_hb_interval')}</td></tr>
                            <tr><td>ハートビート損失閾値</td><td>{self._with_default(ha.hb_lost_threshold, 'ha_hb_lost_threshold')}</td></tr>
                            <tr><td>暗号化</td><td>{'有効' if ha.encryption else '無効'}</td></tr>
                            <tr><td>認証</td><td>{'有効' if ha.authentication else '無効'}</td></tr>
                        </table>
                    </div>
                </div>
                {hb_section}
                {mgmt_section}
            </div>'''

    def _generate_logging_section(self, section_num: str = "1.5", section_id: str = "global-logging") -> str:
        """ログ・監視設定セクション（グローバル）"""
        logging = self.config.logging

        # Syslog
        syslog_rows = ""
        for syslog in logging.syslog_servers:
            log_types_display = self._list_to_str(syslog.log_types) if syslog.log_types else "全種別"
            syslog_rows += f'''<tr>
                <td><code>{self.escape(syslog.server)}</code></td>
                <td>{self.escape(syslog.port)}</td>
                <td>{log_types_display}</td>
                <td>{self.escape(syslog.status)}</td>
            </tr>'''

        # SNMP
        snmp_rows = ""
        for snmp in logging.snmp:
            trap_hosts_display = self._list_to_str(snmp.trap_hosts) if snmp.trap_hosts else "-"
            hosts_display = self._list_to_str(snmp.hosts) if snmp.hosts else "-"
            snmp_rows += f'''<tr>
                <td>{'有効' if snmp.enabled else '無効'}</td>
                <td>{self.escape(snmp.version)}</td>
                <td>{self.escape(snmp.community) if snmp.community else self.escape(snmp.username)}</td>
                <td>{hosts_display}</td>
                <td>{trap_hosts_display}</td>
            </tr>'''

        # 集中管理（表形式）
        central_mgmt_rows = ""
        if logging.fortianalyzer_server:
            status_display = self.escape(logging.fortianalyzer_status) if logging.fortianalyzer_status else "-"
            central_mgmt_rows += f'''<tr>
                <td>FortiAnalyzer</td>
                <td><code>{self.escape(logging.fortianalyzer_server)}</code></td>
                <td>{status_display}</td>
            </tr>'''
        if logging.panorama_server:
            central_mgmt_rows += f'''<tr>
                <td>Panorama</td>
                <td><code>{self.escape(logging.panorama_server)}</code></td>
                <td>-</td>
            </tr>'''

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} ログ・監視設定</h3>

                <h4>ログ転送</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>サーバーIPアドレス</th><th>ポート</th><th>転送ログ種別</th><th>状態</th></tr>
                        {syslog_rows if syslog_rows else '<tr><td colspan="4">Syslog設定なし</td></tr>'}
                    </table>
                </div>

                <h4>集中管理</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>管理システム</th><th>サーバーIPアドレス</th><th>状態</th></tr>
                        {central_mgmt_rows if central_mgmt_rows else '<tr><td colspan="3">集中管理設定なし（FortiAnalyzer/Panorama未設定）</td></tr>'}
                    </table>
                </div>

                <h4>SNMP</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>SNMP有効化</th><th>バージョン</th><th>コミュニティ名/ユーザー名</th><th>ホスト</th><th>トラップ送信先IPアドレス</th></tr>
                        {snmp_rows if snmp_rows else '<tr><td colspan="5">SNMP設定なし</td></tr>'}
                    </table>
                </div>
            </div>'''
