#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ジョブ管理ルートのテスト
"""

import pytest
import json
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import shutil

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app


@pytest.fixture
def client():
    """Flaskテストクライアント"""
    app.config["TESTING"] = True
    app.config["UPLOAD_FOLDER"] = "/tmp/test_uploads_jobs"

    # テスト用アップロードフォルダを作成
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    with app.test_client() as client:
        yield client

    # クリーンアップ
    shutil.rmtree(app.config["UPLOAD_FOLDER"], ignore_errors=True)


@pytest.fixture
def sample_file_id():
    """サンプルファイルID"""
    return str(uuid.uuid4())


@pytest.fixture
def sample_metadata(sample_file_id):
    """サンプルメタデータ"""
    return {
        "filename": "test_output.html",
        "path": f"/tmp/test_uploads_jobs/{sample_file_id}_test_output.html",
        "file_count": 1,
        "created_at": datetime.now(),
        "status": "completed",
        "progress_percent": 100,
        "progress_message": "完了",
        "progress_stage": "completed",
        "device_type": "FortiGate",
        "hostname": "FW-TEST-01",
        "version": "7.2.5",
    }


class TestListJobs:
    """ジョブ一覧エンドポイントのテスト"""

    def test_list_jobs_empty(self, client):
        """ジョブが存在しない場合"""
        response = client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    @patch("routes.jobs.load_file_metadata")
    def test_list_jobs_with_data(self, mock_load, client, sample_file_id, sample_metadata):
        """ジョブが存在する場合"""
        # メタデータファイルを作成
        upload_folder = Path(client.application.config["UPLOAD_FOLDER"])
        meta_path = upload_folder / f"{sample_file_id}.meta.json"
        meta_path.write_text(json.dumps({"filename": "test.html"}))

        mock_load.return_value = sample_metadata

        response = client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

        # クリーンアップ
        meta_path.unlink(missing_ok=True)

    def test_list_jobs_with_limit(self, client):
        """リミットパラメータのテスト"""
        response = client.get("/api/v1/jobs?limit=10")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    def test_list_jobs_with_invalid_limit(self, client):
        """無効なリミットパラメータ"""
        response = client.get("/api/v1/jobs?limit=invalid")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True


class TestGetJob:
    """ジョブ詳細エンドポイントのテスト"""

    def test_get_job_invalid_id(self, client):
        """無効なファイルID"""
        response = client.get("/api/v1/jobs/invalid-id")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_FILE_ID"

    @patch("routes.jobs.load_file_metadata")
    def test_get_job_not_found(self, mock_load, client, sample_file_id):
        """ジョブが見つからない場合"""
        mock_load.return_value = None

        response = client.get(f"/api/v1/jobs/{sample_file_id}")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]["code"] == "FILE_NOT_FOUND"

    @patch("routes.jobs.load_file_metadata")
    def test_get_job_success(self, mock_load, client, sample_file_id, sample_metadata):
        """ジョブ取得成功"""
        mock_load.return_value = sample_metadata

        response = client.get(f"/api/v1/jobs/{sample_file_id}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "job" in data
        assert data["job"]["file_id"] == sample_file_id
        assert data["job"]["filename"] == "test_output.html"
        assert data["job"]["status"] == "completed"


class TestDeleteJob:
    """ジョブ削除エンドポイントのテスト"""

    def test_delete_job_invalid_id(self, client):
        """無効なファイルID"""
        response = client.delete("/api/v1/jobs/invalid-id")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_FILE_ID"

    def test_delete_job_success(self, client, sample_file_id):
        """ジョブ削除成功"""
        # テストファイルを作成
        upload_folder = Path(client.application.config["UPLOAD_FOLDER"])
        test_file = upload_folder / f"{sample_file_id}_test.html"
        test_file.write_text("<html></html>")

        response = client.delete(f"/api/v1/jobs/{sample_file_id}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["file_id"] == sample_file_id
        assert "deleted_files" in data

    def test_delete_job_no_files(self, client, sample_file_id):
        """削除するファイルがない場合"""
        response = client.delete(f"/api/v1/jobs/{sample_file_id}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["deleted_files"] == 0
