#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成ファイルのダウンロード/プレビュー系ルート
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from flask import jsonify, send_file

from utils.storage import load_file_metadata

logger = logging.getLogger(__name__)


def register(app) -> None:
    """ファイル系ルートを登録"""

    @app.route("/download/<file_id>")
    def download_file(file_id):
        """生成ファイルのダウンロード"""
        try:
            uuid.UUID(file_id)
        except (ValueError, AttributeError):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "INVALID_FILE_ID", "message": "無効なファイルIDです"},
                    }
                ),
                400,
            )

        file_info = load_file_metadata(file_id)
        if file_info is None:
            logger.warning(f"ファイルIDが見つかりません: {file_id}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "FILE_NOT_FOUND", "message": "ファイルが見つかりません"},
                    }
                ),
                404,
            )

        file_path = Path(file_info["path"])
        upload_folder = Path(app.config["UPLOAD_FOLDER"]).resolve()
        file_path_resolved = file_path.resolve()

        if not file_path_resolved.is_relative_to(upload_folder):
            logger.warning(
                f"パストラバーサル攻撃の可能性: {file_id}, Path: {file_path_resolved}, Upload: {upload_folder}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "INVALID_PATH", "message": "無効なファイルパスです"},
                    }
                ),
                400,
            )

        if not file_path_resolved.exists():
            logger.warning(f"ファイルが存在しません: {file_path_resolved}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "FILE_NOT_FOUND", "message": "ファイルが削除されました"},
                    }
                ),
                404,
            )

        logger.info(f"ファイルダウンロード: {file_path_resolved}")
        return send_file(
            file_path_resolved, as_attachment=True, download_name=file_info["filename"]
        )

    @app.route("/api/v1/download/<file_id>")
    def download_file_v1(file_id):
        """生成ファイルのダウンロード（v1 エイリアス）"""
        return download_file(file_id)

    @app.route("/preview/<file_id>")
    def preview_file(file_id):
        """生成ファイルのプレビュー"""
        try:
            uuid.UUID(file_id)
        except (ValueError, AttributeError):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "INVALID_FILE_ID", "message": "無効なファイルIDです"},
                    }
                ),
                400,
            )

        file_info = load_file_metadata(file_id)
        if file_info is None:
            logger.warning(f"ファイルIDが見つかりません: {file_id}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "FILE_NOT_FOUND", "message": "ファイルが見つかりません"},
                    }
                ),
                404,
            )

        file_path = Path(file_info["path"])
        upload_folder = Path(app.config["UPLOAD_FOLDER"]).resolve()
        file_path_resolved = file_path.resolve()

        if not file_path_resolved.is_relative_to(upload_folder):
            logger.warning(
                f"パストラバーサル攻撃の可能性: {file_id}, Path: {file_path_resolved}, Upload: {upload_folder}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "INVALID_PATH", "message": "無効なファイルパスです"},
                    }
                ),
                400,
            )

        if not file_path_resolved.exists():
            logger.warning(f"ファイルが存在しません: {file_path_resolved}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "FILE_NOT_FOUND", "message": "ファイルが削除されました"},
                    }
                ),
                404,
            )

        logger.info(f"ファイルプレビュー: {file_path_resolved}")
        return send_file(file_path_resolved)

    @app.route("/api/v1/preview/<file_id>")
    def preview_file_v1(file_id):
        """生成ファイルのプレビュー（v1 エイリアス）"""
        return preview_file(file_id)
