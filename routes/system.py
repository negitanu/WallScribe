#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
システム系（spec/metrics/health）ルート
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from flask import jsonify, request

logger = logging.getLogger(__name__)


def register(app, get_metrics) -> None:
    """システム系ルートを登録"""

    @app.route("/api/v1/spec", methods=["GET"])
    def api_spec():
        """Swagger仕様(JSON)

        ---
        tags:
          - システム
        responses:
          200:
            description: Swagger 2.0 仕様(JSON)
        """
        from api.specs import API_SPEC

        return jsonify(API_SPEC)

    @app.route("/swagger.json", methods=["GET"])
    def swagger_json_alias():
        """Swagger仕様(JSON)のエイリアス"""
        return api_spec()

    @app.route("/metrics")
    def metrics():
        """Prometheusメトリクスエンドポイント"""
        return get_metrics(), 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}

    @app.route("/health")
    def health_check():
        """基本的なヘルスチェック"""
        return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

    @app.route("/health/ready")
    def readiness_check():
        """レディネスチェック（ディスク容量、メモリ等）"""
        import shutil

        try:
            upload_folder = Path(app.config["UPLOAD_FOLDER"])
            if not upload_folder.exists():
                return (
                    jsonify(
                        {
                            "status": "not_ready",
                            "reason": "upload_folder_not_found",
                        }
                    ),
                    503,
                )
            disk_usage = shutil.disk_usage(upload_folder)
            free_space_gb = disk_usage.free / (1024**3)

            if free_space_gb < 1.0:
                return (
                    jsonify(
                        {
                            "status": "not_ready",
                            "reason": "insufficient_disk_space",
                            "free_space_gb": round(free_space_gb, 2),
                        }
                    ),
                    503,
                )

            return jsonify({"status": "ready", "free_space_gb": round(free_space_gb, 2)}), 200
        except Exception as e:
            logger.error(f"レディネスチェックエラー: {e}", exc_info=True)
            return (
                jsonify({"status": "not_ready", "reason": "check_failed"}),
                503,
            )

    @app.route("/health/live")
    def liveness_check():
        """ライブネスチェック（アプリケーションが応答するか）"""
        return jsonify({"status": "alive", "timestamp": datetime.now().isoformat()}), 200
