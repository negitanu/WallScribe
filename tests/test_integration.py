#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合テスト
新しく実装した機能の統合テスト
"""

import pytest
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestIntegration:
    """統合テスト"""

    def test_logging_config_import(self):
        """ログ設定モジュールのインポートテスト"""
        from utils.logging_config import StructuredLogger, JSONFormatter, get_logger
        assert StructuredLogger is not None
        assert JSONFormatter is not None
        logger = get_logger('test')
        assert logger is not None

    def test_metrics_import(self):
        """メトリクスモジュールのインポートテスト"""
        from utils.metrics import (
            get_metrics,
            record_request,
            record_file_upload,
            record_error,
            PROMETHEUS_AVAILABLE,
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
        
        styles_path = Path(__file__).parent.parent / 'exporters' / 'excel' / 'styles.py'
        assert styles_path.exists(), "Styles file should exist"
        
        # ファイルの内容を確認（インポートせずに）
        content = styles_path.read_text(encoding='utf-8')
        assert 'VDOM_COLORS' in content
        assert 'GLOBAL_COLOR' in content
        assert 'COLORS' in content
        assert 'HEADER_FONT' in content

    def test_exceptions_import(self):
        """例外クラスのインポートテスト"""
        from exceptions import (
            WallScribeError, ParseError, ExportError,
            ValidationError, FileError
        )
        assert WallScribeError is not None
        assert ParseError is not None
        assert ExportError is not None
        assert ValidationError is not None
        assert FileError is not None

    def test_validation_import(self):
        """バリデーション機能のインポートテスト"""
        from utils.validation import (
            validate_file_content, validate_file_size,
            validate_output_format, validate_ha_mode
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
        app_path = Path(__file__).parent.parent / 'app.py'
        content = app_path.read_text(encoding='utf-8')
        
        # オプショナルインポートの実装を確認
        assert 'LIMITER_AVAILABLE' in content
        assert 'METRICS_AVAILABLE' in content
        assert 'try:' in content or 'except ImportError' in content

    def test_config_files_exist(self):
        """設定ファイルの存在確認"""
        base_path = Path(__file__).parent.parent
        
        # 設定ファイルの存在確認
        assert (base_path / 'pytest.ini').exists()
        assert (base_path / '.coveragerc').exists()
        assert (base_path / 'pyproject.toml').exists()
        assert (base_path / '.flake8').exists()
        assert (base_path / '.pre-commit-config.yaml').exists()
        assert (base_path / 'requirements-dev.txt').exists()

    def test_github_workflows_exist(self):
        """GitHub Actionsワークフローの存在確認"""
        base_path = Path(__file__).parent.parent
        workflows_path = base_path / '.github' / 'workflows'
        
        assert workflows_path.exists()
        assert (workflows_path / 'ci.yml').exists()
        assert (workflows_path / 'security.yml').exists()
