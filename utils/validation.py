#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
バリデーション機能
"""

from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def validate_file_content(file_data: bytes, filename: str) -> Tuple[bool, Optional[str]]:
    """ファイル内容の検証
    
    Args:
        file_data: ファイルのバイトデータ
        filename: ファイル名
    
    Returns:
        Tuple[bool, Optional[str]]: (有効かどうか, エラーメッセージ)
    """
    ext = Path(filename).suffix.lower()
    
    if ext == '.conf':
        # FortiGate設定ファイルの検証
        try:
            # 先頭500バイトを読み込んで検証
            content_start = file_data[:500].decode('utf-8', errors='ignore')
            # FortiGate設定ファイルの特徴的な文字列を確認
            if '#config-version=' in content_start or 'config system global' in content_start:
                logger.debug(f"FortiGate設定ファイルとして検証成功: {filename}")
                return True, None
            return False, "FortiGate設定ファイルの形式が正しくありません"
        except Exception as e:
            logger.warning(f"ファイル内容の検証に失敗: {filename}, {e}")
            return False, f"ファイル内容の検証に失敗しました: {e}"
    
    elif ext == '.xml':
        # Palo Alto設定ファイルの検証
        try:
            # defusedxmlを使用して安全にXMLを検証
            try:
                from defusedxml.ElementTree import fromstring as safe_fromstring
                # 先頭2KBのみ検証（パフォーマンス考慮）
                safe_fromstring(file_data[:2000])
                logger.debug(f"Palo Alto設定ファイルとして検証成功: {filename}")
                return True, None
            except ImportError:
                # defusedxmlが利用できない場合は標準ライブラリを使用
                import xml.etree.ElementTree as ET
                ET.fromstring(file_data[:2000])
                logger.debug(f"Palo Alto設定ファイルとして検証成功（標準ライブラリ）: {filename}")
                return True, None
        except Exception as e:
            logger.warning(f"XML形式の検証に失敗: {filename}, {e}")
            return False, f"XML形式が正しくありません: {e}"
    
    return False, "サポートされていないファイル形式です"


def validate_file_size(file_data: bytes, max_size: int) -> Tuple[bool, Optional[str]]:
    """ファイルサイズの検証
    
    Args:
        file_data: ファイルのバイトデータ
        max_size: 最大サイズ（バイト）
    
    Returns:
        Tuple[bool, Optional[str]]: (有効かどうか, エラーメッセージ)
    """
    file_size = len(file_data)
    if file_size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        file_size_mb = file_size / (1024 * 1024)
        return False, f"ファイルサイズが{max_size_mb:.1f}MBを超えています（現在: {file_size_mb:.1f}MB）"
    return True, None


def validate_output_format(output_format: str) -> Tuple[bool, Optional[str]]:
    """出力形式の検証
    
    Args:
        output_format: 出力形式
    
    Returns:
        Tuple[bool, Optional[str]]: (有効かどうか, エラーメッセージ)
    """
    valid_formats = ['html', 'pdf', 'excel']
    if output_format not in valid_formats:
        return False, f"無効な出力形式: {output_format}（対応形式: {', '.join(valid_formats)}）"
    return True, None


def validate_ha_mode(ha_mode: str) -> Tuple[bool, Optional[str]]:
    """HAモードの検証
    
    Args:
        ha_mode: HAモード
    
    Returns:
        Tuple[bool, Optional[str]]: (有効かどうか, エラーメッセージ)
    """
    valid_modes = ['auto', 'single', 'cluster']
    if ha_mode not in valid_modes:
        return False, f"無効なHAモード: {ha_mode}（対応モード: {', '.join(valid_modes)}）"
    return True, None
