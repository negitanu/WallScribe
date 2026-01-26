#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ヘルスチェックエンドポイントのテスト
"""

import pytest
import sys
from pathlib import Path


# オプショナルな依存関係がない場合でもテストできるようにする
# app.pyのインポートは重いので、直接テストする
@pytest.fixture
def client():
    """テストクライアント（オプショナル依存関係を考慮）"""
    try:
        from app import app

        app.config["TESTING"] = True
        app.config["UPLOAD_FOLDER"] = "./test_uploads"
        with app.test_client() as client:
            yield client
    except ImportError as e:
        # weasyprintなどのオプショナルな依存関係がない場合はスキップ
        pytest.skip(f"Optional dependencies not available: {e}")


class TestHealthCheck:
    """ヘルスチェックエンドポイントのテスト"""

    def test_health_check(self, client):
        """基本的なヘルスチェックのテスト"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_liveness_check(self, client):
        """ライブネスチェックのテスト"""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    def test_readiness_check(self, client):
        """レディネスチェックのテスト"""
        response = client.get("/health/ready")
        # ディスク容量が十分な場合は200、不足している場合は503
        assert response.status_code in [200, 503]
        data = response.get_json()
        assert data["status"] in ["ready", "not_ready"]
        if response.status_code == 200:
            assert "free_space_gb" in data
