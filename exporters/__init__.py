"""エクスポーターモジュール"""

from typing import Any, Optional

from .html import HTMLExporter

__all__ = ["HTMLExporter"]

# PDFExporterはweasyprintが必要なため、条件付きでインポート
PDFExporter: Optional[Any]
try:
    from .pdf import PDFExporter

    __all__.append("PDFExporter")
except (ImportError, OSError):
    PDFExporter = None  # weasyprint またはネイティブ依存が利用できない場合
