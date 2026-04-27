#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""アップロード系ルートで共有する検証とレスポンス補助。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from flask import jsonify


class PathValidationError(ValueError):
    """パス検証エラー用のカスタム例外。"""


def error_response(code: str, message: str, status: int, details: Optional[str] = None):
    """既存API形状に合わせたエラーレスポンスを返す。"""
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return jsonify({"success": False, "error": error}), status


def parse_sections(sections_json: str) -> Optional[List[Any]]:
    """sections フォーム値を配列として読み取る。無効なJSONは従来通り無指定扱い。"""
    try:
        sections = json.loads(sections_json)
    except json.JSONDecodeError:
        return None
    return sections if isinstance(sections, list) else None


def validate_output_dependency(
    output_format: str,
    *,
    pdf_available: bool,
    excel_available: bool,
) -> Optional[Tuple[Any, int]]:
    """出力形式に必要な任意依存が利用可能か確認する。"""
    if output_format == "pdf" and not pdf_available:
        return error_response(
            "DEPENDENCY_MISSING",
            "PDF出力にはweasyprintが必要です",
            400,
            "pip install -r requirements.txt を実行してください",
        )
    if output_format == "excel" and not excel_available:
        return error_response(
            "DEPENDENCY_MISSING",
            "Excel出力にはopenpyxlが必要です",
            400,
            "pip install -r requirements.txt を実行してください",
        )
    return None


def validate_uploaded_content(
    file_data: bytes,
    original_filename: str,
    *,
    max_content_length: int,
    validate_file_size: Callable[[bytes, int], Tuple[bool, Optional[str]]],
    validate_file_content: Callable[[bytes, str], Tuple[bool, Optional[str]]],
    detail_prefix: str = "",
) -> Optional[Tuple[Any, int]]:
    """アップロードされたファイルのサイズと内容を検証する。"""
    is_valid_size, size_error = validate_file_size(file_data, max_content_length)
    if not is_valid_size:
        return error_response("FILE_TOO_LARGE", str(size_error), 400)

    is_valid_content, content_error = validate_file_content(file_data, original_filename)
    if not is_valid_content:
        details = f"{detail_prefix}{content_error}" if detail_prefix else str(content_error)
        return error_response(
            "INVALID_FILE_CONTENT",
            "ファイル内容の検証に失敗しました",
            400,
            details,
        )
    return None


def ensure_child_path(parent: Path, child: Path) -> Path:
    """child が parent 配下にあることを確認して返す。"""
    parent = parent.resolve()
    child = child.resolve()
    try:
        child.relative_to(parent)
    except ValueError as exc:
        raise PathValidationError("Invalid file path detected") from exc
    return child
