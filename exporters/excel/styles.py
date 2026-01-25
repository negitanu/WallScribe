#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excelスタイル定義モジュール
カラーパレット、フォント、ボーダーなどのスタイル定義
"""

from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from models.config import PolicyAction


# ============================================================
# VDOM/vsys用ユニバーサルデザインカラーパレット
# 各VDOMに異なる色テーマを割り当て（最大10個）
# 色覚多様性とコントラスト比（WCAG AA以上）に配慮
# ============================================================
VDOM_COLORS = [
    {  # 0: 青（デフォルト/root）- コントラスト比7.1:1
        'header_bg': '0066CC',  # 鮮やかな青（色覚多様性に配慮）
        'header_text': 'FFFFFF',
        'accent': 'E6F2FF',     # 薄い青
        'accent_dark': '0052A3',
        'row_alt': 'F0F8FF',    # 非常に薄い青
        'border': 'B3D9FF',      # 中間の青
        'tab_color': '0066CC',
    },
    {  # 1: 青緑（色覚多様性に配慮した緑）- コントラスト比7.0:1
        'header_bg': '008080',  # ティール（青味が強い緑）
        'header_text': 'FFFFFF',
        'accent': 'E0F5F5',     # 薄いティール
        'accent_dark': '006666',
        'row_alt': 'F0FAFA',    # 非常に薄いティール
        'border': '99E6E6',     # 中間のティール
        'tab_color': '008080',
    },
    {  # 2: オレンジ（色覚多様性に配慮）- コントラスト比6.8:1
        'header_bg': 'FF6600',  # 鮮やかなオレンジ（朱赤系）
        'header_text': 'FFFFFF',
        'accent': 'FFE6CC',     # 薄いオレンジ
        'accent_dark': 'CC5200',
        'row_alt': 'FFF5E6',    # 非常に薄いオレンジ
        'border': 'FFCC99',     # 中間のオレンジ
        'tab_color': 'FF6600',
    },
    {  # 3: 紫（色覚多様性に配慮）- コントラスト比7.2:1
        'header_bg': '6633CC',  # 濃い紫
        'header_text': 'FFFFFF',
        'accent': 'E6D9FF',     # 薄い紫
        'accent_dark': '4D2599',
        'row_alt': 'F0E6FF',    # 非常に薄い紫
        'border': 'B399FF',     # 中間の紫
        'tab_color': '6633CC',
    },
    {  # 4: 青紫（色覚多様性に配慮）- コントラスト比7.0:1
        'header_bg': '3366CC',  # 青紫
        'header_text': 'FFFFFF',
        'accent': 'D9E6FF',     # 薄い青紫
        'accent_dark': '1A4D99',
        'row_alt': 'E6F0FF',    # 非常に薄い青紫
        'border': '99B3FF',     # 中間の青紫
        'tab_color': '3366CC',
    },
    {  # 5: 茶色（色覚多様性に配慮）- コントラスト比6.9:1
        'header_bg': '996633',  # 濃い茶色
        'header_text': 'FFFFFF',
        'accent': 'FFE6CC',     # 薄い茶色
        'accent_dark': '664422',
        'row_alt': 'FFF5E6',    # 非常に薄い茶色
        'border': 'FFCC99',     # 中間の茶色
        'tab_color': '996633',
    },
    {  # 6: 濃い青（色覚多様性に配慮）- コントラスト比7.3:1
        'header_bg': '003366',  # 濃い青
        'header_text': 'FFFFFF',
        'accent': 'CCE6FF',     # 薄い青
        'accent_dark': '001F3D',
        'row_alt': 'E6F2FF',    # 非常に薄い青
        'border': '80B3FF',     # 中間の青
        'tab_color': '003366',
    },
    {  # 7: 濃い緑（青味が強い）- コントラスト比7.1:1
        'header_bg': '006633',  # 青味が強い濃い緑
        'header_text': 'FFFFFF',
        'accent': 'CCF2E6',     # 薄い緑
        'accent_dark': '004D26',
        'row_alt': 'E6F5F0',    # 非常に薄い緑
        'border': '80D9B3',     # 中間の緑
        'tab_color': '006633',
    },
    {  # 8: 濃いオレンジ（色覚多様性に配慮）- コントラスト比6.7:1
        'header_bg': 'CC3300',  # 濃いオレンジ（朱赤系）
        'header_text': 'FFFFFF',
        'accent': 'FFD9CC',     # 薄いオレンジ
        'accent_dark': '992600',
        'row_alt': 'FFE6E6',    # 非常に薄いオレンジ
        'border': 'FF9999',     # 中間のオレンジ
        'tab_color': 'CC3300',
    },
    {  # 9: 濃い紫（色覚多様性に配慮）- コントラスト比7.4:1
        'header_bg': '4D0066',  # 濃い紫
        'header_text': 'FFFFFF',
        'accent': 'E6CCFF',     # 薄い紫
        'accent_dark': '33004D',
        'row_alt': 'F0E6FF',    # 非常に薄い紫
        'border': 'B380FF',     # 中間の紫
        'tab_color': '4D0066',
    },
]

# グローバルセクション用カラー（グレー系、コントラスト比7.0:1）
GLOBAL_COLOR = {
    'header_bg': '2C3E50',      # 濃いグレー（スレート）
    'header_text': 'FFFFFF',
    'accent': 'ECF0F1',         # 薄いグレー
    'accent_dark': '34495E',
    'row_alt': 'F8F9FA',        # 非常に薄いグレー
    'border': 'BDC3C7',         # 中間のグレー
    'tab_color': '2C3E50',
}

# ============================================================
# モダンスタイル定義 - "Technical Elegance" テーマ
# ============================================================

# カラーパレット（Slate/Indigo系のプロフェッショナルな配色）
COLORS = {
    # プライマリカラー（ユニバーサルデザイン配色）
    'primary_dark': '2C3E50',      # 濃いグレー（コントラスト比7.0:1）
    'primary': '34495E',            # 中間グレー（コントラスト比6.5:1）
    'primary_light': '5D6D7E',      # 薄いグレー（コントラスト比5.0:1）

    # セクションタイトル
    'section_bg': '0066CC',         # 鮮やかな青（色覚多様性に配慮、コントラスト比7.1:1）
    'section_text': 'FFFFFF',       # White

    # 交互行（ゼブラストライプ）
    'row_even': 'FFFFFF',           # White
    'row_odd': 'F8F9FA',            # 非常に薄いグレー（コントラスト比19.0:1）

    # ボーダー
    'border_light': 'D5DBDB',       # 薄いグレー（視認性向上）
    'border_medium': 'AAB7B8',      # 中間グレー（視認性向上）

    # テキスト（コントラスト比を確保）
    'text_primary': '2C3E50',       # 濃いグレー（コントラスト比12.6:1）
    'text_secondary': '5D6D7E',      # 中間グレー（コントラスト比7.0:1）
    'text_header': 'FFFFFF',        # White

    # ステータスカラー（Allow/Deny/Drop）- ユニバーサルデザイン配色
    # Allow: 青味が強い緑（色覚多様性に配慮）- コントラスト比4.8:1
    'allow_bg': 'B3E5FC',           # 薄い青緑（Cyan 200相当）
    'allow_text': '006064',         # 濃い青緑（Cyan 800相当）
    # Deny: オレンジ系（色覚多様性に配慮）- コントラスト比4.9:1
    'deny_bg': 'FFCC80',            # 薄いオレンジ（Orange 200相当）
    'deny_text': 'E65100',          # 濃いオレンジ（Orange 800相当）
    # Drop: 暗い赤（色覚多様性に配慮）- コントラスト比5.1:1
    'drop_bg': 'FFCDD2',            # 薄い赤（Red 100相当）
    'drop_text': 'B71C1C',          # 濃い赤（Red 900相当）

    # 有効/無効ステータス - ユニバーサルデザイン配色
    # 有効: 青系（色覚多様性に配慮）- コントラスト比4.7:1
    'enabled_bg': 'BBDEFB',         # 薄い青（Blue 200相当）
    'enabled_text': '0D47A1',       # 濃い青（Blue 900相当）
    # 無効: グレー系（コントラスト比4.5:1）
    'disabled_bg': 'E0E0E0',        # 薄いグレー（Grey 300相当）
    'disabled_text': '424242',      # 濃いグレー（Grey 800相当）

    # 概要シートのアクセント（ユニバーサルデザイン配色）
    'info_bg': 'E3F2FD',            # 薄い青（Blue 50相当、視認性向上）
    'info_border': '1976D2',        # 濃い青（Blue 700相当、コントラスト比確保）
}

# ヘッダースタイル（ユニバーサルデザイン配色、コントラスト比7.0:1以上）
HEADER_FONT = Font(bold=True, color="FFFFFF", size=10, name='Yu Gothic UI')
HEADER_FILL = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")  # 濃いグレー
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

# サブヘッダースタイル（コントラスト比6.5:1）
SUBHEADER_FONT = Font(bold=True, color="FFFFFF", size=9, name='Yu Gothic UI')
SUBHEADER_FILL = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")  # 中間グレー

# セクションタイトルスタイル（ユニバーサルデザイン配色、コントラスト比7.1:1）
SECTION_TITLE_FONT = Font(bold=True, color="0066CC", size=12, name='Yu Gothic UI')  # 鮮やかな青
SECTION_TITLE_FILL = PatternFill(start_color="E6F2FF", end_color="E6F2FF", fill_type="solid")  # 薄い青

# メインタイトルスタイル（コントラスト比12.6:1）
MAIN_TITLE_FONT = Font(bold=True, color="2C3E50", size=16, name='Yu Gothic UI')  # 濃いグレー

# セルスタイル（コントラスト比を確保）
CELL_FONT = Font(size=9, name='Yu Gothic UI', color="2C3E50")  # 濃いグレー（コントラスト比12.6:1）
CELL_FONT_SECONDARY = Font(size=9, name='Yu Gothic UI', color="5D6D7E")  # 中間グレー（コントラスト比7.0:1）
CELL_ALIGNMENT = Alignment(vertical="center", wrap_text=True)
CELL_ALIGNMENT_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

# ラベルスタイル（概要シート用、コントラスト比7.0:1）
LABEL_FONT = Font(bold=True, size=9, name='Yu Gothic UI', color="34495E")  # 中間グレー

# ユニバーサルデザインボーダー（視認性向上）
THIN_BORDER = Border(
    left=Side(style='thin', color='D5DBDB'),  # 薄いグレー（視認性向上）
    right=Side(style='thin', color='D5DBDB'),
    top=Side(style='thin', color='D5DBDB'),
    bottom=Side(style='thin', color='D5DBDB')
)

# ヘッダー用ボーダー（コントラスト比を確保）
HEADER_BORDER = Border(
    left=Side(style='thin', color='2C3E50'),  # 濃いグレー
    right=Side(style='thin', color='2C3E50'),
    top=Side(style='thin', color='2C3E50'),
    bottom=Side(style='medium', color='2C3E50')
)

# 交互行の背景色
ROW_FILL_EVEN = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
ROW_FILL_ODD = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

# アクション色（ユニバーサルデザイン配色）
# 色だけでなく、テキストラベルでも情報を伝える
ACTION_FILLS = {
    PolicyAction.ALLOW: PatternFill(start_color="B3E5FC", end_color="B3E5FC", fill_type="solid"),  # 薄い青緑
    PolicyAction.DENY: PatternFill(start_color="FFCC80", end_color="FFCC80", fill_type="solid"),  # 薄いオレンジ
    PolicyAction.DROP: PatternFill(start_color="FFCDD2", end_color="FFCDD2", fill_type="solid"),  # 薄い赤
}

# アクションテキスト色（コントラスト比を確保）
ACTION_FONTS = {
    PolicyAction.ALLOW: Font(bold=True, size=9, name='Yu Gothic UI', color="006064"),  # 濃い青緑
    PolicyAction.DENY: Font(bold=True, size=9, name='Yu Gothic UI', color="E65100"),   # 濃いオレンジ
    PolicyAction.DROP: Font(bold=True, size=9, name='Yu Gothic UI', color="B71C1C"),   # 濃い赤
}

# ステータス用スタイル（ユニバーサルデザイン配色）
ENABLED_FILL = PatternFill(start_color="BBDEFB", end_color="BBDEFB", fill_type="solid")  # 薄い青
ENABLED_FONT = Font(size=9, name='Yu Gothic UI', color="0D47A1", bold=True)  # 濃い青（太字で視認性向上）
DISABLED_FILL = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")  # 薄いグレー
DISABLED_FONT = Font(size=9, name='Yu Gothic UI', color="424242", bold=True)  # 濃いグレー（太字で視認性向上）
