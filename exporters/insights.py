"""HTML/SVG rendering of offline analysis, with no external rendering service."""

import math
import unicodedata
from html import escape

from analyzers import analyze_security, infer_topology

SEVERITY = {"high": "高", "medium": "中", "info": "確認"}


def render_security(config, section_num, section_id, cluster=False):
    report = analyze_security(config)
    if cluster:
        report.limitations.append(
            "クラスタ代表機の設定を診断しています。メンバーごとの設定差分は対象外です。"
        )
    rows = []
    for finding in report.findings:
        values = [
            f"{SEVERITY[finding.severity]} / {finding.rule_id}",
            finding.title,
            f"{finding.scope} / {finding.target}",
            finding.evidence,
            finding.recommendation,
            "高" if finding.confidence == "high" else "中",
        ]
        cells = "".join(f"<td>{escape(v)}</td>" for v in values)
        reference = (
            f'<a href="{escape(finding.reference, quote=True)}" rel="noreferrer">公式資料</a>'
            if finding.reference
            else "ルールベース診断"
        )
        rows.append(f'<tr class="finding-{finding.severity}">{cells}<td>{reference}</td></tr>')
    counts = " / ".join(f"{SEVERITY[key]}: {value} 件" for key, value in report.counts.items())
    notes = "".join(f"<li>{escape(note)}</li>" for note in report.limitations)
    body = (
        "".join(rows)
        or '<tr><td colspan="7">対応する診断項目では指摘が見つかりませんでした。</td></tr>'
    )
    return f"""<div id="{escape(section_id)}" class="subsection security-analysis">
<h3>{section_num} セキュリティ診断</h3><div class="summary-box">{counts}</div>
<p>検査項目: {escape(', '.join(report.checks))}</p><ul>{notes}</ul>
<div class="table-responsive"><table class="table table-bordered table-striped">
<thead><tr><th>重要度 / ID</th><th>指摘</th><th>対象</th><th>根拠</th><th>改善案</th><th>確信度</th><th>参照</th></tr></thead>
<tbody>{body}</tbody></table></div></div>"""


def _lines(node, width):
    lines = []
    for value in (
        [node.label] + node.details + (["設定上 IF 無効"] if node.status == "down" else [])
    ):
        line, columns = "", 0
        for character in value:
            advance = 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
            if character == "\n" or columns + advance > width:
                lines.append(line)
                line, columns = "", 0
            if character != "\n":
                line += character
                columns += advance
        lines.append(line)
    return lines


def _box(node, x, y, width, height, line_width):
    colors = {
        "device": ("#172c45", "#ffffff"),
        "interface": ("#eaf3ff", "#183c61"),
        "subnet": ("#edf7f3", "#195b48"),
        "route": ("#fff5e6", "#70430f"),
        "discard": ("#fcecec", "#842b2b"),
    }
    fill, color = colors[node.kind]
    dash = ' stroke-dasharray="6 4"' if node.kind == "subnet" else ""
    text = []
    lines = _lines(node, line_width)
    top = y + (height - len(lines) * 19) / 2 + 15
    for i, line in enumerate(lines):
        text.append(
            f'<tspan x="{x+14}" y="{top+i*19}" font-weight="{600 if i == 0 else 400}">{escape(line)}</tspan>'
        )
    return f"""<g><title>{escape(node.label + ': ' + '; '.join(node.details))}</title>
<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="9" fill="{fill}" stroke="{color}"{dash}/>
<text fill="{color}" font-size="14" font-family="sans-serif">{''.join(text)}</text></g>"""


