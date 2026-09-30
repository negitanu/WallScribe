# WallScribe

FortiGate と PA-Series ファイアウォールの設定ファイルから、統一フォーマットのパラメータシートを自動生成するツールです。

## 技術スタック

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=flat-square&logo=flask&logoColor=white)
![WeasyPrint](https://img.shields.io/badge/WeasyPrint-62.0+-FF6B6B?style=flat-square)
![Gunicorn](https://img.shields.io/badge/Gunicorn-20.0+-499848?style=flat-square&logo=gunicorn&logoColor=white)
![Jinja2](https://img.shields.io/badge/Jinja2-3.0+-B41717?style=flat-square&logo=jinja&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-20.10+-2496ED?style=flat-square&logo=docker&logoColor=white)

## 対応機器

概要は下表のとおりです。詳細は [docs/SPECIFICATION.md](docs/SPECIFICATION.md) の第 1 章・第 2 章を参照してください。

| ベンダー | 機種 | 設定ファイル形式 |
| --- | --- | --- |
| Fortinet | FortiGate シリーズ | `.conf` (テキスト形式) |
| Palo Alto Networks | PA シリーズ | `.xml` (XML 形式) |

## 出力形式

- **HTML**: スタイル付きの見やすいレポート（印刷対応、インタラクティブツールチップ付き）
- **PDF**: 印刷に最適化されたPDF形式（A3横向き）
- **Excel**: 編集可能なスプレッドシート形式（VDOM/vsys単位出力、モダンスタイリング対応）

出力レイアウト・スタイルの仕様は [docs/SPECIFICATION.md](docs/SPECIFICATION.md) の第 3 章にまとめています。

## インストール

### 必要環境

#### ローカル環境（Python直接実行）

- Python 3.12 以上

#### Docker環境

- Docker 20.10 以上
- Docker Compose 2.0 以上

### セットアップ

```bash
# リポジトリのクローン
git clone <repository-url>
cd WallScribe

# 仮想環境の作成と有効化
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 依存パッケージのインストール
pip install -r requirements.txt
```

## 使用方法

### CLI（コマンドライン）

```bash
# FortiGate設定からHTML生成
python3 main.py fortigate.conf -o output.html

# FortiGate設定からExcel生成
python3 main.py fortigate.conf -f excel -o output.xlsx

# HA構成（複数ファイル）をクラスタとしてHTML生成（自動判定）
python3 main.py primary.conf secondary.conf --ha-mode auto -o ha_cluster.html

# 詳細ログ付きで実行
python3 main.py config.conf -v
```

補足:

- **CLIの出力形式は `html` / `excel`** です（PDFはWebインターフェースから生成します）
- 複数ファイル指定時は、HA情報（group-id / mode / priority 等）をもとにクラスタ判定します

### Webインターフェース

```bash
# 開発モード
python3 app.py

# 本番モード（Gunicorn使用）
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

ブラウザで `http://localhost:8080` にアクセスし、設定ファイルをアップロードしてください。

Webインターフェースの特徴:

- **生成中の進捗表示**（% とステータスメッセージ）
- **複数ファイル選択（HA構成）**: 2つ以上の設定ファイルを選択し、`HAモード（自動/クラスタ/単一）` を指定可能

### Docker

#### 基本的な使い方

```bash
# ビルド
docker compose build

# 起動
docker compose up -d

# ログ確認
docker compose logs -f

# 停止
docker compose down

# アクセス
# http://localhost:80 (ポート80で公開)
```

#### コンテナ内でテスト（profile `test`）

アプリ起動（`docker compose up`）とは別に、テスト用イメージで `pytest` を実行します。リポジトリを `/app` にマウントするため、ホストの `tests/` がそのまま使われます。

```bash
# テスト用イメージのビルド（初回または Dockerfile.test / 依存変更時）
docker compose --profile test build test

# テスト実行（終了後コンテナ削除）
docker compose --profile test run --rm test

# PDF / WeasyPrint まわりを除く例
docker compose --profile test run --rm test pytest -m "not pdf"
```

#### 環境変数の設定

`docker-compose.yml`で環境変数を設定できます。`.env`ファイルを作成して設定することも可能です：

```bash
# .envファイルの例
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
MAX_CONTENT_LENGTH=52428800
CLEANUP_INTERVAL=3600
TZ=Asia/Tokyo
```

#### ボリュームマウント

アップロードファイルを永続化する場合、`docker-compose.yml`で既に設定されています：

```yaml
volumes:
  - ./uploads:/app/uploads
```

#### Docker Compose（シェルから直接）

```bash
# ビルド（本番 web 用）
docker compose build

# キャッシュなしで再ビルド
docker compose build --no-cache

# 起動
docker compose up -d

# 停止
docker compose down

# ログ確認
docker compose logs -f

# 停止してから再度起動
docker compose down && docker compose up -d
```

#### 開発環境での使用

開発時にコードをホットリロードする場合、`docker-compose.yml`のコメントアウトされたボリュームマウントを有効化してください：

```yaml
volumes:
  - ./uploads:/app/uploads
  # 開発時のみ: コードをマウントしてホットリロード
  - ./app.py:/app/app.py
  - ./parsers:/app/parsers
  - ./models:/app/models
  - ./exporters:/app/exporters
  - ./web:/app/web
  - ./static:/app/static
```

#### トラブルシューティング

**ポートが既に使用されている場合：**

```bash
# docker-compose.ymlでポートを変更
ports:
  - "8080:8080"  # 左側を変更
```

**コンテナが起動しない場合：**

```bash
# ログを確認
docker compose logs

# コンテナを再ビルド
docker compose build --no-cache
docker compose up -d
```

**アップロードファイルの権限エラー：**

```bash
# アップロードディレクトリの権限を確認
chmod 755 uploads
```

## ディレクトリ構成

```text
WallScribe/
├── main.py                # エントリーポイント（CLI）
├── app.py                 # Webアプリケーション（Flask）
├── exceptions.py          # カスタム例外クラス
├── docs/                  # 仕様・設計（正本: docs/SPECIFICATION.md）
├── parsers/               # パーサーモジュール
│   ├── base.py           # 基底パーサークラス
│   ├── cluster.py        # HAクラスタ構成パーサー（複数ファイル統合）
│   ├── device_identification.py  # TextFSM による機器識別
│   ├── textfsm_utils.py  # TextFSM 実行
│   ├── textfsm_templates/# 機器識別等のテンプレート
│   ├── fortigate/        # FortiGate用パーサー
│   ├── paloalto.py       # Palo Alto用パーサー
│   └── utils.py          # ユーティリティ関数
├── api/                   # REST API仕様（Swagger定義・ドキュメント）
├── models/                # データモデル
│   ├── config.py         # 設定データ構造の定義
│   └── cluster.py        # HAクラスタ統合データモデル
├── exporters/             # 出力モジュール
│   ├── html.py           # HTML出力
│   ├── pdf.py            # PDF出力
│   └── excel.py          # Excel出力
├── utils/                 # 共通ユーティリティ（logging/metrics/validation）
├── static/                # 静的ファイル
│   └── data/
│       └── appid.csv     # アプリケーションIDマッピング
└── web/                   # Webインターフェース
    └── templates/         # Web UI テンプレート（index/result/error）
```

## データファイル

### アプリケーションIDマッピング (`static/data/appid.csv`)

FortiGateのアプリケーションコントロールで使用されるアプリケーションIDを、アプリケーション名・カテゴリ・リスクレベルに変換するためのマッピングデータです。

| カラム | 説明 |
| --- | --- |
| app_id | アプリケーションID（数値） |
| app_name | アプリケーション名 |
| category | カテゴリ（例: Social.Media, P2P, Email） |
| risk | リスクレベル（1-5） |
| description | 説明 |

#### 使用例

```python
from parsers.utils import get_app_name, get_app_info

# アプリケーション名を取得
name = get_app_name('15832')  # => "Facebook"

# 詳細情報を取得
info = get_app_info('12753')
# => {'app_name': 'Skype', 'category': 'Collaboration', 'risk': '2', ...}
```

## 主な機能

### インタラクティブツールチップ

HTML出力では、以下のオブジェクトにマウスオーバーで詳細情報を表示します：

- インターフェース、アドレスオブジェクト、サービスオブジェクト
- セキュリティプロファイル、Internet Service

### CIDR表記への自動変換

IPアドレスとサブネットマスクを自動的にCIDR表記（例: `192.168.1.0/24`）に変換します。

### IPv6対応（主にFortiGate）

- インターフェース: `ip6-address`
- ルーティング: `router static6`
- アドレス/グループ: `firewall address6` / `firewall addrgrp6`
- FortiOS 8.0: ポリシーの `srcaddr6` / `dstaddr6` と IPv6 wildcard address 参照を既存の送信元/宛先アドレス欄へ統合

### ルーティングのblackhole/discard対応

- FortiGate: `set blackhole enable` を検出して `blackhole` ルートとして出力
- Palo Alto: `<nexthop><discard/></nexthop>` を検出して `blackhole` ルートとして出力

### 動的ルーティングプロトコル対応

Excel出力では、以下の動的ルーティングプロトコルに対応しています：

- **OSPF / OSPFv6**: エリア設定、インターフェース設定、再配布設定
- **BGP**: AS番号、Router ID、ネイバー設定、ネットワーク広告、再配布設定
- **ポリシールート**: 送信元/宛先、プロトコル、入力/出力インターフェース、ゲートウェイ

### HAクラスタ（複数ファイル）対応

- 複数ファイルからHAクラスタ判定（group-id / HAモード / priority など）
- HTML/Excelで **クラスタ概要（メンバー/差分）** を出力

### Internet Service対応

FortiGateのInternet Service（ISDB）に対応し、サービス名を自動解決して表示します。

### FortiOS 8.0 対応

FortiOS 8.0 の `#config-version`、カスタムタグ（アドレス/アドレスグループ/サービス/ポリシー）、`internet-service-id`、IPv6 ポリシーアドレス、従来形式の `vpn ipsec phase1` / `phase2` をパースします。

### Excel出力のVDOM/vsys単位対応

Excel出力では、グローバル設定とVDOM/vsys単位の設定を分離して出力します：

- **グローバル設定シート**: 機器概要、システム設定、HA設定、ログ・監視設定
- **VDOM/vsys単位シート**: 各VDOMごとにインターフェース、ルーティング、オブジェクト、ポリシー、NAT、VPN、セキュリティプロファイルを出力
- **モダンスタイリング**: VDOMごとに異なる色テーマを自動割り当て、タブ色やヘッダー色で視覚的に区別
- **視覚的区別**: アクション（Allow/Deny/Drop）やステータス（有効/無効）を色分けで表示

## 抽出項目

パラメータシートには以下の情報が含まれます：

1. **機器概要**: ホスト名、モデル名、OSバージョン、動作モード
2. **システム設定**: 管理IP、DNS、NTP、管理者アカウント
3. **ネットワーク設定**: インターフェース、ルーティング（スタティック、OSPF、OSPFv6、BGP、ポリシールート）、DHCP（CIDR表記）
4. **オブジェクト定義**: アドレス、サービス、グループ（CIDR表記）
5. **ファイアウォールポリシー**: セキュリティルール、Internet Service、Local-inポリシー
6. **NAT設定**: SNAT、DNAT、VIP
7. **VPN設定**: IPsec VPN、SSL-VPN
8. **セキュリティプロファイル**: AV、Webフィルタ、アプリケーションコントロール、IPS
9. **HA設定**: 高可用性設定（HA管理ステータス含む）
10. **ログ・監視設定**: Syslog、SNMP、FortiAnalyzer/Panorama

## 環境変数

| 変数名 | 説明 | デフォルト値 |
| --- | --- | --- |
| `FLASK_ENV` | 実行環境 | `production` |
| `FLASK_PORT` | リッスンポート | `8080` |
| `SECRET_KEY` | セッション暗号化キー | ランダム生成 |
| `UPLOAD_FOLDER` | アップロード先 | `./uploads` |
| `MAX_CONTENT_LENGTH` | 最大アップロードサイズ | `52428800` (50MB) |
| `CLEANUP_INTERVAL` | クリーンアップ間隔(秒) | `3600` |
| `TZ` | タイムゾーン | `Asia/Tokyo` |

## テスト

方針の詳細は [tests/README.md](tests/README.md) を参照してください。

ローカルでは先に `pip install -r requirements.txt` と `pip install -e ".[dev]"` を実行してください。Docker だけで回す場合は上記「コンテナ内でテスト」を参照してください。

```bash
# リポジトリルートで全テスト
pytest

# 簡潔な出力
pytest -q

# PDF / WeasyPrint まわりを除く（Linux・Docker 等向け）
pytest -m "not pdf"

# 特定のファイルのみ
pytest tests/test_parsers.py -v

# マーカー例
pytest -m "not slow"
pytest -m "unit"
pytest -m "integration"
```

テストスイートには以下が含まれます：

- パーサーのテスト（FortiGate、Palo Alto）
- エクスポーターのテスト（HTML、PDF、Excel）
- データモデルのテスト
- ユーティリティ関数のテスト
- Webアプリケーションのテスト

## 開発

### 開発環境のセットアップ

```bash
# ランタイム依存
pip install -r requirements.txt
# 開発用（black / pytest / pre-commit 等は pyproject.toml の [project.optional-dependencies] dev）
pip install -e ".[dev]"

# Pre-commitフックのインストール
pre-commit install
```

### 開発コマンド

```bash
# コードフォーマット
black .
isort .

# フォーマット確認のみ
black --check .
isort --check-only .

# リンター
flake8 . --max-line-length=100 --extend-ignore=E203,W503

# 型チェック
mypy . --ignore-missing-imports --no-strict-optional

# テスト
pytest -v

# セキュリティチェック
safety check
pip-audit
```

### CI/CD

GitHub Actionsによる自動テストとコード品質チェックが設定されています：

- Python 3.12 以上でのテスト
- コードフォーマットチェック（black, isort）
- リンター（flake8）
- 型チェック（mypy）
- Dockerイメージのビルド

## 詳細仕様

要件・設計の詳細は [docs/SPECIFICATION.md](docs/SPECIFICATION.md) を参照してください。入口は [docs/README.md](docs/README.md) からもどうぞ。

## API ドキュメント

REST APIの詳細なドキュメントについては [api/README.md](api/README.md) を参照してください。

Swagger UIでインタラクティブにAPIをテストできます：

- URL: `http://localhost:8080/apidocs` (flasggerがインストールされている場合)
- Dockerで起動している場合: `http://localhost/apidocs`（ポート80で公開）
- 仕様(JSON): `http://localhost:8080/swagger.json`

主なAPI（抜粋）:

- `POST /api/v1/upload`（非同期受付・複数ファイル/HA対応）
- `GET /api/progress/<file_id>` / `GET /api/status/<file_id>`（進捗・結果）
- `GET /api/v1/jobs` / `GET|DELETE /api/v1/jobs/<file_id>`（ジョブ管理）
- `GET /api/v1/spec` / `GET /swagger.json`（Swagger仕様JSON）
- `GET /health` / `GET /health/ready` / `GET /health/live`（ヘルスチェック）

## 変更履歴

変更履歴は [CHANGELOG.md](CHANGELOG.md) を参照してください。

## ライセンス

Apache 2.0 License - 詳細は [LICENSE](LICENSE) を参照してください。

### セキュリティ診断・推定ネットワーク構造

設定内の平文管理アクセス、広い許可ルール、ログ不足などを根拠・改善案付きで指摘し、IF・直結ネットワーク・静的ルートから論理構造を図示できます。Web 画面で出力対象を選択でき、CLI の `--analysis-json` で診断・構造を JSON に保存できます。

[対応項目、使い方、推定の限界](docs/SECURITY_AND_TOPOLOGY.md)を参照してください。
