#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
構造化ログ設定のテスト
"""

import json
import logging
import sys
from io import StringIO

import pytest

from utils.logging_config import JSONFormatter, StructuredLogger, get_logger


class TestJSONFormatter:
    """JSONフォーマッターのテスト"""

    def test_format_basic(self):
        """基本的なログフォーマット"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["logger"] == "test"
        assert "timestamp" in data
        assert "module" in data
        assert "function" in data
        assert "line" in data

    def test_format_with_exception(self):
        """例外情報を含むログフォーマット"""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "ERROR"
        assert data["message"] == "Error occurred"
        assert "exception" in data
        assert "exception_type" in data
        assert data["exception_type"] == "ValueError"


class TestStructuredLogger:
    """構造化ロガーのテスト"""

    def test_setup_logging_json(self):
        """JSON形式のログ設定"""
        output = StringIO()
        StructuredLogger.setup_logging(level="INFO", format_type="json", output_stream=output)

        logger = logging.getLogger("test")
        logger.info("Test message")

        # 出力を確認
        output.seek(0)
        lines = output.readlines()
        assert len(lines) > 0

        # JSON形式であることを確認
        try:
            data = json.loads(lines[-1].strip())
            assert data["level"] == "INFO"
            assert data["message"] == "Test message"
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")

    def test_setup_logging_text(self):
        """テキスト形式のログ設定"""
        output = StringIO()
        StructuredLogger.setup_logging(level="INFO", format_type="text", output_stream=output)

        logger = logging.getLogger("test")
        logger.info("Test message")

        # 出力を確認
        output.seek(0)
        content = output.read()
        assert "Test message" in content
        assert "INFO" in content

    def test_get_logger(self):
        """ロガー取得のテスト"""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"


class TestLoggingIntegration:
    """ロギング統合テスト"""

    def test_log_levels(self):
        """ログレベルのテスト"""
        output = StringIO()
        StructuredLogger.setup_logging(level="DEBUG", format_type="json", output_stream=output)

        logger = logging.getLogger("test")
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # 出力を確認
        output.seek(0)
        lines = [line.strip() for line in output.readlines() if line.strip()]

        levels = [json.loads(line)["level"] for line in lines]
        assert "DEBUG" in levels
        assert "INFO" in levels
        assert "WARNING" in levels
        assert "ERROR" in levels
