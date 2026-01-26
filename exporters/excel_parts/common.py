#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExcelExporter 共通ヘルパー（セル/見出し/列幅など）

Excel本体クラスから切り出して巨大化を抑制する。
"""

from __future__ import annotations

from typing import Any, List, Optional

from models.config import PolicyAction

try:
    from openpyxl.styles import Alignment, Border, Side  # type: ignore
    from openpyxl.worksheet.worksheet import Worksheet  # type: ignore
except ImportError:  # pragma: no cover
    from exporters.excel_styles import Alignment, Border, Side  # type: ignore

    Worksheet = Any  # type: ignore


class ExcelCommonMixin:
    """ExcelExporter用の共通ヘルパー群（mixin）"""

    def _create_sheet(self, title: str, vdom: Optional[str] = None) -> Worksheet:
        """シートを作成（VDOM名付きでタブ色を設定）"""
        # シート名を構築
        if vdom:
            full_title = f"{vdom} - {title}"
        else:
            full_title = title

        # シート名は31文字まで
        sheet_title = full_title[:31]
        ws = self.workbook.create_sheet(title=sheet_title)

        # タブ色を設定（16進数文字列をRGBオブジェクトに変換）
        try:
            from openpyxl.styles.colors import RGB  # type: ignore

            color = self._get_vdom_color(vdom) if vdom else self.GLOBAL_COLOR
            hex_color = color["tab_color"]
            if len(hex_color) == 6:
                hex_color = "FF" + hex_color
            ws.sheet_properties.tabColor = RGB(hex_color)
        except (ImportError, AttributeError, ValueError, TypeError):
            try:
                color = self._get_vdom_color(vdom) if vdom else self.GLOBAL_COLOR
                ws.sheet_properties.tabColor = color["tab_color"]
            except (AttributeError, TypeError):
                pass

        return ws

    def _set_header_row(self, ws: Worksheet, headers: List[str], row: int = 1):
        """ヘッダ行を設定（VDOMコンテキストの色を使用）"""
        styles = self._get_vdom_styles()
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = styles["header_font"]
            cell.fill = styles["header_fill"]
            cell.alignment = self.HEADER_ALIGNMENT
            cell.border = styles["header_border"]
        # 行の高さを少し広めに設定
        ws.row_dimensions[row].height = 28
        # まだフリーズペインが設定されていない場合は、このヘッダーの直下で固定する
        if getattr(ws, "freeze_panes", None) is None:
            ws.freeze_panes = ws.cell(row=row + 1, column=1)

    def _set_cell(
        self,
        ws: Worksheet,
        row: int,
        col: int,
        value: Any,
        fill=None,
        font=None,
        center: bool = False,
        is_status: bool = False,
        status_value: Optional[bool] = None,
    ):
        """セルに値を設定（VDOMコンテキストの色を使用）"""
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
            cell.font = font if font else self.CELL_FONT
            cell.alignment = self.CELL_ALIGNMENT_CENTER if center else self.CELL_ALIGNMENT

            # 背景色（ゼブラストライプ or 指定色）
            if fill:
                cell.fill = fill
            else:
                cell.fill = styles["row_alt_fill"] if row % 2 == 0 else self.ROW_FILL_EVEN

        cell.border = styles["border"]
        return cell

    def _set_status_cell(
        self,
        ws: Worksheet,
        row: int,
        col: int,
        enabled: bool,
        enabled_text: str = "有効",
        disabled_text: str = "無効",
    ):
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

    def _set_section_title(self, ws: Worksheet, row: int, col: int, title: str, colspan: int = 1):
        """セクションタイトルを設定（VDOMコンテキストの色を使用）"""
        styles = self._get_vdom_styles()
        cell = ws.cell(row=row, column=col, value=title)
        cell.font = styles["section_font"]
        cell.fill = styles["section_fill"]
        cell.alignment = Alignment(vertical="center")
        cell.border = Border(bottom=Side(style="medium", color=self._current_color["header_bg"]))
        ws.row_dimensions[row].height = 26
        if colspan > 1:
            ws.merge_cells(
                start_row=row, start_column=col, end_row=row, end_column=col + colspan - 1
            )
        return cell

    def _auto_column_width(self, ws: Worksheet, min_width: int = 8, max_width: int = 50):
        """列幅を自動調整"""
        try:
            from openpyxl.cell.cell import MergedCell  # type: ignore
        except Exception:
            return

        for column_cells in ws.columns:
            max_length = 0
            column_letter = None
            for cell in column_cells:
                if not isinstance(cell, MergedCell):
                    column_letter = getattr(cell, "column_letter", None)
                    break
            if column_letter is None:
                continue

            for cell in column_cells:
                if isinstance(cell, MergedCell):
                    continue
                try:
                    if cell.value:
                        cell_length = sum(2 if ord(c) > 127 else 1 for c in str(cell.value))
                        max_length = max(max_length, cell_length)
                except Exception:
                    pass

            adjusted_width = min(max(max_length + 2, min_width), max_width)
            ws.column_dimensions[column_letter].width = adjusted_width

    def _list_to_str(self, items: List[Any], separator: str = "\n") -> str:
        """リストを文字列に変換"""
        if not items:
            return "-"
        return separator.join(str(item) for item in items)
