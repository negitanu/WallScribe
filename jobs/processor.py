#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
非同期ジョブ処理（パース & エクスポート & メタデータ/進捗更新）
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from services.conversion import (
    ExportCapabilities,
    ExportDependencyMissing,
    UnsupportedConfigFormat,
    UnsupportedOutputFormat,
    export_config,
    load_contents_from_paths,
    parse_contents,
)

logger = logging.getLogger(__name__)


class JobProcessor:
    def __init__(
        self,
        *,
        update_progress,
        save_file_metadata,
        metrics_available: bool,
        record_file_upload,
        record_processed_file,
        record_error,
        html_exporter_cls,
        pdf_exporter_cls,
        excel_exporter_cls,
        pdf_available: bool,
        excel_available: bool,
    ) -> None:
        self.update_progress = update_progress
        self.save_file_metadata = save_file_metadata

        self.metrics_available = metrics_available
        self.record_file_upload = record_file_upload
        self.record_processed_file = record_processed_file
        self.record_error = record_error

        self.html_exporter_cls = html_exporter_cls
        self.pdf_exporter_cls = pdf_exporter_cls
        self.excel_exporter_cls = excel_exporter_cls
        self.pdf_available = pdf_available
        self.excel_available = excel_available

    def process_job_multi(
        self,
        file_id: str,
        input_paths: List[Path],
        original_filenames: List[str],
        output_format: str,
        sections: Optional[List[str]],
        upload_folder: Path,
        output_path: Path,
        output_filename: str,
        ha_mode: str = "auto",
    ) -> None:
        """非同期でパース＆出力を実行し、進捗を更新する（複数ファイル対応）"""
        import time

        start_time = time.time()
        device_type = "unknown"
        total_size = 0

        try:
            self.update_progress(file_id, 5, "ファイルを受信しました", stage="received")

            for input_path in input_paths:
                total_size += input_path.stat().st_size

            for i, (input_path, original_filename) in enumerate(
                zip(input_paths, original_filenames)
            ):
                self.update_progress(
                    file_id,
                    10 + (i * 5),
                    f"ファイル {i+1}/{len(input_paths)} を処理中...",
                    stage="detect_encoding",
                )
            contents = load_contents_from_paths(input_paths, original_filenames)

            if ha_mode == "single" or (ha_mode == "auto" and len(contents) == 1):
                self.update_progress(
                    file_id, 25, "設定ファイルの形式を判別しています...", stage="detect_parser"
                )
                try:
                    parse_result = parse_contents(contents, ha_mode=ha_mode)
                except UnsupportedConfigFormat:
                    self.update_progress(
                        file_id,
                        100,
                        "設定ファイルの形式を判別できませんでした",
                        stage="error",
                        extra={
                            "status": "error",
                            "error": {
                                "code": "UNSUPPORTED_FORMAT",
                                "message": "設定ファイルの形式を判別できません",
                                "details": "対応形式: .conf (FortiGate), .xml (Palo Alto)",
                            },
                        },
                    )
                    return
                self.update_progress(file_id, 35, "設定ファイルを解析しています...", stage="parsing")
            else:
                self.update_progress(
                    file_id,
                    25,
                    f"HAクラスタ構成を解析中 ({len(contents)} ファイル)...",
                    stage="detect_parser",
                )
                parse_result = parse_contents(contents, ha_mode=ha_mode)

                if parse_result.is_cluster:
                    self.update_progress(
                        file_id, 35, "HAクラスタ構成を解析しています...", stage="parsing"
                    )
                else:
                    self.update_progress(
                        file_id, 35, "設定ファイルを解析しています...", stage="parsing"
                    )

            config = parse_result.config

            self.update_progress(file_id, 70, "出力ファイルを生成しています...", stage="exporting")

            try:
                export_config(
                    config,
                    output_format,
                    output_path,
                    ExportCapabilities(
                        html_exporter_cls=self.html_exporter_cls,
                        pdf_exporter_cls=self.pdf_exporter_cls,
                        excel_exporter_cls=self.excel_exporter_cls,
                        pdf_available=self.pdf_available,
                        excel_available=self.excel_available,
                    ),
                    sections=sections,
                )
            except ExportDependencyMissing as e:
                message = str(e)
                self.update_progress(
                    file_id,
                    100,
                    f"{output_format.upper()}出力に必要な依存関係がありません",
                    stage="error",
                    extra={
                        "status": "error",
                        "error": {
                            "code": "DEPENDENCY_MISSING",
                            "message": message,
                            "details": "pip install -r requirements.txt を実行してください",
                        },
                    },
                )
                return
            except UnsupportedOutputFormat:
                self.update_progress(
                    file_id,
                    100,
                    f"サポートされていない出力形式です: {output_format}",
                    stage="error",
                    extra={
                        "status": "error",
                        "error": {
                            "code": "UNSUPPORTED_FORMAT",
                            "message": f"サポートされていない出力形式です: {output_format}",
                            "details": "対応形式: html, pdf, excel",
                        },
                    },
                )
                return

            self.update_progress(file_id, 95, "メタデータを保存しています...", stage="finalizing")
            summary = config.get_summary()
            device_type = summary.get("device_type", "unknown")
            normalized_path = str(output_path.resolve())
            metadata: Dict[str, object] = {
                "filename": output_filename,
                "path": normalized_path,
                "device_type": device_type,
                "hostname": summary["hostname"],
                "version": summary["version"],
                "summary": summary,
                "is_cluster": summary.get("is_cluster", False),
                "created_at": datetime.now(),
                "status": "done",
                "progress_percent": 100,
                "progress_message": "パラメータシートを生成しました",
                "progress_stage": "done",
            }
            self.save_file_metadata(file_id, metadata)
            logger.info(
                f"生成完了(非同期): {output_filename} (ID: {file_id}, Path: {normalized_path})"
            )

            if self.metrics_available:
                duration = time.time() - start_time
                self.record_file_upload(output_format, device_type, total_size, duration)
                self.record_processed_file(output_format, "success")

        except Exception as e:
            logger.error(f"非同期処理エラー: {e}", exc_info=True)
            is_production = os.environ.get("FLASK_ENV", "production") == "production"
            error_details = "詳細はログを確認してください" if is_production else str(e)
            self.update_progress(
                file_id,
                100,
                "生成中にエラーが発生しました",
                stage="error",
                extra={
                    "status": "error",
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "予期しないエラーが発生しました",
                        "details": error_details,
                    },
                },
            )
            if self.metrics_available:
                self.record_error("INTERNAL_ERROR", "upload_async")
                self.record_processed_file(output_format, "error")
