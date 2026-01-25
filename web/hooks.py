#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask アプリのフック/ハンドラ登録
"""

from __future__ import annotations

import os
import logging
from pathlib import Path

from flask import jsonify, render_template, request

from utils.storage import set_upload_folder

logger = logging.getLogger(__name__)


def register_error_handlers(app) -> None:
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "リクエストが多すぎます。しばらく待ってから再度お試しください。",
                        "details": str(e.description) if hasattr(e, "description") else None,
                    },
                }
            ),
            429,
        )

    @app.errorhandler(413)
    def request_entity_too_large(_error):
        return jsonify({"success": False, "error": {"code": "FILE_TOO_LARGE", "message": "ファイルサイズが50MBを超えています"}}), 413

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", error={"code": "404", "message": "ページが見つかりません"}), 404

    @app.errorhandler(500)
    def internal_error(_error):
        return render_template("error.html", error={"code": "500", "message": "サーバー内部エラーが発生しました"}), 500


def register_request_hooks(app, *, metrics_available: bool, record_request) -> None:
    @app.before_request
    def before_request():
        # UPLOAD_FOLDER を storage 側にも反映（テストで config を差し替えるケースにも対応）
        try:
            set_upload_folder(Path(app.config["UPLOAD_FOLDER"]))
        except Exception:
            pass

        import time

        request._start_time = time.time()

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp

        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        if metrics_available and request.endpoint:
            try:
                import time

                duration = time.time() - getattr(request, "_start_time", time.time())
                record_request(method=request.method, endpoint=request.endpoint, status=response.status_code, duration=duration)
            except Exception:
                pass

        return response


def swagger_setup(app, *, swagger_available: bool):
    """Swagger UI を初期化（利用可能な場合のみ）"""
    if not swagger_available:
        return None, False

    try:
        from flasgger import Swagger
        from api.specs import API_SPEC

        swagger = Swagger(app, template=API_SPEC)
        logger.info("Swagger UI有効化: /apidocs")
        return swagger, True
    except ImportError as e:
        logger.warning(f"Swagger設定エラー（依存/モジュール未検出）: {e}")
        return None, False
    except Exception as e:
        logger.warning(f"Swagger設定エラー: {e}")
        return None, False

