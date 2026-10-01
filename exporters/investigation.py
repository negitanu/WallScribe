"""Reviewable offline investigation report sections."""

import json
from html import escape
from pathlib import Path

from analyzers import flow_snapshot
from analyzers.network import LIMITATIONS


def script():
    content = (
        Path(__file__).resolve().parent.parent / "static/js/network_investigation.js"
    ).read_text(encoding="utf-8")
    # defer initialization until all optional sections have been parsed.
    return (
        '<script>document.addEventListener("DOMContentLoaded",function(){'
        + content
        + "});</script>"
    )


def render_flow(config, num, section_id, for_pdf=False):
    notes = "".join("<li>" + escape(n) + "</li>" for n in LIMITATIONS)
    header = f'<div id="{escape(section_id)}" class="subsection"><h3>{num} 通信候補の確認</h3><ul>{notes}</ul>'
    if for_pdf:
        return (
            header
            + "<p>入力による照合は HTML レポートまたは CLI の --flow オプションを利用してください。</p></div>"
        )
    scopes = list(
        dict.fromkeys(
            [p.vdom for p in config.firewall_policies] + [i.vdom for i in config.interfaces]
        )
    ) or ["root"]
    options = "".join(f"<option>{escape(s)}</option>" for s in scopes)
    data = flow_snapshot(config)
    data["incomplete"] = bool(config.parse_errors or config.unsupported_sections)
    data["limitations"] = LIMITATIONS
    encoded = (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    return (
        header
        + f"""<p>IP は NAT 変換前のパケットとして入力してください。ポリシーは入力アドレスで照合し、NAT 変換後のポリシー・ルートは自動評価しません。</p><form id="flow-query" class="flow-query">
<label>送信元 IP <input name="source" required placeholder="192.0.2.10"></label>
<label>宛先 IP <input name="destination" required placeholder="198.51.100.20"></label>
<label>プロトコル <select name="protocol"><option>TCP</option><option>UDP</option></select></label>
<label>宛先ポート <input name="port" type="number" min="1" max="65535" value="443" required></label>
<label>区画 <select name="scope">{options}</select></label>
<label>送信元 IF / ゾーン（任意）<input name="source_interface"></label>
<label>宛先 IF / ゾーン（任意）<input name="destination_interface"></label>
<button type="submit">候補と根拠を確認</button></form>
<div id="flow-result" aria-live="polite"></div><script type="application/json" id="flow-data">{encoded}</script></div>"""
        + script()
    )
