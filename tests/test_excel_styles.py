#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excelスタイル定義のテスト
"""

import pytest
import sys
from pathlib import Path

# スタイル定義を直接インポート（excel.pyを経由しない）
sys.path.insert(0, str(Path(__file__).parent.parent / 'exporters' / 'excel'))

try:
    from styles import (
        VDOM_COLORS,
        GLOBAL_COLOR,
        COLORS,
        HEADER_FONT,
        HEADER_FILL,
        ACTION_FILLS,
        ACTION_FONTS,
    )
    from models.config import PolicyAction
except ImportError:
    # フォールバック: 直接インポート
    import importlib.util
    styles_path = Path(__file__).parent.parent / 'exporters' / 'excel' / 'styles.py'
    spec = importlib.util.spec_from_file_location("styles", styles_path)
    styles = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(styles)
    
    VDOM_COLORS = styles.VDOM_COLORS
    GLOBAL_COLOR = styles.GLOBAL_COLOR
    COLORS = styles.COLORS
    HEADER_FONT = styles.HEADER_FONT
    HEADER_FILL = styles.HEADER_FILL
    ACTION_FILLS = styles.ACTION_FILLS
    ACTION_FONTS = styles.ACTION_FONTS
    
    from models.config import PolicyAction


class TestExcelStyles:
    """Excelスタイル定義のテスト"""

    def test_vdom_colors_count(self):
        """VDOMカラーパレットの数"""
        assert len(VDOM_COLORS) == 10

    def test_vdom_colors_structure(self):
        """VDOMカラーパレットの構造"""
        for color in VDOM_COLORS:
            assert 'header_bg' in color
            assert 'header_text' in color
            assert 'accent' in color
            assert 'tab_color' in color

    def test_global_color_structure(self):
        """グローバルカラーの構造"""
        assert 'header_bg' in GLOBAL_COLOR
        assert 'header_text' in GLOBAL_COLOR
        assert 'tab_color' in GLOBAL_COLOR

    def test_colors_structure(self):
        """カラーパレットの構造"""
        assert 'primary_dark' in COLORS
        assert 'section_bg' in COLORS
        assert 'allow_bg' in COLORS
        assert 'deny_bg' in COLORS
        assert 'drop_bg' in COLORS

    def test_header_font(self):
        """ヘッダーフォント"""
        assert HEADER_FONT.bold is True
        assert HEADER_FONT.color == "FFFFFF"
        assert HEADER_FONT.size == 10

    def test_header_fill(self):
        """ヘッダーフィル"""
        assert HEADER_FILL.start_color == "2C3E50"
        assert HEADER_FILL.fill_type == "solid"

    def test_action_fills(self):
        """アクションフィル"""
        assert PolicyAction.ALLOW in ACTION_FILLS
        assert PolicyAction.DENY in ACTION_FILLS
        assert PolicyAction.DROP in ACTION_FILLS

    def test_action_fonts(self):
        """アクションフォント"""
        assert PolicyAction.ALLOW in ACTION_FONTS
        assert PolicyAction.DENY in ACTION_FONTS
        assert PolicyAction.DROP in ACTION_FONTS
