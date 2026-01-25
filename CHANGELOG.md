# 変更履歴

このファイルには、プロジェクトへの重要な変更が記録されます。

形式は [Keep a Changelog](https://keepachangelog.com/ja/1.0.0/) に基づいており、
このプロジェクトは [Semantic Versioning](https://semver.org/lang/ja/) に準拠しています。

## [Unreleased]

### 追加
- レート制限機能（Flask-Limiter）
  - `/upload`と`/upload_async`エンドポイントにレート制限を追加（10回/分）
  - 429エラーハンドラーの実装
  - 環境変数による設定対応
- 構造化ログ機能
  - JSON形式のログ出力対応
  - 環境変数`LOG_FORMAT=json`で有効化
  - テキスト形式も維持（後方互換性）
- Prometheusメトリクス
  - `/metrics`エンドポイントの追加
  - リクエスト、ファイル処理、エラーのメトリクス収集
- コード品質ツール
  - Black、isort、flake8、mypyの設定
  - Pre-commitフックの設定
  - CI/CDパイプライン（GitHub Actions）
- 開発ドキュメント
  - CONTRIBUTING.mdの追加
  - 開発環境セットアップガイド
- Excelスタイル定義の分離
  - `exporters/excel/styles.py`にスタイル定義を分離

### 変更
- テストカバレッジ設定の改善
  - `pytest.ini`にカバレッジ設定を追加
  - `.coveragerc`ファイルの作成
  - カバレッジ目標を70%に設定
- Makefileの拡張
  - 開発用コマンドの追加（format, lint, type-check, test等）
  - セキュリティチェックコマンドの追加

### 改善
- レート制限のオプショナルインポート対応
  - `flask_limiter`がインストールされていない環境でも動作
- ログ管理の改善
  - 構造化ログモジュールの実装
  - 環境変数による柔軟な設定

## [1.1] - 2026-01-23

### 追加
- Excel出力: クラスタメンバーシートに「モデル」「OSバージョン」「HA管理IP」列を追加
- Excel出力: ルーティングシートにOSPF、OSPFv6、BGP、ポリシールート対応を追加
- Excel出力: HA設定に「HA管理ステータス」を追加
- HTML出力: CSSスタイリングを改善（ユニバーサルデザイン、視認性向上）

## [1.0] - 2026-01-20

### 追加
- 初回リリース
- HTML / PDF / Excel 出力
- Web: 非同期生成＋進捗表示
- Web/CLI: 複数ファイル（HAクラスタ）対応
- FortiGate: IPv6対応
- ルーティング: blackhole/discard対応
- Internet Service対応
- CIDR表記への自動変換
- インタラクティブツールチップ機能
- Docker対応
