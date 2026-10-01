"""Excel sheets for configuration findings and the inferred topology model."""

from analyzers import analyze_security, infer_topology
from exporters.insights import SEVERITY


class ExcelInsightsMixin:
    def _create_security_analysis_sheet(self):
        report = analyze_security(self.config)
        if self.cluster_config is not None:
            report.limitations.append(
                "クラスタ代表機の設定を診断しています。メンバーごとの設定差分は対象外です。"
            )
        ws = self._create_sheet("セキュリティ診断")
        headers = [
            "重要度",
            "ルール ID",
            "指摘",
            "区画",
            "対象",
            "根拠",
            "改善案",
            "確信度",
            "参照",
        ]
        self._set_header_row(ws, headers)
        row = 2
        for finding in report.findings:
            values = [
                SEVERITY[finding.severity],
                finding.rule_id,
                finding.title,
                finding.scope,
                finding.target,
                finding.evidence,
                finding.recommendation,
                finding.confidence,
                finding.reference,
            ]
            for column, value in enumerate(values, 1):
                self._set_cell(ws, row, column, value)
            row += 1
        if not report.findings:
            self._set_cell(ws, row, 1, "対応する診断項目では指摘が見つかりませんでした。")
            row += 1
        self._set_section_title(ws, row + 1, 1, "検査範囲と限界", colspan=9)
        self._set_cell(ws, row + 2, 1, "検査項目: " + ", ".join(report.checks))
        for offset, limitation in enumerate(report.limitations, row + 3):
            self._set_cell(ws, offset, 1, limitation)
        self._auto_column_width(ws)

    def _create_topology_sheet(self):
        topology = infer_topology(self.config)
        if self.cluster_config is not None:
            topology.limitations.append("クラスタ代表機の論理構造です。HA の物理配線は対象外です。")
        ws = self._create_sheet("推定ネットワーク構造")
        self._set_section_title(ws, 1, 1, "構造ノード（HTML / PDF では図示）", colspan=6)
        self._set_header_row(ws, ["ID", "区画", "種別", "ラベル", "詳細", "状態"], 2)
        row = 3
        for node in topology.nodes:
            for column, value in enumerate(
                [node.id, node.scope, node.kind, node.label, "; ".join(node.details), node.status],
                1,
            ):
                self._set_cell(ws, row, column, value)
            row += 1
        row += 1
        self._set_section_title(ws, row, 1, "接続・推定の根拠", colspan=5)
        self._set_header_row(ws, ["接続元 ID", "接続先 ID", "関係", "確度", "根拠"], row + 1)
        row += 2
        for edge in topology.edges:
            for column, value in enumerate(
                [edge.source, edge.target, edge.relation, edge.confidence, edge.evidence], 1
            ):
                self._set_cell(ws, row, column, value)
            row += 1
        for offset, limitation in enumerate(topology.limitations, row + 1):
            self._set_cell(ws, offset, 1, limitation)
        self._auto_column_width(ws)

    def _create_flow_analysis_sheet(self):
        ws = self._create_sheet("通信候補の確認")
        self._set_header_row(ws, ["機能", "利用方法", "判断範囲"])
        for column, value in enumerate(
            [
                "通信候補の確認",
                "HTML レポートのフォームまたは CLI --flow SOURCE DEST TCP PORT --analysis-json result.json",
                "静的な候補照合です。実効経路・NAT 適用・疎通は人が確認します。",
            ],
            1,
        ):
            self._set_cell(ws, 2, column, value)
        self._auto_column_width(ws)
