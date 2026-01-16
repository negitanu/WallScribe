#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ファイアウォール パラメータシート生成ツール - CLI
"""

import argparse
import sys
import logging
from pathlib import Path

from parsers.base import get_parser_for_file
from exporters.html import HTMLExporter

__version__ = "1.0.0"

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description='ファイアウォール設定ファイルからパラメータシートを生成',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  python main.py fortigate.conf -o output.html
  python main.py pa440.xml -o pa_param.html
  python main.py config.conf -v

対応形式:
  FortiGate: .conf (FortiOS 6.x/7.x)
  Palo Alto: .xml (PAN-OS 10.x/11.x)
'''
    )

    parser.add_argument(
        'input_file',
        help='入力設定ファイル (.conf または .xml)'
    )

    parser.add_argument(
        '-o', '--output',
        default='output.html',
        help='出力ファイルパス (デフォルト: output.html)'
    )

    parser.add_argument(
        '-f', '--format',
        choices=['html', 'excel'],
        default='html',
        help='出力形式 (デフォルト: html)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='詳細ログを出力'
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    return parser.parse_args()


def main():
    """メイン処理"""
    args = parse_args()

    # 詳細ログ設定
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    input_path = Path(args.input_file)

    # ファイル存在確認
    if not input_path.exists():
        logger.error(f"ファイルが見つかりません: {input_path}")
        sys.exit(1)

    logger.info(f"ファイル読み込み: {input_path}")

    # パーサー取得
    parser = get_parser_for_file(str(input_path))
    if parser is None:
        logger.error(f"サポートされていないファイル形式です: {input_path.suffix}")
        logger.info("対応形式: .conf (FortiGate), .xml (Palo Alto)")
        sys.exit(1)

    # パース実行
    logger.info(f"{parser.__class__.__name__} でパース中...")
    config = parser.parse(str(input_path))

    if parser.errors:
        for error in parser.errors:
            logger.warning(error)

    # サマリー表示
    summary = config.get_summary()
    logger.info(f"機器タイプ: {summary['device_type']}")
    logger.info(f"ホスト名: {summary['hostname']}")
    logger.info(f"バージョン: {summary['version']}")
    logger.info(f"パース完了: {summary['policies']}ポリシー、{summary['objects']}オブジェクト")

    # 出力
    output_path = Path(args.output)

    if args.format == 'html':
        exporter = HTMLExporter(config)
        exporter.export(str(output_path))
        logger.info(f"HTML出力: {output_path}")
    elif args.format == 'excel':
        logger.error("Excel出力は現在未実装です")
        sys.exit(1)

    logger.info("完了")


if __name__ == '__main__':
    main()
