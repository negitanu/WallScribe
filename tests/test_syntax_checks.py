"""The shared syntax gate must reject broken sources instead of skipping checks."""

import shutil

import pytest

from scripts.check_syntax import check


@pytest.mark.parametrize(
    "relative, source",
    [
        ("app.py", "def broken(:\n"),
        ("web/templates/broken.html", "{% if value %}"),
        ("static/css/broken.css", ".card { color red; }"),
        ("static/js/broken.js", "const = ;"),
    ],
)
def test_gate_rejects_invalid_sources(tmp_path, relative, source):
    if relative.endswith(".js") and not shutil.which("node"):
        pytest.skip("Node.js unavailable")
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    _, failures = check(tmp_path)
    assert len(failures) == 1 and relative in failures[0]


def test_valid_pdf_page_margins_and_missing_node_are_distinguished(tmp_path, monkeypatch):
    css = tmp_path / "static/css/page.css"
    css.parent.mkdir(parents=True)
    css.write_text("@page { size: A3 landscape; @bottom-center { content: counter(page); } }")
    assert not check(tmp_path)[1]
    javascript = tmp_path / "static/js/valid.js"
    javascript.parent.mkdir(parents=True)
    javascript.write_text("const valid = true;")
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert check(tmp_path)[1] == ["JavaScript: Node.js is required; checks were not run"]


def test_generated_report_embedded_javascript_has_valid_syntax():
    from html.parser import HTMLParser
    from pathlib import Path
    import subprocess

    from exporters.html import HTMLExporter
    from parsers.fortigate import FortiGateParser

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")

    class Scripts(HTMLParser):
        def __init__(self):
            super().__init__()
            self.active = False
            self.sources = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "script":
                self.active = not attrs.get("src") and attrs.get("type", "") in (
                    "",
                    "text/javascript",
                    "module",
                )
                if self.active:
                    self.sources.append("")

        def handle_data(self, data):
            if self.active:
                self.sources[-1] += data

        def handle_endtag(self, tag):
            if tag == "script":
                self.active = False

    config = FortiGateParser().parse_content(Path("examples/fortigate-vdom.conf").read_text())
    parser = Scripts()
    parser.feed(HTMLExporter(config).export())
    assert parser.sources
    for source in parser.sources:
        checked = subprocess.run(
            [node, "--check"], input=source, text=True, capture_output=True, timeout=30
        )
        assert checked.returncode == 0, checked.stderr
