#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
構造化ログ設定モジュール
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """JSON形式のログフォーマッター"""

    def format(self, record: logging.LogRecord) -> str:
        """ログレコードをJSON形式に変換"""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 追加のコンテキスト情報
        if hasattr(record, "extra") and record.extra:
            log_data.update(record.extra)

        # 例外情報
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            log_data["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None

        # プロセス情報
        log_data["process_id"] = record.process
        log_data["thread_id"] = record.thread
        log_data["thread_name"] = record.threadName

        return json.dumps(log_data, ensure_ascii=False)


class StructuredLogger:
    """構造化ログをサポートするロガーラッパー"""

    @staticmethod
    def setup_logging(
        level: str = None, format_type: str = "json", output_stream: Any = None
    ) -> None:
        """
        ロギングを設定

        Args:
            level: ログレベル（'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'）
            format_type: フォーマットタイプ（'json' または 'text'）
            output_stream: 出力ストリーム（デフォルト: sys.stdout）
        """
        if level is None:
            level = os.environ.get("LOG_LEVEL", "INFO").upper()

        log_level = getattr(logging, level.upper(), logging.INFO)

        if output_stream is None:
            output_stream = sys.stdout

        # ルートロガーの設定
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # 既存のハンドラーをクリア
        root_logger.handlers.clear()

        # ハンドラーの作成
        handler = logging.StreamHandler(output_stream)
        handler.setLevel(log_level)

        # フォーマッターの設定
        formatter: logging.Formatter
        if format_type == "json":
            formatter = JSONFormatter()
        else:
            # テキスト形式（後方互換性のため）
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )

        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

        # 外部ライブラリのログレベルを調整
        logging.getLogger("werkzeug").setLevel(logging.WARNING)
        logging.getLogger("gunicorn").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """
    ロガーを取得

    Args:
        name: ロガー名（通常は __name__）

    Returns:
        Loggerインスタンス
    """
    return logging.getLogger(name)
