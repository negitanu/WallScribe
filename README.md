# ファイアウォール パラメータシート生成ツール

FortiGate および Palo Alto Networks ファイアウォールの設定ファイルから、統一フォーマットのパラメータシートを自動生成するツールです。

## 技術スタック

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=flat-square&logo=flask&logoColor=white)
![WeasyPrint](https://img.shields.io/badge/WeasyPrint-62.0+-FF6B6B?style=flat-square)
![Gunicorn](https://img.shields.io/badge/Gunicorn-20.0+-499848?style=flat-square&logo=gunicorn&logoColor=white)
![Jinja2](https://img.shields.io/badge/Jinja2-3.0+-B41717?style=flat-square&logo=jinja&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-20.10+-2496ED?style=flat-square&logo=docker&logoColor=white)

## 対応機器

| ベンダー | 機種 | 設定ファイル形式 |
|----------|------|------------------|
| Fortinet | FortiGate シリーズ | `.conf` (テキスト形式) |
| Palo Alto Networks | PA シリーズ | `.xml` (XML 形式) |

## 出力形式

- **HTML**: スタイル付きの見やすいレポート（印刷対応、インタラクティブツールチップ付き）
- **PDF**: 印刷に最適化されたPDF形式（A3横向き）
- **Excel**: 編集可能なスプレッドシート形式

## インストール

### 必要環境

#### ローカル環境（Python直接実行）

- Python 3.8 以上

#### Docker環境

- Docker 20.10 以上
- Docker Compose 2.0 以上

### セットアップ

```bash
# リポジトリのクローン
git clone <repository-url>
cd gen-parameter-sheet

# 仮想環境の作成と有効化
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 依存パッケージのインストール
pip install -r requirements.txt
```

## 使用方法

### CLI（コマンドライン）

```bash
# FortiGate設定からHTML生成
python main.py fortigate.conf -o output.html

# FortiGate設定からExcel生成
python main.py fortigate.conf -f excel -o output.xlsx

# HA構成（複数ファイル）をクラスタとしてHTML生成（自動判定）
python main.py primary.conf secondary.conf --ha-mode auto -o ha_cluster.html

# 詳細ログ付きで実行
python main.py config.conf -v
```

補足:

- **CLIの出力形式は `html` / `excel`** です（PDFはWebインターフェースから生成します）
- 複数ファイル指定時は、HA情報（group-id / mode / priority 等）をもとにクラスタ判定します

### Webインターフェース

```bash
# 開発モード
python app.py

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
docker-compose build

# 起動
docker-compose up -d

# ログ確認
docker-compose logs -f

# 停止
docker-compose down

# アクセス
# http://localhost:80 (ポート80で公開)
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

#### Makefileを使用した操作

```bash
# ビルド
make build

# 起動
make up

# 停止
make down

# ログ確認
make logs

# 再起動
make restart
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
docker-compose logs

# コンテナを再ビルド
docker-compose build --no-cache
docker-compose up -d
```

**アップロードファイルの権限エラー：**

```bash
# アップロードディレクトリの権限を確認
chmod 755 uploads
```

## ディレクトリ構成

```text
gen-parameter-sheet/
├── main.py                # エントリーポイント（CLI）
├── app.py                 # Webアプリケーション（Flask）
├── parsers/               # パーサーモジュール
│   ├── base.py           # 基底パーサークラス
│   ├── cluster.py        # HAクラスタ構成パーサー（複数ファイル統合）
│   ├── fortigate/        # FortiGate用パーサー
│   ├── paloalto.py       # Palo Alto用パーサー
│   └── utils.py          # ユーティリティ関数
├── models/                # データモデル
│   ├── config.py         # 設定データ構造の定義
│   └── cluster.py        # HAクラスタ統合データモデル
├── exporters/             # 出力モジュール
│   ├── html.py           # HTML出力
│   ├── pdf.py            # PDF出力
│   └── excel.py          # Excel出力
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
|--------|------|
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

### ルーティングのblackhole/discard対応

- FortiGate: `set blackhole enable` を検出して `blackhole` ルートとして出力
- Palo Alto: `<nexthop><discard/></nexthop>` を検出して `blackhole` ルートとして出力

### HAクラスタ（複数ファイル）対応

- 複数ファイルからHAクラスタ判定（group-id / HAモード / priority など）
- HTML/Excelで **クラスタ概要（メンバー/差分）** を出力

### Internet Service対応

FortiGateのInternet Service（ISDB）に対応し、サービス名を自動解決して表示します。

## 抽出項目

パラメータシートには以下の情報が含まれます：

1. **機器概要**: ホスト名、モデル名、OSバージョン、動作モード
2. **システム設定**: 管理IP、DNS、NTP、管理者アカウント
3. **ネットワーク設定**: インターフェース、ルーティング、DHCP（CIDR表記）
4. **オブジェクト定義**: アドレス、サービス、グループ（CIDR表記）
5. **ファイアウォールポリシー**: セキュリティルール、Internet Service、Local-inポリシー
6. **NAT設定**: SNAT、DNAT、VIP
7. **VPN設定**: IPsec VPN、SSL-VPN
8. **セキュリティプロファイル**: AV、Webフィルタ、アプリケーションコントロール、IPS
9. **HA設定**: 高可用性設定
10. **ログ・監視設定**: Syslog、SNMP、FortiAnalyzer/Panorama

## 環境変数

| 変数名 | 説明 | デフォルト値 |
|--------|------|--------------|
| `FLASK_ENV` | 実行環境 | `production` |
| `FLASK_PORT` | リッスンポート | `8080` |
| `SECRET_KEY` | セッション暗号化キー | ランダム生成 |
| `UPLOAD_FOLDER` | アップロード先 | `./uploads` |
| `MAX_CONTENT_LENGTH` | 最大アップロードサイズ | `52428800` (50MB) |
| `CLEANUP_INTERVAL` | クリーンアップ間隔(秒) | `3600` |
| `TZ` | タイムゾーン | `Asia/Tokyo` |

## テスト

```bash
# すべてのテストを実行
pytest -v

# カバレッジ付きで実行
pytest --cov=. --cov-report=html -v

# 特定のテストファイルを実行
pytest tests/test_parsers.py -v
```

テストスイートには以下が含まれます：

- パーサーのテスト（FortiGate、Palo Alto）
- エクスポーターのテスト（HTML、PDF、Excel）
- データモデルのテスト
- ユーティリティ関数のテスト
- Webアプリケーションのテスト

## 詳細仕様

詳細な仕様については [SPECIFICATION.md](SPECIFICATION.md) を参照してください。

## ライセンス

MIT License
