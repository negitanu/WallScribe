# 開発ガイド

Python 3.12 以降と `requirements.txt` と `pip install -e ".[dev]"` を使います。実機設定を fixtures やスクリーンショットに追加せず、`examples/` と同様に架空のアドレス・名称を使って再現してください。

変更する責務を分けます。

- `parsers/`：ベンダー設定から共通モデルへの変換。
- `models/`：共通モデル。項目追加時には既存入力との互換性を確認。
- `analyzers/`：設定の静的調査。情報不足を許可と断定しない。
- `services/`：ユースケースと構築テスト。`routes/` は入力検証と HTTP 応答。
- `exporters/`：成果物。Web の画面操作に依存しない。
- `static/css/tokens.css`：共通デザイン定義。画面固有の配置は各 CSS。

再現テストでは、正常な例だけでなく、曖昧な条件、共有オブジェクト、循環参照、巨大なグループ、IPv6、未知の設定、境界ポートを確認します。ブラウザ側の調査ロジックを変更した場合は Python の判定との整合性も確認してください。

```bash
WALLSCRIBE_DISABLE_CLEANUP_THREAD=1 UPLOAD_FOLDER=/tmp/wallscribe-tests pytest -q
python -m compileall -q analyzers parsers services routes exporters models
node --check static/js/lab.js
```

CI は Python / Jinja / JavaScript / CSS の構文に加えて、未使用 import・変数、重複定義、未定義名を検査します。互換用の再エクスポートや任意依存の存在確認は削除せず、用途を明記して検査対象から除外します。

配布対象は `pyproject.toml` の `include` と `package-data` で管理します。実行時に使う CSV・TextFSM・Web テンプレート・静的資産を追加した場合は wheel に収録されることを確認してください。アップロード、出力、ローカル検証ログは配布対象に含めません。

機能ごとに commit を分け、何が変わるか、検証した内容、未検証の条件を記載してください。UI 変更はデスクトップ・モバイル・キーボード操作とオフライン HTML を確認します。README の GIF は架空設定の実画面を収録し、1 ファイル 1 MB 未満を目安にしてください。
