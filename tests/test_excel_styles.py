#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excelスタイル定義のテスト
"""

import pytest

from exporters.excel_styles import (
    ACTION_FILLS,
    ACTION_FONTS,
    COLORS,
    GLOBAL_COLOR,
    HEADER_FILL,
    HEADER_FONT,
    VDOM_COLORS,
)
from models.config import PolicyAction


class TestExcelStyles:
    """Excelスタイル定義のテスト"""

    def test_vdom_colors_count(self):
        """VDOMカラーパレットの数"""
        assert len(VDOM_COLORS) == 10

    def test_vdom_colors_structure(self):
        """VDOMカラーパレットの構造"""
        for color in VDOM_COLORS:
            assert "header_bg" in color
            assert "header_text" in color
            assert "accent" in color
            assert "tab_color" in color

    def test_global_color_structure(self):
        """グローバルカラーの構造"""
        assert "header_bg" in GLOBAL_COLOR
        assert "header_text" in GLOBAL_COLOR
        assert "tab_color" in GLOBAL_COLOR

    def test_colors_structure(self):
        """カラーパレットの構造"""
        assert "primary_dark" in COLORS
        assert "section_bg" in COLORS
        assert "allow_bg" in COLORS
        assert "deny_bg" in COLORS
        assert "drop_bg" in COLORS

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
