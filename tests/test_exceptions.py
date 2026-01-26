#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
カスタム例外クラスのテスト
"""

import pytest
from exceptions import WallScribeError, ParseError, ExportError, ValidationError, FileError


class TestWallScribeError:
    """WallScribeErrorのテスト"""

    def test_basic_error(self):
        """基本的なエラーのテスト"""
        error = WallScribeError("Test error")
        assert str(error) == "Test error"
        assert error.code == "UNKNOWN_ERROR"
        assert error.details is None

    def test_error_with_code(self):
        """エラーコード付きエラーのテスト"""
        error = WallScribeError("Test error", code="TEST_ERROR")
        assert error.code == "TEST_ERROR"

    def test_error_with_details(self):
        """詳細情報付きエラーのテスト"""
        error = WallScribeError("Test error", details="Additional info")
        assert error.details == "Additional info"

    def test_to_dict(self):
        """to_dictメソッドのテスト"""
        error = WallScribeError("Test error", code="TEST_ERROR", details="Details")
        result = error.to_dict()
        assert result == {"code": "TEST_ERROR", "message": "Test error", "details": "Details"}

    def test_to_dict_without_details(self):
        """詳細情報なしのto_dictテスト"""
        error = WallScribeError("Test error", code="TEST_ERROR")
        result = error.to_dict()
        assert "details" not in result


class TestParseError:
    """ParseErrorのテスト"""

    def test_parse_error(self):
        """ParseErrorのテスト"""
        error = ParseError("Parse failed", details="Invalid format")
        assert str(error) == "Parse failed"
        assert error.code == "PARSE_ERROR"
        assert error.details == "Invalid format"


class TestExportError:
    """ExportErrorのテスト"""

    def test_export_error(self):
        """ExportErrorのテスト"""
        error = ExportError("Export failed", details="File write error")
        assert str(error) == "Export failed"
        assert error.code == "EXPORT_ERROR"
        assert error.details == "File write error"


class TestValidationError:
    """ValidationErrorのテスト"""

    def test_validation_error(self):
        """ValidationErrorのテスト"""
        error = ValidationError("Validation failed", details="Invalid input")
        assert str(error) == "Validation failed"
        assert error.code == "VALIDATION_ERROR"
        assert error.details == "Invalid input"


class TestFileError:
    """FileErrorのテスト"""

    def test_file_error(self):
        """FileErrorのテスト"""
        error = FileError("File operation failed", details="File not found")
        assert str(error) == "File operation failed"
        assert error.code == "FILE_ERROR"
        assert error.details == "File not found"
