#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基底パーサークラス
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple
import logging

from models.config import ConfigModel, DeviceType

logger = logging.getLogger(__name__)


def detect_encoding(data: bytes) -> Tuple[str, str]:
    """バイトデータのエンコーディングを検出

    Args:
        data: バイトデータ

    Returns:
        Tuple[str, str]: (デコードされた文字列, 使用したエンコーディング名)

    Raises:
        UnicodeDecodeError: すべてのエンコーディングで失敗した場合
    """
    # 試行するエンコーディングの順序
    encodings = ['utf-8', 'utf-8-sig', 'cp932', 'latin-1']

    for encoding in encodings:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    # すべて失敗した場合（latin-1は通常失敗しないが念のため）
    raise UnicodeDecodeError(
        'all', data, 0, len(data),
        f'すべてのエンコーディング({", ".join(encodings)})でデコードに失敗しました'
    )


class BaseConfigParser(ABC):
    """設定パーサーの基底クラス"""

    def __init__(self):
        self.config_model = ConfigModel()
        self.errors: list = []

    @abstractmethod
    def parse(self, file_path: str) -> ConfigModel:
        """設定ファイルをパースする

        Args:
            file_path: 設定ファイルのパス

        Returns:
            ConfigModel: パース結果
        """
        pass

    @abstractmethod
    def parse_content(self, content: str, filename: str = "") -> ConfigModel:
        """設定ファイルの内容をパースする

        Args:
            content: 設定ファイルの内容
            filename: ファイル名（オプション）

        Returns:
            ConfigModel: パース結果
        """
        pass

    @staticmethod
    @abstractmethod
    def detect_file_type(file_path: str) -> bool:
        """ファイル形式を判定する

        Args:
            file_path: ファイルパス

        Returns:
            bool: 対応ファイルならTrue
        """
        pass

    @staticmethod
    @abstractmethod
    def detect_content_type(content: str) -> bool:
        """ファイル内容から形式を判定する

        Args:
            content: ファイル内容

        Returns:
            bool: 対応形式ならTrue
        """
        pass

    def read_file(self, file_path: str) -> Optional[str]:
        """ファイルを読み込む

        Args:
            file_path: ファイルパス

        Returns:
            Optional[str]: ファイル内容、失敗時はNone
        """
        try:
            path = Path(file_path)
            if not path.exists():
                self.errors.append(f"ファイルが存在しません: {file_path}")
                return None

            # UTF-8で試行
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except UnicodeDecodeError:
                pass

            # UTF-8-BOMで試行
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    return f.read()
            except UnicodeDecodeError:
                pass

            # CP932（Shift-JIS）で試行
            try:
                with open(file_path, 'r', encoding='cp932') as f:
                    return f.read()
            except UnicodeDecodeError:
                pass

            # Latin-1で試行（最終手段）
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()

        except Exception as e:
            self.errors.append(f"ファイル読み込みエラー: {e}")
            logger.error(f"ファイル読み込みエラー: {e}")
            return None

    def add_error(self, message: str):
        """エラーを追加"""
        self.errors.append(message)
        logger.warning(message)


def get_parser_for_file(file_path: str) -> Optional[BaseConfigParser]:
    """ファイルに対応するパーサーを取得

    Args:
        file_path: ファイルパス

    Returns:
        Optional[BaseConfigParser]: 対応するパーサー、見つからない場合はNone
    """
    from .fortigate import FortiGateParser
    from .paloalto import PaloAltoParser

    parsers = [FortiGateParser, PaloAltoParser]

    for parser_class in parsers:
        if parser_class.detect_file_type(file_path):
            return parser_class()

    return None


def get_parser_for_content(content: str) -> Optional[BaseConfigParser]:
    """ファイル内容に対応するパーサーを取得

    Args:
        content: ファイル内容

    Returns:
        Optional[BaseConfigParser]: 対応するパーサー、見つからない場合はNone
    """
    from .fortigate import FortiGateParser
    from .paloalto import PaloAltoParser

    parsers = [FortiGateParser, PaloAltoParser]

    for parser_class in parsers:
        if parser_class.detect_content_type(content):
            return parser_class()

    return None
