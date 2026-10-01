# 構成とリファクタリング（2026-10-01）

## 責務

- `parsers/`: 入力設定を `models/` のモデルへ変換する。静的な通信照合・診断は `analyzers/` が担当する。
- `services/conversion.py`: CLI / Web / ジョブで共用するパースと出力の入口。
- `exporters/html.py`: HTMLExporter の互換入口、出力項目、目次、文書全体の組み立て。
- `exporters/html_parts/`: `tooltips.py` は名前解決とツールチップ、`network.py` はネットワーク、`vdom.py` はオブジェクト・ポリシー・NAT・VPN・セキュリティプロファイル、`global_sections.py` は機器・システム・クラスタ・HA・ログの描画。
- `exporters/excel_parts/`: Excel の各シートの描画。既存の `exporters/excel/styles.py` は互換用の再エクスポートとして残す。
- `exporters/sections.py`: HTML / Excel の出力項目選択と旧グループ名の互換解決。HTML の network と Excel の interfaces/routes/dhcp の粒度差を保持する。
- `exporters/insights.py`: 診断と論理構造の HTML/SVG。対象別の指摘インデックスを作り、IF・ルールごとに全指摘を走査する処理を避ける。
- `exporters/investigation.py` / `static/js/network_investigation.js`: 通信候補フォームとオフライン照合。Python と JS の候補判定は回帰テストで比較する。

## 撤去したもの

出力から削除済みの整理候補・解析範囲セクションの HTML / Excel 描画、判断記録ダウンロードの JS、専用 CSS を撤去した。CLI の分析 JSON に使う `analyzers/cleanup.py` と `analyzers/review.py` は維持している。JSON ログの日時は timezone-aware UTC に変更し、文字列形式は末尾 Z を保持する。

## 検証

変更前は388件成功、4件スキップ。HTML / Excel / クラスタ / CLI / Webアップロード / 非同期ジョブ / パーサー / 通信照合の既存テストを変更後も実行する。旧項目選択の互換解決について回帰テストを追加する。PDFのネイティブ依存がない環境ではPDF描画は検証対象外になる。

## 維持方針

公開クラスとimportパス、CLI、API、保存済みUI設定の互換を維持する。設定やアップロードの生成物は整理対象として削除しない。巨大ファイルの分割ではメソッドの内容を維持し、独立した責務ごとに移動する。解析モデルの変更は出力・診断・オフラインJSへの影響を同時に確認する。
