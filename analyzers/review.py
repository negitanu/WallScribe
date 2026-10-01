"""Coverage and firmware-specific default provenance; no online scraping at runtime."""

import re

from .network import Resolver, network

FORTI_GLOBAL = "https://docs.fortinet.com/document/fortigate/7.4.8/cli-reference/339914554/config-system-global"
PAN_RULES = "https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-admin/policy/security-policy"
CATALOG = [
    {
        "vendor": "FortiGate",
        "firmware": "7.4.8",
        "field": "system_settings.https_port",
        "value": "443",
        "source": FORTI_GLOBAL,
        "precision": "patch",
    },
    {
        "vendor": "FortiGate",
        "firmware": "7.4.8",
        "field": "system_settings.ssh_port",
        "value": "22",
        "source": FORTI_GLOBAL,
        "precision": "patch",
    },
    {
        "vendor": "Palo Alto",
        "firmware": "11.1",
        "field": "implicit.intrazone",
        "value": "allow",
        "source": PAN_RULES,
        "precision": "minor",
    },
    {
        "vendor": "Palo Alto",
        "firmware": "11.1",
        "field": "implicit.interzone",
        "value": "deny",
        "source": PAN_RULES,
        "precision": "minor",
    },
]


def default_provenance(config, field):
    versions = re.findall(r"(?<![\d.])(\d+\.\d+(?:\.\d+)?)(?![\d.])", config.device_info.os_version)
    version = versions[0] if versions else ""
    for entry in CATALOG:
        applies = (
            version == entry["firmware"]
            if entry["precision"] == "patch"
            else version == entry["firmware"] or version.startswith(entry["firmware"] + ".")
        )
        if (
            entry["vendor"] == config.device_info.device_type.value
            and entry["field"] == field
            and config.device_info.os_version_source != "config-schema-version"
            and applies
        ):
            return dict(
                entry,
                status="documented_default",
                detected_firmware=config.device_info.os_version,
                checked_on="2026-09-30",
                version_evidence=config.device_info.os_version_source or "指定されたモデル値",
                review="公式資料の版を照合。稼働機の上書き・モデル差・パッチ差を確認してください",
            )
    return {
        "field": field,
        "status": "unverified_default",
        "detected_firmware": config.device_info.os_version or "不明",
        "value": "未検証",
        "version_evidence": config.device_info.os_version_source or "不明",
        "source": "",
        "review": "該当ファームウェアの公式資料と show full-configuration / 実効設定で確認してください",
    }


