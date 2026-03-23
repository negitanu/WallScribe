#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
古い生成物/メタデータのクリーンアップ
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def start_cleanup_thread(app, *, load_file_metadata, delete_file_metadata) -> threading.Thread:
    """クリーンアップスレッドを開始して返す"""

    def cleanup_old_files():
        while True:
            try:
                now = datetime.now()
                upload_folder = Path(app.config["UPLOAD_FOLDER"])

                if upload_folder.exists():
                    for file_path in upload_folder.iterdir():
                        if file_path.is_file():
                            try:
                                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                                if now - mtime > timedelta(hours=1):
                                    file_path.unlink()
                                    logger.info(f"クリーンアップ: {file_path.name}")
                            except Exception as e:
                                logger.warning(f"ファイルクリーンアップエラー: {file_path.name}, {e}")

                if upload_folder.exists():
                    for meta_path in upload_folder.glob("*.meta.json"):
                        try:
                            file_id = meta_path.stem.replace(".meta", "")
                            metadata = load_file_metadata(file_id)
                            if metadata:
                                created_at = metadata.get("created_at")
                                if isinstance(created_at, str):
                                    created_at = datetime.fromisoformat(created_at)
                                if created_at and now - created_at > timedelta(hours=1):
                                    delete_file_metadata(file_id)
                                    logger.info(f"メタデータクリーンアップ: {meta_path.name}")
                        except Exception as e:
                            logger.warning(f"メタデータクリーンアップエラー: {meta_path.name}, {e}")

                time.sleep(int(app.config.get("CLEANUP_INTERVAL", 3600)))
            except Exception as e:
                logger.error(f"クリーンアップエラー: {e}")
                time.sleep(3600)

    t = threading.Thread(target=cleanup_old_files, daemon=True)
    t.start()
    return t
