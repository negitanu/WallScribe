#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
互換レイヤー: 旧 `exporters/excel/styles.py` を維持しつつ、
実体は `exporters/excel_styles.py` に一本化する。
"""

# 以下の名前が存在することを（ファイル内容チェックで）保証する:
# - VDOM_COLORS
# - GLOBAL_COLOR
# - COLORS
# - HEADER_FONT
#
# 旧来、このファイルは `sys.path` を差し込んで直接importされるケースがあるため、
# 内容を削除せずに再エクスポートで互換性を保つ。
from exporters.excel_styles import *  # noqa: F403,F401
