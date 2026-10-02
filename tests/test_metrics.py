#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prometheusメトリクスのテスト
"""

from utils.metrics import (
    PROMETHEUS_AVAILABLE,
    get_metrics,
    record_error,
    record_file_upload,
    record_processed_file,
    record_request,
    set_active_jobs,
)


class TestMetrics:
    """メトリクスのテスト"""

    def test_get_metrics(self):
        """メトリクス取得のテスト"""
        metrics = get_metrics()
        assert isinstance(metrics, bytes)
        assert len(metrics) > 0
        # Prometheus形式であることを確認（利用可能な場合）
        if PROMETHEUS_AVAILABLE:
            assert b"# HELP" in metrics or b"# TYPE" in metrics
        else:
            # モックの場合
            assert b"Prometheus" in metrics or b"not available" in metrics

    def test_record_request(self):
        """リクエスト記録のテスト"""
        # エラーが発生しないことを確認
        record_request("GET", "index", 200, 0.1)
        record_request("POST", "upload", 201, 0.5)
        record_request("GET", "download", 404, 0.2)

    def test_record_file_upload(self):
        """ファイルアップロード記録のテスト"""
        record_file_upload("html", "fortigate", 1024, 1.5)
        record_file_upload("excel", "paloalto", 2048, 2.0)
        record_file_upload("pdf", "fortigate", 512, 0.8)

    def test_record_error(self):
        """エラー記録のテスト"""
        record_error("INTERNAL_ERROR", "upload")
        record_error("VALIDATION_ERROR", "upload_async")
        record_error("FILE_NOT_FOUND", "download")

    def test_set_active_jobs(self):
        """アクティブジョブ数設定のテスト"""
        set_active_jobs(0)
        set_active_jobs(5)
        set_active_jobs(10)

    def test_record_processed_file(self):
        """処理済みファイル記録のテスト"""
        record_processed_file("html", "success")
        record_processed_file("excel", "success")
        record_processed_file("pdf", "error")

    def test_metrics_format(self):
        """メトリクス形式のテスト"""
        metrics = get_metrics()
        metrics_str = metrics.decode("utf-8")

        # Prometheus clientが利用可能な場合とそうでない場合で異なる
        if PROMETHEUS_AVAILABLE:
            # 基本的なPrometheus形式の確認
            assert (
                "wallscribe" in metrics_str.lower()
                or "# HELP" in metrics_str
                or "# TYPE" in metrics_str
            )
        else:
            # モックの場合、メッセージが含まれることを確認
            assert "prometheus" in metrics_str.lower() or "not available" in metrics_str.lower()
