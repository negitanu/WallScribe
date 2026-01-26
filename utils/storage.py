#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ファイルシステムベースのメタデータ保存/取得ユーティリティ

NOTE:
- ワーカースレッドからも呼ばれるため、Flaskのcurrent_appに依存しない
- UPLOAD_FOLDER は app 初期化時に set_upload_folder() で注入する
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_UPLOAD_FOLDER: Optional[Path] = None


def set_upload_folder(path: Path) -> None:
    """メタデータ保存先（UPLOAD_FOLDER）を設定する。"""
    global _UPLOAD_FOLDER
    _UPLOAD_FOLDER = Path(path).resolve()


def _get_upload_folder() -> Path:
    """UPLOAD_FOLDER を取得（未設定の場合は環境変数から推定）"""
    if _UPLOAD_FOLDER is not None:
        return _UPLOAD_FOLDER
    return Path(os.environ.get("UPLOAD_FOLDER", "./uploads")).resolve()


def get_metadata_path(file_id: str) -> Path:
    """メタデータファイルのパスを取得"""
    upload_folder = _get_upload_folder()
    return upload_folder / f"{file_id}.meta.json"


def save_file_metadata(file_id: str, metadata: dict) -> None:
    """ファイルメタデータを保存"""
    try:
        metadata_path = get_metadata_path(file_id)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        # created_atを文字列に変換（JSONシリアライズ可能にする）
        metadata_copy = metadata.copy()
        if "created_at" in metadata_copy and isinstance(metadata_copy["created_at"], datetime):
            metadata_copy["created_at"] = metadata_copy["created_at"].isoformat()

        # JSON読み込み中の部分書き込みを避けるため、テンポラリに書いてから置換する
        tmp_path = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(metadata_copy, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, metadata_path)
    except Exception as e:
        logger.error(f"メタデータ保存エラー: {e}", exc_info=True)


def load_file_metadata(file_id: str) -> Optional[Dict[str, Any]]:
    """ファイルメタデータを読み込み"""
    try:
        metadata_path = get_metadata_path(file_id)
        if not metadata_path.exists():
            return None

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata: Dict[str, Any] = json.load(f)
            # created_atをdatetimeに変換
            if "created_at" in metadata and isinstance(metadata["created_at"], str):
                metadata["created_at"] = datetime.fromisoformat(metadata["created_at"])
            return metadata
    except Exception as e:
        logger.error(f"メタデータ読み込みエラー: {e}", exc_info=True)
        return None


def delete_file_metadata(file_id: str) -> None:
    """ファイルメタデータを削除"""
    try:
        metadata_path = get_metadata_path(file_id)
        if metadata_path.exists():
            metadata_path.unlink()
    except Exception as e:
        logger.error(f"メタデータ削除エラー: {e}", exc_info=True)


def update_progress(
    file_id: str,
    percent: int,
    message: str,
    stage: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """進捗情報をメタデータに書き込む（ワーカー間共有のためファイルに保存）"""
    try:
        percent = max(0, min(100, int(percent)))
    except Exception:
        percent = 0

    metadata = load_file_metadata(file_id) or {}
    metadata.update(
        {
            "status": metadata.get("status", "processing"),
            "progress_percent": percent,
            "progress_message": str(message or ""),
            "progress_stage": str(stage or ""),
            "updated_at": datetime.now().isoformat(),
        }
    )
    if extra:
        metadata.update(extra)
    if "created_at" not in metadata:
        metadata["created_at"] = datetime.now()
    save_file_metadata(file_id, metadata)
