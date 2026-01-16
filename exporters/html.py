#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTMLエクスポーター
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.config import (
    ConfigModel, PolicyAction, HAMode, DeviceType
)
from exporters.utils import (
    STATIC_DIR, load_isdb, load_css, load_search_js, HtmlFormatter
)

logger = logging.getLogger(__name__)


class HTMLExporter:
    """HTML形式でパラメータシートを出力（VDOM/vsys単位）"""

    # グローバルセクション定義（VDOM横断の設定）
    GLOBAL_SECTIONS = [
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

    def __init__(self, config: ConfigModel, sections: List[str] = None, for_pdf: bool = False):
        """HTMLエクスポーターを初期化
        
        Args:
            config: 設定データモデル
            sections: 出力するセクションのリスト（Noneの場合は全セクション）
            for_pdf: PDF用に最適化する場合True（JavaScript削除など）
        """
        self.config = config
        # セクション指定は現在未使用（将来の拡張用に保持）
        self.sections = sections
        self.for_pdf = for_pdf

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
        isdb = load_isdb()
        # IDをそのまま検索
        if isdb_id in isdb:
            return isdb[isdb_id]
        # 数字のみの場合もそのまま検索
        id_str = str(isdb_id).strip()
        if id_str in isdb:
            return isdb[id_str]
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
        for i, (key, title, _) in enumerate(self.GLOBAL_SECTIONS, 1):
            toc.append(f'                        <li><a href="#global-{key}">1.{i} {title}</a></li>')
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

        for i, (key, title, method_name) in enumerate(self.GLOBAL_SECTIONS, 1):
            method = getattr(self, method_name)
            section_html = method(section_num=f"1.{i}", section_id=f"global-{key}")
            sections_html.append(section_html)

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
    </script>'''

        return f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.escape(device_info.device_type.value)} パラメータシート - {self.escape(device_info.hostname)}</title>
    <style>
{load_css()}
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
            route_rows += f'''<tr>
                <td>{self.escape(route.name)}</td>
                <td><code>{self.escape(route.destination)}</code></td>
                <td><code>{self.escape(route.gateway)}</code></td>
                <td>{self.escape(route.interface)}</td>
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
            </div>'''

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

        policy_rows = [
            f'''<tr>
                <td>{idx}</td>
                <td>{self.escape(policy.policy_id)}</td>
                <td>{self.escape(policy.name)} {"" if policy.enabled else '<span class="disabled">(無効)</span>'}</td>
                <td>{self._list_to_lines(policy.source_interface)}</td>
                <td>{self._list_to_lines(policy.destination_interface)}</td>
                <td>{self._list_to_lines(policy.source_address)}</td>
                <td>{self._list_to_lines(policy.destination_address)}</td>
                <td>{self._services_to_badges(policy.service)}</td>
                <td class="{self._get_action_class(policy.action)}">{self.escape(policy.action.value)}</td>
                <td>{"有効" if policy.nat_enabled else "無効"}</td>
                <td>{self._security_profiles_to_badges(policy.security_profiles)}</td>
                <td>{"有効" if policy.log_enabled else "無効"}</td>
                <td>{self.escape(policy.description)}</td>
            </tr>'''
            for idx, policy in enumerate(firewall_policies, 1)
        ]

        # Local-in ポリシー
        local_in_rows = [
            f'''<tr>
                <td>{idx}</td>
                <td>{self.escape(policy.policy_id)}</td>
                <td>{self.escape(policy.name)} {"" if policy.enabled else '<span class="disabled">(無効)</span>'}</td>
                <td>{self.escape(policy.source_interface)}</td>
                <td>{self._list_to_lines(policy.source_address)}</td>
                <td>{self._list_to_lines(policy.destination_address)}</td>
                <td>{self._services_to_badges(policy.service)}</td>
                <td class="{self._get_action_class(policy.action)}">{self.escape(policy.action.value)}</td>
                <td>{self.escape(policy.description)}</td>
            </tr>'''
            for idx, policy in enumerate(local_in_policies, 1)
        ]

        return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} ファイアウォールポリシー</h3>

                <div class="summary-box">
                    <strong>ポリシー数:</strong> {len(firewall_policies)} ルール
                </div>

                <h4>ポリシー一覧</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>No</th><th>ID</th><th>ポリシー名</th><th>送信元IF</th><th>宛先IF</th><th>送信元アドレス</th><th>宛先アドレス</th><th>サービス</th><th>アクション</th><th>NAT</th><th>セキュリティプロファイル</th><th>ログ</th><th>備考</th></tr>
                        {''.join(policy_rows) if policy_rows else '<tr><td colspan="13">ポリシー設定なし</td></tr>'}
                    </table>
                </div>

                <h4>Local-in ポリシー</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>No</th><th>ID</th><th>ポリシー名</th><th>送信元IF</th><th>送信元アドレス</th><th>宛先アドレス</th><th>サービス</th><th>アクション</th><th>備考</th></tr>
                        {''.join(local_in_rows) if local_in_rows else '<tr><td colspan="9">Local-in ポリシー設定なし</td></tr>'}
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

    def _generate_ha_section(self, section_num: str = "1.3", section_id: str = "global-ha") -> str:
        """HA設定セクション（グローバル）"""
        ha = self.config.ha

        if ha.mode == HAMode.STANDALONE:
            return f'''
            <div id="{section_id}" class="subsection">
                <h3>{section_num} HA設定</h3>
                <p>HA設定なし（スタンドアロン）</p>
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
                            <tr><td>優先度</td><td>{self.escape(ha.priority)}</td></tr>
                            <tr><td>プリエンプト</td><td>{'有効' if ha.preempt else '無効'}</td></tr>
                        </table>
                    </div>
                    <div class="info-card">
                        <h4>監視設定</h4>
                        <table class="table table-sm table-bordered">
                            <tr><td>監視インターフェース</td><td>{self.escape(self._list_to_str(ha.monitor_interfaces))}</td></tr>
                            <tr><td>HAインターフェース</td><td>{self.escape(self._list_to_str(ha.ha_interfaces))}</td></tr>
                        </table>
                    </div>
                </div>
            </div>'''

    def _generate_logging_section(self, section_num: str = "1.4", section_id: str = "global-logging") -> str:
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

        # 集中管理
        central_mgmt = ""
        if logging.fortianalyzer_server:
            central_mgmt = f"FortiAnalyzer: <code>{self.escape(logging.fortianalyzer_server)}</code> (状態: {self.escape(logging.fortianalyzer_status)})"
        elif logging.panorama_server:
            central_mgmt = f"Panorama: <code>{self.escape(logging.panorama_server)}</code>"

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
                <p>{central_mgmt if central_mgmt else '集中管理設定なし（FortiAnalyzer/Panorama未設定）'}</p>

                <h4>SNMP</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>SNMP有効化</th><th>バージョン</th><th>コミュニティ名/ユーザー名</th><th>ホスト</th><th>トラップ送信先IPアドレス</th></tr>
                        {snmp_rows if snmp_rows else '<tr><td colspan="5">SNMP設定なし</td></tr>'}
                    </table>
                </div>
            </div>'''
