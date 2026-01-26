#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
エクスポーター共通ユーティリティ
"""

import csv
import html
import logging
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 静的ファイルのベースパス
STATIC_DIR = Path(__file__).parent.parent / "static"


class CacheManager:
    """キャッシュ管理（スレッドセーフなシングルトン）"""

    _instance: Optional["CacheManager"] = None
    _lock: Lock = Lock()
    _caches: Dict[str, Any]

    def __new__(cls) -> "CacheManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._caches = {}
        return cls._instance

    def get(self, key: str) -> Optional[Any]:
        """キャッシュを取得"""
        return self._caches.get(key)

    def set(self, key: str, value: Any) -> None:
        """キャッシュを設定"""
        self._caches[key] = value

    def clear(self, key: Optional[str] = None) -> None:
        """キャッシュをクリア（テスト用）"""
        if key is None:
            self._caches.clear()
        elif key in self._caches:
            del self._caches[key]

    @classmethod
    def reset_instance(cls) -> None:
        """インスタンスをリセット（テスト用）"""
        with cls._lock:
            cls._instance = None


def load_isdb() -> Dict[str, str]:
    """ISDBのCSVを読み込み、ID→アプリケーション名のマッピングを返す

    appid.csvファイルを使用して、app_id→app_nameのマッピングを返す
    """
    cache = CacheManager()
    cached = cache.get("isdb")
    if cached is not None:
        return cached

    isdb_data: Dict[str, str] = {}
    isdb_path = STATIC_DIR / "data" / "appid.csv"

    try:
        with open(isdb_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                isdb_id = row.get("app_id", "")
                app_name = row.get("app_name", "")
                if isdb_id and app_name:
                    isdb_data[isdb_id] = app_name
        logger.debug(f"ISDBをキャッシュに読み込みました: {len(isdb_data)}件")
    except FileNotFoundError:
        logger.warning(f"ISDBファイルが見つかりません: {isdb_path}")
    except csv.Error as e:
        logger.warning(f"ISDB CSV解析エラー: {e}")

    cache.set("isdb", isdb_data)
    return isdb_data


def load_css() -> str:
    """CSSを読み込み（Bootstrap + カスタムCSS）"""
    cache = CacheManager()
    cached = cache.get("css")
    if cached is not None:
        return cached

    css_parts = []

    # Bootstrap CSS
    bootstrap_path = STATIC_DIR / "css" / "bootstrap.min.css"
    try:
        css_parts.append(bootstrap_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning(f"Bootstrap CSSファイルが見つかりません: {bootstrap_path}")

    # カスタムCSS
    css_path = STATIC_DIR / "css" / "parameter_sheet.css"
    try:
        css_parts.append(css_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning(f"CSSファイルが見つかりません: {css_path}")
        css_parts.append(_get_fallback_css())

    css_content = "\n".join(css_parts)
    cache.set("css", css_content)
    logger.debug("CSSをキャッシュに読み込みました")
    return css_content


def load_css_for_pdf() -> str:
    """PDF用の軽量CSSを読み込み（Bootstrap除外、必要最小限のスタイルのみ）

    PDF生成では大きなBootstrap CSSを読み込む必要がなく、
    pdf.cssに必要なスタイルがすべて含まれています。
    これにより、WeasyPrintのCSS解析時間を大幅に削減します。
    """
    cache = CacheManager()
    cached = cache.get("css_for_pdf")
    if cached is not None:
        return cached

    css_parts = []

    # PDF用の最小限Bootstrapサブセット（テーブルとグリッドのみ）
    css_parts.append(_get_minimal_bootstrap_for_pdf())

    # カスタムCSS（parameter_sheet.cssのPDF互換部分）
    css_path = STATIC_DIR / "css" / "parameter_sheet.css"
    try:
        css_parts.append(css_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning(f"CSSファイルが見つかりません: {css_path}")

    css_content = "\n".join(css_parts)
    cache.set("css_for_pdf", css_content)
    logger.debug("PDF用CSSをキャッシュに読み込みました")
    return css_content


def _get_minimal_bootstrap_for_pdf() -> str:
    """PDF用の最小限Bootstrapスタイル

    フルBootstrap (232KB) の代わりに、実際に使用するクラスのみを含む
    軽量版 (~5KB) を返します。
    """
    return """
/* Minimal Bootstrap for PDF - Essential styles only */

/* Base resets */
*, *::before, *::after { box-sizing: border-box; }

/* Container */
.container { width: 100%; padding-right: 15px; padding-left: 15px; margin-right: auto; margin-left: auto; }

