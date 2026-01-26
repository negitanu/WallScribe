"""エクスポーターモジュール"""

from typing import Any, Optional

from .html import HTMLExporter

__all__ = ["HTMLExporter"]

# PDFExporterはweasprintが必要なため、条件付きでインポート
PDFExporter: Optional[Any]
try:
    from .pdf import PDFExporter

    __all__.append("PDFExporter")
except ImportError:
    PDFExporter = None  # weasprintがインストールされていない場合