def analyze_review(config, *, include_coverage_details=True):
    items = []

    def add(kind, scope, target, evidence, suggestion, source=""):
        items.append(
            dict(
                kind=kind,
                scope=scope,
                target=target,
                evidence=evidence,
                suggestion=suggestion,
                source=source,
            )
        )

    for path in config.unsupported_sections if include_coverage_details else []:
        add(
            "未対応/部分解析",
            "-",
            path,
            "この設定パスは診断モデルに完全に反映していません（値は表示しません）",
            "原本と実効設定を確認。通信・整理の結論を保留",
        )
    if config.parse_errors:
        add(
            "パース警告",
            "-",
            "入力設定",
            f"{len(config.parse_errors)} 件。警告がある入力からは実効設定を保証できません",
            "形式と原本を確認して再出力。秘密情報を含む可能性がある原文は表示しません",
        )
    if config.device_info.os_version_source == "config-schema-version":
        add(
            "ファームウェア未確定",
            "-",
            "機器の版",
            "XML version は設定スキーマの版であり、稼働ファームウェアの証拠にはしません",
            "detail-version または実機情報を取得してください。CLI --firmware-version で実機確認済みの版を指定できます",
        )
    resolver = Resolver(config)
    o = config.objects
    for policies in (config.firewall_policies, config.local_in_policies):
        for p in policies:
            for attr, collections in [
                ("source_address", [o.addresses, o.address_groups]),
                ("destination_address", [o.addresses, o.address_groups]),
                ("service", [o.services, o.service_groups]),
            ]:
                for name in getattr(p, attr):
                    if name.lower() in ("any", "all"):
                        continue
                    if attr != "service":
                        try:
                            network(name)
                            continue
                        except ValueError:
                            pass
                    if resolver.lookup(name, p.vdom, collections) is None:
                        add(
                            "未解決参照",
                            p.vdom,
                            f"{p.policy_id}: {attr} / {name}",
                            "組み込み定義、VIP、外部管理定義、欠落のいずれかを確定できません",
                            "該当版の組み込み定義と Panorama/VDOM の実効設定を確認",
                        )
            for name in getattr(p, "unmodeled_fields", []):
                add("未確定条件", p.vdom, p.policy_id, name, "条件の実効値・既定値を人が確認")
    for groups, collections in [
        (o.address_groups, [o.addresses, o.address_groups]),
        (o.service_groups, [o.services, o.service_groups]),
    ]:
        # Each definition and member edge is inspected once. A per-path seen set
        # still enumerates exponentially many paths through a diamond graph.
        colors = {}
        unresolved = set()
        for group in groups:
            if getattr(group, "dynamic_filter", ""):
                add(
                    "動的条件",
                    group.vdom,
                    group.name,
                    "動的グループの実行時メンバーは設定単体では不明",
                    "タグ登録状況と実行時メンバーを確認",
                )
            if colors.get(id(group)):
                continue
            colors[id(group)] = 1
            pending = [(group, iter(group.members))]
            while pending:
                current, members = pending[-1]
                name = next(members, None)
                if name is None:
                    colors[id(current)] = 2
                    pending.pop()
                    continue
                obj = resolver.lookup(name, current.vdom, collections)
                if obj is None and name.lower() not in ("all", "any"):
                    edge = (id(current), name)
                    if edge not in unresolved:
                        unresolved.add(edge)
                        add(
                            "未解決参照",
                            current.vdom,
                            current.name + " → " + name,
                            "グループメンバーを解決できません",
                            "組み込み定義または欠落を確認",
                        )
                elif obj is not None and hasattr(obj, "members"):
                    color = colors.get(id(obj), 0)
                    if color == 1:
                        add(
                            "参照循環",
                            group.vdom,
                            group.name,
                            "グループ参照が循環しています",
                            "構成と実効メンバーを確認",
                        )
                    elif color == 0:
                        colors[id(obj)] = 1
                        pending.append((obj, iter(obj.members)))
    for iface in config.interfaces:
        if not iface.vdom_assignment_known or not iface.management_access_known:
            add(
                "所属/参照不明",
                iface.vdom,
                iface.name,
                "IF 所属または管理プロファイルを確定できません",
                "vsys import、ゾーン、管理プロファイルを確認",
            )
    defaults = [default_provenance(config, path) for path in sorted(config.default_fields)]
    if config.device_info.device_type.value == "Palo Alto":
        defaults += [
            default_provenance(config, "implicit." + zone) for zone in ("intrazone", "interzone")
        ]
    for d in defaults:
        add(
            "既定値確認",
            "-",
            d["field"],
            f"機器版: {d['detected_firmware']} / {'公式資料で確認' if d['status'] == 'documented_default' else '未検証'} / 値: {d['value']} / 資料版: {d.get('firmware','未登録')} ({'パッチ一致' if d.get('precision') == 'patch' else '系列の資料・パッチ個別確認が必要' if d.get('precision') == 'minor' else '照合不可'})",
            d["review"],
            d["source"],
        )
    return {
        "items": items,
        "defaults": defaults,
        "human_decision_required": True,
        "limitations": [
            "設定単体の解析は完全解析の保証ではありません。解析したセクションも全オプションを網羅しません。",
            "既定値の資料は版別のローカルカタログです。未登録版へ別版の値を流用しません。公式資料の既定値は実機設定の証明ではありません。",
        ],
    }
