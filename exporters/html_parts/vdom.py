"""HTML vdom rendering."""

from models.config import DeviceType, PolicyAction


class HTMLVDOMMixin:
    def _generate_objects_section(
        self, section_num: str = "2.2", section_id: str = "vdom-root-objects", vdom: str = None
    ) -> str:
        """オブジェクト定義セクション（VDOM単位）"""
        # VDOMでフィルタリング
        addresses = (
            self._filter_by_vdom(self.config.objects.addresses, vdom)
            if vdom
            else self.config.objects.addresses
        )
        services = (
            self._filter_by_vdom(self.config.objects.services, vdom)
            if vdom
            else self.config.objects.services
        )

        # アドレスオブジェクト（最初の100件）
        addr_rows = ""
        for addr in addresses:
            tags_html = ""
            if hasattr(addr, "tags") and addr.tags:
                tags_html = " ".join(
                    f'<span class="tag">{self.escape(t)}</span>' for t in addr.tags
                )
            addr_rows += f"""<tr>
                <td>{self.escape(addr.name)}</td>
                <td>{self.escape(addr.object_type)}</td>
                <td><code>{self.escape(addr.value)}</code></td>
                <td>{tags_html}</td>
            </tr>"""

        # サービスオブジェクト（最初の100件）
        svc_rows = ""
        for svc in services:
            tags_html = ""
            if hasattr(svc, "tags") and svc.tags:
                tags_html = " ".join(f'<span class="tag">{self.escape(t)}</span>' for t in svc.tags)
            svc_rows += f"""<tr>
                <td>{self.escape(svc.name)}</td>
                <td>{self.escape(svc.protocol)}</td>
                <td>{self.escape(svc.port)}</td>
                <td>{tags_html}</td>
            </tr>"""

        group_tables = []
        for title, items in (
            ("アドレスグループ", self.config.objects.address_groups),
            ("サービスグループ", self.config.objects.service_groups),
        ):
            groups = self._filter_by_vdom(items, vdom) if vdom else items
            rows = "".join(
                f"<tr><td>{self.escape(g.name)}</td>"
                f"<td>{self.escape(', '.join(g.members))}</td>"
                f"<td>{self.escape(getattr(g, 'dynamic_filter', ''))}</td>"
                f"<td>{self.escape(g.description)}</td></tr>"
                for g in groups
            )
            if rows:
                group_tables.append(
                    f'<h4>{title}</h4><div class="table-responsive">'
                    '<table class="table table-striped table-bordered">'
                    "<tr><th>グループ名</th><th>メンバー</th>"
                    f"<th>動的フィルター</th><th>説明</th></tr>{rows}</table></div>"
                )

        return f"""
            <div id="{section_id}" class="subsection">
                <h3>{section_num} オブジェクト定義</h3>

                <div class="summary-box">
                    <strong>オブジェクト数:</strong> アドレス {len(addresses)} 件、サービス {len(services)} 件
                </div>

                <h4>アドレスオブジェクト</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>オブジェクト名</th><th>タイプ</th><th>値</th><th>タグ</th></tr>
                        {addr_rows if addr_rows else '<tr><td colspan="4">アドレスオブジェクト設定なし</td></tr>'}
                    </table>
                </div>

                <h4>サービスオブジェクト</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>オブジェクト名</th><th>プロトコル</th><th>ポート</th><th>タグ</th></tr>
                        {svc_rows if svc_rows else '<tr><td colspan="4">サービスオブジェクト設定なし</td></tr>'}
                    </table>
                </div>
                {''.join(group_tables)}
            </div>"""

    def _generate_policies_section(
        self, section_num: str = "2.3", section_id: str = "vdom-root-policies", vdom: str = None
    ) -> str:
        """ポリシーセクション（VDOM単位）"""
        # VDOMでフィルタリング
        firewall_policies = (
            self._filter_by_vdom(self.config.firewall_policies, vdom)
            if vdom
            else self.config.firewall_policies
        )
        local_in_policies = (
            self._filter_by_vdom(self.config.local_in_policies, vdom)
            if vdom
            else self.config.local_in_policies
        )
        current_vdom = vdom or "root"
        is_paloalto = self.config.device_info.device_type == DeviceType.PALOALTO

        policy_rows = []
        for idx, policy in enumerate(firewall_policies, 1):
            # 宛先アドレスの表示（Internet Service名がある場合はそれも含める）
            destination_display = self._addresses_to_lines_with_tooltip(
                policy.destination_address, current_vdom
            )
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
                    internet_services.append(
                        f'<span class="badge bg-info has-tooltip" data-tooltip="{self.escape(tooltip)}">{self.escape(service_name)}</span>'
                    )

                if destination_display and destination_display != "-":
                    destination_display += "<br>" + " ".join(internet_services)
                else:
                    destination_display = " ".join(internet_services)

            source_display = self._addresses_to_lines_with_tooltip(
                policy.source_address, current_vdom
            )
            if policy.internet_service_source_enabled:
                source_display = "ISDB: " + self.escape(
                    ", ".join(policy.internet_service_source_name) or "選択条件未確定"
                )
            conditions = [
                ("ISDB 宛先否定", "有効" if policy.internet_service_negate else ""),
                ("ISDB 送信元否定", "有効" if policy.internet_service_source_negate else ""),
                ("スケジュール", policy.schedule),
                ("送信元否定", "有効" if policy.source_negate else "無効"),
                ("宛先否定", "有効" if policy.destination_negate else "無効"),
                ("ユーザー", ", ".join(policy.source_users)),
                ("グループ", ", ".join(policy.source_groups)),
                ("開始ログ", "有効" if policy.log_start else "無効"),
                ("ログ転送", policy.log_profile),
                ("タグ", ", ".join(policy.tags)),
            ]
            condition_html = "<br>".join(
                f"{label}: {self.escape(value)}" for label, value in conditions if value
            )
            id_cell = "" if is_paloalto else f"<td>{self.escape(policy.policy_id)}</td>"
            policy_rows.append(
                f"""<tr class="policy-row">
                <td>{idx}</td>
                {id_cell}
                <td class="policy-name">{self.escape(policy.name)} {"" if policy.enabled else '<span class="disabled">(無効)</span>'}</td>
                <td>{self._interfaces_to_lines_with_tooltip(policy.source_interface, current_vdom)}</td>
                <td>{self._interfaces_to_lines_with_tooltip(policy.destination_interface, current_vdom)}</td>
                <td>{source_display}</td>
                <td>{destination_display}</td>
                {'<td>' + ' '.join(f'<span class="tag">{self.escape(app)}</span>' for app in policy.application) + '</td>' if is_paloalto else ''}
                <td>{self._services_to_badges_with_tooltip(policy.service, current_vdom)}</td>
                <td class="{self._get_action_class(policy.action)}">{self.escape(policy.action.value)}</td>
                <td class="policy-flag">{"有効" if policy.nat_enabled else "無効"}</td>
                <td>{self._security_profiles_to_badges_with_tooltip(policy.security_profiles, current_vdom)}</td>
                <td class="policy-flag">{"有効" if policy.log_enabled else "無効"}</td>
                <td class="policy-note">{self.escape(policy.description)}</td>
                <td class="policy-cond">{condition_html}</td>
            </tr>"""
            )

        # Local-in ポリシー
        local_in_rows = []
        for idx, policy in enumerate(local_in_policies, 1):
            # source_interfaceは文字列の場合とリストの場合がある
            source_if_display = ""
            if isinstance(policy.source_interface, list):
                source_if_display = self._interfaces_to_lines_with_tooltip(
                    policy.source_interface, current_vdom
                )
            elif policy.source_interface:
                source_if_display = self._interface_with_tooltip(
                    policy.source_interface, current_vdom
                )
            else:
                source_if_display = "-"

            local_id_cell = "" if is_paloalto else f"<td>{self.escape(policy.policy_id)}</td>"
            local_in_rows.append(
                f"""<tr class="policy-row">
                <td>{idx}</td>
                {local_id_cell}
                <td class="policy-name">{self.escape(policy.name)} {"" if policy.enabled else '<span class="disabled">(無効)</span>'}</td>
                <td>{source_if_display}</td>
                <td>{self._addresses_to_lines_with_tooltip(policy.source_address, current_vdom)}</td>
                <td>{self._addresses_to_lines_with_tooltip(policy.destination_address, current_vdom)}</td>
                <td>{self._services_to_badges_with_tooltip(policy.service, current_vdom)}</td>
                <td class="{self._get_action_class(policy.action)}">{self.escape(policy.action.value)}</td>
                <td class="policy-note">{self.escape(policy.description)}</td>
            </tr>"""
            )

        return f"""
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
                                {"" if is_paloalto else "<th>ID</th>"}
                                <th>ポリシー名</th>
                                <th>送信元IF</th>
                                <th>宛先IF</th>
                                <th>送信元アドレス</th>
                                <th>宛先アドレス</th>
                                {"<th>アプリケーション</th>" if is_paloalto else ""}
                                <th>サービス</th>
                                <th>アクション</th>
                                <th>NAT</th>
                                <th>セキュリティプロファイル</th>
                                <th>ログ</th>
                                <th>備考</th><th>詳細条件</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(policy_rows) if policy_rows else f'<tr><td colspan="{14 if is_paloalto else 14}">ポリシー設定なし</td></tr>'}
                        </tbody>
                    </table>
                </div>

                <h4>Local-in ポリシー</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <thead>
                            <tr>
                                <th>No</th>
                                {"" if is_paloalto else "<th>ID</th>"}
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
                            {''.join(local_in_rows) if local_in_rows else f'<tr><td colspan="{8 if is_paloalto else 9}">Local-in ポリシー設定なし</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>"""

    def _get_action_class(self, action: PolicyAction) -> str:
        """アクションからCSSクラスを取得"""
        if action == PolicyAction.ALLOW:
            return "allow"
        elif action == PolicyAction.DENY:
            return "deny"
        elif action == PolicyAction.DROP:
            return "drop"
        return ""

    def _generate_nat_section(
        self, section_num: str = "2.4", section_id: str = "vdom-root-nat", vdom: str = None
    ) -> str:
        """NAT設定セクション（VDOM単位）"""
        # VDOMでフィルタリング
        nat_policies = (
            self._filter_by_vdom(self.config.nat_policies, vdom)
            if vdom
            else self.config.nat_policies
        )

        # VIP/DNAT
        vip_rows = ""
        # SNAT/IP Pool
        snat_rows = ""
        # Central SNAT Map
        central_snat_rows = ""

        for nat in nat_policies:
            if nat.nat_type in ("vip", "dnat"):
                port_forward_display = ""
                if nat.port_forward:
                    port_forward_display = (
                        f"{self.escape(nat.original_port)} → {self.escape(nat.translated_port)}"
                    )
                else:
                    port_forward_display = "なし"

                vip_rows += f"""<tr>
                    <td>{self.escape(nat.name)}</td>
                    <td>{self.escape(nat.external_interface)}</td>
                    <td><code>{self.escape(nat.external_ip)}</code></td>
                    <td><code>{self.escape(nat.internal_ip)}</code></td>
                    <td>{port_forward_display}</td>
                    <td>{self.escape(nat.description)}</td>
                </tr>"""
            elif nat.nat_type == "central-snat":
                protocol_display = (
                    self._format_protocol_number(nat.protocol) if nat.protocol else "ALL"
                )
                status_display = "有効" if nat.enabled else "無効"
                central_snat_rows += f"""<tr>
                    <td>{self.escape(nat.name)}</td>
                    <td>{self.escape(nat.original_source)}</td>
                    <td>{self.escape(nat.original_destination)}</td>
                    <td>{self.escape(nat.nat_ippool)}</td>
                    <td>{self.escape(protocol_display)}</td>
                    <td>{self.escape(nat.interface)}</td>
                    <td>{status_display}</td>
                    <td>{self.escape(nat.description)}</td>
                </tr>"""
            elif nat.nat_type in ("snat", "ippool"):
                snat_rows += f"""<tr>
                    <td>{self.escape(nat.name)}</td>
                    <td><code>{self.escape(nat.translated_source)}</code></td>
                    <td>{self.escape(nat.interface)}</td>
                    <td>{self.escape(nat.description)}</td>
                </tr>"""

        # Central SNAT Mapセクション
        central_snat_section = ""
        if central_snat_rows or self.config.system_settings.central_nat:
            central_snat_section = f"""
                <h4>Central SNAT Map</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>ID</th><th>送信元</th><th>宛先</th><th>NAT IP Pool</th><th>プロトコル</th><th>インターフェース</th><th>状態</th><th>備考</th></tr>
                        {central_snat_rows if central_snat_rows else '<tr><td colspan="8">Central SNAT Map設定なし</td></tr>'}
                    </table>
                </div>"""

        return f"""
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
                {central_snat_section}
            </div>"""

    def _generate_vpn_section(
        self, section_num: str = "2.5", section_id: str = "vdom-root-vpn", vdom: str = None
    ) -> str:
        """VPN設定セクション（VDOM単位）"""
        # VDOMでフィルタリング
        # VPN設定はネットワークレベル（Palo Alto: device/network配下）のため、
        # vdom属性を持たないエントリは最初のvsysで表示する
        from models.config import DeviceType

        is_paloalto = self.config.device_info.device_type == DeviceType.PALOALTO
        first_vdom = self._get_vdom_list()[0] if self._get_vdom_list() else "root"
        if vdom:
            if is_paloalto and vdom == first_vdom:
                # Palo Altoの最初のvsysでは全VPN設定を表示
                ipsec_phase1 = self.config.vpn.ipsec_phase1
                ipsec_phase2 = self.config.vpn.ipsec_phase2
            else:
                ipsec_phase1 = self._filter_by_vdom(self.config.vpn.ipsec_phase1, vdom)
                ipsec_phase2 = self._filter_by_vdom(self.config.vpn.ipsec_phase2, vdom)
        else:
            ipsec_phase1 = self.config.vpn.ipsec_phase1
            ipsec_phase2 = self.config.vpn.ipsec_phase2
        ssl_vpn = (
            self._filter_by_vdom(self.config.vpn.ssl_vpn, vdom) if vdom else self.config.vpn.ssl_vpn
        )

        # IPsec Phase1
        p1_rows = ""
        for p1 in ipsec_phase1:
            ike_version_display = p1.ike_version if p1.ike_version else "-"
            p1_rows += f"""<tr>
                <td>{self.escape(p1.name)}</td>
                <td><code>{self.escape(p1.remote_gateway)}</code></td>
                <td>{self.escape(p1.interface)}</td>
                <td>{self.escape(str(ike_version_display))}</td>
                <td>{self.escape(p1.encryption)} / {self.escape(p1.authentication)}</td>
                <td>{self.escape(p1.dh_group)}</td>
                <td>{self.escape(p1.lifetime)}</td>
                <td>{'有' if p1.psk else '無'}</td>
            </tr>"""

        # IPsec Phase2
        p2_rows = ""
        for p2 in ipsec_phase2:
            p2_rows += f"""<tr>
                <td>{self.escape(p2.name)}</td>
                <td>{self.escape(p2.phase1_name)}</td>
                <td><code>{self.escape(p2.local_subnet)}</code></td>
                <td><code>{self.escape(p2.remote_subnet)}</code></td>
                <td>{self.escape(p2.encryption)} / {self.escape(p2.authentication)}</td>
                <td>{self.escape(p2.pfs)}</td>
                <td>{self.escape(p2.lifetime)}</td>
            </tr>"""

        # SSL-VPN
        ssl_rows = ""
        for ssl in ssl_vpn:
            auth_method_display = self.escape(ssl.auth_method) if ssl.auth_method else "ローカル"
            mode_display = self.escape(ssl.mode) if ssl.mode else "-"
            realm_display = self.escape(ssl.realm) if ssl.realm else "-"
            portal_display = self.escape(ssl.portal) if ssl.portal else "-"

            ssl_rows += f"""<tr>
                <td>{realm_display} / {portal_display}</td>
                <td>{self.escape(ssl.listen_port)}</td>
                <td>{self.escape(ssl.listen_interface)}</td>
                <td>{auth_method_display}</td>
                <td><code>{self.escape(ssl.tunnel_ip_pool)}</code></td>
                <td>{self.escape(self._list_to_str(ssl.user_groups))}</td>
                <td>{mode_display}</td>
            </tr>"""

        return f"""
            <div id="{section_id}" class="subsection">
                <h3>{section_num} VPN設定</h3>

                <h4>IPsec-VPN Phase1</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>VPN名</th><th>対向機器IP（ピア）</th><th>インターフェース</th><th>IKE</th><th>暗号化/認証</th><th>DHグループ</th><th>ライフタイム</th><th>事前共有鍵</th></tr>
                        {p1_rows if p1_rows else '<tr><td colspan="8">IPsec Phase1設定なし</td></tr>'}
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
            </div>"""

    def _generate_security_profiles_section(
        self,
        section_num: str = "2.6",
        section_id: str = "vdom-root-security_profiles",
        vdom: str = None,
    ) -> str:
        """セキュリティプロファイルセクション（VDOM単位）"""
        # VDOMでフィルタリング
        security_profiles = (
            self._filter_by_vdom(self.config.security_profiles, vdom)
            if vdom
            else self.config.security_profiles
        )
        antivirus = (
            self._filter_by_vdom(self.config.security_profiles_detail.antivirus, vdom)
            if vdom
            else self.config.security_profiles_detail.antivirus
        )
        webfilter = (
            self._filter_by_vdom(self.config.security_profiles_detail.webfilter, vdom)
            if vdom
            else self.config.security_profiles_detail.webfilter
        )
        app_control = (
            self._filter_by_vdom(self.config.security_profiles_detail.app_control, vdom)
            if vdom
            else self.config.security_profiles_detail.app_control
        )
        ips = (
            self._filter_by_vdom(self.config.security_profiles_detail.ips, vdom)
            if vdom
            else self.config.security_profiles_detail.ips
        )
        ssl_inspection = (
            self._filter_by_vdom(self.config.security_profiles_detail.ssl_inspection, vdom)
            if vdom
            else self.config.security_profiles_detail.ssl_inspection
        )

        # プロファイル一覧
        profile_rows = ""
        for profile in security_profiles:
            profile_rows += f"""<tr>
                <td>{self.escape(profile.name)}</td>
                <td>{self.escape(profile.profile_type)}</td>
                <td>{'有効' if profile.enabled else '無効'}</td>
                <td>{self.escape(profile.description)}</td>
            </tr>"""

        # 詳細プロファイル - アンチウイルス
        av_rows = ""
        for av in antivirus:
            protocols_display = self._list_to_str(av.protocols) if av.protocols else "-"
            av_rows += f"""<tr>
                <td>{self.escape(av.name)}</td>
                <td>{'有効' if av.enabled else '無効'}</td>
                <td>{self.escape(av.scan_mode)}</td>
                <td>{protocols_display}</td>
                <td>{self.escape(av.action)}</td>
            </tr>"""

        # 詳細プロファイル - Webフィルタ
        wf_rows = ""
        for wf in webfilter:
            categories_display = self._list_to_str(wf.categories[:10]) if wf.categories else "-"
            if len(wf.categories) > 10:
                categories_display += f" ... (他{len(wf.categories) - 10}件)"
            wf_rows += f"""<tr>
                <td>{self.escape(wf.name)}</td>
                <td>{'有効' if wf.enabled else '無効'}</td>
                <td>{categories_display}</td>
                <td>{self.escape(wf.action)}</td>
            </tr>"""

        # 詳細プロファイル - アプリケーションコントロール
        app_rows = ""
        for app in app_control:
            categories_display = self._list_to_str(app.categories[:10]) if app.categories else "-"
            if len(app.categories) > 10:
                categories_display += f" ... (他{len(app.categories) - 10}件)"
            app_rows += f"""<tr>
                <td>{self.escape(app.name)}</td>
                <td>{'有効' if app.enabled else '無効'}</td>
                <td>{categories_display}</td>
                <td>{self.escape(app.action)}</td>
            </tr>"""

        # 詳細プロファイル - IPS
        ips_rows = ""
        for i in ips:
            signatures_display = f"{len(i.signatures)}件" if i.signatures else "-"
            ips_rows += f"""<tr>
                <td>{self.escape(i.name)}</td>
                <td>{'有効' if i.enabled else '無効'}</td>
                <td>{signatures_display}</td>
                <td>{self.escape(i.action)}</td>
            </tr>"""

        # 詳細プロファイル - SSLインスペクション
        ssl_rows = ""
        for ssl in ssl_inspection:
            ssl_rows += f"""<tr>
                <td>{self.escape(ssl.name)}</td>
                <td>{'有効' if ssl.enabled else '無効'}</td>
                <td>{self.escape(ssl.mode)}</td>
            </tr>"""

        return f"""
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
            </div>"""
