"""One embedded, offline network map for all configured logical partitions."""

import json
import unicodedata
from collections import defaultdict
from dataclasses import asdict
from html import escape
from pathlib import Path

from analyzers import analyze_security, infer_topology
from analyzers.network import LIMITATIONS, flow_snapshot
from exporters.investigation import script
from exporters.network_layout import layout_topology


def short_label(value, columns=30):
    """Bound labels by display width; full text remains in title and inspector."""
    used, text = 0, ""
    for char in value:
        used += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
        if used > columns:
            return text + "…"
        text += char
    return text


def render_network_map(config, section_num, section_id, for_pdf=False, cluster=False):
    topology = infer_topology(config)
    scopes = list(dict.fromkeys(node.scope for node in topology.nodes))
    grouped = defaultdict(list)
    scoped_policies = defaultdict(list)
    for index, policy in enumerate(config.firewall_policies):
        scoped_policies[policy.vdom].append((index, policy))
    findings = defaultdict(list)
    for finding in analyze_security(config).findings:
        findings[(finding.scope, finding.target)].append(asdict(finding))
    for node in topology.nodes:
        grouped[node.scope].append(node)
    positions, bounds, width, height = layout_topology(topology)
    cards, nodes = [], []
    for scope in scopes:
        x, y, box_width, box_height = bounds[scope]
        cards.append(
            f'<g class="map-scope" data-scope="{escape(scope, quote=True)}"><rect x="{x}" y="{y}" width="{box_width}" height="{box_height}" rx="20"/><text x="{x+22}" y="{y+30}" class="map-scope-title">{escape(scope)}</text><text x="{x+22}" y="{y+52}" class="map-scope-meta">{sum(n.kind == "interface" for n in grouped[scope])} IF · {sum(n.kind in ("route", "discard") for n in grouped[scope])} 設定ルート</text></g>'
        )
        for node in grouped[scope]:
            item = asdict(node)
            item["findings"] = (
                findings[(node.scope, node.label)] if node.kind == "interface" else []
            )
            interface = (
                next(
                    (i for i in config.interfaces if i.name == node.label and i.vdom == scope), None
                )
                if node.kind == "interface"
                else None
            )
            references = {node.label, interface.zone if interface else ""}
            item["zone"] = interface.zone if interface else ""
            item["policies"] = [
                index
                for index, p in scoped_policies[scope]
                if node.kind in ("device", "interface")
                and (
                    node.kind in ("device", "router")
                    or bool(references.intersection(p.source_interface + p.destination_interface))
                    or any(
                        n.lower() in ("any", "all")
                        for n in p.source_interface + p.destination_interface
                    )
                )
            ]
            nodes.append(item)
    edges, lines = [], []
    lookup = {node.id: node for node in topology.nodes}
    ports = defaultdict(list)
    for edge in topology.edges:
        if lookup[edge.source].scope == lookup[edge.target].scope:
            for endpoint in (edge.source, edge.target):
                if lookup[endpoint].kind in ("device", "router"):
                    ports[endpoint].append(edge)

    def anchor(endpoint, edge):
        x, _, w, _ = positions[endpoint]
        siblings = ports[endpoint]
        if not siblings:
            return x + w / 2
        return x + w * (siblings.index(edge) + 1) / (len(siblings) + 1)

    for index, edge in enumerate(topology.edges):
        item = asdict(edge) | {"id": "edge-" + str(index)}
        item["active"] = (
            lookup[edge.source].status != "down" and lookup[edge.target].status != "down"
        )
        edges.append(item)
        sx, sy, sw, sh = positions[edge.source]
        tx, ty, tw, th = positions[edge.target]
        if edge.relation in ("VDOM 間リンク", "vsys 間接続", "VR 所属", "next-vr"):
            # Cross-partition links run in the outer gutter, never through a node.
            source_box = bounds[lookup[edge.source].scope]
            target_box = bounds[lookup[edge.target].scope]
            if source_box[1] + source_box[3] <= target_box[1]:
                lane = source_box[1] + source_box[3] + 30 + (index % 5) * 9
            elif target_box[1] + target_box[3] <= source_box[1]:
                lane = target_box[1] + target_box[3] + 30 + (index % 5) * 9
            else:
                lane = min(source_box[1], target_box[1]) - 22 - (index % 5) * 9
            left_gutter = bounds[lookup[edge.source].scope][0] + 8
            right_gutter = bounds[lookup[edge.target].scope][0] + 8
            path = f"M{sx+sw/2} {sy+sh} V{sy+sh+14} H{left_gutter} V{lane} H{right_gutter} V{ty-14} H{tx+tw/2} V{ty}"
        else:
            # Local graph levels flow top-to-bottom, with centered fan-out.
            if sy != ty:
                ax, bx = anchor(edge.source, edge), anchor(edge.target, edge)
                ay, by = (sy + sh, ty) if sy < ty else (sy, ty + th)
                middle = (ay + by) / 2
                if abs(sy - ty) > 150:
                    # Wrapped tiers use a side corridor, avoiding opaque intermediate nodes.
                    gutter = bounds[lookup[edge.source].scope][0] + 8 + (index % 3) * 5
                    step = 14 if by > ay else -14
                    path = f"M{ax} {ay} V{ay+step} H{gutter} V{by-step} H{bx} V{by}"
                else:
                    path = f"M{ax} {ay} V{middle} H{bx} V{by}"
            else:
                ax, bx = (sx + sw, tx) if sx < tx else (sx, tx + tw)
                path = f"M{ax} {sy+sh/2} H{bx}"
        kind = (
            "interlink"
            if edge.relation in ("VDOM 間リンク", "vsys 間接続", "VR 所属", "next-vr")
            else "inferred" if edge.confidence == "inferred" else "configured"
        )
        arrow = ' marker-end="url(#map-arrow)"' if edge.directed else ""
        lines.append(
            f'<path{arrow} class="map-edge {kind}{" inactive" if not item["active"] else ""}" data-edge="{item["id"]}" d="{path}" tabindex="0" role="button" aria-label="{escape(edge.relation + ": " + edge.evidence, quote=True)}"><title>{escape(edge.relation + ": " + edge.evidence)}</title></path>'
        )
    shapes = []
    for node in nodes:
        x, y, w, h = positions[node["id"]]
        risk = (
            " high"
            if any(f["severity"] == "high" for f in node["findings"])
            else " warning" if node["findings"] else ""
        )
        label = short_label(node["label"])
        detail = short_label(" · ".join(node["details"]), 38)
        shapes.append(
            f'<g class="map-node {node["kind"]}{risk}{" inactive" if node["status"] == "down" else ""}" data-node="{node["id"]}" tabindex="0" role="button" aria-label="{escape(node["scope"] + ": " + node["label"], quote=True)}"><title>{escape(node["label"] + ": " + "; ".join(node["details"]))}</title><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10"/><text x="{x+14}" y="{y+25}" class="map-node-label">{escape(label)}</text><text x="{x+14}" y="{y+46}" class="map-node-detail">{escape(detail)}</text></g>'
        )
    styles = (Path(__file__).resolve().parent.parent / "static/css/network_map.css").read_text()
    svg_styles = styles[styles.index(".map-scope rect") : styles.index(".map-inspector {")]
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" class="network-map-svg" viewBox="0 0 {width} {height}" role="img" aria-label="全区画 の統合ネットワーク図"><style>{svg_styles}</style><defs><marker id="map-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="#247b94"/></marker></defs>{"".join(cards)}{"".join(lines)}{"".join(shapes)}</svg>'
    notes = topology.limitations + (
        ["クラスタ代表機の論理構造です。メンバー間の物理配線は示しません。"] if cluster else []
    )
    note_html = (
        '<details class="map-limitations"><summary>図の根拠と確認が必要な範囲</summary><ul>'
        + "".join("<li>" + escape(n) + "</li>" for n in notes)
        + "</ul></details>"
    )
    header = f'<div id="{escape(section_id)}" class="subsection network-topology"><h3>{section_num} 推定ネットワーク構造</h3><p>全区画を一つの図に集約。青線は設定上の区画間接続・VR 所属、破線は IP から推定したネットワークです。通信可否の最終判断は人が行います。</p>'
    if for_pdf:
        return (
            header + '<figure class="topology-figure">' + svg + "</figure>" + note_html + "</div>"
        )
    scope_options = "".join(
        f'<option value="{escape(s, quote=True)}">{escape(s)}</option>'
        for s in scopes
        if s != "IF 所属未確定"
    )
    security_options = "".join(
        f'<option value="{escape(s, quote=True)}">{escape(s)}</option>'
        for s in scopes
        if not s.startswith("VR: ") and s != "IF 所属未確定"
    )
    encoded = (
        json.dumps(
            {
                "nodes": nodes,
                "edges": edges,
                "policy_findings": {
                    index: findings[(p.vdom, f"{p.policy_id}: {p.name}")]
                    for index, p in enumerate(config.firewall_policies)
                },
                "flow": flow_snapshot(config)
                | {
                    "incomplete": bool(config.parse_errors or config.unsupported_sections),
                    "limitations": LIMITATIONS,
                },
            },
            ensure_ascii=False,
        )
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    runtime = (Path(__file__).resolve().parent.parent / "static/js/network_map.js").read_text()
    return (
        header
        + "<style>"
        + styles
        + "</style>"
        + f"""<div class="network-explorer" data-network-explorer>
<div class="map-toolbar"><label>図内検索 <input data-map-search type="search" placeholder="IF・IP・VDOM・ルート"></label><label>区画 <select data-map-scope><option value="">全区画</option>{scope_options}</select></label><label class="map-toggle"><input data-map-hide-disabled type="checkbox">無効 IF を隠す</label><div class="map-buttons"><button type="button" data-map-zoom="in" aria-label="拡大">＋</button><button type="button" data-map-zoom="out" aria-label="縮小">−</button><button type="button" data-map-fit>全体表示</button><button type="button" data-map-fullscreen>図を広げる</button><button type="button" data-map-export>SVG 保存</button></div></div>
<div class="map-legend"><span class="legend-link">区画間接続・VR</span><span>設定上の所属・経路</span><span class="legend-inferred">IP から推定</span><span>赤: 要確認 · 薄表示: 無効</span></div>
<div class="map-workspace"><aside class="map-inspector map-device-panel" aria-live="polite"><p class="map-eyebrow">デバイス・接続情報</p><h4>ノードを選択</h4><p>図の機器や IF を選ぶと設定の詳細を表示します。</p></aside><div class="map-viewport">{svg}</div><aside class="map-policy-panel map-inspector" aria-live="polite"><p class="map-eyebrow">関連ポリシー</p><h4>インターフェースを選択</h4><p>入口・出口に関係するルールを表示します。ポリシーを選ぶと図上で方向を確認できます。</p></aside></div>
<form class="map-trace"><div class="map-trace-heading"><strong>区画間の動作を確認</strong><span>構造上の接続と区画別の通信候補を照合</span></div><label>送信元区画<select name="from_scope">{security_options}</select></label><label>宛先区画<select name="to_scope">{security_options}</select></label><label>送信元 IP<input name="source" placeholder="192.0.2.10" required></label><label>宛先 IP<input name="destination" placeholder="198.51.100.20" required></label><label>プロトコル<select name="protocol"><option>TCP</option><option>UDP</option></select></label><label>宛先ポート<input name="port" type="number" min="1" max="65535" value="443" required></label><button type="submit">図上で追跡</button><details class="map-trace-advanced"><summary>入口・出口の IF / ゾーンを指定（任意）</summary><label>送信元側の入口<input name="source_interface" placeholder="lan / trust"></label><label>宛先側の出口<input name="destination_interface" placeholder="wan / untrust"></label></details></form>
<div class="map-trace-result" aria-live="polite"></div><script type="application/json" class="map-data">{encoded}</script></div>"""
        + note_html
        + script()
        + '<script>document.addEventListener("DOMContentLoaded",function(){'
        + runtime
        + "});</script></div>"
    )
