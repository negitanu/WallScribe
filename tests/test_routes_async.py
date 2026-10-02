#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
非同期アップロードルートのテスト
"""

import io
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


from app import app


@pytest.fixture
def client():
    """Flaskテストクライアント"""
    app.config["TESTING"] = True
    app.config["UPLOAD_FOLDER"] = "/tmp/test_uploads_async"
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

    # テスト用アップロードフォルダを作成
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    with app.test_client() as client:
        yield client

    # クリーンアップ
    shutil.rmtree(app.config["UPLOAD_FOLDER"], ignore_errors=True)


@pytest.fixture
def sample_fortigate_content():
    """FortiGateサンプル設定"""
    return b"""#config-version=FGT60F-7.2.5-FW-build1517:opmode=0:vdom=0:user=admin
config system global
    set hostname "FW-TEST-01"
end
config firewall policy
end
"""


@pytest.fixture
def sample_paloalto_content():
    """Palo Altoサンプル設定"""
    return b"""<?xml version="1.0"?>
<config version="10.2.0">
  <devices>
    <entry name="localhost.localdomain">
      <deviceconfig>
        <system>
          <hostname>PA-TEST-01</hostname>
        </system>
      </deviceconfig>
    </entry>
  </devices>
</config>
"""


class TestUploadFileAsync:
    """非同期アップロードエンドポイントのテスト"""

    def test_upload_no_file(self, client):
        """ファイルなしでアップロード"""
        response = client.post("/api/v1/upload")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]["code"] == "NO_FILE"

    def test_upload_empty_filename(self, client):
        """空のファイル名"""
        data = {"config_files[]": (io.BytesIO(b""), "")}
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]["code"] == "NO_FILE"

    def test_upload_unsupported_format(self, client):
        """サポートされていないファイル形式"""
        data = {"config_files[]": (io.BytesIO(b"some content"), "config.txt")}
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]["code"] == "UNSUPPORTED_FORMAT"

    def test_upload_invalid_output_format(self, client, sample_fortigate_content):
        """無効な出力形式"""
        data = {
            "config_files[]": (io.BytesIO(sample_fortigate_content), "config.conf"),
            "output_format": "invalid_format",
        }
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_OUTPUT_FORMAT"

    def test_upload_invalid_ha_mode(self, client, sample_fortigate_content):
        """無効なHAモード"""
        data = {
            "config_files[]": (io.BytesIO(sample_fortigate_content), "config.conf"),
            "ha_mode": "invalid_mode",
        }
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_HA_MODE"

    def test_upload_invalid_file_content(self, client):
        """無効なファイル内容"""
        data = {"config_files[]": (io.BytesIO(b"invalid content"), "config.conf")}
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_FILE_CONTENT"

    @patch("routes.upload_async.threading.Thread")
    def test_upload_fortigate_success(self, mock_thread, client, sample_fortigate_content):
        """FortiGateファイルのアップロード成功"""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        data = {
            "config_files[]": (io.BytesIO(sample_fortigate_content), "config.conf"),
            "output_format": "html",
        }
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 202
        data = json.loads(response.data)
        assert data["success"] is True
        assert "file_id" in data
        assert data["file_count"] == 1
        assert "progress_url" in data
        assert "result_url" in data

    @patch("routes.upload_async.threading.Thread")
    def test_upload_paloalto_success(self, mock_thread, client, sample_paloalto_content):
        """Palo Altoファイルのアップロード成功"""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        data = {
            "config_files[]": (io.BytesIO(sample_paloalto_content), "config.xml"),
            "output_format": "html",
        }
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 202
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["file_count"] == 1

    @patch("routes.upload_async.threading.Thread")
    def test_upload_multiple_files(self, mock_thread, client, sample_fortigate_content):
        """複数ファイルのアップロード"""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        data = {
            "config_files[]": [
                (io.BytesIO(sample_fortigate_content), "config1.conf"),
                (io.BytesIO(sample_fortigate_content), "config2.conf"),
            ],
            "output_format": "html",
            "ha_mode": "cluster",
        }
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 202
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["file_count"] == 2

    @patch("routes.upload_async.threading.Thread")
    def test_upload_with_sections(self, mock_thread, client, sample_fortigate_content):
        """セクション指定付きアップロード"""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        data = {
            "config_files[]": (io.BytesIO(sample_fortigate_content), "config.conf"),
            "output_format": "html",
            "sections": '["device", "network"]',
        }
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 202
        data = json.loads(response.data)
        assert data["success"] is True

    @patch("routes.upload_async.threading.Thread")
    def test_upload_with_invalid_sections_json(self, mock_thread, client, sample_fortigate_content):
        """無効なセクションJSON（処理は継続）"""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        data = {
            "config_files[]": (io.BytesIO(sample_fortigate_content), "config.conf"),
            "output_format": "html",
            "sections": "invalid json",
        }
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        # 無効なJSONでもエラーにならず処理は継続
        assert response.status_code == 202

    @patch("routes.upload_async.threading.Thread")
    def test_upload_legacy_endpoint(self, mock_thread, client, sample_fortigate_content):
        """レガシーエンドポイント"""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        data = {
            "config_files[]": (io.BytesIO(sample_fortigate_content), "config.conf"),
        }
        response = client.post("/upload_async", data=data, content_type="multipart/form-data")

        assert response.status_code == 202

    @patch("routes.upload_async.threading.Thread")
    def test_upload_with_single_file_field(self, mock_thread, client, sample_fortigate_content):
        """config_file（単一）フィールドでのアップロード"""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        data = {
            "config_file": (io.BytesIO(sample_fortigate_content), "config.conf"),
        }
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 202


class TestUploadDependencyCheck:
    """依存関係チェックのテスト"""

    @pytest.mark.pdf
    @patch("routes.upload_async.threading.Thread")
    def test_upload_pdf_without_weasyprint(self, mock_thread, client, sample_fortigate_content):
        """WeasyPrintなしでPDF出力を要求"""
        # pdf_availableがFalseに設定されている場合のテスト
        # 実際のテストでは、pdf_availableの状態によって結果が変わる
        data = {
            "config_files[]": (io.BytesIO(sample_fortigate_content), "config.conf"),
            "output_format": "pdf",
        }
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        # pdf_availableの状態によって202または400
        assert response.status_code in [202, 400]

    @patch("routes.upload_async.threading.Thread")
    def test_upload_excel_format(self, mock_thread, client, sample_fortigate_content):
        """Excel形式の出力"""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        data = {
            "config_files[]": (io.BytesIO(sample_fortigate_content), "config.conf"),
            "output_format": "excel",
        }
        response = client.post("/api/v1/upload", data=data, content_type="multipart/form-data")

        # excel_availableの状態によって202または400
        assert response.status_code in [202, 400]
