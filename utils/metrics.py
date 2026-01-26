#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prometheusメトリクスモジュール
"""

# オプショナルインポート（prometheus_clientがインストールされていない場合でも動作）
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # モッククラス
    class _MockCounter:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def inc(self, value=1):
            pass

    class _MockHistogram:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def observe(self, value):
            pass

    class _MockGauge:
        def __init__(self, *args, **kwargs):
            pass

        def set(self, value):
            pass

    def generate_latest():
        return b"# Prometheus client not available\n"

    # エイリアスを設定
    Counter = _MockCounter  # type: ignore[misc,assignment]
    Histogram = _MockHistogram  # type: ignore[misc,assignment]
    Gauge = _MockGauge  # type: ignore[misc,assignment]

from typing import Optional

# リクエストメトリクス
request_count = Counter(
    "wallscribe_requests_total", "Total number of requests", ["method", "endpoint", "status"]
)

request_duration = Histogram(
    "wallscribe_request_duration_seconds", "Request duration in seconds", ["method", "endpoint"]
)

# ファイル処理メトリクス
file_upload_count = Counter(
    "wallscribe_file_uploads_total", "Total number of file uploads", ["format", "device_type"]
)

file_processing_duration = Histogram(
    "wallscribe_file_processing_seconds",
    "File processing duration in seconds",
    ["format", "device_type"],
)

file_size_bytes = Histogram("wallscribe_file_size_bytes", "Uploaded file size in bytes", ["format"])

# エラーメトリクス
error_count = Counter(
    "wallscribe_errors_total", "Total number of errors", ["error_type", "endpoint"]
)

# システムメトリクス
active_jobs = Gauge("wallscribe_active_jobs", "Number of active processing jobs")

processed_files_total = Counter(
    "wallscribe_processed_files_total", "Total number of processed files", ["format", "status"]
)


def get_metrics() -> bytes:
    """Prometheusメトリクスを取得"""
    return generate_latest()


def record_request(method: str, endpoint: str, status: int, duration: float):
    """リクエストメトリクスを記録"""
    request_count.labels(method=method, endpoint=endpoint, status=status).inc()
    request_duration.labels(method=method, endpoint=endpoint).observe(duration)


def record_file_upload(format_type: str, device_type: str, size: int, duration: float):
    """ファイルアップロードメトリクスを記録"""
    file_upload_count.labels(format=format_type, device_type=device_type).inc()
    file_processing_duration.labels(format=format_type, device_type=device_type).observe(duration)
    file_size_bytes.labels(format=format_type).observe(size)


def record_error(error_type: str, endpoint: str):
    """エラーメトリクスを記録"""
    error_count.labels(error_type=error_type, endpoint=endpoint).inc()


def set_active_jobs(count: int):
    """アクティブなジョブ数を設定"""
    active_jobs.set(count)


def record_processed_file(format_type: str, status: str):
    """処理済みファイル数を記録"""
    processed_files_total.labels(format=format_type, status=status).inc()
