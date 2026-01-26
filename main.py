#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ファイアウォール パラメータシート生成ツール - CLI
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Union

from exporters.html import HTMLExporter
from models.cluster import ClusterConfig
from models.config import ConfigModel
from parsers.base import get_parser_for_file
from parsers.cluster import parse_ha_cluster

try:
    import exporters.excel as excel_module  # type: ignore

    ExcelExporter = excel_module.ExcelExporter  # type: ignore[attr-defined]
    EXCEL_AVAILABLE = bool(getattr(excel_module, "OPENPYXL_AVAILABLE", True))
except ImportError:
    ExcelExporter = None  # type: ignore[assignment]
    EXCEL_AVAILABLE = False

__version__ = "1.1"

# ロギング設定
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_args():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description="ファイアウォール設定ファイルからパラメータシートを生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python main.py fortigate.conf -o output.html
  python main.py pa440.xml -o pa_param.html
  python main.py config.conf -v
  python main.py primary.conf secondary.conf -o ha_cluster.html

HA構成:
  複数ファイルを指定すると、HAクラスタとして処理します。
  python main.py primary.conf secondary.conf --ha-mode auto

対応形式:
  FortiGate: .conf (FortiOS 6.x/7.x)
  Palo Alto: .xml (PAN-OS 10.x/11.x)
""",
    )

    parser.add_argument(
        "input_files",
        nargs="+",
        help="入力設定ファイル (.conf または .xml)。複数指定でHA構成として処理",
    )

    parser.add_argument(
        "-o", "--output", default="output.html", help="出力ファイルパス (デフォルト: output.html)"
    )

    parser.add_argument(
        "-f",
        "--format",
        choices=["html", "excel"],
        default="html",
        help="出力形式 (デフォルト: html)",
    )

    parser.add_argument(
        "--ha-mode",
        choices=["auto", "single", "cluster"],
        default="auto",
        help="HAモード: auto=自動判定, single=単一機器として処理, cluster=クラスタとして処理 (デフォルト: auto)",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="詳細ログを出力")

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    return parser.parse_args()


def main():
    """メイン処理"""
    args = parse_args()

    # 詳細ログ設定
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ファイル存在確認
    input_paths = []
    for input_file in args.input_files:
        input_path = Path(input_file)
        if not input_path.exists():
            logger.error(f"ファイルが見つかりません: {input_path}")
            sys.exit(1)
        input_paths.append(str(input_path))

    # HAモード判定と処理
    config: Union[ConfigModel, ClusterConfig]
    is_cluster = False

    if args.ha_mode == "single" or (args.ha_mode == "auto" and len(input_paths) == 1):
        # 単一ファイルモード
        logger.info(f"ファイル読み込み: {input_paths[0]}")

        parser = get_parser_for_file(input_paths[0])
        if parser is None:
            logger.error(f"サポートされていないファイル形式です: {Path(input_paths[0]).suffix}")
            logger.info("対応形式: .conf (FortiGate), .xml (Palo Alto)")
            sys.exit(1)

        logger.info(f"{parser.__class__.__name__} でパース中...")
        config = parser.parse(input_paths[0])

        if parser.errors:
            for error in parser.errors:
                logger.warning(error)
    else:
        # 複数ファイル（HAクラスタ）モード
        logger.info(f"HAクラスタモード: {len(input_paths)} ファイルを読み込み")
        for path in input_paths:
            logger.info(f"  - {path}")

        cluster_config = parse_ha_cluster(input_paths)

        if cluster_config.is_cluster:
            logger.info(f"HAクラスタを検出: グループID={cluster_config.cluster_info.group_id}")
            logger.info(f"メンバー数: {cluster_config.cluster_info.get_member_count()}")
            for member in cluster_config.cluster_info.members:
                logger.info(
                    f"  - {member.hostname} ({member.role.value}, Priority: {member.priority})"
                )
            is_cluster = True
        else:
            logger.info("HAクラスタ構成は検出されませんでした。最初のファイルを使用します。")

        config = cluster_config

    # サマリー表示
    summary = config.get_summary()
    logger.info(f"機器タイプ: {summary['device_type']}")
    logger.info(f"ホスト名: {summary['hostname']}")
    logger.info(f"バージョン: {summary['version']}")
    logger.info(
        f"パース完了: {summary.get('policies', 0)}ポリシー、{summary.get('objects', 0)}オブジェクト"
    )

    if is_cluster:
        logger.info(f"HAモード: {summary.get('ha_mode', '-')}")
        logger.info(f"メンバー数: {summary.get('member_count', 0)}")

    # 出力
    output_path = Path(args.output)

    if args.format == "html":
        exporter = HTMLExporter(config)
        exporter.export(str(output_path))
        logger.info(f"HTML出力: {output_path}")
    elif args.format == "excel":
        if not EXCEL_AVAILABLE or ExcelExporter is None:
            raise RuntimeError(
                "Excel出力には openpyxl が必要です。requirements.txt をインストールしてください。"
            )
        # 出力ファイルの拡張子を.xlsxに変更
        if output_path.suffix.lower() != ".xlsx":
            output_path = output_path.with_suffix(".xlsx")
        exporter = ExcelExporter(config)
        exporter.export(str(output_path))
        logger.info(f"Excel出力: {output_path}")

    logger.info("完了")


if __name__ == "__main__":
    main()
