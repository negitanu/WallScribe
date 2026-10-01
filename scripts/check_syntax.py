"""Fail closed on Python, Jinja, JavaScript and CSS syntax errors."""

import shutil
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, TemplateSyntaxError
import tinycss2

SOURCE_DIRS = (
    "analyzers",
    "api",
    "exporters",
    "jobs",
    "models",
    "parsers",
    "routes",
    "services",
    "utils",
    "web",
    "tests",
    "scripts",
)


def css_errors(rules):
    errors = []
    for rule in rules:
        if rule.type == "error":
            errors.append(f"line {rule.source_line}: {rule.message}")
        elif rule.type == "qualified-rule":
            declarations = tinycss2.parse_declaration_list(
                rule.content, skip_comments=True, skip_whitespace=True
            )
            errors.extend(css_errors(declarations))
        elif rule.type == "at-rule" and rule.content is not None:
            if rule.lower_at_keyword in (
                "font-face",
                "page",
                "property",
                "top-left-corner",
                "top-left",
                "top-center",
                "top-right",
                "top-right-corner",
                "bottom-left-corner",
                "bottom-left",
                "bottom-center",
                "bottom-right",
                "bottom-right-corner",
                "left-top",
                "left-middle",
                "left-bottom",
                "right-top",
                "right-middle",
                "right-bottom",
            ):
                children = tinycss2.parse_declaration_list(
                    rule.content, skip_comments=True, skip_whitespace=True
                )
            else:
                children = tinycss2.parse_rule_list(
                    rule.content, skip_comments=True, skip_whitespace=True
                )
            errors.extend(css_errors(children))
        elif rule.type == "declaration":
            # Token-level errors include unclosed strings and invalid URLs.
            errors.extend(css_errors(rule.value))
        elif rule.type in ("function", "() block", "[] block", "{} block"):
            errors.extend(css_errors(rule.arguments if rule.type == "function" else rule.content))
    return errors


def check(root):
    failures, counts = [], {}
    python_files = sorted(
        {*root.glob("*.py"), *(p for name in SOURCE_DIRS for p in (root / name).rglob("*.py"))}
    )
    templates = sorted((root / "web/templates").rglob("*.html"))
    javascript = sorted((root / "static/js").rglob("*.js"))
    css = sorted((root / "static/css").rglob("*.css"))
    node = shutil.which("node")
    if javascript and not node:
        failures.append("JavaScript: Node.js is required; checks were not run")
    for kind, paths in (
        ("Python", python_files),
        ("Jinja", templates),
        ("JavaScript", javascript),
        ("CSS", css),
    ):
        counts[kind] = len(paths)
        for path in paths:
            try:
                source = path.read_text(encoding="utf-8-sig")
                if kind == "Python":
                    compile(source, str(path), "exec", dont_inherit=True)
                elif kind == "Jinja":
                    Environment().parse(source)
                elif kind == "JavaScript":
                    if not node:
                        continue
                    result = subprocess.run(
                        [node, "--check", str(path)], capture_output=True, text=True, timeout=30
                    )
                    if result.returncode:
                        raise ValueError(result.stderr.strip())
                else:
                    errors = css_errors(
                        tinycss2.parse_stylesheet(source, skip_comments=True, skip_whitespace=True)
                    )
                    if errors:
                        raise ValueError("; ".join(errors))
            except (
                SyntaxError,
                TemplateSyntaxError,
                ValueError,
                OSError,
                subprocess.TimeoutExpired,
            ) as error:
                failures.append(f"{path.relative_to(root)}: {error}")
    return counts, failures


if __name__ == "__main__":
    counts, failures = check(Path(__file__).resolve().parent.parent)
    print("Syntax checks: " + ", ".join(f"{kind} {count}" for kind, count in counts.items()))
    for failure in failures:
        print(failure, file=sys.stderr)
    sys.exit(bool(failures))
