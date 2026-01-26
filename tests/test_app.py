#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flaskアプリケーションのテスト
"""

import pytest
import json
import io
from pathlib import Path

# Flaskアプリをインポート（テスト設定で）
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app, allowed_file, get_file_extension


@pytest.fixture
def client():
    """Flaskテストクライアント"""
    app.config["TESTING"] = True
    app.config["UPLOAD_FOLDER"] = "/tmp/test_uploads"

    # テスト用アップロードフォルダを作成
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    with app.test_client() as client:
        yield client

    # クリーンアップ
    import shutil

    shutil.rmtree(app.config["UPLOAD_FOLDER"], ignore_errors=True)


class TestAllowedFile:
    """ファイル拡張子チェックのテスト"""

    def test_allowed_conf(self):
        """confファイルは許可"""
        assert allowed_file("config.conf") is True
        assert allowed_file("CONFIG.CONF") is True

    def test_allowed_xml(self):
        """xmlファイルは許可"""
        assert allowed_file("config.xml") is True
        assert allowed_file("CONFIG.XML") is True

    def test_not_allowed_txt(self):
        """txtファイルは拒否"""
        assert allowed_file("config.txt") is False

    def test_not_allowed_exe(self):
        """exeファイルは拒否"""
        assert allowed_file("malware.exe") is False

    def test_no_extension(self):
        """拡張子なしは拒否"""
        assert allowed_file("config") is False


class TestGetFileExtension:
    """ファイル拡張子取得のテスト"""

    def test_conf_extension(self):
        """conf拡張子"""
        assert get_file_extension("config.conf") == ".conf"

    def test_xml_extension(self):
        """xml拡張子"""
        assert get_file_extension("config.xml") == ".xml"

    def test_uppercase_extension(self):
        """大文字拡張子"""
        assert get_file_extension("config.CONF") == ".conf"


class TestIndexRoute:
    """インデックスページのテスト"""

    def test_index_page(self, client):
        """インデックスページの表示"""
        response = client.get("/")

        assert response.status_code == 200
        # HTMLが返されることを確認
        assert b"<!DOCTYPE html>" in response.data or b"<html" in response.data


class TestUploadRoute:
    """アップロードエンドポイントのテスト"""

    def test_upload_no_file(self, client):
        """ファイルなしでアップロード"""
        response = client.post("/upload")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]["code"] == "NO_FILE"

    def test_upload_empty_filename(self, client):
        """空のファイル名でアップロード"""
        data = {"config_file": (io.BytesIO(b""), "")}
        response = client.post("/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"]["code"] == "NO_FILE"

    def test_upload_unsupported_format(self, client):
        """サポート外形式のアップロード"""
        data = {"config_file": (io.BytesIO(b"test content"), "config.txt")}
        response = client.post("/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 400
        result = json.loads(response.data)
        assert result["success"] is False
        assert result["error"]["code"] == "UNSUPPORTED_FORMAT"

    def test_upload_invalid_content(self, client):
        """無効な内容のアップロード"""
        data = {"config_file": (io.BytesIO(b"invalid content"), "config.conf")}
        response = client.post("/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 400
        result = json.loads(response.data)
        assert result["success"] is False

    def test_upload_valid_fortigate(self, client, sample_fortigate_config):
        """有効なFortiGate設定のアップロード"""
        data = {
            "config_file": (io.BytesIO(sample_fortigate_config.encode("utf-8")), "config.conf"),
            "output_format": "html",
        }
        response = client.post("/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["success"] is True
        assert "file_id" in result
        assert "download_url" in result
        assert result["device_type"] == "FortiGate"

    def test_upload_valid_paloalto(self, client, sample_paloalto_config):
        """有効なPalo Alto設定のアップロード"""
        data = {
            "config_file": (io.BytesIO(sample_paloalto_config.encode("utf-8")), "config.xml"),
            "output_format": "html",
        }
        response = client.post("/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["success"] is True
        assert result["device_type"] == "Palo Alto"

    def test_upload_excel_format(self, client, sample_fortigate_config):
        """Excel形式での出力"""
        if not getattr(__import__("app"), "EXCEL_AVAILABLE", True):
            pytest.skip("openpyxl が未導入のため excel 出力テストをスキップ")
        data = {
            "config_file": (io.BytesIO(sample_fortigate_config.encode("utf-8")), "config.conf"),
            "output_format": "excel",
        }
        response = client.post("/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["success"] is True
        assert result["filename"].endswith(".xlsx")

    def test_upload_pdf_format(self, client, sample_fortigate_config):
        """PDF形式での出力"""
        if not getattr(__import__("app"), "PDF_AVAILABLE", True):
            pytest.skip("weasyprint が未導入のため pdf 出力テストをスキップ")
        data = {
            "config_file": (io.BytesIO(sample_fortigate_config.encode("utf-8")), "config.conf"),
            "output_format": "pdf",
        }
        response = client.post("/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["success"] is True
        assert result["filename"].endswith(".pdf")

    def test_upload_with_sections(self, client, sample_fortigate_config):
        """セクション指定でのアップロード"""
        import json as json_module

        data = {
            "config_file": (io.BytesIO(sample_fortigate_config.encode("utf-8")), "config.conf"),
            "output_format": "html",
            "sections": json_module.dumps(["device_info", "policies"]),
        }
        response = client.post("/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["success"] is True

    def test_upload_with_internet_service(self, client):
        """Internet Serviceを含むポリシーのアップロード"""
        config_content = """#config-version=FGT60F-7.2.5-FW-build1517
