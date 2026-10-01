#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTMLエクスポーター
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from exporters.insights import render_security, render_topology
from exporters.investigation import render_flow
from exporters.sections import section_selected
from exporters.utils import (
    HtmlFormatter,
    load_css,
    load_isdb,
    load_search_js,
    load_tooltip_js,
)
from models.cluster import ClusterConfig
from models.config import ConfigModel, DeviceType

logger = logging.getLogger(__name__)


from exporters.html_parts.global_sections import HTMLGlobalMixin
from exporters.html_parts.network import HTMLNetworkMixin
from exporters.html_parts.tooltips import HTMLTooltipsMixin
from exporters.html_parts.vdom import HTMLVDOMMixin


class HTMLExporter(HTMLTooltipsMixin, HTMLNetworkMixin, HTMLVDOMMixin, HTMLGlobalMixin):
    """HTML形式でパラメータシートを出力（VDOM/vsys単位）"""

    # グローバルセクション定義（VDOM横断の設定）
    GLOBAL_SECTIONS = [
        ("security_analysis", "セキュリティ診断", "_generate_security_analysis_section"),
        ("topology", "推定ネットワーク構造", "_generate_topology_section"),
        ("flow_analysis", "通信候補の確認", "_generate_flow_section"),
        ("cluster_overview", "クラスタ概要", "_generate_cluster_overview_section"),
        ("device_info", "機器概要", "_generate_device_info_section"),
        ("system_settings", "システム設定", "_generate_system_settings_section"),
        ("ha", "HA設定", "_generate_ha_section"),
        ("logging", "ログ・監視設定", "_generate_logging_section"),
    ]

    # VDOM単位セクション定義
    VDOM_SECTIONS = [
        ("network", "ネットワーク設定", "_generate_network_section"),
        ("objects", "オブジェクト定義", "_generate_objects_section"),
        ("policies", "ファイアウォールポリシー", "_generate_policies_section"),
        ("nat", "NAT設定", "_generate_nat_section"),
        ("vpn", "VPN設定", "_generate_vpn_section"),
        ("security_profiles", "セキュリティプロファイル", "_generate_security_profiles_section"),
    ]

    def __init__(
        self,
        config: Union[ConfigModel, ClusterConfig],
        sections: List[str] = None,
        for_pdf: bool = False,
    ):
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

        # Output section selection is shared with the Excel exporter.
        self.sections = sections
        self.for_pdf = for_pdf
        # ISDBデータをキャッシュ（ループ内での関数呼び出し削減）
        self._isdb_cache = load_isdb()
        # 設定内に登場する Internet Service 名（ISDB未整備でも識別できるように）
        self._internet_service_names = set()
        try:
            for p in getattr(self.config, "firewall_policies", []) or []:
                for n in getattr(p, "internet_service_name", []) or []:
                    if n:
                        self._internet_service_names.add(str(n))
        except Exception:
            pass
        # ツールチップ生成キャッシュ（同じオブジェクトの重複生成を防止）
        self._tooltip_cache: Dict[tuple, str] = {}
        # オブジェクト辞書を構築（ツールチップ用）
        self._build_object_lookups()

    # フォーマッター（委譲）
    escape = staticmethod(HtmlFormatter.escape)
    _list_to_str = staticmethod(HtmlFormatter.list_to_str)
    _list_to_lines = staticmethod(HtmlFormatter.list_to_lines)

    def _with_default(self, value: Optional[str], default_key: str) -> str:
        """値が空の場合はデフォルト値を表示（グレー表示）"""
        default = "未記載・既定値未検証"
        return HtmlFormatter.with_default(value, default)

    def _list_with_default(self, items: List[Any], default_key: str) -> str:
        """リストが空の場合はデフォルト値を表示"""
        default = "未記載・既定値未検証"
        return HtmlFormatter.list_with_default(items, default)

    # バッジ色マッピング
    SECURITY_PROFILE_COLORS = {
        "av": "danger",
        "antivirus": "danger",
        "ips": "warning",
        "ssl": "info",
        "ssl-ssh-profile": "info",
        "webfilter": "primary",
        "web-filter": "primary",
        "application": "success",
        "app-ctrl": "success",
        "dlp": "secondary",
        "emailfilter": "dark",
        "dns": "light",
        "dnsfilter": "light",
    }

    SERVICE_COLORS = {
        "all": "danger",
        "http": "primary",
        "https": "primary",
        "web access": "primary",
        "ssh": "dark",
        "telnet": "dark",
        "rdp": "dark",
        "vnc": "dark",
        "dns": "info",
        "ntp": "info",
        "snmp": "info",
        "syslog": "info",
        "icmp": "info",
        "ping": "info",
        "smtp": "warning",
        "smtps": "warning",
        "pop3": "warning",
        "pop3s": "warning",
        "imap": "warning",
        "imaps": "warning",
        "ftp": "success",
        "tftp": "success",
        "smb": "success",
        "nfs": "success",
    }

    def _get_vdom_label(self) -> str:
        """デバイスタイプに応じたラベルを返す（VDOM/vsys）"""
        if self.config.device_info.device_type == DeviceType.PALOALTO:
            return "vsys"
        return "VDOM"

    def export(self, output_path: Optional[str] = None) -> str:
        """HTMLを生成"""
        html_content = self._generate_html()

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

        return html_content

    def _section_selected(self, key: str) -> bool:
        return section_selected(self.sections, key, "html")

    def _generate_security_analysis_section(
        self, section_num="1.1", section_id="global-security_analysis"
    ):
        return render_security(
            self.config, section_num, section_id, self.cluster_config is not None
        )

    def _generate_topology_section(self, section_num="1.2", section_id="global-topology"):
        return render_topology(
            self.config, section_num, section_id, self.for_pdf, self.cluster_config is not None
        )

    def _generate_flow_section(self, section_num="1.3", section_id="global-flow_analysis"):
        return render_flow(self.config, section_num, section_id, self.for_pdf)

    def _generate_toc(self) -> str:
        """階層的目次を生成（グローバル設定 → 各VDOM/vsys）"""
        toc = []
        vdom_label = self._get_vdom_label()

        # 1. グローバル設定セクション
        toc.append('                <li><a href="#global">1. グローバル設定</a>')
        toc.append("                    <ul>")
        section_num = 1
        for key, title, _ in self.GLOBAL_SECTIONS:
            if not self._section_selected(key):
                continue
            # クラスタ概要はクラスタ構成時のみ表示
            if key == "cluster_overview" and not self.is_cluster:
                continue
            toc.append(
                f'                        <li><a href="#global-{key}">1.{section_num} {title}</a></li>'
            )
            section_num += 1
        toc.append("                    </ul>")
        toc.append("                </li>")

        # 2. 各VDOM/vsysセクション
        vdom_list = self._get_vdom_list()
        for vdom_idx, vdom in enumerate(
            (
                vdom_list
                if any(self._section_selected(key) for key, _, _ in self.VDOM_SECTIONS)
                else []
            ),
            2,
        ):
            toc.append(
                f'                <li><a href="#vdom-{self.escape(vdom)}">{vdom_idx}. {vdom_label}: {self.escape(vdom)}</a>'
            )
            toc.append("                    <ul>")
            for i, (key, title, _) in enumerate(self.VDOM_SECTIONS, 1):
                if not self._section_selected(key):
                    continue
                toc.append(
                    f'                        <li><a href="#vdom-{self.escape(vdom)}-{key}">{vdom_idx}.{i} {title}</a></li>'
                )
            toc.append("                    </ul>")
            toc.append("                </li>")

        return "\n".join(toc)

    def _generate_sections(self) -> str:
        """グローバル設定とVDOM単位セクションを生成"""
        sections_html = []
        vdom_label = self._get_vdom_label()

        # 1. グローバル設定セクション
        sections_html.append(
            f"""
        <section id="global" class="vdom-section global-section">
            <h2>1. グローバル設定</h2>"""
        )

        section_num = 1
        for key, title, method_name in self.GLOBAL_SECTIONS:
            if not self._section_selected(key):
                continue
            # クラスタ概要はクラスタ構成時のみ表示
            if key == "cluster_overview" and not self.is_cluster:
                continue
            method = getattr(self, method_name)
            section_html = method(section_num=f"1.{section_num}", section_id=f"global-{key}")
            sections_html.append(section_html)
            section_num += 1

        sections_html.append("        </section>")

        # 2. 各VDOM/vsysセクション
        vdom_list = self._get_vdom_list()
        for vdom_idx, vdom in enumerate(
            (
                vdom_list
                if any(self._section_selected(key) for key, _, _ in self.VDOM_SECTIONS)
                else []
            ),
            2,
        ):
            sections_html.append(
                f"""
        <section id="vdom-{self.escape(vdom)}" class="vdom-section">
            <h2>{vdom_idx}. {vdom_label}: {self.escape(vdom)}</h2>"""
            )

            for i, (key, title, method_name) in enumerate(self.VDOM_SECTIONS, 1):
                if not self._section_selected(key):
                    continue
                method = getattr(self, method_name)
                section_html = method(
                    section_num=f"{vdom_idx}.{i}",
                    section_id=f"vdom-{self.escape(vdom)}-{key}",
                    vdom=vdom,
                )
                sections_html.append(section_html)

            sections_html.append("        </section>")

        return "\n".join(sections_html)

    def _generate_html(self) -> str:
        """HTML全体を生成"""
        device_info = self.config.device_info
        today = datetime.now().strftime("%Y年%m月%d日")

        # 検索ボックス（PDF用の場合は非表示）
        search_box = (
            ""
            if self.for_pdf
            else f"""        <div class="document-tools" role="search" aria-label="シート内検索">
            <div class="search-box">
                <input type="search" id="searchInput" aria-label="パラメータシート内を検索" placeholder="IP・オブジェクト名・設定値を検索" autocomplete="off">
                <button type="button" id="searchBtn" onclick="performSearch()">検索</button>
                <button type="button" id="clearBtn" onclick="clearSearch()" style="display:none;">クリア</button>
                <span id="searchNavigation" class="search-navigation" hidden>
                    <button type="button" onclick="moveSearchMatch(-1)" aria-label="前の検索結果">↑ 前へ</button>
                    <button type="button" onclick="moveSearchMatch(1)" aria-label="次の検索結果">↓ 次へ</button>
                </span>
                <span id="searchResults" class="search-results" role="status" aria-live="polite"></span>
            </div>
            <p class="search-help">/ で検索に移動 · Enter で次へ · Shift + Enter で前へ · Esc で解除</p>
        </div>"""
        )

        # JavaScript（PDF用の場合は削除）
        script_tag = (
            ""
            if self.for_pdf
            else f"""    <script>
{load_search_js()}
{load_tooltip_js()}
    </script>"""
        )

        # PDF生成では WeasyPrint 側でキャッシュ済みCSSを渡すため、HTML内にCSSを重複展開しない。
        css_content = "" if self.for_pdf else load_css()

        return f"""<!DOCTYPE html>
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
    <a class="skip-link" href="#document-content">本文へ移動</a>
    <div class="container">
        <header>
            <p class="doc-kind">{self.escape(device_info.device_type.value)} パラメータシート</p>
            <h1>{self.escape(device_info.hostname or device_info.model or device_info.device_type.value)}</h1>
            <div class="meta">
                <div class="meta-item"><span class="meta-label">機種</span><span class="meta-value">{self.escape(device_info.model or device_info.device_type.value)}</span></div>
                <div class="meta-item"><span class="meta-label">OS バージョン</span><span class="meta-value">{self.escape(device_info.os_version)}</span></div>
                <div class="meta-item"><span class="meta-label">設定ファイル</span><span class="meta-value">{self.escape(Path(self.config.source_file).name)}</span></div>
                <div class="meta-item"><span class="meta-label">作成日</span><span class="meta-value">{today}</span></div>
            </div>
            <div class="document-summary" aria-label="設定の件数">
                <span><strong>{len(self.config.interfaces)}</strong> インターフェース</span>
                <span><strong>{len(self.config.firewall_policies)}</strong> ポリシー</span>
                <span><strong>{len(self.config.objects.addresses)}</strong> アドレス</span>
                <span><strong>{len(self._get_vdom_list())}</strong> {self._get_vdom_label()}</span>
            </div>
        </header>
{search_box}

        <nav class="toc" aria-label="パラメータシートの目次">
            <h2>目次</h2>
            <ul>
{self._generate_toc()}
            </ul>
        </nav>

<main id="document-content" tabindex="-1">
{self._generate_sections()}
        </main>

        <footer>
            <p>{self.escape(device_info.device_type.value)} Version: {self.escape(device_info.os_version)} | Device: {self.escape(device_info.hostname)}</p>
        </footer>
    </div>
{script_tag}
</body>
</html>"""
