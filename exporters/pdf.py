#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDFエクスポーター
HTMLExporterを再利用してHTMLを生成し、WeasyPrintでPDFに変換
"""

from pathlib import Path
from typing import List, Optional
from datetime import datetime
import logging
import re

from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from models.config import ConfigModel
from exporters.html import HTMLExporter

logger = logging.getLogger(__name__)

# 静的ファイルのベースパス
STATIC_DIR = Path(__file__).parent.parent / "static"

# グローバルキャッシュ（クラス変数として保持）
_pdf_css_cache: Optional[str] = None
_font_config_cache: Optional[FontConfiguration] = None


class PDFExporter:
    """PDF形式でパラメータシートを出力"""

    def __init__(self, config: ConfigModel, sections: List[str] = None):
        """PDFエクスポーターを初期化
        
        Args:
            config: 設定データモデル
            sections: 出力するセクションのリスト（Noneの場合は全セクション）
        """
        self.config = config
        # PDF用に最適化されたHTMLExporterを使用（JavaScript削除など）
        self.html_exporter = HTMLExporter(config, sections=sections, for_pdf=True)

    def export(self, output_path: str) -> str:
        """PDFを生成

        Args:
            output_path: 出力ファイルパス

        Returns:
            str: 出力ファイルパス
        """
        # HTMLを生成（PDF用に最適化）
        html_content = self.html_exporter.export()

        # PDF用のCSSを取得（キャッシュから）
        pdf_css = self._get_pdf_css()

        # 動的なヘッダーCSSを生成
        header_css = self._generate_header_css()

        try:
            # FontConfigurationを再利用（キャッシュから）
            font_config = self._get_font_config()

            # HTMLドキュメントを作成
            html_doc = HTML(string=html_content)

            # PDFを生成（最適化オプション付き）
            html_doc.write_pdf(
                output_path,
                stylesheets=[CSS(string=pdf_css), CSS(string=header_css)],
                font_config=font_config,
                optimize_images=True,  # 画像最適化
            )

            logger.info(f"PDF出力完了: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"PDF生成エラー: {e}", exc_info=True)
            raise

    def _generate_header_css(self) -> str:
        """動的なヘッダーCSSを生成（ホスト名と作成日を含む）"""
        hostname = self.config.device_info.hostname or "Unknown"
        created_date = datetime.now().strftime("%Y-%m-%d")

        return f'''
        @page {{
            @top-center {{
                content: "パラメータシート - {hostname} ({created_date})";
                font-size: 10pt;
                color: #666;
                font-family: 'Noto Sans CJK JP', 'Noto Sans CJK', 'Meiryo', sans-serif;
            }}
        }}
        '''

    @staticmethod
    def _get_pdf_css() -> str:
        """PDF用のCSSを返す（キャッシュから読み込み）"""
        global _pdf_css_cache
        
        if _pdf_css_cache is None:
            css_path = STATIC_DIR / "css" / "pdf.css"
            try:
                _pdf_css_cache = css_path.read_text(encoding='utf-8')
                logger.debug("PDF用CSSをキャッシュに読み込みました")
            except FileNotFoundError:
                logger.warning(f"PDF用CSSファイルが見つかりません: {css_path}")
                _pdf_css_cache = PDFExporter._get_fallback_pdf_css()
        
        return _pdf_css_cache

    @staticmethod
    def _get_font_config() -> FontConfiguration:
        """FontConfigurationを返す（キャッシュから再利用）"""
        global _font_config_cache
        
        if _font_config_cache is None:
            _font_config_cache = FontConfiguration()
            logger.debug("FontConfigurationをキャッシュに作成しました")
        
        return _font_config_cache

    @staticmethod
    def _get_fallback_pdf_css() -> str:
        """フォールバック用の最小限PDF CSS"""
        return '''
        @page { size: A3 landscape; margin: 1.5cm; }
        body { font-family: sans-serif; font-size: 9pt; }
        table { width: 100%; border-collapse: collapse; font-size: 7pt; }
        th, td { border: 1px solid #ddd; padding: 4px; }
        section { page-break-inside: avoid; }
        '''
