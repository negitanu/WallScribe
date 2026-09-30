"""Conservative configuration checks; findings are review items, not exploit claims."""

from dataclasses import asdict, dataclass, field
from ipaddress import ip_interface, ip_network
from typing import List

from models.config import ConfigModel, DeviceType, PolicyAction

FORTINET = "https://docs.fortinet.com/document/fortigate/7.6.0/best-practices/555436/hardening"
PALOALTO = "https://docs.paloaltonetworks.com/ngfw/networking/configure-interfaces/use-interface-management-profiles-to-restrict-access"
POLICY_REFERENCE = "https://docs.paloaltonetworks.com/best-practices/10-1/internet-gateway-best-practices/best-practice-internet-gateway-security-policy"


@dataclass(frozen=True)
class SecurityFinding:
    rule_id: str
    severity: str
    title: str
    scope: str
    target: str
    evidence: str
    recommendation: str
    confidence: str = "high"
    reference: str = ""


@dataclass
class SecurityReport:
    findings: List[SecurityFinding] = field(default_factory=list)
    checks: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @property
    def counts(self):
        return {
            level: sum(f.severity == level for f in self.findings)
            for level in ("high", "medium", "info")
        }


def _universal(value: str) -> bool:
    if value.lower() in {"any", "all"}:
        return True
    try:
        return ip_network(value, strict=False).prefixlen == 0
    except ValueError:
        return False


def _addresses_unrestricted(names, scope, objects, groups):
    """Resolve static groups iteratively, preserving the defining object's scope."""
    pending = [(name, scope) for name in names]
    seen = set()
    while pending:
        name, context = pending.pop()
        if (context, name) in seen:
            continue
        seen.add((context, name))
        if _universal(name):
            return True
        for owner in dict.fromkeys((context, "shared")):
            obj = objects.get((owner, name))
            group = groups.get((owner, name))
            if obj:
                if obj.object_type in {"subnet", "ip-netmask"} and _universal(obj.value):
                    return True
                break
            if group:
                if not group.dynamic_filter:
                    pending.extend((member, owner) for member in group.members)
                break
    return False