def render_topology(config, section_num, section_id, for_pdf=False, cluster=False):
    topology = infer_topology(config)
    if cluster:
        topology.limitations.append(
            "クラスタ代表機の論理構造です。HA の物理配線・メンバー別の構造は対象外です。"
        )
    figures = []
    scopes = list(dict.fromkeys(node.scope for node in topology.nodes))
    for scope_index, scope in enumerate(scopes):
        nodes = [node for node in topology.nodes if node.scope == scope]
        device = next(node for node in nodes if node.kind == "device")
        interfaces = [node for node in nodes if node.kind == "interface"]
        routes = [node for node in nodes if node.kind in {"route", "discard"}]
        nodes_by_id = {node.id: node for node in nodes}
        interface_ids = {node.id for node in interfaces}
        subnet_by_interface = {
            edge.target: nodes_by_id[edge.source]
            for edge in topology.edges
            if edge.relation == "IP から推定" and edge.target in interface_ids
        }
        page_count = max(1, math.ceil(max(len(interfaces), len(routes)) / 4))
        for page in range(page_count):
            left = interfaces[page * 4 : (page + 1) * 4]
            right = routes[page * 4 : (page + 1) * 4]
            rows = max(1, len(left), len(right))
            heights = []
            for i in range(rows):
                candidates = []
                if i < len(left):
                    candidates.append((left[i], 30))
                    if left[i].id in subnet_by_interface:
                        candidates.append((subnet_by_interface[left[i].id], 31))
                if i < len(right):
                    candidates.append((right[i], 36))
                heights.append(
                    max([100] + [len(_lines(node, width)) * 19 + 32 for node, width in candidates])
                )
            device_min = len(_lines(device, 20)) * 19 + 40
            if sum(heights) + (rows - 1) * 45 < device_min:
                heights[0] += device_min - (sum(heights) + (rows - 1) * 45)
            diagram_height = sum(heights) + (rows - 1) * 45 + 110
            markup = []
            label_y = 29
            for x, title in (
                (20, "直結ネットワーク（推定）"),
                (315, "インターフェース"),
                (610, "論理区画"),
                (830, "設定ルート / next-hop"),
            ):
                markup.append(
                    f'<text x="{x}" y="{label_y}" fill="#45566d" font-size="14" font-family="sans-serif">{title}</text>'
                )
            y = 65
            for i, height in enumerate(heights):
                middle = y + height / 2
                if i < len(left):
                    iface = left[i]
                    subnet = subnet_by_interface.get(iface.id)
                    if subnet:
                        markup.append(_box(subnet, 20, y, 250, height, 31))
                        markup.append(
                            f'<path d="M270 {middle} H315" fill="none" stroke="#397d68" stroke-width="2" stroke-dasharray="5 5"/>'
                        )
                    markup.append(_box(iface, 315, y, 240, height, 30))
                    markup.append(
                        f'<path d="M555 {middle} H610" fill="none" stroke="#3e6589" stroke-width="2"/>'
                    )
                if i < len(right):
                    markup.append(_box(right[i], 830, y, 295, height, 36))
                    markup.append(
                        f'<path d="M790 {middle} H830" fill="none" stroke="#98692a" stroke-width="2"/>'
                    )
                y += height + 45
            markup.append(_box(device, 610, 65, 180, diagram_height - 110, 20))
            if not interfaces and not routes:
                markup.append(
                    '<text x="20" y="100" font-size="14" fill="#45566d">IF / ルート情報がなく、周辺構造は推定できません。</text>'
                )
            suffix = f" ({page+1}/{page_count})" if page_count > 1 else ""
            figures.append(
                f"""<figure class="topology-figure"><figcaption>{escape(scope)}{suffix}</figcaption>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1145 {diagram_height}" width="100%" role="img"
aria-labelledby="topology-title-{scope_index}-{page}"><title id="topology-title-{scope_index}-{page}">{escape(scope)} の設定から推定した論理構造</title>{''.join(markup)}</svg></figure>"""
            )
    flow_rows = "".join(
        f"<tr><td>{escape(flow.scope)}</td><td>{escape(flow.policy)}</td>"
        f'<td>{escape(", ".join(flow.source))}</td><td>{escape(", ".join(flow.destination))}</td>'
        f"<td>{escape(flow.conditions)}</td></tr>"
        for flow in topology.flows
    )
    if flow_rows:
        flows = f"""<details {'open' if for_pdf else ''}><summary>許可ポリシーの通信条件（物理接続ではありません）</summary>
<div class="table-responsive"><table class="table table-bordered"><tr><th>区画</th><th>ルール</th><th>送信元 IF / ゾーン</th><th>宛先 IF / ゾーン</th><th>条件</th></tr>{flow_rows}</table></div></details>"""
    else:
        flows = "<p>解析された有効な許可ポリシーはありません。</p>"
    notes = "".join(f"<li>{escape(note)}</li>" for note in topology.limitations)
    return f"""<div id="{escape(section_id)}" class="subsection network-topology"><h3>{section_num} 推定ネットワーク構造</h3>
<ul>{notes}</ul>{''.join(figures)}{flows}</div>"""
