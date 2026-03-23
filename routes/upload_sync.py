#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
アップロード（同期）系ルート
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from flask import jsonify, request
from werkzeug.utils import secure_filename

from utils.storage import save_file_metadata

logger = logging.getLogger(__name__)


class PathValidationError(ValueError):
    """パス検証エラー用のカスタム例外"""

    pass


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
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": {"code": "NO_FILE", "message": "ファイルが選択されていません"},
                        }
                    ),
                    400,
                )

            file = request.files["config_file"]
            if file.filename == "":
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": {"code": "NO_FILE", "message": "ファイルが選択されていません"},
                        }
                    ),
                    400,
                )

            if not allowed_file(file.filename):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": {
                                "code": "UNSUPPORTED_FORMAT",
                                "message": "サポートされていないファイル形式です",
                                "details": "対応形式: .conf (FortiGate), .xml (Palo Alto)",
                            },
                        }
                    ),
                    400,
                )

            output_format = request.form.get("output_format", "html")
            is_valid_format, format_error = validate_output_format(output_format)
            if not is_valid_format:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": {"code": "INVALID_OUTPUT_FORMAT", "message": format_error},
                        }
                    ),
                    400,
                )

            # 依存関係チェック（オプショナル出力）
            if output_format == "pdf" and not pdf_available:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": {
                                "code": "DEPENDENCY_MISSING",
                                "message": "PDF出力にはweasyprintが必要です",
                                "details": "pip install -r requirements.txt を実行してください",
                            },
                        }
                    ),
                    400,
                )
            if output_format == "excel" and not excel_available:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": {
                                "code": "DEPENDENCY_MISSING",
                                "message": "Excel出力にはopenpyxlが必要です",
                                "details": "pip install -r requirements.txt を実行してください",
                            },
                        }
                    ),
                    400,
                )

            # 出力セクション
            sections_json = request.form.get("sections", "[]")
            try:
                sections_list = json.loads(sections_json)
                sections: Optional[List[Any]] = (
                    sections_list if isinstance(sections_list, list) else None
                )
            except json.JSONDecodeError:
                sections = None

            file_data = file.read()

            is_valid_size, size_error = validate_file_size(
                file_data, app.config["MAX_CONTENT_LENGTH"]
            )
            if not is_valid_size:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": {"code": "FILE_TOO_LARGE", "message": size_error},
                        }
                    ),
                    400,
                )

            original_filename = secure_filename(file.filename)
            is_valid_content, content_error = validate_file_content(file_data, original_filename)
            if not is_valid_content:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": {
                                "code": "INVALID_FILE_CONTENT",
                                "message": "ファイル内容の検証に失敗しました",
                                "details": content_error,
                            },
                        }
                    ),
                    400,
                )

            content, detected_encoding = detect_encoding(file_data)
            logger.info(f"検出されたエンコーディング: {detected_encoding}")

            parser = get_parser_for_content(content)
            if parser is None:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": {
                                "code": "UNSUPPORTED_FORMAT",
                                "message": "設定ファイルの形式を判別できません",
                                "details": "対応形式: .conf (FortiGate), .xml (Palo Alto)",
                            },
                        }
                    ),
                    400,
                )

            logger.info(f"パース開始: {original_filename}")
            config = parser.parse_content(content, original_filename)

            if getattr(parser, "errors", None):
                for error in parser.errors:
                    logger.warning(f"パースエラー: {error}")

            file_id = str(uuid.uuid4())
            upload_folder = Path(app.config["UPLOAD_FOLDER"]).resolve()
            upload_folder.mkdir(parents=True, exist_ok=True)

            if output_format == "html":
                output_filename = f"{Path(original_filename).stem}_param.html"
                output_path = (upload_folder / f"{file_id}_{output_filename}").resolve()
                if not output_path.is_relative_to(upload_folder):
                    raise PathValidationError("Invalid file path detected")

                if sections is None or not isinstance(sections, list):
                    exporter = html_exporter_cls(config)
                else:
                    sections_list_str = [s for s in sections if isinstance(s, str)]
                    exporter = html_exporter_cls(config, sections=sections_list_str)
                exporter.export(str(output_path))

            elif output_format == "pdf":
                if not pdf_available or pdf_exporter_cls is None:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": {
                                    "code": "DEPENDENCY_MISSING",
                                    "message": "PDF出力にはweasyprintが必要です",
                                    "details": "pip install -r requirements.txt を実行してください",
                                },
                            }
                        ),
                        400,
                    )
                output_filename = f"{Path(original_filename).stem}_param.pdf"
                output_path = (upload_folder / f"{file_id}_{output_filename}").resolve()
                if not output_path.is_relative_to(upload_folder):
                    raise PathValidationError("Invalid file path detected")
                if sections is None or not isinstance(sections, list):
                    exporter = pdf_exporter_cls(config)
                else:
                    sections_list_str = [s for s in sections if isinstance(s, str)]
                    exporter = pdf_exporter_cls(config, sections=sections_list_str)
                exporter.export(str(output_path))

            elif output_format == "excel":
                if not excel_available or excel_exporter_cls is None:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": {
                                    "code": "DEPENDENCY_MISSING",
                                    "message": "Excel出力にはopenpyxlが必要です",
                                    "details": "pip install -r requirements.txt を実行してください",
                                },
                            }
                        ),
                        400,
                    )
                output_filename = f"{Path(original_filename).stem}_param.xlsx"
                output_path = (upload_folder / f"{file_id}_{output_filename}").resolve()
                if not output_path.is_relative_to(upload_folder):
                    raise PathValidationError("Invalid file path detected")
                if sections is None or not isinstance(sections, list):
                    exporter = excel_exporter_cls(config)
                else:
                    sections_list_str = [s for s in sections if isinstance(s, str)]
                    exporter = excel_exporter_cls(config, sections=sections_list_str)
                exporter.export(str(output_path))

            else:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": {
                                "code": "UNSUPPORTED_FORMAT",
                                "message": f"サポートされていない出力形式です: {output_format}",
                                "details": "対応形式: html, pdf, excel",
                            },
                        }
                    ),
                    400,
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
