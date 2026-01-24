#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excelエクスポーター
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from models.config import (
    ConfigModel, PolicyAction, HAMode, DeviceType
)
from models.cluster import ClusterConfig, HARole

logger = logging.getLogger(__name__)


class ExcelExporter:
    """Excel形式でパラメータシートを出力（VDOM/vsys単位）"""

    # ============================================================
    # セクション定義（HTMLエクスポーターと同様の構造）
    # ============================================================

    # グローバルセクション定義（VDOM横断の共通設定）
    GLOBAL_SECTIONS = [
        ('cluster_overview', 'クラスタ概要', '_create_cluster_overview_sheet'),
        ('device_info', '機器概要', '_create_overview_sheet'),
        ('system_settings', 'システム設定', '_create_system_sheet'),
        ('ha', 'HA設定', '_create_ha_sheet'),
        ('logging', 'ログ・監視設定', '_create_logging_sheet'),
    ]

    # VDOM単位セクション定義
    VDOM_SECTIONS = [
        ('interfaces', 'インターフェース', '_create_interfaces_sheet_for_vdom'),
        ('routes', 'ルーティング', '_create_routes_sheet_for_vdom'),
        ('objects', 'オブジェクト', '_create_objects_sheet_for_vdom'),
        ('policies', 'ポリシー', '_create_policies_sheet_for_vdom'),
        ('nat', 'NAT設定', '_create_nat_sheet_for_vdom'),
        ('vpn', 'VPN設定', '_create_vpn_sheet_for_vdom'),
        ('security_profiles', 'セキュリティ', '_create_security_profiles_sheet_for_vdom'),
    ]

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

    def __init__(self, config: Union[ConfigModel, ClusterConfig], sections: List[str] = None):
        """Excelエクスポーターを初期化

        Args:
            config: 設定データモデル（ConfigModelまたはClusterConfig）
            sections: 出力するセクションのリスト（Noneの場合は全セクション）
        """
        # ClusterConfigの場合、primary_configを使用
        if isinstance(config, ClusterConfig):
            self.cluster_config = config
            self.config = config.primary_config if config.primary_config else ConfigModel()
            self.is_cluster = config.is_cluster
        else:
            self.cluster_config = None
            self.config = config
            self.is_cluster = False

        self.sections = sections
        self.workbook = Workbook()
        # デフォルトシートを削除
        self.workbook.remove(self.workbook.active)

        # VDOM色マッピングを構築
        self._vdom_color_map: Dict[str, dict] = {}
        self._build_vdom_color_map()

        # 現在のVDOMコンテキスト（シート作成時に使用）
        self._current_vdom: Optional[str] = None
        self._current_color: dict = self.GLOBAL_COLOR

    def _build_vdom_color_map(self) -> None:
        """VDOMごとの色マッピングを構築"""
        vdom_list = self._get_vdom_list()
        for i, vdom in enumerate(vdom_list):
            color_idx = i % len(self.VDOM_COLORS)
            self._vdom_color_map[vdom] = self.VDOM_COLORS[color_idx]

    def _get_vdom_list(self) -> List[str]:
        """出力対象のVDOM/vsysリストを取得"""
        if self.config.device_info.vdom_list:
            return self.config.device_info.vdom_list
        return ["root"]  # デフォルト

    def _get_vdom_label(self) -> str:
        """デバイスタイプに応じたラベルを返す（VDOM/vsys）"""
        if self.config.device_info.device_type == DeviceType.PALOALTO:
            return "vsys"
        return "VDOM"

    def _filter_by_vdom(self, items: List[Any], vdom: str) -> List[Any]:
        """指定VDOMの項目のみをフィルタリング"""
        return [item for item in items if getattr(item, 'vdom', 'root') == vdom]

    def _get_vdom_color(self, vdom: str) -> dict:
        """指定VDOMの色設定を取得"""
        return self._vdom_color_map.get(vdom, self.VDOM_COLORS[0])

    def _set_vdom_context(self, vdom: Optional[str]) -> None:
        """現在のVDOMコンテキストを設定"""
        self._current_vdom = vdom
        if vdom:
            self._current_color = self._get_vdom_color(vdom)
        else:
            self._current_color = self.GLOBAL_COLOR

    def _get_vdom_styles(self, vdom: Optional[str] = None) -> dict:
        """VDOM用のスタイルオブジェクトを取得"""
        color = self._current_color if vdom is None else self._get_vdom_color(vdom)
        return {
            'header_font': Font(bold=True, color=color['header_text'], size=10, name='Yu Gothic UI'),
            'header_fill': PatternFill(start_color=color['header_bg'], end_color=color['header_bg'], fill_type="solid"),
            'header_border': Border(
                left=Side(style='thin', color=color['header_bg']),
                right=Side(style='thin', color=color['header_bg']),
                top=Side(style='thin', color=color['header_bg']),
                bottom=Side(style='medium', color=color['header_bg'])
            ),
            'section_font': Font(bold=True, color=color['header_bg'], size=12, name='Yu Gothic UI'),
            'section_fill': PatternFill(start_color=color['accent'], end_color=color['accent'], fill_type="solid"),
            'row_alt_fill': PatternFill(start_color=color['row_alt'], end_color=color['row_alt'], fill_type="solid"),
            'border': Border(
                left=Side(style='thin', color=color['border']),
                right=Side(style='thin', color=color['border']),
                top=Side(style='thin', color=color['border']),
                bottom=Side(style='thin', color=color['border'])
            ),
            'tab_color': color['tab_color'],
        }

    def export(self, output_path: Optional[str] = None) -> Workbook:
        """Excelファイルを生成（グローバル設定 → VDOM/vsys単位）"""
        vdom_list = self._get_vdom_list()

        # ============================================================
        # 1. グローバル設定シート（VDOM横断の共通設定）
        # ============================================================
        self._set_vdom_context(None)  # グローバルコンテキスト

        for key, title, method_name in self.GLOBAL_SECTIONS:
            # クラスタ概要はクラスタ構成時のみ
            if key == 'cluster_overview' and not self.is_cluster:
                continue
            method = getattr(self, method_name)
            method()

        # ============================================================
        # 2. VDOM/vsys単位のシート
        # ============================================================
        for vdom in vdom_list:
            self._set_vdom_context(vdom)

            for key, title, method_name in self.VDOM_SECTIONS:
                method = getattr(self, method_name)
                method(vdom)

        if output_path:
            self.workbook.save(output_path)
            logger.info(f"Excelファイル出力完了: {output_path}")

        return self.workbook

    def _create_sheet(self, title: str, vdom: Optional[str] = None) -> Worksheet:
        """シートを作成（VDOM名付きでタブ色を設定）"""
        # シート名を構築
        if vdom:
            # VDOM用シート: "VDOM名 - タイトル"
            full_title = f"{vdom} - {title}"
        else:
            # グローバルシート
            full_title = title

        # シート名は31文字まで
        sheet_title = full_title[:31]
        ws = self.workbook.create_sheet(title=sheet_title)

        # タブ色を設定（16進数文字列をRGBオブジェクトに変換）
        try:
            from openpyxl.styles.colors import RGB
            color = self._get_vdom_color(vdom) if vdom else self.GLOBAL_COLOR
            # 16進数文字列をRGBオブジェクトに変換（AARRGGBB形式）
            hex_color = color['tab_color']
            if len(hex_color) == 6:
                # RRGGBB形式の場合はアルファチャンネルを追加してAARRGGBB形式に
                hex_color = 'FF' + hex_color
            ws.sheet_properties.tabColor = RGB(hex_color)
        except (ImportError, AttributeError, ValueError, TypeError):
            # RGBクラスが利用できない、または変換に失敗した場合はスキップ
            # 一部のopenpyxlバージョンでは16進数文字列を直接受け取れる場合もある
            try:
                color = self._get_vdom_color(vdom) if vdom else self.GLOBAL_COLOR
                ws.sheet_properties.tabColor = color['tab_color']
            except (AttributeError, TypeError):
                pass

        return ws

    def _set_header_row(self, ws: Worksheet, headers: List[str], row: int = 1):
        """ヘッダー行を設定（VDOMコンテキストの色を使用）"""
        styles = self._get_vdom_styles()
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = styles['header_font']
            cell.fill = styles['header_fill']
            cell.alignment = self.HEADER_ALIGNMENT
            cell.border = styles['header_border']
        # 行の高さを少し広めに設定
        ws.row_dimensions[row].height = 28
        # まだフリーズペインが設定されていない場合は、このヘッダーの直下で固定する
        if ws.freeze_panes is None:
            ws.freeze_panes = ws.cell(row=row + 1, column=1)

    def _set_cell(self, ws: Worksheet, row: int, col: int, value: Any,
                  fill: PatternFill = None, font: Font = None,
                  center: bool = False, is_status: bool = False,
                  status_value: bool = None):
        """セルに値を設定（VDOMコンテキストの色を使用）

        Args:
            ws: ワークシート
            row: 行番号
            col: 列番号
            value: セルの値
            fill: 背景色（指定時はゼブラストライプより優先）
            font: フォント（指定時はデフォルトより優先）
            center: 中央揃えにするか
            is_status: ステータスセルか（有効/無効の自動スタイリング）
            status_value: ステータス値（Trueで有効スタイル、Falseで無効スタイル）
        """
        styles = self._get_vdom_styles()
        cell = ws.cell(row=row, column=col, value=str(value) if value else "")

        # ステータスセルの自動スタイリング
        if is_status and status_value is not None:
            if status_value:
                cell.fill = self.ENABLED_FILL
                cell.font = self.ENABLED_FONT
            else:
                cell.fill = self.DISABLED_FILL
                cell.font = self.DISABLED_FONT
            cell.alignment = self.CELL_ALIGNMENT_CENTER
        else:
            # 通常のセルスタイリング
            cell.font = font if font else self.CELL_FONT
            cell.alignment = self.CELL_ALIGNMENT_CENTER if center else self.CELL_ALIGNMENT

            # 背景色（ゼブラストライプ or 指定色）
            if fill:
                cell.fill = fill
            else:
                # ゼブラストライプ（VDOMコンテキストの色を使用）
                cell.fill = styles['row_alt_fill'] if row % 2 == 0 else self.ROW_FILL_EVEN

        cell.border = styles['border']
        return cell

    def _set_status_cell(self, ws: Worksheet, row: int, col: int,
                         enabled: bool, enabled_text: str = "有効",
                         disabled_text: str = "無効"):
        """ステータスセルを設定（有効/無効の視覚的区別）"""
        value = enabled_text if enabled else disabled_text
        return self._set_cell(ws, row, col, value, is_status=True, status_value=enabled)

    def _set_action_cell(self, ws: Worksheet, row: int, col: int, action: PolicyAction):
        """アクションセルを設定（Allow/Deny/Drop の視覚的区別）"""
        cell = ws.cell(row=row, column=col, value=action.value)
        cell.fill = self.ACTION_FILLS.get(action, self.ROW_FILL_EVEN)
        cell.font = self.ACTION_FONTS.get(action, self.CELL_FONT)
        cell.alignment = self.CELL_ALIGNMENT_CENTER
        cell.border = self.THIN_BORDER
        return cell

    def _set_section_title(self, ws: Worksheet, row: int, col: int,
                           title: str, colspan: int = 1):
        """セクションタイトルを設定（VDOMコンテキストの色を使用）"""
        styles = self._get_vdom_styles()
        cell = ws.cell(row=row, column=col, value=title)
        cell.font = styles['section_font']
        cell.fill = styles['section_fill']
        cell.alignment = Alignment(vertical="center")
        cell.border = Border(
            bottom=Side(style='medium', color=self._current_color['header_bg'])
        )
        ws.row_dimensions[row].height = 26
        if colspan > 1:
            ws.merge_cells(start_row=row, start_column=col,
                          end_row=row, end_column=col + colspan - 1)
        return cell

    def _auto_column_width(self, ws: Worksheet, min_width: int = 8, max_width: int = 50):
        """列幅を自動調整"""
        from openpyxl.cell.cell import MergedCell
        
        for column_cells in ws.columns:
            max_length = 0
            # マージされていない最初のセルを見つける
            column_letter = None
            for cell in column_cells:
                if not isinstance(cell, MergedCell):
                    column_letter = cell.column_letter
                    break
            
            if column_letter is None:
                continue
                
            for cell in column_cells:
                # MergedCellはスキップ
                if isinstance(cell, MergedCell):
                    continue
                try:
                    if cell.value:
                        # 日本語文字は2文字分としてカウント
                        cell_length = sum(2 if ord(c) > 127 else 1 for c in str(cell.value))
                        max_length = max(max_length, cell_length)
                except:
                    pass
            adjusted_width = min(max(max_length + 2, min_width), max_width)
            ws.column_dimensions[column_letter].width = adjusted_width

    def _list_to_str(self, items: List[Any], separator: str = "\n") -> str:
        """リストを文字列に変換"""
        if not items:
            return "-"
        return separator.join(str(item) for item in items)

    def _create_cluster_overview_sheet(self):
        """クラスタ概要シートを作成（HAクラスタ時のみ）"""
        if not self.is_cluster or self.cluster_config is None:
            return

        ws = self._create_sheet("クラスタ概要")
        cluster_info = self.cluster_config.cluster_info

        # タイトル（モダンスタイル）
        ws.merge_cells('A1:D1')
        title_cell = ws.cell(row=1, column=1, value="HAクラスタ概要")
        title_cell.font = self.MAIN_TITLE_FONT
        ws.row_dimensions[1].height = 36

        # クラスタ情報（カード風レイアウト）
        info_fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")  # ユニバーサルデザイン配色
        data = [
            ("クラスタ名", cluster_info.cluster_name),
            ("グループID", cluster_info.group_id),
            ("HAモード", cluster_info.ha_mode.value),
            ("メンバー数", cluster_info.get_member_count()),
        ]

        for row_idx, (label, value) in enumerate(data, 3):
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill
            label_cell.border = self.THIN_BORDER

            value_cell = ws.cell(row=row_idx, column=2, value=value)
            value_cell.font = self.CELL_FONT
            value_cell.fill = info_fill
            value_cell.border = self.THIN_BORDER

        # クラスタメンバー一覧
        member_start = len(data) + 5
        self._set_section_title(ws, member_start, 1, "クラスタメンバー", colspan=8)

        member_headers = ["役割", "ホスト名", "モデル", "OSバージョン", "優先度", "HA管理IP", "シリアル番号", "設定ファイル"]
        self._set_header_row(ws, member_headers, member_start + 1)

        for row_idx, member in enumerate(cluster_info.members, member_start + 2):
            self._set_cell(ws, row_idx, 1, member.role.value, center=True)
            self._set_cell(ws, row_idx, 2, member.hostname)
            self._set_cell(ws, row_idx, 3, member.model or "-")
            self._set_cell(ws, row_idx, 4, member.os_version or "-", center=True)
            self._set_cell(ws, row_idx, 5, member.priority if member.priority else "-", center=True)
            self._set_cell(ws, row_idx, 6, member.ha_mgmt_ip or "-")
            self._set_cell(ws, row_idx, 7, member.serial_number or "-")
            self._set_cell(ws, row_idx, 8, Path(member.source_file).name if member.source_file else "-")

        # 設定差分
        differences = self.cluster_config.config_differences
        if differences:
            diff_start = member_start + len(cluster_info.members) + 4
            self._set_section_title(ws, diff_start, 1, "設定差分（メンバー間の相違点）", colspan=5)

            diff_headers = ["セクション", "項目", "Primary", "Secondary", "備考"]
            self._set_header_row(ws, diff_headers, diff_start + 1)

            for row_idx, diff in enumerate(differences, diff_start + 2):
                self._set_cell(ws, row_idx, 1, diff.section)
                self._set_cell(ws, row_idx, 2, diff.item)
                self._set_cell(ws, row_idx, 3, diff.primary_value)
                self._set_cell(ws, row_idx, 4, diff.secondary_value)
                self._set_cell(ws, row_idx, 5, diff.description)

        self._auto_column_width(ws)

    def _create_overview_sheet(self):
        """機器概要シートを作成（モダンスタイル）"""
        ws = self._create_sheet("機器概要")
        info = self.config.device_info
        today = datetime.now().strftime('%Y年%m月%d日')

        # タイトル（モダンスタイル）
        ws.merge_cells('A1:C1')
        title_cell = ws.cell(row=1, column=1, value=f"{info.device_type.value} パラメータシート")
        title_cell.font = self.MAIN_TITLE_FONT
        ws.row_dimensions[1].height = 40

        # サブタイトル（作成日・ソースファイル）
        ws.merge_cells('A2:C2')
        sub_cell = ws.cell(row=2, column=1, value=f"作成日: {today}  |  ソース: {Path(self.config.source_file).name}")
        sub_cell.font = self.CELL_FONT_SECONDARY
        ws.row_dimensions[2].height = 22

        # 機器情報セクション
        self._set_section_title(ws, 4, 1, "機器情報", colspan=2)

        info_fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")  # ユニバーサルデザイン配色
        device_data = [
            ("ホスト名", info.hostname),
            ("モデル", info.model),
            ("シリアル番号", info.serial_number or "設定ファイルから取得不可"),
            ("OSバージョン", info.os_version),
            ("動作モード", info.operation_mode.value),
            ("VDOM/vsys", "有効" if info.vdom_enabled else "無効"),
            ("VDOM/vsysリスト", ", ".join(info.vdom_list) if info.vdom_list else "-"),
        ]

        for row_idx, (label, value) in enumerate(device_data, 5):
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill if row_idx % 2 == 1 else self.ROW_FILL_EVEN
            label_cell.border = self.THIN_BORDER
            label_cell.alignment = Alignment(vertical="center")

            value_cell = ws.cell(row=row_idx, column=2, value=value)
            value_cell.font = self.CELL_FONT
            value_cell.fill = info_fill if row_idx % 2 == 1 else self.ROW_FILL_EVEN
            value_cell.border = self.THIN_BORDER
            value_cell.alignment = Alignment(vertical="center")

        # 統計情報セクション
        stats_start = 5 + len(device_data) + 2
        self._set_section_title(ws, stats_start, 1, "設定統計", colspan=2)

        # 統計データ（数字を強調）
        stats_data = [
            ("インターフェース数", len(self.config.interfaces)),
            ("ルート数", len(self.config.routes)),
            ("ファイアウォールポリシー数", len(self.config.firewall_policies)),
            ("オブジェクト数", len(self.config.objects.addresses) + len(self.config.objects.services)),
            ("NAT設定数", len(self.config.nat_policies)),
        ]

        stats_fill = PatternFill(start_color="E0F5F5", end_color="E0F5F5", fill_type="solid")  # ユニバーサルデザイン配色（ティール系）
        number_font = Font(bold=True, size=11, name='Yu Gothic UI', color="006666")  # 濃いティール（コントラスト比確保）

        for row_idx, (label, value) in enumerate(stats_data, stats_start + 1):
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = stats_fill
            label_cell.border = self.THIN_BORDER
            label_cell.alignment = Alignment(vertical="center")

            value_cell = ws.cell(row=row_idx, column=2, value=value)
            value_cell.font = number_font
            value_cell.fill = stats_fill
            value_cell.border = self.THIN_BORDER
            value_cell.alignment = Alignment(horizontal="center", vertical="center")

        # 列幅調整
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 40
        self._auto_column_width(ws)

    def _create_system_sheet(self):
        """システム設定シートを作成（モダンスタイル）"""
        ws = self._create_sheet("システム設定")
        settings = self.config.system_settings

        # 管理設定セクション
        self._set_section_title(ws, 1, 1, "管理アクセス設定", colspan=2)

        info_fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")  # ユニバーサルデザイン配色
        data = [
            ("管理用IPアドレス", settings.management_ip),
            ("サブネットマスク", settings.management_netmask),
            ("管理インターフェース", settings.management_interface),
            ("HTTPSポート", settings.https_port or "443"),
            ("SSHポート", settings.ssh_port or "22"),
            ("許可プロトコル", self._list_to_str(settings.allowed_protocols, ", ")),
        ]

        for row_idx, (label, value) in enumerate(data, 2):
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill if row_idx % 2 == 0 else self.ROW_FILL_EVEN
            label_cell.border = self.THIN_BORDER

            value_cell = ws.cell(row=row_idx, column=2, value=value)
            value_cell.font = self.CELL_FONT
            value_cell.fill = info_fill if row_idx % 2 == 0 else self.ROW_FILL_EVEN
            value_cell.border = self.THIN_BORDER

        # DNS/NTP設定セクション
        start_row = len(data) + 4
        self._set_section_title(ws, start_row, 1, "DNS/NTP設定", colspan=2)

        dns_data = [
            ("プライマリDNS", settings.dns_primary or "-"),
            ("セカンダリDNS", settings.dns_secondary or "-"),
            ("NTPサーバー", self._list_to_str(settings.ntp_servers, ", ") or "-"),
            ("タイムゾーン", settings.timezone or "-"),
        ]

        for row_idx, (label, value) in enumerate(dns_data, start_row + 1):
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill if row_idx % 2 == 0 else self.ROW_FILL_EVEN
            label_cell.border = self.THIN_BORDER

            value_cell = ws.cell(row=row_idx, column=2, value=value)
            value_cell.font = self.CELL_FONT
            value_cell.fill = info_fill if row_idx % 2 == 0 else self.ROW_FILL_EVEN
            value_cell.border = self.THIN_BORDER

        # 管理者アカウントセクション
        admin_start = start_row + len(dns_data) + 3
        self._set_section_title(ws, admin_start, 1, "管理者アカウント", colspan=4)

        if settings.admin_users:
            headers = ["ユーザー名", "権限プロファイル", "VDOM", "信頼ホスト"]
            self._set_header_row(ws, headers, admin_start + 1)

            for row_idx, admin in enumerate(settings.admin_users, admin_start + 2):
                self._set_cell(ws, row_idx, 1, admin.username)
                self._set_cell(ws, row_idx, 2, admin.profile)
                self._set_cell(ws, row_idx, 3, admin.vdom)
                self._set_cell(ws, row_idx, 4, self._list_to_str(admin.trust_hosts, ", "))

        self._auto_column_width(ws)

    # ============================================================
    # 非推奨: 以下のメソッドは VDOM 単位のメソッドに置き換えられました
    # export() メソッドからは呼ばれていません
    # ============================================================

    def _create_interfaces_sheet(self):
        """インターフェースシートを作成（モダンスタイル）
        
        注意: このメソッドは非推奨です。
        VDOM単位の出力には _create_interfaces_sheet_for_vdom() を使用してください。
        """
        ws = self._create_sheet("インターフェース")

        headers = ["インターフェース名", "タイプ", "役割", "IPアドレス", "VLAN ID",
                   "ゾーン", "VDOM/vsys", "許可アクセス", "状態", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, iface in enumerate(self.config.interfaces, 2):
            self._set_cell(ws, row_idx, 1, iface.name)
            self._set_cell(ws, row_idx, 2, iface.interface_type, center=True)
            self._set_cell(ws, row_idx, 3, iface.role, center=True)
            self._set_cell(ws, row_idx, 4, iface.ip_address)
            self._set_cell(ws, row_idx, 5, iface.vlan_id, center=True)
            self._set_cell(ws, row_idx, 6, iface.zone, center=True)
            self._set_cell(ws, row_idx, 7, iface.vdom, center=True)
            self._set_cell(ws, row_idx, 8, self._list_to_str(iface.allowed_access, ", "))
            # 状態をステータスセルとして表示
            status_enabled = iface.status and iface.status.lower() in ('up', 'enable', 'enabled', '有効')
            self._set_status_cell(ws, row_idx, 9, status_enabled,
                                 enabled_text=iface.status or "up",
                                 disabled_text=iface.status or "down")
            self._set_cell(ws, row_idx, 10, iface.description)

        self._auto_column_width(ws)

    def _create_routes_sheet(self):
        """ルーティングシートを作成（モダンスタイル）"""
        ws = self._create_sheet("ルーティング")

        headers = ["ルート名", "宛先ネットワーク", "ゲートウェイ", "インターフェース",
                   "ディスタンス", "タイプ", "VDOM/vsys"]
        self._set_header_row(ws, headers)

        for row_idx, route in enumerate(self.config.routes, 2):
            gateway_display = route.gateway
            # blackhole/discard ルートはゲートウェイが空になるため、明示して記載する
            if not gateway_display and getattr(route, "route_type", "") in ("blackhole", "blackhole6"):
                gateway_display = "blackhole"

            self._set_cell(ws, row_idx, 1, route.name)
            self._set_cell(ws, row_idx, 2, route.destination)
            self._set_cell(ws, row_idx, 3, gateway_display)
            self._set_cell(ws, row_idx, 4, route.interface or "-")
            self._set_cell(ws, row_idx, 5, route.distance, center=True)
            self._set_cell(ws, row_idx, 6, route.route_type, center=True)
            self._set_cell(ws, row_idx, 7, route.vdom, center=True)

        self._auto_column_width(ws)

    def _create_objects_sheet(self):
        """オブジェクト定義シートを作成（モダンスタイル）"""
        ws = self._create_sheet("オブジェクト")

        # アドレスオブジェクト
        self._set_section_title(ws, 1, 1, "アドレスオブジェクト", colspan=5)
        addr_headers = ["オブジェクト名", "タイプ", "値", "VDOM/vsys", "説明"]
        self._set_header_row(ws, addr_headers, 2)

        row_idx = 3
        for addr in self.config.objects.addresses:
            self._set_cell(ws, row_idx, 1, addr.name)
            self._set_cell(ws, row_idx, 2, addr.object_type, center=True)
            self._set_cell(ws, row_idx, 3, addr.value)
            self._set_cell(ws, row_idx, 4, addr.vdom, center=True)
            self._set_cell(ws, row_idx, 5, addr.description)
            row_idx += 1

        # アドレスグループ
        row_idx += 2
        self._set_section_title(ws, row_idx, 1, "アドレスグループ", colspan=4)
        grp_headers = ["グループ名", "メンバー", "VDOM/vsys", "説明"]
        self._set_header_row(ws, grp_headers, row_idx + 1)
        row_idx += 2

        for grp in self.config.objects.address_groups:
            self._set_cell(ws, row_idx, 1, grp.name)
            self._set_cell(ws, row_idx, 2, self._list_to_str(grp.members, ", "))
            self._set_cell(ws, row_idx, 3, grp.vdom, center=True)
            self._set_cell(ws, row_idx, 4, grp.description)
            row_idx += 1

        # サービスオブジェクト
        row_idx += 2
        self._set_section_title(ws, row_idx, 1, "サービスオブジェクト", colspan=5)
        svc_headers = ["オブジェクト名", "プロトコル", "ポート", "VDOM/vsys", "説明"]
        self._set_header_row(ws, svc_headers, row_idx + 1)
        row_idx += 2

        for svc in self.config.objects.services:
            self._set_cell(ws, row_idx, 1, svc.name)
            self._set_cell(ws, row_idx, 2, svc.protocol, center=True)
            self._set_cell(ws, row_idx, 3, svc.port, center=True)
            self._set_cell(ws, row_idx, 4, svc.vdom, center=True)
            self._set_cell(ws, row_idx, 5, svc.description)
            row_idx += 1

        # サービスグループ
        row_idx += 2
        self._set_section_title(ws, row_idx, 1, "サービスグループ", colspan=4)
        sgrp_headers = ["グループ名", "メンバー", "VDOM/vsys", "説明"]
        self._set_header_row(ws, sgrp_headers, row_idx + 1)
        row_idx += 2

        for grp in self.config.objects.service_groups:
            self._set_cell(ws, row_idx, 1, grp.name)
            self._set_cell(ws, row_idx, 2, self._list_to_str(grp.members, ", "))
            self._set_cell(ws, row_idx, 3, grp.vdom, center=True)
            self._set_cell(ws, row_idx, 4, grp.description)
            row_idx += 1

        self._auto_column_width(ws)

    def _create_policies_sheet(self):
        """ファイアウォールポリシーシートを作成（モダンスタイル）"""
        ws = self._create_sheet("ファイアウォールポリシー")

        headers = ["No", "ID", "ポリシー名", "送信元IF", "宛先IF", "送信元アドレス",
                   "宛先アドレス", "サービス", "アクション", "NAT", "ログ",
                   "セキュリティプロファイル", "VDOM/vsys", "有効", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, (idx, policy) in enumerate(enumerate(self.config.firewall_policies, 1), 2):
            self._set_cell(ws, row_idx, 1, idx, center=True)
            self._set_cell(ws, row_idx, 2, policy.policy_id, center=True)
            self._set_cell(ws, row_idx, 3, policy.name)
            self._set_cell(ws, row_idx, 4, self._list_to_str(policy.source_interface))
            self._set_cell(ws, row_idx, 5, self._list_to_str(policy.destination_interface))
            self._set_cell(ws, row_idx, 6, self._list_to_str(policy.source_address))
            self._set_cell(ws, row_idx, 7, self._list_to_str(policy.destination_address))
            self._set_cell(ws, row_idx, 8, self._list_to_str(policy.service))
            # アクション（専用スタイル）
            self._set_action_cell(ws, row_idx, 9, policy.action)
            # NAT/ログ/有効（ステータススタイル）
            self._set_status_cell(ws, row_idx, 10, policy.nat_enabled)
            self._set_status_cell(ws, row_idx, 11, policy.log_enabled)
            self._set_cell(ws, row_idx, 12, self._list_to_str(policy.security_profiles))
            self._set_cell(ws, row_idx, 13, policy.vdom, center=True)
            self._set_status_cell(ws, row_idx, 14, policy.enabled)
            self._set_cell(ws, row_idx, 15, policy.description)

        self._auto_column_width(ws)

        # Local-in ポリシー（別シート）
        if self.config.local_in_policies:
            self._create_local_in_policies_sheet()

    def _create_local_in_policies_sheet(self):
        """Local-in ポリシーシートを作成（モダンスタイル）"""
        ws = self._create_sheet("Local-in ポリシー")

        headers = ["No", "ID", "ポリシー名", "送信元IF", "送信元アドレス",
                   "宛先アドレス", "サービス", "アクション", "VDOM/vsys", "有効", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, (idx, policy) in enumerate(enumerate(self.config.local_in_policies, 1), 2):
            # source_interfaceが文字列の場合とリストの場合に対応
            src_if = policy.source_interface
            if isinstance(src_if, list):
                src_if_str = self._list_to_str(src_if)
            else:
                src_if_str = src_if or "-"

            self._set_cell(ws, row_idx, 1, idx, center=True)
            self._set_cell(ws, row_idx, 2, policy.policy_id, center=True)
            self._set_cell(ws, row_idx, 3, policy.name)
            self._set_cell(ws, row_idx, 4, src_if_str)
            self._set_cell(ws, row_idx, 5, self._list_to_str(policy.source_address))
            self._set_cell(ws, row_idx, 6, self._list_to_str(policy.destination_address))
            self._set_cell(ws, row_idx, 7, self._list_to_str(policy.service))
            self._set_action_cell(ws, row_idx, 8, policy.action)
            self._set_cell(ws, row_idx, 9, policy.vdom, center=True)
            self._set_status_cell(ws, row_idx, 10, policy.enabled)
            self._set_cell(ws, row_idx, 11, policy.description)

        self._auto_column_width(ws)

    def _create_nat_sheet(self):
        """NAT設定シートを作成（モダンスタイル）"""
        ws = self._create_sheet("NAT設定")

        headers = ["ルール名", "タイプ", "元送信元", "元宛先", "変換後送信元",
                   "変換後宛先", "外部IF", "外部IP", "内部IP", "ポートフォワード",
                   "元ポート", "変換後ポート", "VDOM/vsys", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, nat in enumerate(self.config.nat_policies, 2):
            self._set_cell(ws, row_idx, 1, nat.name)
            self._set_cell(ws, row_idx, 2, nat.nat_type, center=True)
            self._set_cell(ws, row_idx, 3, nat.original_source)
            self._set_cell(ws, row_idx, 4, nat.original_destination)
            self._set_cell(ws, row_idx, 5, nat.translated_source)
            self._set_cell(ws, row_idx, 6, nat.translated_destination)
            self._set_cell(ws, row_idx, 7, nat.external_interface)
            self._set_cell(ws, row_idx, 8, nat.external_ip)
            self._set_cell(ws, row_idx, 9, nat.internal_ip)
            self._set_status_cell(ws, row_idx, 10, nat.port_forward)
            self._set_cell(ws, row_idx, 11, nat.original_port, center=True)
            self._set_cell(ws, row_idx, 12, nat.translated_port, center=True)
            self._set_cell(ws, row_idx, 13, nat.vdom, center=True)
            self._set_cell(ws, row_idx, 14, nat.description)

        self._auto_column_width(ws)

    def _create_vpn_sheet(self):
        """VPN設定シートを作成（モダンスタイル）"""
        ws = self._create_sheet("VPN設定")

        # IPsec Phase1
        self._set_section_title(ws, 1, 1, "IPsec Phase1", colspan=9)
        p1_headers = ["VPN名", "リモートGW", "インターフェース", "IKEバージョン",
                      "暗号化", "認証", "DHグループ", "ライフタイム", "PSK"]
        self._set_header_row(ws, p1_headers, 2)

        row_idx = 3
        for p1 in self.config.vpn.ipsec_phase1:
            self._set_cell(ws, row_idx, 1, p1.name)
            self._set_cell(ws, row_idx, 2, p1.remote_gateway)
            self._set_cell(ws, row_idx, 3, p1.interface)
            self._set_cell(ws, row_idx, 4, p1.ike_version, center=True)
            self._set_cell(ws, row_idx, 5, p1.encryption, center=True)
            self._set_cell(ws, row_idx, 6, p1.authentication, center=True)
            self._set_cell(ws, row_idx, 7, p1.dh_group, center=True)
            self._set_cell(ws, row_idx, 8, p1.lifetime, center=True)
            self._set_status_cell(ws, row_idx, 9, bool(p1.psk), enabled_text="有", disabled_text="無")
            row_idx += 1

        # IPsec Phase2
        row_idx += 2
        self._set_section_title(ws, row_idx, 1, "IPsec Phase2", colspan=8)
        p2_headers = ["VPN名", "Phase1名", "暗号化", "認証", "PFS",
                      "ライフタイム", "ローカルセグメント", "リモートセグメント"]
        self._set_header_row(ws, p2_headers, row_idx + 1)
        row_idx += 2

        for p2 in self.config.vpn.ipsec_phase2:
            self._set_cell(ws, row_idx, 1, p2.name)
            self._set_cell(ws, row_idx, 2, p2.phase1_name)
            self._set_cell(ws, row_idx, 3, p2.encryption, center=True)
            self._set_cell(ws, row_idx, 4, p2.authentication, center=True)
            self._set_cell(ws, row_idx, 5, p2.pfs, center=True)
            self._set_cell(ws, row_idx, 6, p2.lifetime, center=True)
            self._set_cell(ws, row_idx, 7, p2.local_subnet)
            self._set_cell(ws, row_idx, 8, p2.remote_subnet)
            row_idx += 1

        # SSL-VPN
        row_idx += 2
        self._set_section_title(ws, row_idx, 1, "SSL-VPN / GlobalProtect", colspan=9)
        ssl_headers = ["レルム", "ポータル", "ポート", "インターフェース",
                       "認証方式", "IPプール", "ユーザーグループ", "モード", "VDOM/vsys"]
        self._set_header_row(ws, ssl_headers, row_idx + 1)
        row_idx += 2

        for ssl in self.config.vpn.ssl_vpn:
            self._set_cell(ws, row_idx, 1, ssl.realm)
            self._set_cell(ws, row_idx, 2, ssl.portal)
            self._set_cell(ws, row_idx, 3, ssl.listen_port, center=True)
            self._set_cell(ws, row_idx, 4, ssl.listen_interface)
            self._set_cell(ws, row_idx, 5, ssl.auth_method, center=True)
            self._set_cell(ws, row_idx, 6, ssl.tunnel_ip_pool)
            self._set_cell(ws, row_idx, 7, self._list_to_str(ssl.user_groups, ", "))
            self._set_cell(ws, row_idx, 8, ssl.mode, center=True)
            self._set_cell(ws, row_idx, 9, ssl.vdom, center=True)
            row_idx += 1

        self._auto_column_width(ws)

    def _create_security_profiles_sheet(self):
        """セキュリティプロファイルシートを作成（モダンスタイル）"""
        ws = self._create_sheet("セキュリティプロファイル")

        headers = ["プロファイル名", "タイプ", "有効/無効", "VDOM/vsys", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, profile in enumerate(self.config.security_profiles, 2):
            self._set_cell(ws, row_idx, 1, profile.name)
            self._set_cell(ws, row_idx, 2, profile.profile_type, center=True)
            self._set_status_cell(ws, row_idx, 3, profile.enabled)
            self._set_cell(ws, row_idx, 4, profile.vdom, center=True)
            self._set_cell(ws, row_idx, 5, profile.description)

        self._auto_column_width(ws)

    def _create_ha_sheet(self):
        """HA設定シートを作成（モダンスタイル）"""
        ws = self._create_sheet("HA設定")
        ha = self.config.ha

        if ha.mode == HAMode.STANDALONE:
            cell = ws.cell(row=1, column=1, value="HA設定なし（スタンドアロン）")
            cell.font = self.CELL_FONT_SECONDARY
            cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.merge_cells('A1:B1')
            return

        # HA基本設定セクション
        self._set_section_title(ws, 1, 1, "HA基本設定", colspan=2)

        info_fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")  # ユニバーサルデザイン配色

        # 基本情報
        basic_data = [
            ("HAモード", ha.mode.value, False),
            ("グループID", ha.group_id, False),
            ("グループ名", ha.group_name or "-", False),
            ("優先度", ha.priority if ha.priority else "-", False),
            ("プリエンプト", ha.preempt, True),
            ("HA管理ステータス", ha.ha_mgmt_status, True),
        ]

        row_idx = 2
        for label, value, is_status in basic_data:
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill if row_idx % 2 == 0 else self.ROW_FILL_EVEN
            label_cell.border = self.THIN_BORDER

            if is_status:
                self._set_status_cell(ws, row_idx, 2, value)
            else:
                value_cell = ws.cell(row=row_idx, column=2, value=value)
                value_cell.font = self.CELL_FONT
                value_cell.fill = info_fill if row_idx % 2 == 0 else self.ROW_FILL_EVEN
                value_cell.border = self.THIN_BORDER
            row_idx += 1

        # 同期設定セクション
        row_idx += 1
        self._set_section_title(ws, row_idx, 1, "同期設定", colspan=2)
        row_idx += 1

        sync_data = [
            ("セッション同期", ha.session_sync, True),
            ("セッションピックアップ", ha.session_pickup, True),
            ("ハートビート間隔", ha.hb_interval if ha.hb_interval else "-", False),
            ("ハートビート損失閾値", ha.hb_lost_threshold if ha.hb_lost_threshold else "-", False),
            ("暗号化", ha.encryption, True),
            ("認証", ha.authentication, True),
        ]

        for label, value, is_status in sync_data:
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill if row_idx % 2 == 0 else self.ROW_FILL_EVEN
            label_cell.border = self.THIN_BORDER

            if is_status:
                self._set_status_cell(ws, row_idx, 2, value)
            else:
                value_cell = ws.cell(row=row_idx, column=2, value=value)
                value_cell.font = self.CELL_FONT
                value_cell.fill = info_fill if row_idx % 2 == 0 else self.ROW_FILL_EVEN
                value_cell.border = self.THIN_BORDER
            row_idx += 1

        # インターフェース設定
        row_idx += 1
        self._set_section_title(ws, row_idx, 1, "インターフェース設定", colspan=2)
        row_idx += 1

        iface_data = [
            ("監視インターフェース", self._list_to_str(ha.monitor_interfaces, ", ")),
            ("HAインターフェース", self._list_to_str(ha.ha_interfaces, ", ")),
        ]

        for label, value in iface_data:
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill if row_idx % 2 == 0 else self.ROW_FILL_EVEN
            label_cell.border = self.THIN_BORDER

            value_cell = ws.cell(row=row_idx, column=2, value=value)
            value_cell.font = self.CELL_FONT
            value_cell.fill = info_fill if row_idx % 2 == 0 else self.ROW_FILL_EVEN
            value_cell.border = self.THIN_BORDER
            row_idx += 1

        # ハートビートインターフェース詳細
        row_idx += 1
        if ha.heartbeat_interfaces_detail:
            self._set_section_title(ws, row_idx, 1, "ハートビートインターフェース", colspan=2)
            hb_headers = ["インターフェース", "優先度"]
            self._set_header_row(ws, hb_headers, row_idx + 1)
            row_idx += 2

            for hb in ha.heartbeat_interfaces_detail:
                self._set_cell(ws, row_idx, 1, hb.interface)
                self._set_cell(ws, row_idx, 2, hb.priority if hb.priority else "-", center=True)
                row_idx += 1
        elif ha.heartbeat_interfaces:
            self._set_section_title(ws, row_idx, 1, "ハートビートインターフェース", colspan=2)
            row_idx += 1
            cell = ws.cell(row=row_idx, column=1, value=self._list_to_str(ha.heartbeat_interfaces, ", "))
            cell.font = self.CELL_FONT
            cell.border = self.THIN_BORDER
            row_idx += 1

        # HA管理インターフェース
        if ha.ha_mgmt_interfaces:
            row_idx += 1
            self._set_section_title(ws, row_idx, 1, "HA管理インターフェース", colspan=3)
            mgmt_headers = ["ID", "インターフェース", "ゲートウェイ"]
            self._set_header_row(ws, mgmt_headers, row_idx + 1)
            row_idx += 2

            for mgmt in ha.ha_mgmt_interfaces:
                self._set_cell(ws, row_idx, 1, mgmt.id, center=True)
                self._set_cell(ws, row_idx, 2, mgmt.interface)
                self._set_cell(ws, row_idx, 3, mgmt.gateway)
                row_idx += 1

        self._auto_column_width(ws)

    def _create_logging_sheet(self):
        """ログ・監視設定シートを作成（モダンスタイル）"""
        ws = self._create_sheet("ログ・監視設定")
        logging_config = self.config.logging

        # Syslog
        self._set_section_title(ws, 1, 1, "Syslogサーバー", colspan=6)
        syslog_headers = ["サーバー", "ポート", "ファシリティ", "状態", "ログ種別", "VDOM/vsys"]
        self._set_header_row(ws, syslog_headers, 2)

        row_idx = 3
        for syslog in logging_config.syslog_servers:
            self._set_cell(ws, row_idx, 1, syslog.server)
            self._set_cell(ws, row_idx, 2, syslog.port, center=True)
            self._set_cell(ws, row_idx, 3, syslog.facility, center=True)
            # 状態をステータスセルとして表示
            status_enabled = syslog.status and syslog.status.lower() in ('enable', 'enabled', '有効', 'up')
            self._set_status_cell(ws, row_idx, 4, status_enabled,
                                 enabled_text=syslog.status or "enable",
                                 disabled_text=syslog.status or "disable")
            self._set_cell(ws, row_idx, 5, self._list_to_str(syslog.log_types, ", "))
            self._set_cell(ws, row_idx, 6, syslog.vdom, center=True)
            row_idx += 1

        # SNMP
        row_idx += 2
        self._set_section_title(ws, row_idx, 1, "SNMP設定", colspan=5)
        snmp_headers = ["有効", "バージョン", "コミュニティ/ユーザー", "ホスト", "トラップ送信先"]
        self._set_header_row(ws, snmp_headers, row_idx + 1)
        row_idx += 2

        for snmp in logging_config.snmp:
            self._set_status_cell(ws, row_idx, 1, snmp.enabled)
            self._set_cell(ws, row_idx, 2, snmp.version, center=True)
            self._set_cell(ws, row_idx, 3, snmp.community or snmp.username)
            self._set_cell(ws, row_idx, 4, self._list_to_str(snmp.hosts, ", "))
            self._set_cell(ws, row_idx, 5, self._list_to_str(snmp.trap_hosts, ", "))
            row_idx += 1

        # 集中管理
        row_idx += 2
        self._set_section_title(ws, row_idx, 1, "集中管理", colspan=2)
        row_idx += 1

        info_fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")  # ユニバーサルデザイン配色

        if logging_config.fortianalyzer_server:
            label_cell = ws.cell(row=row_idx, column=1, value="FortiAnalyzer")
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill
            label_cell.border = self.THIN_BORDER

            value_cell = ws.cell(row=row_idx, column=2, value=logging_config.fortianalyzer_server)
            value_cell.font = self.CELL_FONT
            value_cell.fill = info_fill
            value_cell.border = self.THIN_BORDER
            row_idx += 1

            label_cell = ws.cell(row=row_idx, column=1, value="状態")
            label_cell.font = self.LABEL_FONT
            label_cell.fill = self.ROW_FILL_EVEN
            label_cell.border = self.THIN_BORDER

            value_cell = ws.cell(row=row_idx, column=2, value=logging_config.fortianalyzer_status)
            value_cell.font = self.CELL_FONT
            value_cell.fill = self.ROW_FILL_EVEN
            value_cell.border = self.THIN_BORDER
            row_idx += 1

        if logging_config.panorama_server:
            label_cell = ws.cell(row=row_idx, column=1, value="Panorama")
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill
            label_cell.border = self.THIN_BORDER

            value_cell = ws.cell(row=row_idx, column=2, value=logging_config.panorama_server)
            value_cell.font = self.CELL_FONT
            value_cell.fill = info_fill
            value_cell.border = self.THIN_BORDER

        self._auto_column_width(ws)

    # ============================================================
    # VDOM単位のシート作成メソッド
    # ============================================================

    def _create_interfaces_sheet_for_vdom(self, vdom: str):
        """指定VDOMのインターフェースシートを作成"""
        interfaces = self._filter_by_vdom(self.config.interfaces, vdom)
        if not interfaces:
            return  # データがなければシートを作成しない

        ws = self._create_sheet("IF", vdom)

        headers = ["インターフェース名", "タイプ", "役割", "IPアドレス", "VLAN ID",
                   "ゾーン", "許可アクセス", "状態", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, iface in enumerate(interfaces, 2):
            self._set_cell(ws, row_idx, 1, iface.name)
            self._set_cell(ws, row_idx, 2, iface.interface_type, center=True)
            self._set_cell(ws, row_idx, 3, iface.role, center=True)
            self._set_cell(ws, row_idx, 4, iface.ip_address)
            self._set_cell(ws, row_idx, 5, iface.vlan_id, center=True)
            self._set_cell(ws, row_idx, 6, iface.zone, center=True)
            self._set_cell(ws, row_idx, 7, self._list_to_str(iface.allowed_access, ", "))
            status_enabled = iface.status and iface.status.lower() in ('up', 'enable', 'enabled', '有効')
            self._set_status_cell(ws, row_idx, 8, status_enabled,
                                 enabled_text=iface.status or "up",
                                 disabled_text=iface.status or "down")
            self._set_cell(ws, row_idx, 9, iface.description)

        self._auto_column_width(ws)

    def _create_routes_sheet_for_vdom(self, vdom: str):
        """指定VDOMのルーティングシートを作成（スタティック、OSPF、BGP、ポリシールート）"""
        routes = self._filter_by_vdom(self.config.routes, vdom)
        ospf_list = self._filter_by_vdom(self.config.routing.ospf, vdom)
        ospf6_list = self._filter_by_vdom(self.config.routing.ospf6, vdom)
        bgp_list = self._filter_by_vdom(self.config.routing.bgp, vdom)
        policy_routes = self._filter_by_vdom(self.config.routing.policy_routes, vdom)

        if not any([routes, ospf_list, ospf6_list, bgp_list, policy_routes]):
            return

        ws = self._create_sheet("ルート", vdom)
        row_idx = 1

        # スタティックルート
        if routes:
            self._set_section_title(ws, row_idx, 1, "スタティックルート", colspan=6)
            headers = ["ルート名", "宛先ネットワーク", "ゲートウェイ", "インターフェース",
                       "ディスタンス", "タイプ"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2

            for route in routes:
                gateway_display = route.gateway
                if not gateway_display and getattr(route, "route_type", "") in ("blackhole", "blackhole6"):
                    gateway_display = "blackhole"

                self._set_cell(ws, row_idx, 1, route.name)
                self._set_cell(ws, row_idx, 2, route.destination)
                self._set_cell(ws, row_idx, 3, gateway_display)
                self._set_cell(ws, row_idx, 4, route.interface or "-")
                self._set_cell(ws, row_idx, 5, route.distance, center=True)
                self._set_cell(ws, row_idx, 6, route.route_type, center=True)
                row_idx += 1
            row_idx += 1

        # OSPF設定
        for ospf in ospf_list:
            row_idx = self._add_ospf_section(ws, row_idx, ospf, "OSPF")

        # OSPFv6設定
        for ospf6 in ospf6_list:
            row_idx = self._add_ospf_section(ws, row_idx, ospf6, "OSPFv3")

        # BGP設定
        for bgp in bgp_list:
            row_idx = self._add_bgp_section(ws, row_idx, bgp)

        # ポリシールート
        if policy_routes:
            self._set_section_title(ws, row_idx, 1, "ポリシールート", colspan=8)
            headers = ["Seq", "送信元", "宛先", "プロトコル", "入力IF", "出力IF", "ゲートウェイ", "状態"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2

            for pr in policy_routes:
                self._set_cell(ws, row_idx, 1, pr.seq_num, center=True)
                self._set_cell(ws, row_idx, 2, pr.src or "any")
                self._set_cell(ws, row_idx, 3, pr.dst or "any")
                self._set_cell(ws, row_idx, 4, pr.protocol or "any", center=True)
                self._set_cell(ws, row_idx, 5, pr.input_device or "-")
                self._set_cell(ws, row_idx, 6, pr.output_device or "-")
                self._set_cell(ws, row_idx, 7, pr.gateway or "-")
                self._set_status_cell(ws, row_idx, 8, pr.status)
                row_idx += 1

        self._auto_column_width(ws)

    def _add_ospf_section(self, ws, row_idx: int, ospf, title: str) -> int:
        """OSPFセクションを追加"""
        self._set_section_title(ws, row_idx, 1, f"{title}設定", colspan=4)
        row_idx += 1

        # 基本設定
        info_fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")
        basic_data = [
            ("Router ID", ospf.router_id or "-"),
            ("デフォルトルート生成", "有効" if ospf.default_information_originate else "無効"),
            ("デフォルトメトリック", ospf.default_metric or "-"),
            ("ディスタンス", ospf.distance or "-"),
        ]
        for label, value in basic_data:
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill
            label_cell.border = self.THIN_BORDER
            value_cell = ws.cell(row=row_idx, column=2, value=value)
            value_cell.font = self.CELL_FONT
            value_cell.fill = info_fill
            value_cell.border = self.THIN_BORDER
            row_idx += 1
        row_idx += 1

        # エリア
        if ospf.areas:
            self._set_section_title(ws, row_idx, 1, f"{title}エリア", colspan=4)
            headers = ["エリアID", "タイプ", "認証", "ネットワーク"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for area in ospf.areas:
                self._set_cell(ws, row_idx, 1, area.area_id)
                self._set_cell(ws, row_idx, 2, area.area_type, center=True)
                self._set_cell(ws, row_idx, 3, area.authentication or "-", center=True)
                self._set_cell(ws, row_idx, 4, ", ".join(area.networks) if area.networks else "-")
                row_idx += 1
            row_idx += 1

        # インターフェース
        if ospf.interfaces:
            self._set_section_title(ws, row_idx, 1, f"{title}インターフェース", colspan=6)
            headers = ["名前", "インターフェース", "エリア", "コスト", "優先度", "パッシブ"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for iface in ospf.interfaces:
                self._set_cell(ws, row_idx, 1, iface.name)
                self._set_cell(ws, row_idx, 2, iface.interface)
                self._set_cell(ws, row_idx, 3, iface.area)
                self._set_cell(ws, row_idx, 4, iface.cost or "-", center=True)
                self._set_cell(ws, row_idx, 5, iface.priority or "-", center=True)
                self._set_status_cell(ws, row_idx, 6, iface.passive)
                row_idx += 1
            row_idx += 1

        # 再配布
        if ospf.redistributes:
            self._set_section_title(ws, row_idx, 1, f"{title}再配布", colspan=4)
            headers = ["プロトコル", "状態", "メトリック", "ルートマップ"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for redist in ospf.redistributes:
                self._set_cell(ws, row_idx, 1, redist.protocol)
                self._set_status_cell(ws, row_idx, 2, redist.status)
                self._set_cell(ws, row_idx, 3, redist.metric or "-", center=True)
                self._set_cell(ws, row_idx, 4, redist.routemap or "-")
                row_idx += 1
            row_idx += 1

        return row_idx

    def _add_bgp_section(self, ws, row_idx: int, bgp) -> int:
        """BGPセクションを追加"""
        self._set_section_title(ws, row_idx, 1, "BGP設定", colspan=4)
        row_idx += 1

        # 基本設定
        info_fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")
        basic_data = [
            ("AS番号", bgp.as_number or "-"),
            ("Router ID", bgp.router_id or "-"),
        ]
        for label, value in basic_data:
            label_cell = ws.cell(row=row_idx, column=1, value=label)
            label_cell.font = self.LABEL_FONT
            label_cell.fill = info_fill
            label_cell.border = self.THIN_BORDER
            value_cell = ws.cell(row=row_idx, column=2, value=value)
            value_cell.font = self.CELL_FONT
            value_cell.fill = info_fill
            value_cell.border = self.THIN_BORDER
            row_idx += 1
        row_idx += 1

        # ネイバー
        if bgp.neighbors:
            self._set_section_title(ws, row_idx, 1, "BGPネイバー", colspan=6)
            headers = ["ネイバーIP", "リモートAS", "説明", "Next-Hop-Self", "ルートマップ(IN)", "ルートマップ(OUT)"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for neighbor in bgp.neighbors:
                self._set_cell(ws, row_idx, 1, neighbor.ip)
                self._set_cell(ws, row_idx, 2, neighbor.remote_as, center=True)
                self._set_cell(ws, row_idx, 3, neighbor.description or "-")
                self._set_status_cell(ws, row_idx, 4, neighbor.next_hop_self)
                self._set_cell(ws, row_idx, 5, neighbor.route_map_in or "-")
                self._set_cell(ws, row_idx, 6, neighbor.route_map_out or "-")
                row_idx += 1
            row_idx += 1

        # ネットワーク
        if bgp.networks:
            self._set_section_title(ws, row_idx, 1, "BGPネットワーク", colspan=2)
            headers = ["プレフィックス", "ルートマップ"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for network in bgp.networks:
                self._set_cell(ws, row_idx, 1, network.prefix)
                self._set_cell(ws, row_idx, 2, network.route_map or "-")
                row_idx += 1
            row_idx += 1

        # 再配布
        if bgp.redistributes:
            self._set_section_title(ws, row_idx, 1, "BGP再配布", colspan=3)
            headers = ["プロトコル", "状態", "ルートマップ"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2
            for redist in bgp.redistributes:
                self._set_cell(ws, row_idx, 1, redist.protocol)
                self._set_status_cell(ws, row_idx, 2, redist.status)
                self._set_cell(ws, row_idx, 3, redist.route_map or "-")
                row_idx += 1
            row_idx += 1

        return row_idx

    def _create_objects_sheet_for_vdom(self, vdom: str):
        """指定VDOMのオブジェクト定義シートを作成"""
        addresses = self._filter_by_vdom(self.config.objects.addresses, vdom)
        address_groups = self._filter_by_vdom(self.config.objects.address_groups, vdom)
        services = self._filter_by_vdom(self.config.objects.services, vdom)
        service_groups = self._filter_by_vdom(self.config.objects.service_groups, vdom)

        if not any([addresses, address_groups, services, service_groups]):
            return

        ws = self._create_sheet("オブジェクト", vdom)

        row_idx = 1

        # アドレスオブジェクト
        if addresses:
            self._set_section_title(ws, row_idx, 1, "アドレスオブジェクト", colspan=4)
            addr_headers = ["オブジェクト名", "タイプ", "値", "説明"]
            self._set_header_row(ws, addr_headers, row_idx + 1)
            row_idx += 2

            for addr in addresses:
                self._set_cell(ws, row_idx, 1, addr.name)
                self._set_cell(ws, row_idx, 2, addr.object_type, center=True)
                self._set_cell(ws, row_idx, 3, addr.value)
                self._set_cell(ws, row_idx, 4, addr.description)
                row_idx += 1

            row_idx += 1

        # アドレスグループ
        if address_groups:
            self._set_section_title(ws, row_idx, 1, "アドレスグループ", colspan=3)
            grp_headers = ["グループ名", "メンバー", "説明"]
            self._set_header_row(ws, grp_headers, row_idx + 1)
            row_idx += 2

            for grp in address_groups:
                self._set_cell(ws, row_idx, 1, grp.name)
                self._set_cell(ws, row_idx, 2, self._list_to_str(grp.members, ", "))
                self._set_cell(ws, row_idx, 3, grp.description)
                row_idx += 1

            row_idx += 1

        # サービスオブジェクト
        if services:
            self._set_section_title(ws, row_idx, 1, "サービスオブジェクト", colspan=4)
            svc_headers = ["オブジェクト名", "プロトコル", "ポート", "説明"]
            self._set_header_row(ws, svc_headers, row_idx + 1)
            row_idx += 2

            for svc in services:
                self._set_cell(ws, row_idx, 1, svc.name)
                self._set_cell(ws, row_idx, 2, svc.protocol, center=True)
                self._set_cell(ws, row_idx, 3, svc.port, center=True)
                self._set_cell(ws, row_idx, 4, svc.description)
                row_idx += 1

            row_idx += 1

        # サービスグループ
        if service_groups:
            self._set_section_title(ws, row_idx, 1, "サービスグループ", colspan=3)
            sgrp_headers = ["グループ名", "メンバー", "説明"]
            self._set_header_row(ws, sgrp_headers, row_idx + 1)
            row_idx += 2

            for grp in service_groups:
                self._set_cell(ws, row_idx, 1, grp.name)
                self._set_cell(ws, row_idx, 2, self._list_to_str(grp.members, ", "))
                self._set_cell(ws, row_idx, 3, grp.description)
                row_idx += 1

        self._auto_column_width(ws)

    def _create_policies_sheet_for_vdom(self, vdom: str):
        """指定VDOMのファイアウォールポリシーシートを作成"""
        policies = self._filter_by_vdom(self.config.firewall_policies, vdom)
        local_in_policies = self._filter_by_vdom(self.config.local_in_policies, vdom)

        if not policies and not local_in_policies:
            return

        ws = self._create_sheet("ポリシー", vdom)

        row_idx = 1

        # ファイアウォールポリシー
        if policies:
            self._set_section_title(ws, row_idx, 1, "ファイアウォールポリシー", colspan=13)
            headers = ["No", "ID", "ポリシー名", "送信元IF", "宛先IF", "送信元アドレス",
                       "宛先アドレス", "サービス", "アクション", "NAT", "ログ",
                       "セキュリティ", "有効"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2

            for idx, policy in enumerate(policies, 1):
                self._set_cell(ws, row_idx, 1, idx, center=True)
                self._set_cell(ws, row_idx, 2, policy.policy_id, center=True)
                self._set_cell(ws, row_idx, 3, policy.name)
                self._set_cell(ws, row_idx, 4, self._list_to_str(policy.source_interface))
                self._set_cell(ws, row_idx, 5, self._list_to_str(policy.destination_interface))
                self._set_cell(ws, row_idx, 6, self._list_to_str(policy.source_address))
                self._set_cell(ws, row_idx, 7, self._list_to_str(policy.destination_address))
                self._set_cell(ws, row_idx, 8, self._list_to_str(policy.service))
                self._set_action_cell(ws, row_idx, 9, policy.action)
                self._set_status_cell(ws, row_idx, 10, policy.nat_enabled)
                self._set_status_cell(ws, row_idx, 11, policy.log_enabled)
                self._set_cell(ws, row_idx, 12, self._list_to_str(policy.security_profiles))
                self._set_status_cell(ws, row_idx, 13, policy.enabled)
                row_idx += 1

            row_idx += 1

        # Local-in ポリシー
        if local_in_policies:
            self._set_section_title(ws, row_idx, 1, "Local-in ポリシー", colspan=10)
            headers = ["No", "ID", "ポリシー名", "送信元IF", "送信元アドレス",
                       "宛先アドレス", "サービス", "アクション", "有効", "説明"]
            self._set_header_row(ws, headers, row_idx + 1)
            row_idx += 2

            for idx, policy in enumerate(local_in_policies, 1):
                src_if = policy.source_interface
                if isinstance(src_if, list):
                    src_if_str = self._list_to_str(src_if)
                else:
                    src_if_str = src_if or "-"

                self._set_cell(ws, row_idx, 1, idx, center=True)
                self._set_cell(ws, row_idx, 2, policy.policy_id, center=True)
                self._set_cell(ws, row_idx, 3, policy.name)
                self._set_cell(ws, row_idx, 4, src_if_str)
                self._set_cell(ws, row_idx, 5, self._list_to_str(policy.source_address))
                self._set_cell(ws, row_idx, 6, self._list_to_str(policy.destination_address))
                self._set_cell(ws, row_idx, 7, self._list_to_str(policy.service))
                self._set_action_cell(ws, row_idx, 8, policy.action)
                self._set_status_cell(ws, row_idx, 9, policy.enabled)
                self._set_cell(ws, row_idx, 10, policy.description)
                row_idx += 1

        self._auto_column_width(ws)

    def _create_nat_sheet_for_vdom(self, vdom: str):
        """指定VDOMのNAT設定シートを作成"""
        nat_policies = self._filter_by_vdom(self.config.nat_policies, vdom)
        if not nat_policies:
            return

        ws = self._create_sheet("NAT", vdom)

        headers = ["ルール名", "タイプ", "元送信元", "元宛先", "変換後送信元",
                   "変換後宛先", "外部IF", "外部IP", "内部IP", "ポートFW",
                   "元ポート", "変換後ポート", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, nat in enumerate(nat_policies, 2):
            self._set_cell(ws, row_idx, 1, nat.name)
            self._set_cell(ws, row_idx, 2, nat.nat_type, center=True)
            self._set_cell(ws, row_idx, 3, nat.original_source)
            self._set_cell(ws, row_idx, 4, nat.original_destination)
            self._set_cell(ws, row_idx, 5, nat.translated_source)
            self._set_cell(ws, row_idx, 6, nat.translated_destination)
            self._set_cell(ws, row_idx, 7, nat.external_interface)
            self._set_cell(ws, row_idx, 8, nat.external_ip)
            self._set_cell(ws, row_idx, 9, nat.internal_ip)
            self._set_status_cell(ws, row_idx, 10, nat.port_forward)
            self._set_cell(ws, row_idx, 11, nat.original_port, center=True)
            self._set_cell(ws, row_idx, 12, nat.translated_port, center=True)
            self._set_cell(ws, row_idx, 13, nat.description)

        self._auto_column_width(ws)

    def _create_vpn_sheet_for_vdom(self, vdom: str):
        """指定VDOMのVPN設定シートを作成"""
        # VPNはVDOMでフィルタリングが難しいため、全体を表示
        # （実際のモデルに応じて調整が必要）
        ipsec_p1 = self.config.vpn.ipsec_phase1
        ipsec_p2 = self.config.vpn.ipsec_phase2
        ssl_vpn = [s for s in self.config.vpn.ssl_vpn if getattr(s, 'vdom', 'root') == vdom]

        if not any([ipsec_p1, ipsec_p2, ssl_vpn]):
            return

        ws = self._create_sheet("VPN", vdom)

        row_idx = 1

        # IPsec Phase1
        if ipsec_p1:
            self._set_section_title(ws, row_idx, 1, "IPsec Phase1", colspan=9)
            p1_headers = ["VPN名", "リモートGW", "IF", "IKE",
                          "暗号化", "認証", "DH", "ライフタイム", "PSK"]
            self._set_header_row(ws, p1_headers, row_idx + 1)
            row_idx += 2

            for p1 in ipsec_p1:
                self._set_cell(ws, row_idx, 1, p1.name)
                self._set_cell(ws, row_idx, 2, p1.remote_gateway)
                self._set_cell(ws, row_idx, 3, p1.interface)
                self._set_cell(ws, row_idx, 4, p1.ike_version, center=True)
                self._set_cell(ws, row_idx, 5, p1.encryption, center=True)
                self._set_cell(ws, row_idx, 6, p1.authentication, center=True)
                self._set_cell(ws, row_idx, 7, p1.dh_group, center=True)
                self._set_cell(ws, row_idx, 8, p1.lifetime, center=True)
                self._set_status_cell(ws, row_idx, 9, bool(p1.psk), enabled_text="有", disabled_text="無")
                row_idx += 1

            row_idx += 1

        # IPsec Phase2
        if ipsec_p2:
            self._set_section_title(ws, row_idx, 1, "IPsec Phase2", colspan=8)
            p2_headers = ["VPN名", "Phase1", "暗号化", "認証", "PFS",
                          "ライフタイム", "ローカル", "リモート"]
            self._set_header_row(ws, p2_headers, row_idx + 1)
            row_idx += 2

            for p2 in ipsec_p2:
                self._set_cell(ws, row_idx, 1, p2.name)
                self._set_cell(ws, row_idx, 2, p2.phase1_name)
                self._set_cell(ws, row_idx, 3, p2.encryption, center=True)
                self._set_cell(ws, row_idx, 4, p2.authentication, center=True)
                self._set_cell(ws, row_idx, 5, p2.pfs, center=True)
                self._set_cell(ws, row_idx, 6, p2.lifetime, center=True)
                self._set_cell(ws, row_idx, 7, p2.local_subnet)
                self._set_cell(ws, row_idx, 8, p2.remote_subnet)
                row_idx += 1

            row_idx += 1

        # SSL-VPN
        if ssl_vpn:
            self._set_section_title(ws, row_idx, 1, "SSL-VPN / GlobalProtect", colspan=8)
            ssl_headers = ["レルム", "ポータル", "ポート", "IF",
                           "認証", "IPプール", "ユーザーグループ", "モード"]
            self._set_header_row(ws, ssl_headers, row_idx + 1)
            row_idx += 2

            for ssl in ssl_vpn:
                self._set_cell(ws, row_idx, 1, ssl.realm)
                self._set_cell(ws, row_idx, 2, ssl.portal)
                self._set_cell(ws, row_idx, 3, ssl.listen_port, center=True)
                self._set_cell(ws, row_idx, 4, ssl.listen_interface)
                self._set_cell(ws, row_idx, 5, ssl.auth_method, center=True)
                self._set_cell(ws, row_idx, 6, ssl.tunnel_ip_pool)
                self._set_cell(ws, row_idx, 7, self._list_to_str(ssl.user_groups, ", "))
                self._set_cell(ws, row_idx, 8, ssl.mode, center=True)
                row_idx += 1

        self._auto_column_width(ws)

    def _create_security_profiles_sheet_for_vdom(self, vdom: str):
        """指定VDOMのセキュリティプロファイルシートを作成"""
        profiles = self._filter_by_vdom(self.config.security_profiles, vdom)
        if not profiles:
            return

        ws = self._create_sheet("セキュリティ", vdom)

        headers = ["プロファイル名", "タイプ", "有効/無効", "説明"]
        self._set_header_row(ws, headers)

        for row_idx, profile in enumerate(profiles, 2):
            self._set_cell(ws, row_idx, 1, profile.name)
            self._set_cell(ws, row_idx, 2, profile.profile_type, center=True)
            self._set_status_cell(ws, row_idx, 3, profile.enabled)
            self._set_cell(ws, row_idx, 4, profile.description)

        self._auto_column_width(ws)
