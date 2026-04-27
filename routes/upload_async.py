#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
アップロード（非同期）系ルート
"""

from __future__ import annotations

import logging
import os
import threading as _threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from flask import jsonify, request
from werkzeug.utils import secure_filename

from routes.upload_common import (
    ensure_child_path,
    error_response,
    parse_sections,
    validate_output_dependency,
    validate_uploaded_content,
)
from services.conversion import UnsupportedOutputFormat, build_output_filename
from utils.storage import save_file_metadata

logger = logging.getLogger(__name__)


class _ThreadingProxy:
    """テスト時の Thread モックが標準 threading モジュール全体へ漏れないようにする。"""

    Thread = _threading.Thread


threading = _ThreadingProxy()


def register(
    app,
    limiter,
    *,
    process_job_multi,
    allowed_file,
    get_file_extension,
    validate_output_format,
    validate_ha_mode,
    validate_file_size,
    validate_file_content,
    pdf_available: bool,
    excel_available: bool,
) -> None:
    """非同期アップロード系ルートを登録"""

    @app.route("/api/v1/upload", methods=["POST"])
    @limiter.limit("10 per minute", per_method=True)
    def upload_file_async():
        """ファイルアップロード・変換処理（非同期、複数ファイル対応）

        ---
        tags:
          - ファイル処理
        consumes:
          - multipart/form-data
        parameters:
          - name: config_files[]
            in: formData
            type: array
            items:
              type: file
            required: true
            description: 設定ファイル（複数可、.conf または .xml）
          - name: output_format
            in: formData
            type: string
            enum: [html, pdf, excel]
            default: html
            description: 出力形式
          - name: ha_mode
            in: formData
            type: string
            enum: [auto, single, cluster]
            default: auto
            description: HAモード（auto=自動判定, single=単一機器, cluster=クラスタ）
          - name: sections
            in: formData
            type: string
            default: "[]"
            description: 出力するセクションのJSON配列（空の場合は全セクション）
        responses:
          202:
            description: アップロード受付成功
            schema:
              $ref: '#/definitions/UploadResponse'
          400:
            description: リクエストエラー
            schema:
              $ref: '#/definitions/Error'
          429:
            description: レート制限超過
            schema:
              $ref: '#/definitions/Error'
          500:
            description: サーバーエラー
            schema:
              $ref: '#/definitions/Error'
        """
        try:
            files = request.files.getlist("config_files[]")
            if not files or (len(files) == 1 and files[0].filename == ""):
                if "config_file" in request.files:
                    f = request.files["config_file"]
                    if f.filename != "":
                        files = [f]

            if not files or all(f.filename == "" for f in files):
                return error_response("NO_FILE", "ファイルが選択されていません", 400)

            valid_files = [f for f in files if f.filename and allowed_file(f.filename)]
            if not valid_files:
                return error_response(
                    "UNSUPPORTED_FORMAT",
                    "サポートされていないファイル形式です",
                    400,
                    "対応形式: .conf (FortiGate), .xml (Palo Alto)",
                )

            output_format = request.form.get("output_format", "html")
            is_valid_format, format_error = validate_output_format(output_format)
            if not is_valid_format:
                return error_response("INVALID_OUTPUT_FORMAT", format_error, 400)

            # 依存関係チェック（オプショナル出力）
            dependency_error = validate_output_dependency(
                output_format, pdf_available=pdf_available, excel_available=excel_available
            )
            if dependency_error:
                return dependency_error

            ha_mode = request.form.get("ha_mode", "auto")
            is_valid_ha_mode, ha_mode_error = validate_ha_mode(ha_mode)
            if not is_valid_ha_mode:
                return error_response("INVALID_HA_MODE", ha_mode_error, 400)

            sections_list = parse_sections(request.form.get("sections", "[]"))
            sections: Optional[List[str]] = (
                [s for s in sections_list if isinstance(s, str)]
                if isinstance(sections_list, list)
                else None
            )

            # ファイル内容の検証（各ファイル）
            for f in valid_files:
                file_data = f.read()
                f.seek(0)

                original_filename = secure_filename(f.filename)
                validation_error = validate_uploaded_content(
                    file_data,
                    original_filename,
                    max_content_length=app.config["MAX_CONTENT_LENGTH"],
                    validate_file_size=validate_file_size,
                    validate_file_content=validate_file_content,
                    detail_prefix=f"{original_filename}: ",
                )
                if validation_error:
                    return validation_error

            file_id = str(uuid.uuid4())
            upload_folder = Path(app.config["UPLOAD_FOLDER"]).resolve()
            upload_folder.mkdir(parents=True, exist_ok=True)

            input_paths: List[Path] = []
            original_filenames: List[str] = []
            for i, f in enumerate(valid_files):
                original_filename = secure_filename(f.filename)
                original_filenames.append(original_filename)

                ext = get_file_extension(original_filename)
                input_path = ensure_child_path(
                    upload_folder, upload_folder / f"{file_id}_input_{i}{ext}"
                )
                f.save(str(input_path))
                input_paths.append(input_path)

            base_name = Path(original_filenames[0]).stem
            if len(valid_files) > 1:
                base_name = f"{base_name}_cluster"

            try:
                output_filename = build_output_filename(base_name, output_format)
            except UnsupportedOutputFormat:
                return error_response(
                    "UNSUPPORTED_FORMAT",
                    f"サポートされていない出力形式です: {output_format}",
                    400,
                    "対応形式: html, pdf, excel",
                )

            output_path = ensure_child_path(
                upload_folder, upload_folder / f"{file_id}_{output_filename}"
            )

            save_file_metadata(
                file_id,
                {
                    "filename": output_filename,
                    "path": str(output_path),
                    "file_count": len(valid_files),
                    "created_at": datetime.now(),
                    "status": "processing",
                    "progress_percent": 0,
                    "progress_message": f"アップロードを受け付けました ({len(valid_files)} ファイル)",
                    "progress_stage": "queued",
                },
            )

            t = threading.Thread(
                target=process_job_multi,
                args=(
                    file_id,
                    input_paths,
                    original_filenames,
                    output_format,
                    sections,
                    upload_folder,
                    output_path,
                    output_filename,
                    ha_mode,
                ),
                daemon=True,
            )
            t.start()

            return (
                jsonify(
                    {
                        "success": True,
                        "file_id": file_id,
                        "file_count": len(valid_files),
                        "progress_url": f"/api/progress/{file_id}",
                        "result_url": f"/result/{file_id}",
                    }
                ),
                202,
            )

        except Exception as e:
            logger.error(f"非同期受付エラー: {e}", exc_info=True)
            is_production = os.environ.get("FLASK_ENV", "production") == "production"
            error_details = "詳細はログを確認してください" if is_production else str(e)
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": "INTERNAL_ERROR",
                            "message": "予期しないエラーが発生しました",
                            "details": error_details,
                        },
                    }
                ),
                500,
            )

    # 後方互換性のため、旧エンドポイントも維持
    @app.route("/upload_async", methods=["POST"])
    @limiter.limit("10 per minute", per_method=True)
    def upload_file_async_legacy():
        """ファイルアップロード・変換処理（非同期、複数ファイル対応）- 旧エンドポイント"""
        return upload_file_async()
