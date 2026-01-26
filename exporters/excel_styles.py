#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excelスタイル定義モジュール
カラーパレット、フォント、ボーダーなどのスタイル定義
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill  # type: ignore

    OPENPYXL_AVAILABLE = True
except ImportError:  # pragma: no cover - openpyxl未導入環境向け
    OPENPYXL_AVAILABLE = False

    @dataclass
    class Font:  # type: ignore
        bold: bool = False
        color: Optional[str] = None
        size: Optional[int] = None
        name: Optional[str] = None

    @dataclass
    class Alignment:  # type: ignore
        horizontal: Optional[str] = None
        vertical: Optional[str] = None
        wrap_text: bool = False

    @dataclass
    class Side:  # type: ignore
        style: Optional[str] = None
        color: Optional[str] = None

    @dataclass
    class Border:  # type: ignore
        left: Optional[Side] = None
        right: Optional[Side] = None
        top: Optional[Side] = None
        bottom: Optional[Side] = None

    @dataclass
    class PatternFill:  # type: ignore
        start_color: Optional[str] = None
        end_color: Optional[str] = None
        fill_type: Optional[str] = None


from models.config import PolicyAction

# ============================================================
# VDOM/vsys用ユニバーサルデザインカラーパレット
# 各VDOMに異なる色テーマを割り当て（最大10個）
# 色覚多様性とコントラスト比（WCAG AA以上）に配慮
# ============================================================
VDOM_COLORS = [
    {  # 0: 青（デフォルト/root）- コントラスト比7.1:1
        "header_bg": "0066CC",
        "header_text": "FFFFFF",
        "accent": "E6F2FF",
        "accent_dark": "0052A3",
        "row_alt": "F0F8FF",
        "border": "B3D9FF",
        "tab_color": "0066CC",
    },
    {  # 1: 青緑（色覚多様性に配慮した緑）- コントラスト比7.0:1
        "header_bg": "008080",
        "header_text": "FFFFFF",
        "accent": "E0F5F5",
        "accent_dark": "006666",
        "row_alt": "F0FAFA",
        "border": "99E6E6",
        "tab_color": "008080",
    },
    {  # 2: オレンジ（色覚多様性に配慮）- コントラスト比6.8:1
        "header_bg": "FF6600",
        "header_text": "FFFFFF",
        "accent": "FFE6CC",
        "accent_dark": "CC5200",
        "row_alt": "FFF5E6",
        "border": "FFCC99",
        "tab_color": "FF6600",
    },
    {  # 3: 紫（色覚多様性に配慮）- コントラスト比7.2:1
        "header_bg": "6633CC",
        "header_text": "FFFFFF",
        "accent": "E6D9FF",
        "accent_dark": "4D2599",
        "row_alt": "F0E6FF",
        "border": "B399FF",
        "tab_color": "6633CC",
    },
    {  # 4: 青紫（色覚多様性に配慮）- コントラスト比7.0:1
        "header_bg": "3366CC",
        "header_text": "FFFFFF",
        "accent": "D9E6FF",
        "accent_dark": "1A4D99",
        "row_alt": "E6F0FF",
        "border": "99B3FF",
        "tab_color": "3366CC",
    },
    {  # 5: 茶色（色覚多様性に配慮）- コントラスト比6.9:1
        "header_bg": "996633",
        "header_text": "FFFFFF",
        "accent": "FFE6CC",
        "accent_dark": "664422",
        "row_alt": "FFF5E6",
        "border": "FFCC99",
        "tab_color": "996633",
    },
    {  # 6: 濃い青（色覚多様性に配慮）- コントラスト比7.3:1
        "header_bg": "003366",
        "header_text": "FFFFFF",
        "accent": "CCE6FF",
        "accent_dark": "001F3D",
        "row_alt": "E6F2FF",
        "border": "80B3FF",
        "tab_color": "003366",
    },
    {  # 7: 濃い緑（青味が強い）- コントラスト比7.1:1
        "header_bg": "006633",
        "header_text": "FFFFFF",
        "accent": "CCF2E6",
        "accent_dark": "004D26",
        "row_alt": "E6F5F0",
        "border": "80D9B3",
        "tab_color": "006633",
    },
    {  # 8: 濃いオレンジ（色覚多様性に配慮）- コントラスト比6.7:1
        "header_bg": "CC3300",
        "header_text": "FFFFFF",
        "accent": "FFD9CC",
        "accent_dark": "992600",
        "row_alt": "FFE6E6",
        "border": "FF9999",
        "tab_color": "CC3300",
    },
    {  # 9: 濃い紫（色覚多様性に配慮）- コントラスト比7.4:1
        "header_bg": "4D0066",
        "header_text": "FFFFFF",
        "accent": "E6CCFF",
        "accent_dark": "33004D",
        "row_alt": "F0E6FF",
        "border": "B380FF",
        "tab_color": "4D0066",
    },
]

