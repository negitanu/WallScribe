#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TextFSM実行ユーティリティ
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Sequence

import textfsm

logger = logging.getLogger(__name__)

_TEMPLATE_ROOT = Path(__file__).parent / "textfsm_templates"


def run_textfsm(template_name: str, text_or_lines: str | Sequence[str]) -> List[Dict[str, str]]:
    """TextFSMテンプレートを実行して辞書リストを返す。"""
    template_path = _TEMPLATE_ROOT / template_name
    # パストラバーサル対策: 解決後のパスがテンプレートルート配下か検証
    try:
        resolved = template_path.resolve(strict=False)
        if not resolved.is_relative_to(_TEMPLATE_ROOT.resolve()):
            logger.debug("TextFSM template path traversal attempt: %s", template_name)
            return []
    except ValueError:
        logger.debug("TextFSM template invalid path: %s", template_name)
        return []

    if not template_path.is_file():
        logger.debug("TextFSM template not found: %s", template_path)
        return []

    if isinstance(text_or_lines, str):
        input_text = text_or_lines
    else:
        input_text = "\n".join(text_or_lines)

    try:
        with open(template_path, "r", encoding="utf-8") as tpl_file:
            parser = textfsm.TextFSM(tpl_file)
            rows = parser.ParseText(input_text)
    except Exception as exc:
        logger.debug("TextFSM parse failed (%s): %s", template_name, exc)
        return []

    headers = [h.lower() for h in parser.header]
    result = [{headers[idx]: value for idx, value in enumerate(row)} for row in rows]
    logger.debug("TextFSM matched template=%s rows=%d", template_name, len(result))
    return result
