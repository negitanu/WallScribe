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

- **HTML**: スタイル付きの見やすいレポート（印刷対応）
- **PDF**: 印刷に最適化されたPDF形式（A3横向き）

## インストール

### 必要環境

- Python 3.8 以上

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

# Palo Alto設定からPDF生成
python main.py pa440.xml -f pdf -o output.pdf

# 詳細ログ付きで実行
python main.py config.conf -v
```

### Webインターフェース

```bash
# 開発モード
python app.py

# 本番モード（Gunicorn使用）
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

ブラウザで http://localhost:8080 にアクセスし、設定ファイルをアップロードしてください。

### Docker

```bash
# ビルド
docker-compose build

# 起動
docker-compose up -d

# アクセス
# http://localhost:8080
```

## ディレクトリ構成

```
gen-parameter-sheet/
├── main.py                # エントリーポイント（CLI）
├── app.py                 # Webアプリケーション（Flask）
├── parsers/               # パーサーモジュール
│   ├── base.py           # 基底パーサークラス
│   ├── fortigate/        # FortiGate用パーサー
│   ├── paloalto.py       # Palo Alto用パーサー
│   └── utils.py          # ユーティリティ関数
├── models/                # データモデル
│   └── config.py         # 設定データ構造の定義
├── exporters/             # 出力モジュール
│   ├── html.py           # HTML出力
│   └── pdf.py            # PDF出力
├── templates/             # HTMLテンプレート
├── static/                # 静的ファイル
│   └── data/
│       └── appid.csv     # アプリケーションIDマッピング
└── web/                   # Webインターフェース
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

## 抽出項目

パラメータシートには以下の情報が含まれます：

1. **機器概要**: ホスト名、モデル名、OSバージョン、動作モード
2. **システム設定**: 管理IP、DNS、NTP、管理者アカウント
3. **ネットワーク設定**: インターフェース、ルーティング、DHCP
4. **オブジェクト定義**: アドレス、サービス、グループ
5. **ファイアウォールポリシー**: セキュリティルール、Local-inポリシー
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
| `UPLOAD_FOLDER` | アップロード先 | `./uploads` |
| `MAX_CONTENT_LENGTH` | 最大アップロードサイズ | `52428800` (50MB) |
| `TZ` | タイムゾーン | `Asia/Tokyo` |

## 詳細仕様

詳細な仕様については [SPECIFICATION.md](SPECIFICATION.md) を参照してください。

## ライセンス

MIT License
