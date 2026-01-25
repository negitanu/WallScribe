# WallScribe REST API

## 概要

WallScribe REST APIは、ファイアウォール設定ファイルからパラメータシートを生成するためのRESTful APIです。

## ベースURL

- 開発環境: `http://localhost:8080`
- 本番環境: `https://api.example.com`

## APIバージョン

現在のAPIバージョン: **v1**

## 認証

現在のバージョンでは認証は不要です。将来的にはAPIキー認証を追加予定です。

## エンドポイント

### ファイル処理

#### POST `/api/v1/upload`

設定ファイルをアップロードしてパラメータシートを生成します。

**リクエスト:**

- Content-Type: `multipart/form-data`
- パラメータ:
    - `config_files[]`: 設定ファイル（複数可、.conf または .xml）
    - `output_format`: 出力形式（html, pdf, excel、デフォルト: html）
    - `ha_mode`: HAモード（auto, single, cluster、デフォルト: auto）
    - `sections`: 出力するセクションのJSON配列（オプション）

**レスポンス:**

```json
{
  "success": true,
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_count": 1,
  "progress_url": "/api/progress/550e8400-e29b-41d4-a716-446655440000",
  "result_url": "/result/550e8400-e29b-41d4-a716-446655440000"
}
```

**ステータスコード:**

- `202 Accepted`: アップロード受付成功
- `400 Bad Request`: リクエストエラー
- `429 Too Many Requests`: レート制限超過
- `500 Internal Server Error`: サーバーエラー

### 進捗・ステータス

#### GET `/api/progress/<file_id>`

処理の進捗状況を取得します。

**レスポンス:**

```json
{
  "success": true,
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": {
    "percent": 45,
    "message": "設定ファイルを解析しています...",
    "stage": "parsing"
  },
  "result_url": "/result/550e8400-e29b-41d4-a716-446655440000"
}
```

#### GET `/api/status/<file_id>`

ファイルのステータス情報を取得します。

**レスポンス:**

```json
{
  "success": true,
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "fortigate_param.html",
  "device_type": "fortigate",
  "hostname": "FW-PRIMARY",
  "version": "7.6.2",
  "summary": {
    "policies": 120,
    "objects": 45
  }
}
```

#### v1 エイリアス

- GET `/api/v1/progress/<file_id>`（`/api/progress/<file_id>` のエイリアス）
- GET `/api/v1/status/<file_id>`（`/api/status/<file_id>` のエイリアス）

### ジョブ管理

#### GET `/api/v1/jobs`

最近のジョブ一覧（メタデータ）を取得します。

**クエリ:**

- `limit`: 取得件数（デフォルト 50、最大 200）

**レスポンス:**

```json
{
  "success": true,
  "jobs": [
    {
      "file_id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "fortigate_param.html",
      "status": "processing",
      "created_at": "2026-01-25T09:38:31",
      "file_count": 1,
      "progress_percent": 45,
      "progress_message": "設定ファイルを解析しています...",
      "progress_stage": "parsing",
      "result_url": "/result/550e8400-e29b-41d4-a716-446655440000",
      "download_url": "/download/550e8400-e29b-41d4-a716-446655440000",
      "preview_url": "/preview/550e8400-e29b-41d4-a716-446655440000",
      "status_url": "/api/status/550e8400-e29b-41d4-a716-446655440000",
      "progress_url": "/api/progress/550e8400-e29b-41d4-a716-446655440000"
    }
  ]
}
```

#### GET `/api/v1/jobs/<file_id>`

ジョブの詳細を取得します（一覧の1件分を単体で取得）。

#### DELETE `/api/v1/jobs/<file_id>`

ジョブに紐づく生成物（入力/出力/メタデータ）を削除します。

**レスポンス:**

```json
{
  "success": true,
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "deleted_files": 3
}
```

### ダウンロード

#### GET `/download/<file_id>`

生成されたファイルをダウンロードします。

#### GET `/api/v1/download/<file_id>`

`/download/<file_id>` のエイリアスです。

**レスポンス:**

- Content-Type: ファイル形式に応じたMIMEタイプ
- Content-Disposition: `attachment; filename="..."`

#### GET `/preview/<file_id>`

生成されたファイルをプレビュー表示します。

#### GET `/api/v1/preview/<file_id>`

`/preview/<file_id>` のエイリアスです。

**レスポンス:**

- Content-Type: ファイル形式に応じたMIMEタイプ

### システム

#### GET `/metrics`

Prometheusメトリクスを取得します。

**レスポンス:**

- Content-Type: `text/plain; version=0.0.4; charset=utf-8`
- Prometheus形式のメトリクスデータ

#### GET `/api/v1/spec`

Swagger 仕様（JSON）を返します。

#### GET `/swagger.json`

`/api/v1/spec` のエイリアスです。

## エラーレスポンス

すべてのエラーレスポンスは以下の形式です：

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "エラーメッセージ",
    "details": "詳細情報（開発環境のみ）"
  }
}
```

### エラーコード

- `NO_FILE`: ファイルが選択されていません
- `UNSUPPORTED_FORMAT`: サポートされていないファイル形式
- `INVALID_FILE_ID`: 無効なファイルID
- `FILE_NOT_FOUND`: ファイルが見つかりません
- `RATE_LIMIT_EXCEEDED`: レート制限超過
- `INTERNAL_ERROR`: サーバー内部エラー

## レート制限

- `/api/v1/upload`: 10リクエスト/分
- その他のエンドポイント: 100リクエスト/時間

レート制限を超過した場合、`429 Too Many Requests`が返されます。

## Swagger UI

APIドキュメントはSwagger UIで確認できます：

- URL: `http://localhost:8080/apidocs`
- インタラクティブなAPIテストが可能
- 仕様(JSON): `http://localhost:8080/swagger.json`

## 使用例

### cURL

```bash
# ファイルアップロード
curl -X POST http://localhost:8080/api/v1/upload \
  -F "config_files[]=@fortigate.conf" \
  -F "output_format=html" \
  -F "ha_mode=auto"

# 進捗確認
curl http://localhost:8080/api/progress/550e8400-e29b-41d4-a716-446655440000

# ファイルダウンロード
curl -O http://localhost:8080/download/550e8400-e29b-41d4-a716-446655440000
```

### Python

```python
import requests

# ファイルアップロード
files = {'config_files[]': open('fortigate.conf', 'rb')}
data = {
    'output_format': 'html',
    'ha_mode': 'auto'
}
response = requests.post('http://localhost:8080/api/v1/upload', files=files, data=data)
result = response.json()
file_id = result['file_id']

# 進捗確認
progress = requests.get(f'http://localhost:8080/api/progress/{file_id}').json()
print(f"進捗: {progress['progress']['percent']}%")

# ファイルダウンロード
file_response = requests.get(f'http://localhost:8080/download/{file_id}')
with open('output.html', 'wb') as f:
    f.write(file_response.content)
```

## バージョニング

APIはURLパスでバージョニングされています：

- `/api/v1/...`: バージョン1

将来のバージョンでは、後方互換性を維持しながら新しい機能を追加します。