config system global
    set hostname "FW-TEST-01"
end
config firewall policy
    edit 53
        set name "pref-0053"
        set srcintf "v1312-Internet"
        set dstintf "v930-SCO-WAN"
        set action accept
        set srcaddr "pref-172.21.0.0/16"
        set internet-service enable
        set internet-service-name "Google-Web" "Google-RTMP" "Google-Gmail"
        set schedule "always"
        set logtraffic all
    next
end
"""
        data = {
            "config_file": (io.BytesIO(config_content.encode("utf-8")), "config.conf"),
            "output_format": "html",
        }
        response = client.post("/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["success"] is True
        assert result["device_type"] == "FortiGate"

    def test_upload_unsupported_output_format(self, client, sample_fortigate_config):
        """サポート外出力形式"""
        data = {
            "config_file": (io.BytesIO(sample_fortigate_config.encode("utf-8")), "config.conf"),
            "output_format": "json",
        }
        response = client.post("/upload", data=data, content_type="multipart/form-data")

        assert response.status_code == 400
        result = json.loads(response.data)
        assert result["success"] is False
        # 出力形式のバリデーションエラー
        assert result["error"]["code"] in ("INVALID_OUTPUT_FORMAT", "UNSUPPORTED_FORMAT")


class TestDownloadRoute:
    """ダウンロードエンドポイントのテスト"""

    def test_download_invalid_file_id(self, client):
        """無効なファイルID"""
        response = client.get("/download/invalid-id")

        assert response.status_code == 400
        result = json.loads(response.data)
        assert result["error"]["code"] == "INVALID_FILE_ID"

    def test_download_nonexistent_file(self, client):
        """存在しないファイル"""
        # 有効なUUID形式だが存在しないID
        response = client.get("/download/12345678-1234-1234-1234-123456789abc")

        assert response.status_code == 404
        result = json.loads(response.data)
        assert result["error"]["code"] == "FILE_NOT_FOUND"


class TestPreviewRoute:
    """プレビューエンドポイントのテスト"""

    def test_preview_invalid_file_id(self, client):
        """無効なファイルID"""
        response = client.get("/preview/invalid-id")

        assert response.status_code == 400

    def test_preview_nonexistent_file(self, client):
        """存在しないファイル"""
        response = client.get("/preview/12345678-1234-1234-1234-123456789abc")

        assert response.status_code == 404


class TestStatusRoute:
    """ステータスエンドポイントのテスト"""

    def test_status_invalid_file_id(self, client):
        """無効なファイルID"""
        response = client.get("/api/status/invalid-id")

        assert response.status_code == 400
        result = json.loads(response.data)
        assert result["error"]["code"] == "INVALID_FILE_ID"

    def test_status_nonexistent_file(self, client):
        """存在しないファイル"""
        response = client.get("/api/status/12345678-1234-1234-1234-123456789abc")

        assert response.status_code == 404
        result = json.loads(response.data)
        assert result["error"]["code"] == "FILE_NOT_FOUND"


class TestSecurityHeaders:
    """セキュリティヘッダーのテスト"""

    def test_security_headers(self, client):
        """セキュリティヘッダーの存在確認"""
        response = client.get("/")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Content-Security-Policy" in response.headers


class TestErrorHandlers:
    """エラーハンドラーのテスト"""

    def test_404_error(self, client):
        """404エラー"""
        response = client.get("/nonexistent-page")

        assert response.status_code == 404

    def test_large_file_error(self, client):
        """ファイルサイズ超過エラー（設定による）"""
        # このテストは実際のMAX_CONTENT_LENGTHに依存
        # 50MB以上のファイルをアップロードすると413エラー
        pass