def analyze_security(config: ConfigModel) -> SecurityReport:
    """Run offline checks without contacting devices or exposing password/community values."""
    report = SecurityReport(
        checks=[
            "MGMT-CLEARTEXT",
            "MGMT-PUBLIC",
            "ADMIN-SOURCE",
            "POLICY-BROAD",
            "POLICY-LOG",
            "POLICY-PROFILE",
            "SNMP-LEGACY",
        ],
        limitations=[
            "設定の静的診断です。実際の到達性、上流 ACL、稼働状態、CVE、パッチ適用状況は検証しません。",
            "省略値・未対応の設定・動的オブジェクト・ルールの実効順序により判断できない項目があります。",
            "指摘ゼロは安全性の証明ではありません。業務要件と併せて確認してください。",
        ],
    )
    vendor_reference = (
        PALOALTO if config.device_info.device_type == DeviceType.PALOALTO else FORTINET
    )

    def add(
        rule_id,
        severity,
        title,
        scope,
        target,
        evidence,
        recommendation,
        confidence="high",
        reference="",
    ):
        report.findings.append(
            SecurityFinding(
                rule_id,
                severity,
                title,
                scope,
                target,
                evidence,
                recommendation,
                confidence,
                reference,
            )
        )

    if config.parse_errors:
        add(
            "DATA-PARTIAL",
            "info",
            "解析できない設定があります",
            "global",
            "入力設定",
            f"解析エラー／未対応行: {len(config.parse_errors)} 件",
            "元の設定と解析エラーを確認し、診断・構造図の欠落部分を補ってください。",
        )

    for iface in config.interfaces:
        if iface.status.lower() in {"down", "disabled", "disable"}:
            continue
        if not iface.management_access_known:
            add(
                "DATA-MGMT",
                "info",
                "管理プロファイルの実設定が不明です",
                iface.vdom,
                iface.name,
                f"参照プロファイル: {iface.management_profile}",
                "参照先の管理プロファイルを含む設定を取り込み、許可プロトコルと接続元を確認してください。",
            )
            continue
        protocols = {p.lower() for p in iface.allowed_access}
        cleartext = protocols & {"http", "telnet"}
        if cleartext:
            add(
                "MGMT-CLEARTEXT",
                "high",
                "平文の管理アクセスが有効です",
                iface.vdom,
                iface.name,
                "許可プロトコル: " + ", ".join(sorted(cleartext)),
                "HTTP / Telnet を無効にし、HTTPS / SSH と管理ネットワークに限定してください。",
                reference=vendor_reference,
            )
        public_ips = []
        for raw in iface.ip_address.split(","):
            try:
                if ip_interface(raw.strip()).ip.is_global:
                    public_ips.append(raw.strip())
            except ValueError:
                continue
        if public_ips and protocols & {"http", "https", "ssh", "telnet", "snmp"}:
            restricted = bool(iface.management_permitted_ips) and not any(
                _universal(ip) for ip in iface.management_permitted_ips
            )
            add(
                "MGMT-PUBLIC",
                "medium" if restricted else "high",
                "公開 IP の IF で管理サービスが有効です",
                iface.vdom,
                iface.name,
                f"IP: {', '.join(public_ips)}; 許可: {', '.join(sorted(protocols))}; "
                f"IF 接続元制限: {'設定あり' if restricted else 'モデル上は確認できません'}",
                "管理専用 IF / VPN を利用し、接続元制限、trusted hosts、local-in policy と上流 ACL を確認してください。",
                confidence="medium",
                reference=vendor_reference,
            )

    for admin in config.system_settings.admin_users:
        if not admin.trust_hosts or any(_universal(host) for host in admin.trust_hosts):
            add(
                "ADMIN-SOURCE",
                "medium",
                "管理者の接続元制限を確認してください",
                "global",
                admin.username,
                "解析結果に限定された trusted hosts / permitted IP がありません。",
                "管理用端末・踏み台の IP に制限してください。他の ACL で制限している場合は併せて確認してください。",
                confidence="medium",
                reference=vendor_reference,
            )

    objects = {(a.vdom, a.name): a for a in config.objects.addresses}
    groups = {(g.vdom, g.name): g for g in config.objects.address_groups}
    for policy in config.firewall_policies:
        if not policy.enabled or policy.action != PolicyAction.ALLOW:
            continue
        target = f"{policy.policy_id}: {policy.name}"
        source_any = not policy.source_negate and _addresses_unrestricted(
            policy.source_address, policy.vdom, objects, groups
        )
        dest_any = (
            not policy.destination_negate
            and not policy.internet_service_name
            and _addresses_unrestricted(policy.destination_address, policy.vdom, objects, groups)
        )
        service_any = any(s.lower() in {"any", "all"} for s in policy.service)
        app_any = config.device_info.device_type != DeviceType.PALOALTO or any(
            a.lower() == "any" for a in policy.application
        )
        if source_any and dest_any and service_any and app_any:
            user_constraint = policy.source_groups or any(
                u.lower() != "any" for u in policy.source_users
            )
            add(
                "POLICY-BROAD",
                "medium" if user_constraint else "high",
                "アドレス・サービスの広い許可ルールです",
                policy.vdom,
                target,
                f"送信元={', '.join(policy.source_address)}; 宛先={', '.join(policy.destination_address)}; "
                f"サービス={', '.join(policy.service)}; 否定条件なし。スケジュール={policy.schedule or '未指定'}",
                "必要な通信元・宛先・アプリケーション・サービスに絞り、ルール順序と業務上の必要性を確認してください。",
                reference=(
                    POLICY_REFERENCE
                    if config.device_info.device_type == DeviceType.PALOALTO
                    else FORTINET
                ),
            )
        if not policy.log_enabled:
            add(
                "POLICY-LOG",
                "medium",
                "許可ルールのログ取得を確認してください",
                policy.vdom,
                target,
                "解析結果: ログ有効=False（省略時の既定値を含む）。",
                "セッションログを有効にし、ログ保存・転送・保持期間も確認してください。",
                confidence="medium",
            )
        if not policy.security_profiles:
            add(
                "POLICY-PROFILE",
                "info",
                "脅威検査プロファイルの割り当てを確認してください",
                policy.vdom,
                target,
                "解析結果にセキュリティプロファイルの参照がありません。",
                "インターネット向けなど検査が必要な通信に IPS / AV 等を適用してください。内部通信では業務要件に応じて判断してください。",
                confidence="medium",
            )

    for index, snmp in enumerate(config.logging.snmp, 1):
        if snmp.enabled and snmp.version.lower() in {"v1", "v2", "v2c", "1", "2", "2c"}:
            add(
                "SNMP-LEGACY",
                "medium",
                "SNMP v1/v2c が有効です",
                "global",
                f"SNMP設定 {index}",
                f"version={snmp.version}; enabled=True",
                "SNMPv3 の認証・暗号化を利用し、監視サーバーからの通信だけに制限してください。",
                reference=vendor_reference,
            )
    order = {"high": 0, "medium": 1, "info": 2}
    report.findings.sort(key=lambda f: (order[f.severity], f.scope, f.rule_id, f.target))
    return report
