#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ファイアウォール パラメータシート生成ツール - Web アプリケーション
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union

from flask import (
    Flask,
)

# レート制限（オプショナル）
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False

    # モック用のダミークラス
    class _MockLimiter:
        def __init__(self, *args, **kwargs):
            pass

        def limit(self, *args, **kwargs):
            def decorator(f):
                return f

            return decorator

    def get_remote_address():
        return "127.0.0.1"

    Limiter = _MockLimiter  # type: ignore[misc,assignment]

from parsers.base import get_parser_for_content, detect_encoding
from exporters.html import HTMLExporter

# エクスポーター（環境によりオプショナル）
try:
    from exporters.pdf import PDFExporter  # type: ignore

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    PDFExporter = None  # type: ignore[assignment]

try:
    import exporters.excel as excel_module  # type: ignore

    ExcelExporter = excel_module.ExcelExporter  # type: ignore[attr-defined]
    EXCEL_AVAILABLE = bool(getattr(excel_module, "OPENPYXL_AVAILABLE", True))
except ImportError:
    EXCEL_AVAILABLE = False
    ExcelExporter = None  # type: ignore[assignment]
from exceptions import WallScribeError, ParseError, ExportError, ValidationError, FileError
from utils.validation import (
    validate_file_content,
    validate_file_size,
    validate_output_format,
    validate_ha_mode,
)
from utils.storage import (
    set_upload_folder,
    save_file_metadata,
    load_file_metadata,
    delete_file_metadata,
    update_progress,
)
from routes.jobs import register as register_job_routes
from routes.system import register as register_system_routes
from routes.pages import register as register_page_routes
from routes.files import register as register_file_routes
from routes.status import register as register_status_routes
from routes.upload_async import register as register_upload_async_routes
from routes.upload_sync import register as register_upload_sync_routes
from web.cleanup import start_cleanup_thread
from web.hooks import register_error_handlers, register_request_hooks, swagger_setup
from jobs.processor import JobProcessor

# モニタリング（オプショナル）
try:
    from utils.metrics import (
        record_request,
        record_file_upload,
        record_error,
        set_active_jobs,
        record_processed_file,
        get_metrics,
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

    # モック関数（型チェックを無視）
    def record_request(*args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

    def record_file_upload(*args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

    def record_error(*args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

    def set_active_jobs(*args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

    def record_processed_file(*args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

    def get_metrics() -> bytes:
        return b"# Metrics not available\n"


SWAGGER_AVAILABLE = True

# ロギング設定
# 環境変数でJSON形式を有効化可能（LOG_FORMAT=json）
log_format = os.environ.get("LOG_FORMAT", "text")
if log_format == "json":
    from utils.logging_config import StructuredLogger

    StructuredLogger.setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"), format_type="json")
else:
    # 後方互換性のため、テキスト形式もサポート
    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

logger = logging.getLogger(__name__)

limiter = None  # type: ignore[assignment]
cleanup_thread = None  # type: ignore[assignment]


def create_app() -> Flask:
    """Flask アプリを生成（create_app 形式）"""
    global limiter, cleanup_thread, SWAGGER_AVAILABLE

    app = Flask(__name__, template_folder="web/templates", static_folder="static")

    # 設定
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER", "./uploads")
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024)
    )  # 50MB
    app.config["CLEANUP_INTERVAL"] = int(os.environ.get("CLEANUP_INTERVAL", 3600))  # 1時間

    # メタデータ保存先を共有（ワーカースレッドからも参照）
    set_upload_folder(Path(app.config["UPLOAD_FOLDER"]))

    # Swagger
    _swagger, ok = swagger_setup(app, swagger_available=SWAGGER_AVAILABLE)
    SWAGGER_AVAILABLE = ok

    # レート制限
    if LIMITER_AVAILABLE:
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=[os.environ.get("RATE_LIMIT_DEFAULT", "100 per hour")],
            storage_uri=os.environ.get("RATE_LIMIT_STORAGE", "memory://"),
            headers_enabled=True,
        )
    else:
        limiter = Limiter()

    # ルート登録（巨大化対策）
    processor = JobProcessor(
        update_progress=update_progress,
        save_file_metadata=save_file_metadata,
        metrics_available=METRICS_AVAILABLE,
        record_file_upload=record_file_upload,
        record_processed_file=record_processed_file,
        record_error=record_error,
        html_exporter_cls=HTMLExporter,
        pdf_exporter_cls=PDFExporter,
        excel_exporter_cls=ExcelExporter,
        pdf_available=PDF_AVAILABLE,
        excel_available=EXCEL_AVAILABLE,
    )
    register_job_routes(app, limiter)
    register_system_routes(app, get_metrics)
    register_page_routes(app)
    register_file_routes(app)
    register_status_routes(app)
    register_upload_async_routes(
        app,
        limiter,
        process_job_multi=processor.process_job_multi,
        allowed_file=allowed_file,
        get_file_extension=get_file_extension,
        validate_output_format=validate_output_format,
        validate_ha_mode=validate_ha_mode,
        validate_file_size=validate_file_size,
        validate_file_content=validate_file_content,
        pdf_available=PDF_AVAILABLE,
        excel_available=EXCEL_AVAILABLE,
    )
    register_upload_sync_routes(
        app,
        limiter,
        allowed_file=allowed_file,
        detect_encoding=detect_encoding,
        get_parser_for_content=get_parser_for_content,
        validate_output_format=validate_output_format,
        validate_file_size=validate_file_size,
        validate_file_content=validate_file_content,
        html_exporter_cls=HTMLExporter,
        pdf_exporter_cls=PDFExporter,
        excel_exporter_cls=ExcelExporter,
        pdf_available=PDF_AVAILABLE,
        excel_available=EXCEL_AVAILABLE,
    )

    # エラーハンドラ/フック
    register_error_handlers(app)
    register_request_hooks(app, metrics_available=METRICS_AVAILABLE, record_request=record_request)

    # クリーンアップスレッド
    if os.environ.get("WALLSCRIBE_DISABLE_CLEANUP_THREAD", "").lower() not in ("1", "true", "yes"):
        cleanup_thread = start_cleanup_thread(
            app, load_file_metadata=load_file_metadata, delete_file_metadata=delete_file_metadata
        )

    return app


# 許可拡張子
ALLOWED_EXTENSIONS = {".conf", ".xml"}


def allowed_file(filename: str) -> bool:
    """許可されたファイル拡張子かチェック"""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def get_file_extension(filename: str) -> str:
    """ファイル拡張子を取得"""
    return Path(filename).suffix.lower()


# module-level app（後方互換）
app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 8080))
    debug = os.environ.get("FLASK_ENV", "production") == "development"

    logger.info(f"サーバー起動: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
