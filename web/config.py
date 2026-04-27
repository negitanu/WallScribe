#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Webアプリケーション設定とロギング初期化。"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        logging.getLogger(__name__).warning(
            "環境変数 %s=%r は整数として解釈できないため、既定値 %s を使用します",
            name,
            value,
            default,
        )
        return default


@dataclass(frozen=True)
class AppSettings:
    """Flaskアプリの環境変数由来設定。"""

    secret_key: str
    upload_folder: str
    max_content_length: int
    cleanup_interval: int
    flask_env: str
    flask_port: int
    rate_limit_default: str
    rate_limit_storage: str
    log_format: str
    log_level: str
    cleanup_thread_enabled: bool

    @classmethod
    def from_env(cls) -> "AppSettings":
        secret_key = os.environ.get("SECRET_KEY", "")
        if not secret_key:
            # 互換性維持のため起動失敗にはせず、従来通り一時キーを生成する。
            import os as _os

            secret_key = _os.urandom(24).hex()
            logging.getLogger(__name__).warning(
                "SECRET_KEY が未設定です。一時キーを生成しました。本番では SECRET_KEY を設定してください。"
            )

        cleanup_disabled = os.environ.get("WALLSCRIBE_DISABLE_CLEANUP_THREAD", "").lower() in (
            "1",
            "true",
            "yes",
        )

        return cls(
            secret_key=secret_key,
            upload_folder=os.environ.get("UPLOAD_FOLDER", "./uploads"),
            max_content_length=_get_int("MAX_CONTENT_LENGTH", 50 * 1024 * 1024),
            cleanup_interval=_get_int("CLEANUP_INTERVAL", 3600),
            flask_env=os.environ.get("FLASK_ENV", "production"),
            flask_port=_get_int("FLASK_PORT", 8080),
            rate_limit_default=os.environ.get("RATE_LIMIT_DEFAULT", "100 per hour"),
            rate_limit_storage=os.environ.get("RATE_LIMIT_STORAGE", "memory://"),
            log_format=os.environ.get("LOG_FORMAT", "text"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            cleanup_thread_enabled=not cleanup_disabled,
        )

    def apply_to_flask(self, app) -> None:
        """Flask config に設定値を反映する。"""
        app.config["SECRET_KEY"] = self.secret_key
        app.config["UPLOAD_FOLDER"] = self.upload_folder
        app.config["MAX_CONTENT_LENGTH"] = self.max_content_length
        app.config["CLEANUP_INTERVAL"] = self.cleanup_interval


def configure_logging(settings: AppSettings) -> None:
    """環境変数に従ってロギングを初期化する。"""
    if settings.log_format == "json":
        from utils.logging_config import StructuredLogger

        StructuredLogger.setup_logging(level=settings.log_level, format_type="json")
        return

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
