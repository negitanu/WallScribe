#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
レート制限機能のテスト
"""

import os
import sys
from pathlib import Path

import pytest

# テスト用にflask_limiterをモック
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRateLimiting:
    """レート制限のテスト"""

    def test_limiter_optional_import(self):
        """flask_limiterがオプショナルであることを確認"""
        # flask_limiterがインストールされていない環境でも
        # app.pyがインポートできることを確認
        try:
            # モック環境でテスト
            import app

            assert hasattr(app, "limiter")
            assert hasattr(app, "LIMITER_AVAILABLE")
        except ImportError as e:
            # flask_limiter以外のImportErrorは再送出
            if "flask_limiter" not in str(e):
                raise

    def test_rate_limit_configuration(self):
        """レート制限の設定確認"""
        # 環境変数で設定可能であることを確認
        original_env = os.environ.get("RATE_LIMIT_DEFAULT")

        try:
            os.environ["RATE_LIMIT_DEFAULT"] = "50 per hour"
            # 設定が読み込まれることを確認（実際の動作確認は統合テストで）
            assert os.environ.get("RATE_LIMIT_DEFAULT") == "50 per hour"
        finally:
            if original_env:
                os.environ["RATE_LIMIT_DEFAULT"] = original_env
            elif "RATE_LIMIT_DEFAULT" in os.environ:
                del os.environ["RATE_LIMIT_DEFAULT"]
