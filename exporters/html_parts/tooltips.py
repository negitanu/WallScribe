"""HTML tooltips rendering."""

from typing import Any, Dict, List

from analyzers.review import default_provenance
from exporters.utils import HtmlFormatter


class HTMLTooltipsMixin:
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

    def _security_profiles_to_badges(self, profiles: List[str]) -> str:
        """セキュリティプロファイルをBootstrapバッジで表示"""
        return HtmlFormatter.to_badges(profiles, self.SECURITY_PROFILE_COLORS, extract_key=True)

    def _services_to_badges(self, services: List[str]) -> str:
        """サービスをBootstrapバッジで表示"""
        return HtmlFormatter.to_badges(services, self.SERVICE_COLORS)

    def _get_vdom_list(self) -> List[str]:
        """出力対象のVDOM/vsysリストを取得"""
        vdoms = list(self.config.device_info.vdom_list) or ["root"]
        objects = self.config.objects
        if (
            any(
                item.vdom == "shared"
                for items in (
                    objects.addresses,
                    objects.address_groups,
                    objects.services,
                    objects.service_groups,
                )
                for item in items
            )
            and "shared" not in vdoms
        ):
            vdoms.append("shared")
        return vdoms

    def _filter_by_vdom(self, items: List[Any], vdom: str) -> List[Any]:
        """指定VDOMの項目のみをフィルタリング"""
        return [item for item in items if getattr(item, "vdom", "root") == vdom]

    def _with_default_annotation(self, value: Any, field_path: str) -> str:
        """値がデフォルトの場合にアノテーションを追加"""
        is_default = field_path in self.config.default_fields
        if is_default:
            provenance = default_provenance(self.config, field_path)
            if provenance["status"] != "documented_default":
                return "未記載・既定値未検証"
            return self.escape(str(value)) + "（公式資料の既定値）"
        return HtmlFormatter.with_default_annotation(value, False)

    @staticmethod
    def _format_protocol_number(protocol: str) -> str:
        """プロトコル番号を名前に変換"""
        protocol_map = {"0": "ALL", "6": "TCP", "17": "UDP", "1": "ICMP"}
        return protocol_map.get(str(protocol).strip(), str(protocol))

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
        html.append("<thead><tr>")
        html.append(f"<th>{self.escape(rows[0][0])}</th>")
        html.append(f"<th>{self.escape(rows[0][1])}</th>")
        html.append("</tr></thead>")
        # データ行
        html.append("<tbody>")
        for key, value in rows[1:]:
            html.append("<tr>")
            html.append(f'<td class="tooltip-key">{self.escape(str(key))}</td>')
            html.append(f'<td class="tooltip-value">{self.escape(str(value))}</td>')
            html.append("</tr>")
        html.append("</tbody>")
        html.append("</table>")
        return "".join(html)

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
        # 設定内に Internet Service 名として登場する（ISDBに無くても扱う）
        if name in getattr(self, "_internet_service_names", set()):
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
        addr = self._address_lookup.get((vdom, name)) or self._address_lookup.get(("shared", name))
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
        grp = self._address_group_lookup.get((vdom, name)) or self._address_group_lookup.get(
            ("shared", name)
        )
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
        svc = self._service_lookup.get((vdom, name)) or self._service_lookup.get(("shared", name))
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
        grp = self._service_group_lookup.get((vdom, name)) or self._service_group_lookup.get(
            ("shared", name)
        )
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
        if self.for_pdf:
            return self.escape(text)
        if not tooltip:
            return self.escape(text)
        return f'<span class="has-tooltip" data-tooltip="{self.escape(tooltip)}">{self.escape(text)}</span>'

    def _interface_with_tooltip(self, name: str, vdom: str = "root") -> str:
        """インターフェース名をツールチップ付きで表示"""
        if self.for_pdf:
            return self.escape(name)
        tooltip = self._get_interface_tooltip(name, vdom)
        return self._with_tooltip(name, tooltip)

    def _address_with_tooltip(self, name: str, vdom: str = "root") -> str:
        """アドレス名をツールチップ付きで表示"""
        if self.for_pdf:
            return self.escape(name)
        tooltip = self._get_address_tooltip(name, vdom)
        return self._with_tooltip(name, tooltip)

    def _service_with_tooltip(self, name: str, vdom: str = "root") -> str:
        """サービス名をツールチップ付きで表示"""
        if self.for_pdf:
            return self.escape(name)
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
                if self.for_pdf:
                    lines.append(f'<span class="badge bg-info">{self.escape(display_name)}</span>')
                    continue
                tooltip = self._get_internet_service_tooltip(addr)
                lines.append(
                    f'<span class="badge bg-info has-tooltip" data-tooltip="{self.escape(tooltip)}">{self.escape(display_name)}</span>'
                )
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
            if self.for_pdf:
                badges.append(f'<span class="badge bg-{color}">{self.escape(svc)}</span>')
                continue
            tooltip = self._get_service_tooltip(svc, vdom)
            if tooltip:
                badges.append(
                    f'<span class="badge bg-{color} has-tooltip" data-tooltip="{self.escape(tooltip)}">{self.escape(svc)}</span>'
                )
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
        if hasattr(profile, "scan_mode") and profile.scan_mode:
            # アンチウイルス
            rows.append(("スキャンモード", profile.scan_mode))
            if hasattr(profile, "protocols") and profile.protocols:
                protocols_str = ", ".join(profile.protocols[:3])
                if len(profile.protocols) > 3:
                    protocols_str += f" ... (他{len(profile.protocols) - 3}件)"
                rows.append(("対象プロトコル", protocols_str))
            if hasattr(profile, "action") and profile.action:
                rows.append(("アクション", profile.action))
        elif hasattr(profile, "categories") and profile.categories:
            # Webフィルタ / アプリコントロール
            cat_count = len(profile.categories)
            rows.append(("カテゴリ", f"{cat_count}件設定"))
            if hasattr(profile, "action") and profile.action:
                rows.append(("アクション", profile.action))
        elif hasattr(profile, "signatures"):
            # IPS
            sig_count = len(profile.signatures) if profile.signatures else 0
            rows.append(("シグネチャ", f"{sig_count}件"))
            if hasattr(profile, "action") and profile.action:
                rows.append(("アクション", profile.action))
        elif hasattr(profile, "mode") and profile.mode:
            # SSLインスペクション
            rows.append(("モード", profile.mode))

        result = self._format_tooltip_table(rows)
        self._tooltip_cache[cache_key] = result
        return result

    def _security_profiles_to_badges_with_tooltip(
        self, profiles: List[str], vdom: str = "root"
    ) -> str:
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
            if self.for_pdf:
                badges.append(
                    f'<span class="badge badge-outline badge-outline-{color}">{self.escape(profile)}</span>'
                )
                continue
            tooltip = self._get_security_profile_tooltip(profile, vdom)

            badge_html = f'<span class="badge badge-outline badge-outline-{color} has-tooltip" data-tooltip="{self.escape(tooltip)}">{self.escape(profile)}</span>'
            badges.append(badge_html)

        return " ".join(badges)
