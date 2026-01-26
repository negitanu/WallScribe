#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDFエクスポーター
HTMLExporterを再利用してHTMLを生成し、WeasyPrintでPDFに変換

パフォーマンス最適化:
- CSSオブジェクトのキャッシュ（WeasyPrintのCSS解析は重いため）
- FontConfigurationの再利用
- Bootstrap除外による軽量CSS使用
"""

from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime
import logging

from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from models.config import ConfigModel
from models.cluster import ClusterConfig
from exporters.html import HTMLExporter

logger = logging.getLogger(__name__)

# 静的ファイルのベースパス
STATIC_DIR = Path(__file__).parent.parent / "static"

# グローバルキャッシュ（パフォーマンス最適化）
_pdf_css_cache: Optional[str] = None
_pdf_css_object_cache: Optional[CSS] = None  # パース済みCSSオブジェクト
_font_config_cache: Optional[FontConfiguration] = None


class PDFExporter:
    """PDF形式でパラメータシートを出力"""

    def __init__(self, config: Union[ConfigModel, ClusterConfig], sections: List[str] = None):
        """PDFエクスポーターを初期化

        Args:
            config: 設定データモデル
            sections: 出力するセクションのリスト（Noneの場合は全セクション）
        """
        # HTMLExporter は ClusterConfig も扱えるため、HTML生成は渡された config をそのまま使う。
        self.export_config = config

        # ヘッダー等で参照する代表ConfigModelを解決（ClusterConfig の場合は primary_config を使用）
        if isinstance(config, ClusterConfig):
            self.config = config.primary_config if config.primary_config else ConfigModel()
            self.cluster_config: Optional[ClusterConfig] = config
        else:
            self.config = config
            self.cluster_config = None

        # PDF用に最適化されたHTMLExporterを使用（JavaScript削除など）
        self.html_exporter = HTMLExporter(self.export_config, sections=sections, for_pdf=True)

    def export(self, output_path: str) -> str:
        """PDFを生成

        Args:
            output_path: 出力ファイルパス

        Returns:
            str: 出力ファイルパス

        パフォーマンス最適化:
        - CSSオブジェクトをキャッシュして再利用（解析コスト削減）
        - FontConfigurationを再利用
        - presentational_hints=Falseで高速化
        """
        # HTMLを生成（PDF用に最適化、Bootstrap除外で軽量）
        html_content = self.html_exporter.export()

        # PDF用のCSSオブジェクトを取得（パース済みをキャッシュから）
        pdf_css_obj = self._get_pdf_css_object()

        # 動的なヘッダーCSS（ホスト名・日付が変わるためキャッシュ不可）
        header_css = CSS(string=self._generate_header_css())

        try:
            # FontConfigurationを再利用（キャッシュから）
            font_config = self._get_font_config()

            # HTMLドキュメントを作成
            html_doc = HTML(string=html_content)

            # PDFを生成（最適化オプション付き）
            html_doc.write_pdf(
                output_path,
                stylesheets=[pdf_css_obj, header_css],
                font_config=font_config,
                optimize_images=True,  # 画像最適化
                presentational_hints=False,  # HTML属性からのスタイル推論を無効化（高速化）
            )

            logger.info(f"PDF出力完了: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"PDF生成エラー: {e}", exc_info=True)
            raise

    def _generate_header_css(self) -> str:
        """動的なヘッダーCSSを生成（ホスト名と作成日を含む）"""
        # ClusterConfig を渡された場合も考慮して安全にホスト名/クラスタ名を取得
        hostname = "Unknown"
        if self.cluster_config is not None:
            hostname = (
                self.cluster_config.cluster_info.cluster_name
                or (self.config.device_info.hostname if self.config else "")
                or "Unknown"
            )
        else:
            hostname = self.config.device_info.hostname or "Unknown"
        created_date = datetime.now().strftime("%Y-%m-%d")

        return f"""
        @page {{
            @top-center {{
                content: "パラメータシート - {hostname} ({created_date})";
                font-size: 10pt;
                color: #666;
                font-family: 'Noto Sans CJK JP', 'Noto Sans CJK', 'Meiryo', sans-serif;
            }}
        }}
        """

    @staticmethod
    def _get_pdf_css() -> str:
        """PDF用のCSS文字列を返す（キャッシュから読み込み）"""
        global _pdf_css_cache

        if _pdf_css_cache is None:
            css_path = STATIC_DIR / "css" / "pdf.css"
            try:
                _pdf_css_cache = css_path.read_text(encoding="utf-8")
                logger.debug("PDF用CSSをキャッシュに読み込みました")
            except FileNotFoundError:
                logger.warning(f"PDF用CSSファイルが見つかりません: {css_path}")
                _pdf_css_cache = PDFExporter._get_fallback_pdf_css()

        return _pdf_css_cache

    @staticmethod
    def _get_pdf_css_object() -> CSS:
        """PDF用のパース済みCSSオブジェクトを返す（キャッシュから再利用）

        WeasyPrintのCSS解析は重い処理のため、一度パースしたCSSオブジェクトを
        キャッシュして再利用することで、2回目以降のPDF生成を高速化します。
        """
        global _pdf_css_object_cache

        if _pdf_css_object_cache is None:
            css_string = PDFExporter._get_pdf_css()
            _pdf_css_object_cache = CSS(string=css_string)
            logger.debug("PDF用CSSオブジェクトをキャッシュに作成しました")

        return _pdf_css_object_cache

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
        return """
        @page { size: A3 landscape; margin: 1.5cm; }
        body { font-family: sans-serif; font-size: 9pt; }
        table { width: 100%; border-collapse: collapse; font-size: 7pt; }
        th, td { border: 1px solid #ddd; padding: 4px; }
        section { page-break-inside: avoid; }
        """
