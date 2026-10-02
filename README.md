# WallScribe

FortiGate / Palo Alto の設定ファイルから、レビューと引き継ぎに使うパラメータシートを作成するファイアウォール構築支援ツールです。HTML・Excel・PDF の出力と、構築中の設定を確認する机上テストを用意しています。

## 動作イメージ

設定の取り込みから、パラメータシートの生成・閲覧まで。

![パラメータシートの操作](docs/media/report-workflow.gif)

テストケースの生成と実行、該当ポリシーとルーティングの確認。

![構築テストの操作](docs/media/construction-lab.gif)

GIF は公開用の架空設定で撮影しています。実機の通信や攻撃を実行する機能はありません。

## できること

- FortiGate の VDOM、Palo Alto の vsys・仮想ルーターを含め、インターフェース、ルート、オブジェクト、VPN、セキュリティプロファイルを整理。
- ひとつのネットワーク図で接続関係を確認。ノード選択、検索、拡大、通信条件の調査に対応。
- ISDB、App-ID、application-default を考慮してポリシー候補を調査。カタログや設定だけでは確定できない条件は「要確認」と表示。
- 許可・境界・攻撃を想定した机上ケースを生成。ポリシー不一致、ルート不足、next-vr の循環などを確認。
- CISA KEV / Feodo Tracker の固定 Feed を取得し、公開情報に基づくケースを追加。

パラメータシートが成果物です。構築テストは設定レビューの補助であり、実機の動作・脆弱性・安全性を保証しません。動的ルーティング、実際の App-ID 判定、NAT 後の経路などは実機検証と組み合わせてください。対応範囲と判定条件は [構築テスト](docs/CONSTRUCTION_LAB.md) を参照してください。

## 起動する

Docker Compose を推奨します。PDF に必要なネイティブライブラリも含まれます。

```bash
git clone https://github.com/negitanu/WallScribe.git
cd WallScribe
cp .env.example .env
# .env の SECRET_KEY に、次のコマンドで生成した値を設定
python3 -c 'import secrets; print(secrets.token_hex(32))'
docker compose up --build -d
```

ブラウザで http://localhost:80 を開きます。停止は `docker compose down`。ホスト側の既定ポートは 80、コンテナ内は 8080 です。ポートは `.env` の `WALLSCRIBE_PORT` で変更できます。初期設定はローカルホストのみで公開します。チームで利用する場合は認証付きリバースプロキシの配下に配置してください。

### ローカル開発

