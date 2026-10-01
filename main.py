#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ファイアウォール パラメータシート生成ツール - CLI
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from analyzers import (
    analyze_cleanup,
    analyze_review,
    analyze_security,
    infer_topology,
    investigate_flow,
)
from exporters.html import HTMLExporter
from models.cluster import ClusterConfig
from services.conversion import (
    ExportCapabilities,
    UnsupportedConfigFormat,
    export_config,
    parse_paths,
)

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

    parser.add_argument(
        "--analysis-json",
        type=Path,
        help="セキュリティ診断・推定ネットワーク構造を JSON に追加出力",
    )

    parser.add_argument(
        "--flow",
        nargs=4,
        metavar=("SOURCE", "DEST", "PROTOCOL", "PORT"),
        help="通信候補を照合。JSON 指定時は同じファイルに格納、未指定時は標準出力",
    )
    parser.add_argument(
        "--firmware-version", help="実機で確認したファームウェアの版。クラスタでは代表機にのみ適用"
    )
    parser.add_argument("--flow-scope", default="root", help="通信照合の VDOM/vsys")
    parser.add_argument("--source-interface", default="", help="送信元 IF/ゾーン（任意）")
    parser.add_argument("--destination-interface", default="", help="宛先 IF/ゾーン（任意）")

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

    if args.ha_mode != "single" and not (args.ha_mode == "auto" and len(input_paths) == 1):
        logger.info(f"HAクラスタモード: {len(input_paths)} ファイルを読み込み")
        for path in input_paths:
            logger.info(f"  - {path}")
    else:
        logger.info(f"ファイル読み込み: {input_paths[0]}")

    try:
        parse_result = parse_paths([Path(path) for path in input_paths], ha_mode=args.ha_mode)
    except UnsupportedConfigFormat as e:
        logger.error(str(e))
        logger.info("対応形式: .conf (FortiGate), .xml (Palo Alto)")
        sys.exit(1)

    config = parse_result.config
    is_cluster = parse_result.is_cluster
    if args.firmware_version:
        representative = config.primary_config if isinstance(config, ClusterConfig) else config
        if representative is None:
            raise ValueError("ファームウェアの版を指定できる設定がありません")
        representative.device_info.os_version = args.firmware_version
        representative.device_info.os_version_source = "human supplied CLI"

    if is_cluster:
        cluster_info = config.cluster_info
        logger.info(f"HAクラスタを検出: グループID={cluster_info.group_id}")
        logger.info(f"メンバー数: {cluster_info.get_member_count()}")
        for member in cluster_info.members:
            logger.info(f"  - {member.hostname} ({member.role.value}, Priority: {member.priority})")

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

    if args.analysis_json:
        protected_paths = {Path(path).resolve() for path in input_paths}
        protected_paths.add(output_path.resolve())
        if args.format == "excel":
            protected_paths.add(output_path.with_suffix(".xlsx").resolve())
        if args.analysis_json.resolve() in protected_paths:
            raise ValueError(
                "診断 JSON の保存先は入力設定・出力レポートと別のパスを指定してください"
            )

    if args.format == "html":
        export_config(
            config,
            "html",
            output_path,
            ExportCapabilities(html_exporter_cls=HTMLExporter),
        )
        logger.info(f"HTML出力: {output_path}")
    elif args.format == "excel":
        if not EXCEL_AVAILABLE or ExcelExporter is None:
            raise RuntimeError(
                "Excel出力には openpyxl が必要です。requirements.txt をインストールしてください。"
            )
        # 出力ファイルの拡張子を.xlsxに変更
        if output_path.suffix.lower() != ".xlsx":
            output_path = output_path.with_suffix(".xlsx")
        export_config(
            config,
            "excel",
            output_path,
            ExportCapabilities(
                html_exporter_cls=HTMLExporter,
                excel_exporter_cls=ExcelExporter,
                excel_available=EXCEL_AVAILABLE,
            ),
        )
        logger.info(f"Excel出力: {output_path}")

    if args.analysis_json:
        representative = config.primary_config if isinstance(config, ClusterConfig) else config
        if representative is None:
            raise ValueError("診断できる設定がありません")
        payload = {
            "schema_version": 1,
            "scope": "primary_config" if isinstance(config, ClusterConfig) else "single_device",
            "security": analyze_security(representative).to_dict(),
            "topology": infer_topology(representative).to_dict(),
            "cleanup": analyze_cleanup(representative),
            "review": analyze_review(representative),
        }
        if args.flow:
            payload["flow"] = investigate_flow(
                representative,
                *args.flow[:3],
                port=int(args.flow[3]),
                scope=args.flow_scope,
                source_interface=args.source_interface,
                destination_interface=args.destination_interface,
            )
        args.analysis_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("診断 JSON 出力: %s", args.analysis_json)

    if args.flow and not args.analysis_json:
        representative = config.primary_config if isinstance(config, ClusterConfig) else config
        result = investigate_flow(
            representative,
            *args.flow[:3],
            port=int(args.flow[3]),
            scope=args.flow_scope,
            source_interface=args.source_interface,
            destination_interface=args.destination_interface,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    logger.info("完了")


if __name__ == "__main__":
    main()
