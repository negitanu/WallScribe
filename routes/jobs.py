#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ジョブ管理系 API ルート
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from flask import jsonify, request

from utils.storage import load_file_metadata, delete_file_metadata

logger = logging.getLogger(__name__)


def register(app, limiter) -> None:
    """ジョブ管理ルートを登録"""

    @app.route("/api/v1/jobs", methods=["GET"])
    @limiter.limit("100 per hour", per_method=True)
    def list_jobs():
        """ジョブ一覧

        ---
        tags:
          - ジョブ管理
        parameters:
          - name: limit
            in: query
            type: integer
            required: false
            default: 50
            description: 取得件数（最大200）
        responses:
          200:
            description: ジョブ一覧
            schema:
              $ref: '#/definitions/JobsResponse'
        """
        upload_folder = Path(app.config["UPLOAD_FOLDER"]).resolve()
        upload_folder.mkdir(parents=True, exist_ok=True)

        try:
            limit_raw = request.args.get("limit", "50")
            limit = max(1, min(200, int(limit_raw)))
        except Exception:
            limit = 50

        jobs = []
        for meta_path in sorted(
            upload_folder.glob("*.meta.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            file_id = meta_path.name.replace(".meta.json", "")
            try:
                uuid.UUID(file_id)
            except Exception:
                continue

            info = load_file_metadata(file_id)
            if not info:
                continue

            jobs.append(
                {
                    "file_id": file_id,
                    "filename": info.get("filename"),
                    "status": info.get("status", "processing"),
                    "created_at": (
                        info.get("created_at").isoformat() if info.get("created_at") else None
                    ),
                    "file_count": info.get("file_count"),
                    "progress_percent": info.get("progress_percent"),
                    "progress_message": info.get("progress_message"),
                    "progress_stage": info.get("progress_stage"),
                    "device_type": info.get("device_type"),
                    "hostname": info.get("hostname"),
                    "version": info.get("version"),
                    "result_url": f"/result/{file_id}",
                    "download_url": f"/download/{file_id}",
                    "preview_url": f"/preview/{file_id}",
                    "status_url": f"/api/status/{file_id}",
                    "progress_url": f"/api/progress/{file_id}",
                }
            )
            if len(jobs) >= limit:
                break

        return jsonify({"success": True, "jobs": jobs})

    @app.route("/api/v1/jobs/<file_id>", methods=["GET"])
    @limiter.limit("200 per hour", per_method=True)
    def get_job(file_id):
        """ジョブ詳細

        ---
        tags:
          - ジョブ管理
        parameters:
          - name: file_id
            in: path
            type: string
            required: true
            description: ファイルID（UUID）
        responses:
          200:
            description: ジョブ詳細
            schema:
              $ref: '#/definitions/JobResponse'
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
        except Exception:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "INVALID_FILE_ID", "message": "無効なファイルIDです"},
                    }
                ),
                400,
            )

        info = load_file_metadata(file_id)
        if info is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "FILE_NOT_FOUND", "message": "ファイルが見つかりません"},
                    }
                ),
                404,
            )

        job = {
            "file_id": file_id,
            "filename": info.get("filename"),
            "status": info.get("status", "processing"),
            "created_at": info.get("created_at").isoformat() if info.get("created_at") else None,
            "file_count": info.get("file_count"),
            "progress_percent": info.get("progress_percent"),
            "progress_message": info.get("progress_message"),
            "progress_stage": info.get("progress_stage"),
            "device_type": info.get("device_type"),
            "hostname": info.get("hostname"),
            "version": info.get("version"),
            "result_url": f"/result/{file_id}",
            "download_url": f"/download/{file_id}",
            "preview_url": f"/preview/{file_id}",
            "status_url": f"/api/status/{file_id}",
            "progress_url": f"/api/progress/{file_id}",
        }
        return jsonify({"success": True, "job": job})

    @app.route("/api/v1/jobs/<file_id>", methods=["DELETE"])
    @limiter.limit("30 per hour", per_method=True)
    def delete_job(file_id):
        """ジョブ削除（生成物とメタデータを削除）

        ---
        tags:
          - ジョブ管理
        parameters:
          - name: file_id
            in: path
            type: string
            required: true
            description: ファイルID（UUID）
        responses:
          200:
            description: 削除成功
            schema:
              $ref: '#/definitions/DeleteJobResponse'
          400:
            description: 無効なファイルID
            schema:
              $ref: '#/definitions/Error'
        """
        try:
            uuid.UUID(file_id)
        except Exception:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "INVALID_FILE_ID", "message": "無効なファイルIDです"},
                    }
                ),
                400,
            )

        upload_folder = Path(app.config["UPLOAD_FOLDER"]).resolve()
        upload_folder.mkdir(parents=True, exist_ok=True)

        deleted = 0
        for p in upload_folder.glob(f"{file_id}*"):
            try:
                resolved = p.resolve()
                if not str(resolved).startswith(str(upload_folder)):
                    continue
                if resolved.is_file():
                    resolved.unlink()
                    deleted += 1
            except Exception as e:
                logger.warning(f"ジョブ削除中に失敗: {p} ({e})")

        try:
            delete_file_metadata(file_id)
        except Exception:
            pass

        return jsonify({"success": True, "file_id": file_id, "deleted_files": deleted})
