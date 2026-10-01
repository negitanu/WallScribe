"""HTML network rendering."""

from typing import List


class HTMLNetworkMixin:
    def _generate_network_section(
        self, section_num: str = "2.1", section_id: str = "vdom-root-network", vdom: str = None
    ) -> str:
        """ネットワーク設定セクション（VDOM単位）"""
        # VDOMでフィルタリング
        interfaces = (
            self._filter_by_vdom(self.config.interfaces, vdom) if vdom else self.config.interfaces
        )
        routes = self._filter_by_vdom(self.config.routes, vdom) if vdom else self.config.routes
        dhcp_servers = (
            self._filter_by_vdom(self.config.dhcp_servers, vdom)
            if vdom
            else self.config.dhcp_servers
        )

        # ルーティング設定
        ospf_settings = (
            self._filter_by_vdom(self.config.routing.ospf, vdom)
            if vdom
            else self.config.routing.ospf
        )
        bgp_settings = (
            self._filter_by_vdom(self.config.routing.bgp, vdom) if vdom else self.config.routing.bgp
        )
        policy_routes = (
            self._filter_by_vdom(self.config.routing.policy_routes, vdom)
            if vdom
            else self.config.routing.policy_routes
        )

        vr_memberships = [
            vr
            for vr in self.config.virtual_routers
            if not vdom
            or vdom in vr.vsys
            or (not vr.vsys and vdom == (self.config.device_info.vdom_list or ["root"])[0])
            or any(i.name in vr.interfaces for i in interfaces)
        ]
        if self.config.virtual_routers and vdom:
            contexts = {vr.name for vr in vr_memberships}
            routes = [
                r
                for r in self.config.routes
                if r.routing_context in contexts or (not r.routing_context and r.vdom == vdom)
            ]
        vr_html = ""
        if vr_memberships:
            rows = "".join(
                "<tr><td>"
                + self.escape(vr.name)
                + "</td><td>"
                + self.escape(", ".join(vr.interfaces))
                + "</td><td>"
                + self.escape(", ".join(vr.vsys) or "未確定")
                + "</td><td>"
                + self.escape(", ".join(vr.dynamic_protocols) or "—")
                + "</td></tr>"
                for vr in vr_memberships
            )
            vr_html = (
                '<h4>仮想ルーターの所属</h4><div class="table-responsive"><table class="table table-bordered"><tr><th>VR</th><th>IF</th><th>vsys</th><th>動的経路</th></tr>'
                + rows
                + "</table></div>"
            )

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

            # 状態表示
            status_display = "-"
            status_class = ""
            if iface.status:
                status_lower = iface.status.lower()
                if status_lower in ("up", "enable", "enabled", "有効"):
                    status_class = "allow"
                    status_display = iface.status
                else:
                    status_class = "deny"
                    status_display = iface.status

            iface_rows += f"""<tr>
                <td>{self.escape(iface.name)}</td>
                <td>{self.escape(iface.interface_type)}</td>
                <td>{self.escape(iface.role) if iface.role else '-'}</td>
                <td><code>{self.escape(iface.ip_address)}</code></td>
                <td>{vlan_display}</td>
                <td>{zone_tag}</td>
                <td>{self._format_allowed_access(iface.allowed_access)}</td>
                <td class="{status_class}">{self.escape(status_display)}</td>
                <td>{self.escape(iface.description) if iface.description else '-'}</td>
                {"<td>" + self.escape(iface.routing_context or "未確定") + "</td>" if self.config.virtual_routers else ""}
            </tr>"""

        # ルーティング
        route_rows = ""
        for route in routes:
            gateway_display = route.gateway or ""
            # blackhole/discard ルートはゲートウェイが空になるため、明示して記載する
            if not gateway_display and getattr(route, "route_type", "") in (
                "blackhole",
                "blackhole6",
            ):
                gateway_display = "blackhole"

            interface_display = route.interface or "-"
            name_display = route.name or "-"
            destination_display = route.destination or "-"
            distance_display = route.distance if route.distance is not None else "-"
            route_type_display = route.route_type if route.route_type else "-"

            route_rows += f"""<tr>
                <td>{self.escape(name_display)}</td>
                <td><code>{self.escape(destination_display)}</code></td>
                <td><code>{self.escape(gateway_display) if gateway_display else '-'}</code></td>
                <td>{self.escape(interface_display)}</td>
                <td>{self.escape(str(distance_display))}</td>
                <td>{self.escape(route_type_display)}</td>
                {"<td>" + self.escape(route.routing_context) + "</td>" if self.config.virtual_routers else ""}
            </tr>"""

        # DHCP
        dhcp_cards = ""
        for dhcp in dhcp_servers:
            exclude_ips_display = (
                self._list_to_str(dhcp.exclude_ips) if dhcp.exclude_ips else "なし"
            )
            dhcp_cards += f"""
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
                </div>"""

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
            policy_route_rows += f"""<tr>
                <td>{self.escape(str(pr.sequence_number))}</td>
                <td>{self.escape(pr.name) if pr.name else '-'}</td>
                <td>{self.escape(src_display)}</td>
                <td>{self.escape(dst_display)}</td>
                <td>{self.escape(interface_display)}</td>
                <td><code>{self.escape(gateway_display)}</code></td>
            </tr>"""

        return f"""
            <div id="{section_id}" class="subsection">
                <h3>{section_num} ネットワーク設定</h3>
                {vr_html}

                <h4>インターフェース（物理・VLAN・LAG）</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>インターフェース名</th><th>タイプ</th><th>役割</th><th>IPアドレス</th><th>VLAN ID</th><th>ゾーン</th><th>許可アクセス</th><th>状態</th><th>説明</th>{"<th>VR</th>" if self.config.virtual_routers else ""}</tr>
                        {iface_rows if iface_rows else '<tr><td colspan="9">インターフェース設定なし</td></tr>'}
                    </table>
                </div>

                <h4>スタティックルート</h4>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>名前</th><th>宛先ネットワーク</th><th>ゲートウェイ</th><th>デバイス（インターフェース）</th><th>ディスタンス</th><th>タイプ</th>{"<th>VR</th>" if self.config.virtual_routers else ""}</tr>
                        {route_rows if route_rows else '<tr><td colspan="6">スタティックルート設定なし</td></tr>'}
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
            </div>"""

    def _generate_ospf_html(self, ospf_settings: list) -> str:
        """OSPF設定のHTML生成"""
        if not ospf_settings:
            return """
                <h4>OSPF設定</h4>
                <p>OSPF設定なし</p>
            """

        ospf_html = "<h4>OSPF設定</h4>"

        for ospf in ospf_settings:
            # 基本情報
            ospf_html += f"""
                <div class="info-card mb-3">
                    <h5>OSPF基本設定</h5>
                    <table class="table table-sm table-bordered">
                        <tr><td>ルーターID</td><td><code>{self.escape(ospf.router_id) if ospf.router_id else '-'}</code></td></tr>
                        <tr><td>デフォルトルート配布</td><td>{'有効' if ospf.default_information_originate else '無効'}</td></tr>
                        <tr><td>デフォルトメトリック</td><td>{self.escape(ospf.default_metric) if ospf.default_metric else '-'}</td></tr>
                        <tr><td>距離</td><td>{self.escape(ospf.distance) if ospf.distance else '-'}</td></tr>
                    </table>
                </div>"""

            # エリア
            if ospf.areas:
                area_rows = ""
                for area in ospf.areas:
                    area_rows += f"""<tr>
                        <td>{self.escape(area.area_id)}</td>
                        <td>{self.escape(area.area_type) if area.area_type else 'normal'}</td>
                        <tr><td colspan="2">認証: {self.escape(area.authentication) if area.authentication else 'なし'}</td></tr>
                    </tr>"""
                ospf_html += f"""
                    <div class="table-responsive">
                        <h5>OSPFエリア</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>エリアID</th><th>タイプ</th></tr>
                            {area_rows}
                        </table>
                    </div>"""

            # インターフェース
            if ospf.interfaces:
                iface_rows = ""
                for iface in ospf.interfaces:
                    iface_rows += f"""<tr>
                        <td>{self.escape(iface.name)}</td>
                        <td>{self.escape(iface.area) if iface.area else '-'}</td>
                        <td>{self.escape(str(iface.cost)) if iface.cost else '-'}</td>
                        <td>{self.escape(str(iface.priority)) if iface.priority else '-'}</td>
                        <td>{self.escape(iface.network_type) if iface.network_type else '-'}</td>
                    </tr>"""
                ospf_html += f"""
                    <div class="table-responsive">
                        <h5>OSPFインターフェース</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>インターフェース</th><th>エリア</th><th>コスト</th><th>優先度</th><th>ネットワークタイプ</th></tr>
                            {iface_rows}
                        </table>
                    </div>"""

            # 再配布
            if ospf.redistributes:
                redist_rows = ""
                for redist in ospf.redistributes:
                    redist_rows += f"""<tr>
                        <td>{self.escape(redist.source)}</td>
                        <td>{'有効' if redist.status else '無効'}</td>
                        <td>{self.escape(str(redist.metric)) if redist.metric else '-'}</td>
                        <td>{self.escape(redist.metric_type) if redist.metric_type else '-'}</td>
                        <td>{self.escape(redist.routemap) if redist.routemap else '-'}</td>
                    </tr>"""
                ospf_html += f"""
                    <div class="table-responsive">
                        <h5>OSPF再配布</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>ソース</th><th>ステータス</th><th>メトリック</th><th>メトリックタイプ</th><th>ルートマップ</th></tr>
                            {redist_rows}
                        </table>
                    </div>"""

            # パッシブインターフェース
            if ospf.passive_interfaces:
                passive_list = ", ".join(ospf.passive_interfaces)
                ospf_html += f"""
                    <div class="info-card mb-3">
                        <h5>パッシブインターフェース</h5>
                        <p>{self.escape(passive_list)}</p>
                    </div>"""

        return ospf_html

    def _generate_bgp_html(self, bgp_settings: list) -> str:
        """BGP設定のHTML生成"""
        if not bgp_settings:
            return """
                <h4>BGP設定</h4>
                <p>BGP設定なし</p>
            """

        bgp_html = "<h4>BGP設定</h4>"

        for bgp in bgp_settings:
            # 基本情報
            bgp_html += f"""
                <div class="info-card mb-3">
                    <h5>BGP基本設定</h5>
                    <table class="table table-sm table-bordered">
                        <tr><td>AS番号</td><td><code>{self.escape(bgp.as_number) if bgp.as_number else '-'}</code></td></tr>
                        <tr><td>ルーターID</td><td><code>{self.escape(bgp.router_id) if bgp.router_id else '-'}</code></td></tr>
                    </table>
                </div>"""

            # ネイバー
            if bgp.neighbors:
                neighbor_rows = ""
                for neighbor in bgp.neighbors:
                    neighbor_rows += f"""<tr>
                        <td><code>{self.escape(neighbor.ip)}</code></td>
                        <td>{self.escape(neighbor.remote_as)}</td>
                        <td>{self.escape(neighbor.description) if neighbor.description else '-'}</td>
                        <td>{'有効' if neighbor.activate else '無効'}</td>
                        <td>{self.escape(neighbor.route_map_in) if neighbor.route_map_in else '-'}</td>
                        <td>{self.escape(neighbor.route_map_out) if neighbor.route_map_out else '-'}</td>
                    </tr>"""
                bgp_html += f"""
                    <div class="table-responsive">
                        <h5>BGPネイバー</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>IPアドレス</th><th>リモートAS</th><th>説明</th><th>有効</th><th>ルートマップIn</th><th>ルートマップOut</th></tr>
                            {neighbor_rows}
                        </table>
                    </div>"""

            # ネットワーク
            if bgp.networks:
                network_rows = ""
                for network in bgp.networks:
                    network_rows += f"""<tr>
                        <td><code>{self.escape(network.prefix)}</code></td>
                        <td>{self.escape(network.route_map) if network.route_map else '-'}</td>
                    </tr>"""
                bgp_html += f"""
                    <div class="table-responsive">
                        <h5>BGPネットワーク</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>プレフィックス</th><th>ルートマップ</th></tr>
                            {network_rows}
                        </table>
                    </div>"""

            # 再配布
            if bgp.redistributes:
                redist_rows = ""
                for redist in bgp.redistributes:
                    redist_rows += f"""<tr>
                        <td>{self.escape(redist.source)}</td>
                        <td>{'有効' if redist.status else '無効'}</td>
                        <td>{self.escape(redist.routemap) if redist.routemap else '-'}</td>
                    </tr>"""
                bgp_html += f"""
                    <div class="table-responsive">
                        <h5>BGP再配布</h5>
                        <table class="table table-striped table-hover table-bordered">
                            <tr><th>ソース</th><th>ステータス</th><th>ルートマップ</th></tr>
                            {redist_rows}
                        </table>
                    </div>"""

        return bgp_html

    def _get_zone_class(self, zone: str) -> str:
        """ゾーン名からCSSクラスを取得"""
        zone_lower = zone.lower()
        if "trust" in zone_lower and "untrust" not in zone_lower:
            return "tag-trust"
        elif "untrust" in zone_lower:
            return "tag-untrust"
        elif "dmz" in zone_lower:
            return "tag-dmz"
        return ""

    def _format_allowed_access(self, allowed_access: List[str]) -> str:
        """許可アクセスをBootstrapアウトラインボタンで表示"""
        if not allowed_access:
            return '<span class="btn btn-outline-secondary btn-sm disabled">なし</span>'

        # プロトコルごとのボタン色を定義
        btn_classes = {
            "https": "btn-outline-success",  # セキュア（緑）
            "ssh": "btn-outline-success",  # セキュア（緑）
            "http": "btn-outline-warning",  # 非セキュア（黄）
            "telnet": "btn-outline-danger",  # 非セキュア（赤）
            "ping": "btn-outline-info",  # 診断（青）
            "snmp": "btn-outline-info",  # 監視（青）
            "fmg-access": "btn-outline-primary",  # FortiManager（紫）
            "capwap": "btn-outline-primary",  # 無線AP管理（紫）
            "radius-acct": "btn-outline-secondary",  # RADIUS（グレー）
            "ftm": "btn-outline-secondary",  # FortiToken（グレー）
        }

        buttons = []
        for access in allowed_access:
            access_lower = access.lower()
            btn_class = btn_classes.get(access_lower, "btn-outline-secondary")
            buttons.append(
                f'<span class="btn {btn_class} btn-sm me-1 mb-1">{self.escape(access)}</span>'
            )

        return " ".join(buttons)
