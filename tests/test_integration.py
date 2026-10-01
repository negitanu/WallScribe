#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合テスト
新しく実装した機能の統合テスト
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestIntegration:
    """統合テスト"""

    def test_logging_config_import(self):
        """ログ設定モジュールのインポートテスト"""
        from utils.logging_config import JSONFormatter, StructuredLogger, get_logger

        assert StructuredLogger is not None
        assert JSONFormatter is not None
        logger = get_logger("test")
        assert logger is not None

    def test_metrics_import(self):
        """メトリクスモジュールのインポートテスト"""
        from utils.metrics import (
            PROMETHEUS_AVAILABLE,
            get_metrics,
            record_error,
            record_file_upload,
            record_request,
        )

        assert get_metrics is not None
        assert record_request is not None
        assert record_file_upload is not None
        assert record_error is not None
        assert isinstance(PROMETHEUS_AVAILABLE, bool)

    def test_styles_import(self):
        """スタイル定義のインポートテスト"""
        # スタイルファイルの存在確認のみ（openpyxlが必要なためインポートはスキップ）
        from pathlib import Path

        styles_path = Path(__file__).parent.parent / "exporters" / "excel" / "styles.py"
        assert styles_path.exists(), "Styles file should exist"

        # ファイルの内容を確認（インポートせずに）
        content = styles_path.read_text(encoding="utf-8")
        assert "VDOM_COLORS" in content
        assert "GLOBAL_COLOR" in content
        assert "COLORS" in content
        assert "HEADER_FONT" in content

    def test_exceptions_import(self):
        """例外クラスのインポートテスト"""
        from exceptions import ExportError, FileError, ParseError, ValidationError, WallScribeError

        assert WallScribeError is not None
        assert ParseError is not None
        assert ExportError is not None
        assert ValidationError is not None
        assert FileError is not None

    def test_validation_import(self):
        """バリデーション機能のインポートテスト"""
        from utils.validation import (
            validate_file_content,
            validate_file_size,
            validate_ha_mode,
            validate_output_format,
        )

        assert validate_file_content is not None
        assert validate_file_size is not None
        assert validate_output_format is not None
        assert validate_ha_mode is not None

    def test_app_optional_imports(self):
        """アプリのオプショナルインポートテスト"""
        # 依存パッケージがなくてもインポートできることを確認
        # weasyprintやopenpyxlが必要なため、完全なインポートはスキップ
        # 代わりに、オプショナルインポートの実装を確認
        from pathlib import Path

        app_path = Path(__file__).parent.parent / "app.py"
        content = app_path.read_text(encoding="utf-8")

        # オプショナルインポートの実装を確認
        assert "LIMITER_AVAILABLE" in content
        assert "METRICS_AVAILABLE" in content
        assert "try:" in content or "except ImportError" in content

    def test_config_files_exist(self):
        """設定ファイルの存在確認"""
        base_path = Path(__file__).parent.parent

        # 設定ファイルの存在確認（pytest 設定は pyproject.toml に集約）
        assert (base_path / "pyproject.toml").exists()
        assert "[tool.pytest.ini_options]" in (base_path / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        assert (base_path / "tests" / "README.md").exists()
        pyproject_text = (base_path / "pyproject.toml").read_text(encoding="utf-8")
        assert "optional-dependencies.dev" in pyproject_text
        assert "pytest>=" in pyproject_text
        assert "black==" in pyproject_text
        assert not (base_path / "requirements-dev.txt").exists()
        assert not (base_path / "Makefile").exists()
        flake8 = base_path / ".flake8"
        if flake8.exists():
            assert flake8.is_file()
        pre_commit = base_path / ".pre-commit-config.yaml"
        if pre_commit.exists():
            assert pre_commit.is_file()

    def test_github_workflows_exist(self):
        """GitHub Actionsワークフローの存在確認"""
        base_path = Path(__file__).parent.parent
        workflows_path = base_path / ".github" / "workflows"

        if not workflows_path.exists():
            pytest.skip(".github/workflows が無い環境ではスキップ")

        assert (workflows_path / "tests.yml").is_file()
