# テスト

このプロジェクトでは **pytest** でテストします。

## 設定（`pyproject.toml`）

| 項目 | 内容 |
| --- | --- |
| `testpaths` | `["tests"]` … 対象は `tests/` 配下 |
| `pythonpath` | `["."]` … リポジトリルートをパスに載せる（本リポジトリは `src` レイアウトではないため。editable インストールなしでも `parsers` / `models` 等を import 可能） |
| マーカー `pdf` | PDF / WeasyPrint まわり。Linux や Docker では `pytest -m "not pdf"` で除外しやすくする |

## 実行方法

リポジトリルートで:

```bash
WALLSCRIBE_DISABLE_CLEANUP_THREAD=1 UPLOAD_FOLDER=/tmp/wallscribe-tests pytest
```

静かにまとめて見るなら:

```bash
WALLSCRIBE_DISABLE_CLEANUP_THREAD=1 UPLOAD_FOLDER=/tmp/wallscribe-tests pytest -q
```

## 補足

- テストファイル名は `test_*.py` 形式
- import パスは `pyproject.toml` の `pythonpath` で共通設定し、各テストで `sys.path` を変更しません。
- テスト用保存先には利用中のアップロードディレクトリを指定しないでください。
- 共有フィクスチャ用のデータ置き場は [fixtures/](fixtures/)（必要に応じて利用）
- [conftest.py](conftest.py) に pytest フィクスチャや共通設定を記述

## 依存

- ランタイム: `pip install -r requirements.txt`
- 開発・テスト: `pip install -e ".[dev]"`（`pyproject.toml` の `[project.optional-dependencies]`、`pytest` / `black` 等）
- Docker のみでテストする場合はルート [README.md](../README.md) の「コンテナ内でテスト」を参照