/* Tables */
.table { width: 100%; margin-bottom: 1rem; color: #212529; border-collapse: collapse; }
.table th, .table td { padding: 0.5rem; vertical-align: top; border-top: 1px solid #dee2e6; }
.table thead th { vertical-align: bottom; border-bottom: 2px solid #dee2e6; }
.table tbody + tbody { border-top: 2px solid #dee2e6; }
.table-sm th, .table-sm td { padding: 0.25rem; }
.table-bordered { border: 1px solid #dee2e6; }
.table-bordered th, .table-bordered td { border: 1px solid #dee2e6; }
.table-bordered thead th, .table-bordered thead td { border-bottom-width: 2px; }
.table-striped tbody tr:nth-of-type(odd) { background-color: rgba(0, 0, 0, 0.02); }
.table-hover tbody tr:hover { background-color: rgba(0, 0, 0, 0.04); }
.table-responsive { display: block; width: 100%; overflow-x: auto; }

/* Badges */
.badge { display: inline-block; padding: 0.25em 0.5em; font-size: 75%; font-weight: 700; line-height: 1; text-align: center; white-space: nowrap; vertical-align: baseline; border-radius: 0.25rem; }
.badge-primary { color: #fff; background-color: #007bff; }
.badge-secondary { color: #fff; background-color: #6c757d; }
.badge-success { color: #fff; background-color: #28a745; }
.badge-danger { color: #fff; background-color: #dc3545; }
.badge-warning { color: #212529; background-color: #ffc107; }
.badge-info { color: #fff; background-color: #17a2b8; }
.badge-light { color: #212529; background-color: #f8f9fa; }
.badge-dark { color: #fff; background-color: #343a40; }

/* Buttons (minimal) */
.btn { display: inline-block; font-weight: 400; text-align: center; white-space: nowrap; vertical-align: middle; border: 1px solid transparent; padding: 0.25rem 0.5rem; font-size: 0.875rem; line-height: 1.5; border-radius: 0.25rem; }
.btn-sm { padding: 0.15rem 0.4rem; font-size: 0.75rem; }
.btn-outline-primary { color: #007bff; border-color: #007bff; background-color: transparent; }
.btn-outline-secondary { color: #6c757d; border-color: #6c757d; background-color: transparent; }
.btn-outline-success { color: #28a745; border-color: #28a745; background-color: transparent; }
.btn-outline-danger { color: #dc3545; border-color: #dc3545; background-color: transparent; }
.btn-outline-warning { color: #856404; border-color: #ffc107; background-color: transparent; }
.btn-outline-info { color: #17a2b8; border-color: #17a2b8; background-color: transparent; }
.btn.disabled { opacity: 0.65; pointer-events: none; }

/* Alerts */
.alert { position: relative; padding: 0.75rem 1.25rem; margin-bottom: 1rem; border: 1px solid transparent; border-radius: 0.25rem; }
.alert-warning { color: #856404; background-color: #fff3cd; border-color: #ffeeba; }
.alert-info { color: #0c5460; background-color: #d1ecf1; border-color: #bee5eb; }

/* Utilities */
.text-muted { color: #6c757d !important; }
.text-center { text-align: center !important; }
.mb-1 { margin-bottom: 0.25rem !important; }
.mb-2 { margin-bottom: 0.5rem !important; }
.mb-3 { margin-bottom: 1rem !important; }
.me-1 { margin-right: 0.25rem !important; }
.me-2 { margin-right: 0.5rem !important; }

/* Code */
code { font-size: 87.5%; color: #e83e8c; word-wrap: break-word; }
"""


def load_search_js() -> str:
    """検索機能のJavaScriptを読み込み"""
    cache = CacheManager()
    cached = cache.get("search_js")
    if cached is not None:
        return cached

    js_path = STATIC_DIR / "js" / "search.js"
    try:
        js_content = js_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(f"検索JSファイルが見つかりません: {js_path}")
        js_content = "// Search functionality not available"

    cache.set("search_js", js_content)
    logger.debug("検索JSをキャッシュに読み込みました")
    return js_content


def load_tooltip_js() -> str:
    """ツールチップ機能のJavaScriptを読み込み"""
    cache = CacheManager()
    cached = cache.get("tooltip_js")
    if cached is not None:
        return cached

    js_path = STATIC_DIR / "js" / "tooltip.js"
    try:
        js_content = js_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(f"ツールチップJSファイルが見つかりません: {js_path}")
        js_content = "// Tooltip functionality not available"

    cache.set("tooltip_js", js_content)
    logger.debug("ツールチップJSをキャッシュに読み込みました")
    return js_content


def _get_fallback_css() -> str:
    """フォールバック用の最小限CSS"""
    return """
    body { font-family: sans-serif; margin: 20px; }
    table { width: 100%; border-collapse: collapse; margin: 15px 0; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f8f9fa; }
    h1, h2, h3 { color: #1a5276; }
    section { margin-bottom: 25px; padding: 15px; background: white; border-radius: 8px; }
    """


class HtmlFormatter:
    """HTML生成用フォーマッター"""

    @staticmethod
    def escape(text: Optional[Any]) -> str:
        """HTMLエスケープ"""
        if text is None:
            return ""
        return html.escape(str(text))

    @staticmethod
    def list_to_str(items: List[Any], separator: str = ", ") -> str:
        """リストを文字列に変換"""
        if not items:
            return ""
        return separator.join(str(item) for item in items)

    @classmethod
    def list_to_lines(cls, items: List[Any]) -> str:
        """リストを改行区切りで表示"""
        if not items:
            return ""
        return "<br>".join(cls.escape(str(item)) for item in items)

    @classmethod
    def with_default(cls, value: Optional[str], default: str) -> str:
        """値が空の場合はデフォルト値を表示（グレー表示）"""
        if value:
            return cls.escape(value)
        return f'<span class="text-muted">{cls.escape(default)}</span>'

    @classmethod
    def list_with_default(cls, items: List[Any], default: str) -> str:
        """リストが空の場合はデフォルト値を表示"""
        if items:
            return cls.escape(cls.list_to_str(items))
        return f'<span class="text-muted">{cls.escape(default)}</span>'

    @classmethod
    def to_badges(
        cls, items: List[str], color_map: Dict[str, str], extract_key: bool = False
    ) -> str:
        """リストをBootstrapバッジに変換"""
        if not items:
            return "-"

        badges = [
            f'<span class="badge badge-outline badge-outline-{color_map.get(key, "secondary")}">{cls.escape(item)}</span>'
            for item in items
            for key in [item.lower().split(":")[0] if extract_key and ":" in item else item.lower()]
        ]
        return " ".join(badges)
