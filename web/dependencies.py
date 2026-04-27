#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Webアプリの任意依存を安全に読み込む。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class _MockLimiter:
    def __init__(self, *args, **kwargs):
        pass

    def limit(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


def _mock_remote_address() -> str:
    return "127.0.0.1"


def _noop(*args: Any, **kwargs: Any) -> None:
    return None


def _metrics_unavailable() -> bytes:
    return b"# Metrics not available\n"


@dataclass(frozen=True)
class RuntimeDependencies:
    limiter_cls: Any
    get_remote_address: Callable[[], str]
    limiter_available: bool
    pdf_exporter_cls: Any
    pdf_available: bool
    excel_exporter_cls: Any
    excel_available: bool
    metrics_available: bool
    get_metrics: Callable[[], bytes]
    record_request: Callable[..., None]
    record_file_upload: Callable[..., None]
    record_error: Callable[..., None]
    set_active_jobs: Callable[..., None]
    record_processed_file: Callable[..., None]


def load_runtime_dependencies() -> RuntimeDependencies:
    """任意依存の有無を吸収し、アプリ起動自体は継続できるようにする。"""
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter_cls = Limiter
        limiter_available = True
    except ImportError:
        limiter_cls = _MockLimiter
        get_remote_address = _mock_remote_address
        limiter_available = False

    try:
        from exporters.pdf import PDFExporter  # type: ignore

        pdf_exporter_cls = PDFExporter
        pdf_available = True
    except (ImportError, OSError):
        pdf_exporter_cls = None
        pdf_available = False

    try:
        import exporters.excel as excel_module  # type: ignore

        excel_exporter_cls = excel_module.ExcelExporter  # type: ignore[attr-defined]
        excel_available = bool(getattr(excel_module, "OPENPYXL_AVAILABLE", True))
    except ImportError:
        excel_exporter_cls = None
        excel_available = False

    try:
        from utils.metrics import (
            get_metrics,
            record_error,
            record_file_upload,
            record_processed_file,
            record_request,
            set_active_jobs,
        )

        metrics_available = True
    except ImportError:
        metrics_available = False
        get_metrics = _metrics_unavailable
        record_request = _noop
        record_file_upload = _noop
        record_error = _noop
        set_active_jobs = _noop
        record_processed_file = _noop

    return RuntimeDependencies(
        limiter_cls=limiter_cls,
        get_remote_address=get_remote_address,
        limiter_available=limiter_available,
        pdf_exporter_cls=pdf_exporter_cls,
        pdf_available=pdf_available,
        excel_exporter_cls=excel_exporter_cls,
        excel_available=excel_available,
        metrics_available=metrics_available,
        get_metrics=get_metrics,
        record_request=record_request,
        record_file_upload=record_file_upload,
        record_error=record_error,
        set_active_jobs=set_active_jobs,
        record_processed_file=record_processed_file,
    )
