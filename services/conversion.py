#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""設定ファイルのパースとエクスポートを共有するサービス。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from exporters.html import HTMLExporter
from models.cluster import ClusterConfig
from models.config import ConfigModel
from parsers.base import detect_encoding, get_parser_for_content
from parsers.cluster import parse_ha_cluster_from_contents

logger = logging.getLogger(__name__)


class UnsupportedConfigFormat(ValueError):
    """入力設定ファイルの形式を判別できない場合の例外。"""


class UnsupportedOutputFormat(ValueError):
    """未対応の出力形式を要求された場合の例外。"""


class ExportDependencyMissing(RuntimeError):
    """出力に必要な任意依存が利用できない場合の例外。"""


@dataclass(frozen=True)
class InputContent:
    filename: str
    content: str
    encoding: str
    size: int


@dataclass(frozen=True)
class ExportCapabilities:
    html_exporter_cls: Any = HTMLExporter
    pdf_exporter_cls: Any = None
    excel_exporter_cls: Any = None
    pdf_available: bool = False
    excel_available: bool = False


@dataclass(frozen=True)
class ParseResult:
    config: Union[ConfigModel, ClusterConfig]
    parser_errors: List[str]
    is_cluster: bool

    @property
    def summary(self) -> dict:
        return self.config.get_summary()


def load_contents_from_paths(paths: List[Path], filenames: Optional[List[str]] = None) -> List[InputContent]:
    """ファイルを読み込み、文字コードを検出して文字列化する。"""
    contents: List[InputContent] = []
    for index, input_path in enumerate(paths):
        original_filename = filenames[index] if filenames else input_path.name
        file_data = input_path.read_bytes()
        content, detected = detect_encoding(file_data)
        logger.info("検出されたエンコーディング (%s): %s", original_filename, detected)
        contents.append(
            InputContent(
                filename=original_filename,
                content=content,
                encoding=detected,
                size=len(file_data),
            )
        )
    return contents


def parse_contents(contents: List[InputContent], ha_mode: str = "auto") -> ParseResult:
    """単一ファイルまたはHAクラスタとして設定をパースする。"""
    if not contents:
        raise ValueError("入力ファイルがありません")

    if ha_mode == "single" or (ha_mode == "auto" and len(contents) == 1):
        item = contents[0]
        parser = get_parser_for_content(item.content)
        if parser is None:
            raise UnsupportedConfigFormat("設定ファイルの形式を判別できません")

        config = parser.parse_content(item.content, item.filename)
        parser_errors = [str(error) for error in getattr(parser, "errors", [])]
        for error in parser_errors:
            logger.warning("パースエラー: %s", error)
        return ParseResult(config=config, parser_errors=parser_errors, is_cluster=False)

    cluster_input: List[Tuple[str, str]] = [(item.filename, item.content) for item in contents]
    cluster_config = parse_ha_cluster_from_contents(cluster_input)
    if cluster_config.is_cluster:
        logger.info("HAクラスタを検出: グループID=%s", cluster_config.cluster_info.group_id)
    else:
        logger.info("HAクラスタ構成は検出されませんでした。最初のファイルを使用します。")
    return ParseResult(config=cluster_config, parser_errors=[], is_cluster=cluster_config.is_cluster)


def parse_paths(paths: List[Path], ha_mode: str = "auto") -> ParseResult:
    """パスリストから設定をパースする。"""
    return parse_contents(load_contents_from_paths(paths), ha_mode=ha_mode)


def normalize_sections(sections: Optional[List[Any]]) -> Optional[List[str]]:
    """エクスポータに渡せるセクション配列へ正規化する。"""
    if not isinstance(sections, list):
        return None
    return [section for section in sections if isinstance(section, str)]


def extension_for_format(output_format: str) -> str:
    """出力形式に対応する拡張子を返す。"""
    if output_format == "html":
        return ".html"
    if output_format == "pdf":
        return ".pdf"
    if output_format == "excel":
        return ".xlsx"
    raise UnsupportedOutputFormat(f"サポートされていない出力形式です: {output_format}")


def build_output_filename(base_name: str, output_format: str) -> str:
    """出力ファイル名を生成する。"""
    return f"{base_name}_param{extension_for_format(output_format)}"


def export_config(
    config: Union[ConfigModel, ClusterConfig],
    output_format: str,
    output_path: Path,
    capabilities: ExportCapabilities,
    sections: Optional[List[Any]] = None,
) -> None:
    """設定モデルを指定形式でエクスポートする。"""
    normalized_sections = normalize_sections(sections)

    if output_format == "html":
        exporter_cls = capabilities.html_exporter_cls
    elif output_format == "pdf":
        if not capabilities.pdf_available or capabilities.pdf_exporter_cls is None:
            raise ExportDependencyMissing("PDF出力にはweasyprintが必要です")
        exporter_cls = capabilities.pdf_exporter_cls
    elif output_format == "excel":
        if not capabilities.excel_available or capabilities.excel_exporter_cls is None:
            raise ExportDependencyMissing("Excel出力にはopenpyxlが必要です")
        exporter_cls = capabilities.excel_exporter_cls
    else:
        raise UnsupportedOutputFormat(f"サポートされていない出力形式です: {output_format}")

    exporter = (
        exporter_cls(config)
        if normalized_sections is None
        else exporter_cls(config, sections=normalized_sections)
    )
    exporter.export(str(output_path))
