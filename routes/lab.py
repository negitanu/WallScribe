"""Separate, stateless construction lab: config is parsed in memory, never persisted."""

from flask import jsonify, render_template, request

from parsers.base import detect_encoding, get_parser_for_content
from services.lab.engine import MAX_POLICIES, audit_parameters, generate_cases, run_case
from services.lab.feeds import SOURCES, fetch_feed, snapshots
from services.lab.validation import catalogs, read_json, validate_cases


def register(app, limiter):
    def inputs():
        upload = request.files.get("config")
        if upload is None:
            raise ValueError("設定ファイルを指定してください")
        raw = upload.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("机上テストの設定は 2 MB 以内にしてください")
        content, _ = detect_encoding(raw)
        parser = get_parser_for_content(content)
        if parser is None:
            raise ValueError("FortiGate / Palo Alto の設定を指定してください")
        config = parser.parse_content(content, "")
        if (
            len(config.firewall_policies) > MAX_POLICIES
            or len(config.routes) > 10000
            or len(config.interfaces) > 5000
        ):
            raise ValueError("設定の規模が机上テストの上限を超えました")
        if (
            sum(
                len(getattr(config.objects, name))
                for name in ("addresses", "address_groups", "services", "service_groups")
            )
            > 10000
        ):
            raise ValueError("オブジェクト数が机上テストの上限を超えました")
        if not config.firewall_policies:
            raise ValueError("解析可能なポリシーがありません")
        apps, isdb, provenance = catalogs(read_json(request.form.get("catalog", "")))
        return config, apps, isdb, provenance

    @app.get("/lab")
    def lab_page():
        return render_template("lab.html")

    @app.post("/api/lab/feeds/<key>")
    @limiter.limit("10 per minute")
    def lab_feed(key):
        if key not in SOURCES:
            return jsonify(error="登録されていない Feed です"), 400
        result = fetch_feed(key)
        return jsonify(result), 200 if result["status"] == "ok" else 502

    @app.post("/api/lab/generate")
    @limiter.limit("10 per minute")
    def lab_generate():
        try:
            config, apps, _, provenance = inputs()
            feeds = snapshots()
            cases = generate_cases(config, apps, feeds)
            return jsonify(
                cases=cases,
                summary=config.get_summary(),
                routers=[v.name for v in config.virtual_routers],
                scopes=config.device_info.vdom_list,
                parameter_issues=audit_parameters(config),
                parse_warning_count=len(config.parse_errors) + len(config.unsupported_sections),
                feeds=feeds,
                provenance=provenance,
                truncated=len(config.firewall_policies) * 3 > len(cases),
            )
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            return (
                jsonify(
                    error="入力を解析できません。設定形式・容量・補助 DB の形式を確認してください"
                ),
                400,
            )

    @app.post("/api/lab/run")
    @limiter.limit("10 per minute")
    def lab_run():
        try:
            config, apps, isdb, provenance = inputs()
            cases = read_json(request.form.get("cases", ""), 512000)
            validate_cases(cases, config)
            results = [run_case(config, c, apps, isdb) for c in cases]
            return jsonify(
                results=results,
                provenance=provenance,
                summary={
                    "total": len(results),
                    "attention": sum(r["attention"] for r in results),
                    "review": sum(r["outcome"] == "review" for r in results),
                },
            )
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            return (
                jsonify(
                    error="ケースまたは補助 DB が不正です。IP・ポート・区画・仮想ルーター・上限を確認してください"
                ),
                400,
            )
