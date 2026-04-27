#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ファイアウォール パラメータシート生成ツール - Web アプリケーション
"""

import logging
from pathlib import Path

from flask import Flask

from exporters.html import HTMLExporter
from parsers.base import detect_encoding, get_parser_for_content
from jobs.processor import JobProcessor
from routes.files import register as register_file_routes
from routes.jobs import register as register_job_routes
from routes.pages import register as register_page_routes
from routes.status import register as register_status_routes
from routes.system import register as register_system_routes
from routes.upload_async import register as register_upload_async_routes
from routes.upload_sync import register as register_upload_sync_routes
from utils.storage import (
    delete_file_metadata,
    load_file_metadata,
    save_file_metadata,
    set_upload_folder,
    update_progress,
)
from utils.validation import (
    validate_file_content,
    validate_file_size,
    validate_ha_mode,
    validate_output_format,
)
from web.cleanup import start_cleanup_thread
from web.config import AppSettings, configure_logging
from web.dependencies import load_runtime_dependencies
from web.hooks import register_error_handlers, register_request_hooks, swagger_setup

SWAGGER_AVAILABLE = True

# ロギング設定
# 任意依存の try:/except ImportError は web.dependencies に集約している。
SETTINGS = AppSettings.from_env()
configure_logging(SETTINGS)
RUNTIME = load_runtime_dependencies()
PDFExporter = RUNTIME.pdf_exporter_cls
ExcelExporter = RUNTIME.excel_exporter_cls
PDF_AVAILABLE = RUNTIME.pdf_available
EXCEL_AVAILABLE = RUNTIME.excel_available
METRICS_AVAILABLE = RUNTIME.metrics_available
LIMITER_AVAILABLE = RUNTIME.limiter_available

logger = logging.getLogger(__name__)

limiter = None  # type: ignore[assignment]
cleanup_thread = None  # type: ignore[assignment]


def create_app() -> Flask:
    """Flask アプリを生成（create_app 形式）"""
    global limiter, cleanup_thread, SWAGGER_AVAILABLE

    app = Flask(__name__, template_folder="web/templates", static_folder="static")

    # 設定
    SETTINGS.apply_to_flask(app)

    # メタデータ保存先を共有（ワーカースレッドからも参照）
    set_upload_folder(Path(app.config["UPLOAD_FOLDER"]))

    # Swagger
    _swagger, ok = swagger_setup(app, swagger_available=SWAGGER_AVAILABLE)
    SWAGGER_AVAILABLE = ok

    # レート制限
    if RUNTIME.limiter_available:
        limiter = RUNTIME.limiter_cls(
            app=app,
            key_func=RUNTIME.get_remote_address,
            default_limits=[SETTINGS.rate_limit_default],
            storage_uri=SETTINGS.rate_limit_storage,
            headers_enabled=True,
        )
        limiter.request_filter(lambda: bool(app.config.get("TESTING", False)))
    else:
        limiter = RUNTIME.limiter_cls()

    # ルート登録（巨大化対策）
    processor = JobProcessor(
        update_progress=update_progress,
        save_file_metadata=save_file_metadata,
        metrics_available=METRICS_AVAILABLE,
        record_file_upload=RUNTIME.record_file_upload,
        record_processed_file=RUNTIME.record_processed_file,
        record_error=RUNTIME.record_error,
        html_exporter_cls=HTMLExporter,
        pdf_exporter_cls=PDFExporter,
        excel_exporter_cls=ExcelExporter,
        pdf_available=PDF_AVAILABLE,
        excel_available=EXCEL_AVAILABLE,
    )
    register_job_routes(app, limiter)
    register_system_routes(app, RUNTIME.get_metrics)
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
    register_request_hooks(
        app, metrics_available=METRICS_AVAILABLE, record_request=RUNTIME.record_request
    )

    # クリーンアップスレッド
    if SETTINGS.cleanup_thread_enabled:
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
    port = SETTINGS.flask_port
    debug = SETTINGS.flask_env == "development"

    logger.info(f"サーバー起動: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
