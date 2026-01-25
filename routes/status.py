#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
進捗/ステータス取得系ルート
"""

from __future__ import annotations

import uuid

from flask import jsonify

from utils.storage import load_file_metadata


def register(app) -> None:
    """ステータス系ルートを登録"""

    @app.route("/api/status/<file_id>")
    def get_status(file_id):
        """ファイルのステータス確認

        ---
        tags:
          - 進捗・ステータス
        parameters:
          - name: file_id
            in: path
            type: string
            required: true
            description: ファイルID（UUID）
            example: "550e8400-e29b-41d4-a716-446655440000"
        responses:
          200:
            description: ステータス情報
            schema:
              $ref: '#/definitions/StatusResponse'
          400:
            description: 無効なファイルID
            schema:
              $ref: '#/definitions/Error'
          404:
            description: ファイルが見つかりません
            schema:
              $ref: '#/definitions/Error'
        """
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
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "FILE_NOT_FOUND", "message": "ファイルが見つかりません"},
                    }
                ),
                404,
            )

        return jsonify(
            {
                "success": True,
                "file_id": file_id,
                "filename": file_info["filename"],
                "device_type": file_info["device_type"],
                "hostname": file_info["hostname"],
                "version": file_info["version"],
                "summary": file_info["summary"],
            }
        )

    @app.route("/api/v1/status/<file_id>")
    def get_status_v1(file_id):
        return get_status(file_id)

    @app.route("/api/progress/<file_id>")
    def get_progress(file_id):
        """生成中の進捗を取得（非同期用）

        ---
        tags:
          - 進捗・ステータス
        parameters:
          - name: file_id
            in: path
            type: string
            required: true
            description: ファイルID（UUID）
            example: "550e8400-e29b-41d4-a716-446655440000"
        responses:
          200:
            description: 進捗情報
            schema:
              $ref: '#/definitions/ProgressResponse'
          400:
            description: 無効なファイルID
            schema:
              $ref: '#/definitions/Error'
          404:
            description: ファイルが見つかりません
            schema:
              $ref: '#/definitions/Error'
        """
        try:
            uuid.UUID(file_id)
        except (ValueError, AttributeError):
            return (
                jsonify(
                    {"success": False, "error": {"code": "INVALID_FILE_ID", "message": "無効なファイルIDです"}}
                ),
                400,
            )

        file_info = load_file_metadata(file_id)
        if file_info is None:
            return (
                jsonify(
                    {"success": False, "error": {"code": "FILE_NOT_FOUND", "message": "ファイルが見つかりません"}}
                ),
                404,
            )

        return jsonify(
            {
                "success": True,
                "file_id": file_id,
                "status": file_info.get("status", "processing"),
                "progress": {
                    "percent": file_info.get("progress_percent", 0),
                    "message": file_info.get("progress_message", ""),
                    "stage": file_info.get("progress_stage", ""),
                },
                "error": file_info.get("error"),
                "result_url": f"/result/{file_id}",
            }
        )

    @app.route("/api/v1/progress/<file_id>")
    def get_progress_v1(file_id):
        return get_progress(file_id)

