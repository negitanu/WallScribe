#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
カスタム例外クラス
"""

from typing import Any, Dict, Optional


class WallScribeError(Exception):
    """基底例外クラス"""

    def __init__(self, message: str, code: str = None, details: str = None):
        """
        Args:
            message: エラーメッセージ
            code: エラーコード
            details: 詳細情報
        """
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """エラー情報を辞書に変換

        Returns:
            エラー情報を含む辞書
        """
        result: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            result["details"] = self.details
        return result


class ParseError(WallScribeError):
    """パースエラー"""

    def __init__(self, message: str, details: str = None):
        """
        Args:
            message: エラーメッセージ
            details: 詳細情報
        """
        super().__init__(message, code="PARSE_ERROR", details=details)


class ExportError(WallScribeError):
    """エクスポートエラー"""

    def __init__(self, message: str, details: str = None):
        """
        Args:
            message: エラーメッセージ
            details: 詳細情報
        """
        super().__init__(message, code="EXPORT_ERROR", details=details)


class ValidationError(WallScribeError):
    """バリデーションエラー"""

    def __init__(self, message: str, details: str = None):
        """
        Args:
            message: エラーメッセージ
            details: 詳細情報
        """
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class FileError(WallScribeError):
    """ファイル関連エラー"""

    def __init__(self, message: str, details: str = None):
        """
        Args:
            message: エラーメッセージ
            details: 詳細情報
        """
        super().__init__(message, code="FILE_ERROR", details=details)
