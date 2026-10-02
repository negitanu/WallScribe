"""HTML global sections rendering."""

from pathlib import Path

from models.cluster import HARole
from models.config import HAMode


class HTMLGlobalMixin:
    def _generate_device_info_section(
        self, section_num: str = "1.1", section_id: str = "global-device_info"
    ) -> str:
        """機器概要セクション（グローバル）"""
        info = self.config.device_info
        license = info.license
        vdom_label = self._get_vdom_label()

        ha_status = "未設定"
        if self.config.ha.mode != HAMode.STANDALONE:
            from models.config import DeviceType

            is_pa = self.config.device_info.device_type == DeviceType.PALOALTO
            priority_note = "低い方が優先" if is_pa else "高い方が優先"
            ha_status = f"{self.config.ha.mode.value} (Group: {self.config.ha.group_id}, Priority: {self.config.ha.priority}, {priority_note})"

        # ライセンス情報
        license_rows = ""
        if license.support_expiry or license.utm_expiry or license.av_expiry:
            if license.support_expiry:
                license_rows += f"<tr><td>サポート有効期限</td><td>{self.escape(license.support_expiry)}</td></tr>"
            if license.utm_expiry:
                license_rows += f"<tr><td>UTM Bundle有効期限</td><td>{self.escape(license.utm_expiry)}</td></tr>"
            if license.av_expiry:
                license_rows += f"<tr><td>アンチウイルス有効期限</td><td>{self.escape(license.av_expiry)}</td></tr>"
            if license.webfilter_expiry:
                license_rows += f"<tr><td>Webフィルタ有効期限</td><td>{self.escape(license.webfilter_expiry)}</td></tr>"
            if license.ips_expiry:
                license_rows += (
                    f"<tr><td>IPS有効期限</td><td>{self.escape(license.ips_expiry)}</td></tr>"
                )
        else:
            license_rows = '<tr><td colspan="2">ライセンス情報は設定ファイルから取得できません（別途確認が必要）</td></tr>'

        # VDOM/vsysリスト
        vdom_list = self._get_vdom_list()
        vdom_list_display = ", ".join(vdom_list) if vdom_list else "-"

        return f"""
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
                            <tr><td>NATモード</td><td>{'Central NAT' if self.config.system_settings.central_nat else 'Policy Base NAT'}</td></tr>
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
            </div>"""

    def _generate_system_settings_section(
        self, section_num: str = "1.2", section_id: str = "global-system_settings"
    ) -> str:
        """システム設定セクション（グローバル）"""
        settings = self.config.system_settings
        vdom_label = self._get_vdom_label()

        admin_rows = ""
        for admin in settings.admin_users:
            trust_hosts = self._list_to_str(admin.trust_hosts)
            admin_rows += f"""<tr>
                <td>{self.escape(admin.username)}</td>
                <td>{self.escape(admin.profile)}</td>
                <td>{self.escape(admin.vdom)}</td>
                <td><code>{self.escape(trust_hosts)}</code></td>
            </tr>"""

        # 管理アクセス情報
        mgmt_ip_display = self.escape(settings.management_ip)
        if settings.management_netmask:
            mgmt_ip_display += f" / {self.escape(settings.management_netmask)}"
        elif "/" not in settings.management_ip:
            mgmt_ip_display += " / -"

        return f"""
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
                            <tr><td>HTTPSポート</td><td>{self._with_default_annotation(settings.https_port, 'system_settings.https_port')}</td></tr>
                            <tr><td>SSHポート</td><td>{self._with_default_annotation(settings.ssh_port, 'system_settings.ssh_port')}</td></tr>
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
            </div>"""

    def _generate_cluster_overview_section(
        self, section_num: str = "1.1", section_id: str = "global-cluster_overview"
    ) -> str:
        """クラスタ概要セクション（HAクラスタ時のみ表示）"""
        if not self.is_cluster or self.cluster_config is None:
            return ""  # クラスタ構成でない場合は何も出力しない

        cluster_info = self.cluster_config.cluster_info
        differences = self.cluster_config.config_differences

        # メンバー一覧テーブル
        member_rows = ""
        for member in cluster_info.members:
            role_badge = f'<span class="badge bg-{"success" if member.role == HARole.PRIMARY else "info"}">{member.role.value}</span>'
            member_rows += f"""<tr>
                <td>{role_badge}</td>
                <td><strong>{self.escape(member.hostname)}</strong></td>
                <td>{self.escape(member.model) if member.model else "-"}</td>
                <td>{self.escape(member.os_version) if member.os_version else "-"}</td>
                <td>{self.escape(member.priority) if member.priority is not None else "-"}</td>
                <td><code>{self.escape(member.ha_mgmt_ip) if member.ha_mgmt_ip else "-"}</code></td>
                <td><code>{self.escape(member.serial_number) if member.serial_number else "-"}</code></td>
                <td>{self.escape(Path(member.source_file).name) if member.source_file else '-'}</td>
            </tr>"""

        # 設定差分テーブル
        diff_rows = ""
        if differences:
            for diff in differences:
                diff_rows += f"""<tr>
                    <td>{self.escape(diff.section)}</td>
                    <td>{self.escape(diff.item)}</td>
                    <td><code>{self.escape(diff.primary_value)}</code></td>
                    <td><code>{self.escape(diff.secondary_value)}</code></td>
                    <td>{self.escape(diff.description)}</td>
                </tr>"""

        diff_section = ""
        if diff_rows:
            diff_section = f"""
                <h4>設定差分</h4>
                <div class="warning-box">
                    <strong>注意:</strong> Primary/Secondary間で以下の設定差分が検出されました。
                </div>
                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <tr><th>セクション</th><th>項目</th><th>Primary</th><th>Secondary</th><th>備考</th></tr>
                        {diff_rows}
                    </table>
                </div>"""

        return f"""
            <div id="{section_id}" class="subsection">
                <h3>{section_num} クラスタ概要</h3>

                <div class="info-grid">
                    <div class="info-card">
                        <h4>クラスタ情報</h4>
                        <table class="table table-sm table-bordered">
                            {'<tr><td>クラスタ名</td><td><strong>' + self.escape(cluster_info.cluster_name) + '</strong></td></tr>' if cluster_info.cluster_name else ''}
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
            </div>"""

    def _generate_ha_section(self, section_num: str = "1.4", section_id: str = "global-ha") -> str:
        """HA設定セクション（グローバル）"""
        ha = self.config.ha

        if ha.mode == HAMode.STANDALONE:
            return f"""
            <div id="{section_id}" class="subsection">
                <h3>{section_num} HA設定</h3>
                <p>HA設定なし（スタンドアロン）</p>
            </div>"""

        # ハートビートインターフェース
        hb_rows = ""
        if ha.heartbeat_interfaces_detail:
            for hb in ha.heartbeat_interfaces_detail:
                hb_rows += f"""<tr>
                    <td>{self.escape(hb.interface)}</td>
                    <td>{self.escape(hb.priority) if hb.priority else "-"}</td>
                </tr>"""
        else:
            # 詳細情報がない場合はシンプルなリスト表示
            for iface in ha.heartbeat_interfaces:
                hb_rows += f"""<tr>
                    <td>{self.escape(iface)}</td>
                    <td>-</td>
                </tr>"""

        hb_section = ""
        if hb_rows:
            hb_section = f"""
                <h4>ハートビートインターフェース</h4>
                <div class="table-responsive">
                    <table class="table table-sm table-bordered">
                        <tr><th>インターフェース</th><th>優先度</th></tr>
                        {hb_rows}
                    </table>
                </div>"""

        # HA管理インターフェース
        mgmt_rows = ""
        if ha.ha_mgmt_interfaces:
            for mgmt in ha.ha_mgmt_interfaces:
                mgmt_rows += f"""<tr>
                    <td>{self.escape(mgmt.id)}</td>
                    <td>{self.escape(mgmt.interface)}</td>
                    <td><code>{self.escape(mgmt.dst) if mgmt.dst else '-'}</code></td>
                    <td><code>{self.escape(mgmt.gateway) if mgmt.gateway else '-'}</code></td>
                </tr>"""

        mgmt_section = ""
        if mgmt_rows:
            mgmt_section = f"""
                <h4>HA管理インターフェース</h4>
                <div class="table-responsive">
                    <table class="table table-sm table-bordered">
                        <tr><th>ID</th><th>インターフェース</th><th>管理IPアドレス</th><th>ゲートウェイ</th></tr>
                        {mgmt_rows}
                    </table>
                </div>"""

        return f"""
            <div id="{section_id}" class="subsection">
                <h3>{section_num} HA設定</h3>

                <div class="info-grid">
                    <div class="info-card">
                        <h4>HA基本設定</h4>
                        <table class="table table-sm table-bordered">
                            <tr><td>HAモード</td><td><strong>{self.escape(ha.mode.value)}</strong></td></tr>
                            <tr><td>グループID</td><td>{self.escape(ha.group_id)}</td></tr>
                            <tr><td>グループ名</td><td>{self.escape(ha.group_name) if ha.group_name else "-"}</td></tr>
                            <tr><td>優先度</td><td>{self._with_default_annotation(ha.priority, 'ha.priority') if ha.priority else "-"}</td></tr>
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
                            <tr><td>ハートビート間隔</td><td>{self._with_default_annotation(ha.hb_interval, 'ha.hb_interval')}</td></tr>
                            <tr><td>ハートビート損失閾値</td><td>{self._with_default_annotation(ha.hb_lost_threshold, 'ha.hb_lost_threshold')}</td></tr>
                            <tr><td>暗号化</td><td>{'有効' if ha.encryption else '無効'}</td></tr>
                            <tr><td>認証</td><td>{'有効' if ha.authentication else '無効'}</td></tr>
                        </table>
                    </div>
                </div>
                {hb_section}
                {mgmt_section}
            </div>"""

    def _generate_logging_section(
        self, section_num: str = "1.5", section_id: str = "global-logging"
    ) -> str:
        """ログ・監視設定セクション（グローバル）"""
        logging = self.config.logging

        # Syslog
        syslog_rows = ""
        for syslog in logging.syslog_servers:
            log_types_display = (
                self._list_to_str(syslog.log_types) if syslog.log_types else "全種別"
            )
            syslog_rows += f"""<tr>
                <td><code>{self.escape(syslog.server)}</code></td>
                <td>{self.escape(syslog.port)}</td>
                <td>{log_types_display}</td>
                <td>{self.escape(syslog.status)}</td>
            </tr>"""

        # SNMP
        snmp_rows = ""
        for snmp in logging.snmp:
            trap_hosts_display = self._list_to_str(snmp.trap_hosts) if snmp.trap_hosts else "-"
            hosts_display = self._list_to_str(snmp.hosts) if snmp.hosts else "-"
            snmp_rows += f"""<tr>
                <td>{'有効' if snmp.enabled else '無効'}</td>
                <td>{self.escape(snmp.version)}</td>
                <td>{self.escape(snmp.community) if snmp.community else self.escape(snmp.username)}</td>
                <td>{hosts_display}</td>
                <td>{trap_hosts_display}</td>
            </tr>"""

        # 集中管理（表形式）
        central_mgmt_rows = ""
        if logging.fortianalyzer_server:
            status_display = (
                self.escape(logging.fortianalyzer_status) if logging.fortianalyzer_status else "-"
            )
            central_mgmt_rows += f"""<tr>
                <td>FortiAnalyzer</td>
                <td><code>{self.escape(logging.fortianalyzer_server)}</code></td>
                <td>{status_display}</td>
            </tr>"""
        if logging.panorama_server:
            central_mgmt_rows += f"""<tr>
                <td>Panorama</td>
                <td><code>{self.escape(logging.panorama_server)}</code></td>
                <td>-</td>
            </tr>"""

        return f"""
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
            </div>"""
