"""HTML/SVG rendering of offline analysis, with no external rendering service."""

from html import escape

from analyzers import analyze_security

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


from exporters.network_map import render_network_map as render_topology  # noqa: F401
