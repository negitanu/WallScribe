#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
アップロード（同期）系ルート
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import jsonify, request
from werkzeug.utils import secure_filename

from routes.upload_common import (
    PathValidationError,
    ensure_child_path,
    error_response,
    parse_sections,
    validate_output_dependency,
    validate_uploaded_content,
)
from services.conversion import (
    ExportCapabilities,
    UnsupportedOutputFormat,
    build_output_filename,
    export_config,
)
from utils.storage import save_file_metadata

logger = logging.getLogger(__name__)


def register(
    app,
    limiter,
    *,
    allowed_file,
    detect_encoding,
    get_parser_for_content,
    validate_output_format,
    validate_file_size,
    validate_file_content,
    html_exporter_cls,
    pdf_exporter_cls,
    excel_exporter_cls,
    pdf_available: bool,
    excel_available: bool,
) -> None:
    """同期アップロードルートを登録"""

    @app.route("/upload", methods=["POST"])
    @limiter.limit("10 per minute", per_method=True)
    def upload_file():
        """ファイルアップロード・変換処理"""
        try:
            if "config_file" not in request.files:
                return error_response("NO_FILE", "ファイルが選択されていません", 400)

            file = request.files["config_file"]
            if file.filename == "":
                return error_response("NO_FILE", "ファイルが選択されていません", 400)

            if not allowed_file(file.filename):
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

            sections = parse_sections(request.form.get("sections", "[]"))

            file_data = file.read()
            original_filename = secure_filename(file.filename)
            validation_error = validate_uploaded_content(
                file_data,
                original_filename,
                max_content_length=app.config["MAX_CONTENT_LENGTH"],
                validate_file_size=validate_file_size,
                validate_file_content=validate_file_content,
            )
            if validation_error:
                return validation_error

            content, detected_encoding = detect_encoding(file_data)
            logger.info(f"検出されたエンコーディング: {detected_encoding}")

            parser = get_parser_for_content(content)
            if parser is None:
                return error_response(
                    "UNSUPPORTED_FORMAT",
                    "設定ファイルの形式を判別できません",
                    400,
                    "対応形式: .conf (FortiGate), .xml (Palo Alto)",
                )

            logger.info(f"パース開始: {original_filename}")
            config = parser.parse_content(content, original_filename)

            if getattr(parser, "errors", None):
                for error in parser.errors:
                    logger.warning(f"パースエラー: {error}")

            file_id = str(uuid.uuid4())
            upload_folder = Path(app.config["UPLOAD_FOLDER"]).resolve()
            upload_folder.mkdir(parents=True, exist_ok=True)

            try:
                output_filename = build_output_filename(Path(original_filename).stem, output_format)
                output_path = ensure_child_path(upload_folder, upload_folder / f"{file_id}_{output_filename}")
                export_config(
                    config,
                    output_format,
                    output_path,
                    ExportCapabilities(
                        html_exporter_cls=html_exporter_cls,
                        pdf_exporter_cls=pdf_exporter_cls,
                        excel_exporter_cls=excel_exporter_cls,
                        pdf_available=pdf_available,
                        excel_available=excel_available,
                    ),
                    sections=sections,
                )
            except UnsupportedOutputFormat:
                return error_response(
                    "UNSUPPORTED_FORMAT",
                    f"サポートされていない出力形式です: {output_format}",
                    400,
                    "対応形式: html, pdf, excel",
                )

            summary = config.get_summary()
            normalized_path = str(output_path.resolve())
            metadata = {
                "filename": output_filename,
                "path": normalized_path,
                "device_type": summary["device_type"],
                "hostname": summary["hostname"],
                "version": summary["version"],
                "summary": summary,
                "created_at": datetime.now(),
            }
            save_file_metadata(file_id, metadata)

            logger.info(f"生成完了: {output_filename} (ID: {file_id}, Path: {normalized_path})")

            return jsonify(
                {
                    "success": True,
                    "file_id": file_id,
                    "filename": output_filename,
                    "device_type": summary["device_type"],
                    "hostname": summary["hostname"],
                    "version": summary["version"],
                    "summary": summary,
                    "download_url": f"/download/{file_id}",
                    "preview_url": f"/preview/{file_id}",
                }
            )

        except UnicodeDecodeError:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": "ENCODING_ERROR",
                            "message": "ファイルのエンコーディングを読み取れません",
                            "details": "対応形式: UTF-8, UTF-8 BOM, Shift-JIS (CP932), Latin-1",
                        },
                    }
                ),
                400,
            )
        except PathValidationError as e:
            logger.warning(f"バリデーションエラー: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": str(e),
                        },
                    }
                ),
                400,
            )
        except Exception as e:
            logger.error(f"処理エラー: {e}", exc_info=True)
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
