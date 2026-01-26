#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Webページ系ルート（HTML）
"""

from __future__ import annotations

import uuid

from flask import redirect, render_template, url_for

from utils.storage import load_file_metadata


def register(app) -> None:
    """ページ系ルートを登録"""

    @app.route("/")
    def index():
        """メインページ"""
        return render_template("index.html")

    @app.route("/result/<file_id>")
    def result_page(file_id):
        """結果ページ"""
        try:
            uuid.UUID(file_id)
        except (ValueError, AttributeError):
            return redirect(url_for("index"))

        file_info = load_file_metadata(file_id)
        if file_info is None:
            return redirect(url_for("index"))
        return render_template("result.html", file_id=file_id, file_info=file_info)