Python 3.12 以降を使用します。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
WALLSCRIBE_DISABLE_CLEANUP_THREAD=1 UPLOAD_FOLDER=/tmp/wallscribe-dev python app.py
```

既定ポートは 8080。`FLASK_PORT` で変更できます。PDF 出力には Pango 等が別途必要です。依存関係の揃った Docker で検証できます。

### CLI でシートを生成

```bash
python main.py examples/fortigate-vdom.conf -o /tmp/fortigate.html
python main.py examples/paloalto-vsys.xml --format excel -o /tmp/paloalto.xlsx
python main.py --help
```

[examples](examples/) には架空設定を収録しています。複数ファイルによる HA 構成や診断 JSON の出力は `--help` を参照してください。

## 設定ファイルの扱い

Web のシート生成ではファイルを `uploads/` に保存し、期限切れのファイルを定期削除します。構築テストの設定はメモリ上で解析します。Feed への取得要求に設定ファイルは送信しません。生成されたシートにも内部アドレスや構成情報が含まれるため、元の設定と同じ管理範囲で扱ってください。

Web アップロード上限は既定 50 MB。構築テストは設定 2 MB・ケース 200 件を上限にしています。上限や保存期間は [仕様](docs/SPECIFICATION.md) と [構築テスト](docs/CONSTRUCTION_LAB.md) を参照してください。

## テストと変更

```bash
WALLSCRIBE_DISABLE_CLEANUP_THREAD=1 UPLOAD_FOLDER=/tmp/wallscribe-tests pytest -q
# Python / Jinja / JavaScript / CSS の構文検査（Node.js が必要）
python scripts/check_syntax.py
# PDF を含むコンテナテスト
docker compose --profile test run --rm test
# コンテナ内の構文検査
docker compose --profile test run --rm test python scripts/check_syntax.py
```

テストでは利用中の `uploads/` を指定しないでください。GitHub Actions でもテストを実行します。開発手順と責務の分け方は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。

## 詳細資料

- [構築テスト・Feed・判定の限界](docs/CONSTRUCTION_LAB.md)
- [ネットワーク図](docs/NETWORK_EXPLORER.md) / [通信調査](docs/NETWORK_INVESTIGATION.md)
- [パーサー](docs/PARSER_ENHANCEMENTS.md)
- [アーキテクチャ](docs/ARCHITECTURE.md) / [仕様](docs/SPECIFICATION.md)
- [デザイン共通ルール](docs/DESIGN_SYSTEM.md)

MIT License。バグ報告には機密情報を除いた最小設定、期待した結果、実際の結果を添えてください。

## Docker Hub への自動公開

Python 3.12 / 3.14 のテストと構文検査に成功すると、`linux/amd64` / `linux/arm64` の本番 Docker イメージをビルドし、起動・PDF出力と Trivy の脆弱性スキャンを実行します。スキャンは重大度や修正版の有無で指摘を除外せず、検出があれば公開を停止します。全件の結果は Actions の `wallscribe-cves-*` artifact から確認できます。

`main` への push / 手動実行では、検査に成功した同じイメージを再ビルドせずに `negitanu/wallscribe` に公開します。タグは `latest` と `sha-<完全なコミット SHA>`、各アーキテクチャ用に `sha-<完全なコミット SHA>-amd64` / `-arm64` も作成します。PR や他ブランチからは公開しません。

本番ベースは Python 3.14 / Alpine 3.24 です。PDF の依存は Pango・HarfBuzz と日本語フォントに限定し、pip やビルドツールを本番に含めません。CI ではベースを取得し直してキャッシュなしでビルドするため、OS・Python依存の更新もスキャン対象になります。Docker Scout と Trivy はデータベース・判定基準が異なるため、Hub の検出結果も公開後に確認してください。

`CVE-2025-50422` の対象である Cairo は PDF 生成に不要なため、本番・Docker テスト環境に含めません。Alpine の署名検証済み Pango パッケージから `libpango` / `libpangoft2` だけを取り出し、ELF の依存関係に基づく最小 APK を作成します。元のパッケージ名・バージョン・ソース名を保持するため、Pango 自体の脆弱性検査も継続できます。`--allow-untrusted` はこのビルド内で作成した APK のインストールだけに使用します。CI は両アーキテクチャで Cairo / Poppler のパッケージ・ライブラリが存在しないことと、多言語 PDF 出力を確認します。

初回のみ、Docker Hub に `negitanu/wallscribe` リポジトリを作成し、[GitHub Actions Secrets](https://github.com/negitanu/WallScribe/settings/secrets/actions) に次を登録してください。

- `DOCKERHUB_USERNAME`: Docker Hub のユーザー名。
- `DOCKERHUB_TOKEN`: 公開先への書き込み権限を持つ Docker Hub アクセストークン。パスワードやトークンを設定ファイルへ書かないでください。

未登録の場合、ビルド・起動確認のみを行い、公開をスキップした理由を Actions の Summary に表示します。登録後は `Tests` の `Run workflow` を `main` で実行するか、次の push で初回公開できます。古いコミットが新しい `latest` を置き換えないよう、公開直前に `main` の SHA を照合します。

```bash
docker pull negitanu/wallscribe:latest
docker run --rm -p 127.0.0.1:80:8080 -e SECRET_KEY="${SECRET_KEY}" negitanu/wallscribe:latest
```

`SECRET_KEY` は起動前に環境変数へ設定してください。保存したい生成物は `/app/uploads` を永続ボリュームへマウントします。