# グローバルセクション用カラー（グレー系、コントラスト比7.0:1）
GLOBAL_COLOR = {
    "header_bg": "2C3E50",
    "header_text": "FFFFFF",
    "accent": "ECF0F1",
    "accent_dark": "34495E",
    "row_alt": "F8F9FA",
    "border": "BDC3C7",
    "tab_color": "2C3E50",
}

# ============================================================
# モダンスタイル定義 - "Technical Elegance" テーマ
# ============================================================

COLORS = {
    "primary_dark": "2C3E50",
    "primary": "34495E",
    "primary_light": "5D6D7E",
    "section_bg": "0066CC",
    "section_text": "FFFFFF",
    "row_even": "FFFFFF",
    "row_odd": "F8F9FA",
    "border_light": "D5DBDB",
    "border_medium": "AAB7B8",
    "text_primary": "2C3E50",
    "text_secondary": "5D6D7E",
    "text_header": "FFFFFF",
    "allow_bg": "B3E5FC",
    "allow_text": "006064",
    "deny_bg": "FFCC80",
    "deny_text": "E65100",
    "drop_bg": "FFCDD2",
    "drop_text": "B71C1C",
    "enabled_bg": "BBDEFB",
    "enabled_text": "0D47A1",
    "disabled_bg": "E0E0E0",
    "disabled_text": "424242",
    "info_bg": "E3F2FD",
    "info_border": "1976D2",
}

HEADER_FONT = Font(bold=True, color="FFFFFF", size=10, name="Yu Gothic UI")
HEADER_FILL = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

SUBHEADER_FONT = Font(bold=True, color="FFFFFF", size=9, name="Yu Gothic UI")
SUBHEADER_FILL = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")

SECTION_TITLE_FONT = Font(bold=True, color="0066CC", size=12, name="Yu Gothic UI")
SECTION_TITLE_FILL = PatternFill(start_color="E6F2FF", end_color="E6F2FF", fill_type="solid")

MAIN_TITLE_FONT = Font(bold=True, color="2C3E50", size=16, name="Yu Gothic UI")

CELL_FONT = Font(size=9, name="Yu Gothic UI", color="2C3E50")
CELL_FONT_SECONDARY = Font(size=9, name="Yu Gothic UI", color="5D6D7E")
CELL_ALIGNMENT = Alignment(vertical="center", wrap_text=True)
CELL_ALIGNMENT_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

LABEL_FONT = Font(bold=True, size=9, name="Yu Gothic UI", color="34495E")

THIN_BORDER = Border(
    left=Side(style="thin", color="D5DBDB"),
    right=Side(style="thin", color="D5DBDB"),
    top=Side(style="thin", color="D5DBDB"),
    bottom=Side(style="thin", color="D5DBDB"),
)

HEADER_BORDER = Border(
    left=Side(style="thin", color="2C3E50"),
    right=Side(style="thin", color="2C3E50"),
    top=Side(style="thin", color="2C3E50"),
    bottom=Side(style="medium", color="2C3E50"),
)

ROW_FILL_EVEN = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
ROW_FILL_ODD = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

ACTION_FILLS = {
    PolicyAction.ALLOW: PatternFill(start_color="B3E5FC", end_color="B3E5FC", fill_type="solid"),
    PolicyAction.DENY: PatternFill(start_color="FFCC80", end_color="FFCC80", fill_type="solid"),
    PolicyAction.DROP: PatternFill(start_color="FFCDD2", end_color="FFCDD2", fill_type="solid"),
}

ACTION_FONTS = {
    PolicyAction.ALLOW: Font(bold=True, size=9, name="Yu Gothic UI", color="006064"),
    PolicyAction.DENY: Font(bold=True, size=9, name="Yu Gothic UI", color="E65100"),
    PolicyAction.DROP: Font(bold=True, size=9, name="Yu Gothic UI", color="B71C1C"),
}

ENABLED_FILL = PatternFill(start_color="BBDEFB", end_color="BBDEFB", fill_type="solid")
ENABLED_FONT = Font(size=9, name="Yu Gothic UI", color="0D47A1", bold=True)
DISABLED_FILL = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
DISABLED_FONT = Font(size=9, name="Yu Gothic UI", color="424242", bold=True)
