# WallScribe アーキテクチャガイド

このドキュメントは、WallScribe の実装を読む人、機能を追加する人、運用時の障害を切り分ける人が、全体像から詳細へ順に理解できることを目的にした設計ガイドです。

仕様項目や出力項目の正本は [SPECIFICATION.md](SPECIFICATION.md) です。このガイドでは、コード上の責務分担、処理フロー、拡張時の触り方、運用上の注意点に重点を置きます。

## 1. 概要

WallScribe は、FortiGate と Palo Alto Networks PA-Series の設定ファイルを読み込み、統一された中間モデルに変換し、パラメータシートとして HTML、PDF、Excel に出力する Python / Flask アプリケーションです。

主な利用経路は 2 つです。

- Web UI から設定ファイルをアップロードし、進捗を確認しながら成果物をダウンロードする経路。
- CLI から `main.py` を実行し、ローカルファイルを直接 HTML または Excel に変換する経路。

どちらの経路も、解析と出力の中核処理は `services/conversion.py` に寄せられています。これにより、Web と CLI で挙動が分岐しすぎない構成になっています。

## 2. アーキテクチャ図

詳細な構造は、Archify で生成したインタラクティブ HTML 図でも確認できます。

- 図 HTML: [wallscribe-architecture.html](wallscribe-architecture.html)
- 図仕様 JSON: [wallscribe-architecture.architecture.json](wallscribe-architecture.architecture.json)

図には、Web 変換フロー、CLI 変換フロー、解析から出力までの 3 つのフォーカスビューを入れています。生成 HTML の固定 Viewer UI は英語表示ですが、ノード・ラベル・説明カードなどの著者コンテンツは日本語です。

## 3. リポジトリ構成

主要ディレクトリとファイルの役割は次のとおりです。

- `app.py`: Flask アプリケーションの生成、任意依存の読み込み、ルート登録、エラーハンドラ、クリーンアップスレッド起動を担当します。
- `main.py`: CLI エントリポイントです。入力ファイル、出力形式、HA モードを受け取り、共有変換サービスを呼び出します。
- `services/conversion.py`: Web と CLI の共通変換サービスです。ファイル読み込み、文字コード検出、単体/HA 解析、出力形式ごとの exporter 呼び出しを束ねます。
- `routes/`: Flask の HTTP エンドポイントを機能別に分割した層です。アップロード、ジョブ進捗、結果表示、ダウンロード、ヘルスチェック、メトリクスなどを扱います。
- `jobs/processor.py`: Web の非同期アップロードで使われるジョブ処理です。進捗更新、解析、出力、メタデータ保存を一連の流れとして実行します。
- `parsers/`: 機器設定ファイルを読み、統一モデルへ詰める解析層です。FortiGate、Palo Alto、TextFSM 補助、HA クラスタ解析が含まれます。
- `models/`: 出力形式に依存しない中間データモデルです。単体機器の `ConfigModel` と HA 構成の `ClusterConfig` が中心です。
- `exporters/`: `ConfigModel` または `ClusterConfig` から HTML、PDF、Excel を生成する出力層です。
- `web/`: Flask アプリの設定、依存読み込み、リクエストフック、エラーハンドラ、テンプレートをまとめた Web 支援層です。
- `static/`: CSS、JavaScript、アプリケーション ID CSV などの静的リソースです。
- `utils/`: バリデーション、ファイルメタデータ保存、メトリクス、ログ設定などの横断ユーティリティです。
- `tests/`: ルート、パーサ、モデル、エクスポータ、統合動作のテストです。

## 4. 全体の責務分担

WallScribe は、入力、解析、モデル化、出力、Web 管理の責務を分けています。

入力層は、ファイル形式、サイズ、文字コード、出力形式、HA モードを検証します。Web では `routes/upload_async.py` と `routes/upload_sync.py`、CLI では `main.py` と `services/conversion.py` が入口になります。

解析層は、入力テキストから FortiGate または Palo Alto の設定構造を取り出します。機器識別は `parsers/device_identification.py` と `parsers/base.py` が担当し、実際の抽出は `parsers/fortigate/` と `parsers/paloalto.py` が担当します。

モデル層は、ベンダー差分を吸収する中間表現です。FortiGate の VDOM と Palo Alto の vsys は、出力側では同じように VDOM/vsys 単位のセクションとして扱われます。

出力層は、統一モデルを人が読む成果物に変換します。HTML は標準的なレポート出力、PDF は HTML を WeasyPrint で印刷向けに変換、Excel は openpyxl で編集可能なシートを生成します。

Web 管理層は、非同期処理、進捗表示、成果物の保存、ダウンロード、プレビュー、エラー応答、レート制限、メトリクス公開を担います。

## 5. Web 変換フロー

Web UI では、利用者がブラウザから設定ファイルをアップロードします。現在の主経路は非同期 API です。

1. 利用者が `web/templates/index.html` から設定ファイル、出力形式、HA モード、出力セクションを指定します。
2. `routes/upload_async.py` の `/api/v1/upload` が multipart/form-data を受け取ります。
3. 拡張子、出力形式、任意依存、HA モード、ファイルサイズ、ファイル内容を検証します。
4. UUID ベースの `file_id` を発行し、入力ファイルを `UPLOAD_FOLDER` 配下へ保存します。
5. 初期メタデータを `utils/storage.py` 経由で保存します。
6. `JobProcessor.process_job_multi()` を別スレッドで起動し、HTTP レスポンスとして `202 Accepted`、進捗 URL、結果 URL を返します。
7. ジョブ処理は、入力ファイルの文字コードを検出し、HA モードに応じて単体解析またはクラスタ解析を実行します。
8. 解析結果を exporter に渡し、HTML、PDF、Excel のいずれかを生成します。
9. 成果物パス、サマリー、ステータス、進捗をメタデータに保存します。
10. 利用者は進捗 API と結果ページから完了状態を確認し、プレビューまたはダウンロードします。

非同期フローの特徴は、HTTP リクエストを長時間保持しないことです。大きい設定ファイルや PDF/Excel 生成のように時間がかかる処理でも、受付と実処理を分離できます。

## 6. 同期アップロードフロー

`routes/upload_sync.py` の `/upload` は、後方互換性を持つ同期アップロード経路です。

同期経路では、1 リクエスト内で検証、文字コード検出、パーサ選択、解析、出力、メタデータ保存までを完了します。レスポンスには `file_id`、生成ファイル名、機器種別、ホスト名、バージョン、ダウンロード URL、プレビュー URL が含まれます。

現在の設計では、複数ファイルや進捗管理を伴う通常利用は非同期 API が主役です。同期経路は、既存 UI や既存クライアントとの互換性のために維持される入口として扱うのが自然です。

## 7. CLI 変換フロー

CLI は `main.py` が入口です。

1. `argparse` で入力ファイル、出力先、出力形式、HA モード、詳細ログフラグを受け取ります。
2. 入力パスの存在を確認します。
3. `services/conversion.parse_paths()` に `Path` のリストを渡します。
4. `parse_paths()` は `load_contents_from_paths()` と `parse_contents()` を通じて文字コード検出と解析を行います。
5. 解析結果が HA クラスタの場合は、クラスタ情報とメンバー情報をログ出力します。
6. `export_config()` が指定形式の exporter を選び、成果物を書き出します。

CLI で選べる出力形式は `html` と `excel` です。PDF は Web インターフェース側の出力として扱われています。

## 8. 変換サービス

`services/conversion.py` は、Web と CLI の差を吸収する中核です。

`InputContent` は、元ファイル名、デコード後テキスト、検出エンコーディング、ファイルサイズを保持します。Web ではアップロード時の安全なファイル名、CLI ではローカルファイル名を渡せます。

`ExportCapabilities` は、利用可能な exporter クラスと任意依存の有無をまとめます。PDF や Excel のように依存パッケージがないと動かない形式でも、呼び出し側が同じ関数を使えるようにしています。

`ParseResult` は、解析済み config、パーサエラー、クラスタ判定をまとめます。単体機器なら `ConfigModel`、HA 構成なら `ClusterConfig` が入ります。

`parse_contents()` は、HA モードとファイル数に応じて処理を分けます。`single` または単一ファイルの `auto` では `get_parser_for_content()` で機器別パーサを選びます。複数ファイルでは `parse_ha_cluster_from_contents()` に渡し、クラスタとして扱えるかを判断します。

`export_config()` は、出力形式に応じて exporter を選択します。`html` は常に利用可能な基本形式です。`pdf` は WeasyPrint が必要で、`excel` は openpyxl が必要です。依存が足りない場合は `ExportDependencyMissing` を投げ、Web 側では利用者向けのエラー JSON に変換されます。

## 9. 機器識別とパーサ選択

機器識別は、入力内容から適切なパーサを選ぶための前段です。

`parsers/device_identification.py` は、入力先頭のサンプルに TextFSM テンプレートを当て、FortiGate、Palo Alto set CLI、Palo Alto XML ルートの特徴を検出します。FortiGate では `#config-version` 由来のモデルコードを表示用の FortiGate モデル名へ変換します。

`parsers/base.py` の `detect_encoding()` は、`utf-8-sig`、`utf-8`、`cp932`、`latin-1` の順に試行します。日本語コメントや日本語名を含む設定ファイルを扱いやすくするため、CP932 が明示的に候補に入っています。

`get_parser_for_content()` は、まず機器識別結果に基づいてパーサを選びます。識別に失敗した場合でも、各パーサの `detect_content_type()` を順番に試し、内容ベースで判定します。

## 10. FortiGate 解析

FortiGate 解析の入口は `parsers/fortigate/__init__.py` の `FortiGateParser` です。

FortiGate の設定は、グローバル設定と VDOM 設定が混在します。パーサはまず `_separate_config()` で設定行を `global` と `vdom` に分けます。VDOM が明示されない最小構成では、`root` または global として扱えるように補助ロジックがあります。

`#config-version` 行は `_parse_header_line()` で処理されます。TextFSM テンプレートで model、version、build、opmode、VDOM 有効化情報を取り出し、揺れのある形式に対しては正規表現のフォールバックも持っています。

設定構造の分解後、各カテゴリは converter に委譲されます。`parsers/fortigate/converters/` 配下には、デバイス情報、システム設定、インターフェース、ルート、OSPF、BGP、ポリシールート、DHCP、オブジェクト、ポリシー、NAT、VPN、セキュリティプロファイル、HA、ログ設定などの変換関数があります。

この分割により、FortiGate で新しい抽出カテゴリを追加する場合は、巨大なパーサ本体へ処理を足すのではなく、該当 converter を中心に変更できます。

## 11. Palo Alto 解析

Palo Alto 解析の入口は `parsers/paloalto.py` の `PaloAltoParser` です。

対応入力は XML と set CLI 形式です。XML は `defusedxml` が利用可能であれば安全な `fromstring` を使い、外部エンティティなどの XML セキュリティ問題を避けます。`defusedxml` がない場合は標準ライブラリの `xml.etree.ElementTree` にフォールバックします。

set CLI 形式は `parsers/paloalto_text.py` 側へ委譲されます。XML 形式では、`devices/entry[@name="localhost.localdomain"]` を起点に、deviceconfig、network、vsys、rulebase などの要素をたどって統一モデルへ値を詰めます。

Palo Alto の仮想システムは vsys として表現されますが、出力側では FortiGate の VDOM と同じ単位で扱われます。これにより、HTML や Excel のセクション生成ロジックがベンダーごとに大きく分岐しないようになっています。

## 12. HA クラスタ処理

HA 構成は `models/cluster.py` の `ClusterConfig` で表現されます。

`ClusterConfig` は、クラスタ全体情報、代表設定、設定差分、クラスタ判定フラグを持ちます。クラスタ全体情報には、クラスタ名、グループ ID、HA モード、メンバー一覧が含まれます。

Web 非同期 API と CLI は、複数ファイルが渡された場合に HA モードを見てクラスタ解析を試みます。`auto` の場合、単一ファイルなら単体解析、複数ファイルならクラスタ解析が選ばれます。クラスタとして判定できない場合は、代表となる設定を使って通常のパラメータシート生成へ進みます。

出力側では、クラスタ概要をグローバルセクションとして扱い、代表 config の各 VDOM/vsys セクションと組み合わせて表示します。

## 13. 統一データモデル

`models/config.py` の `ConfigModel` は、出力形式に依存しない中心モデルです。

大きなカテゴリは、機器概要、システム設定、インターフェース、ルート、動的ルーティング、DHCP、オブジェクト、ファイアウォールポリシー、Local-in ポリシー、NAT、VPN、セキュリティプロファイル、HA、ログ・監視設定です。

このモデルがあることで、FortiGate と Palo Alto の設定構造が違っていても、出力層は同じ抽象構造を読めます。たとえば、FortiGate の VDOM と Palo Alto の vsys、FortiGate の policy と Palo Alto の rulebase は、出力上のセクションでは同じ読み方ができます。

`default_fields` は、パーサが値を明示的に取得できなかった場合に、FortiGate のデフォルト値などを注釈付きで表示するために使われます。これは、空欄と「機器の既定値として推定した値」を区別するための重要な補助情報です。

## 14. HTML 出力

`exporters/html.py` の `HTMLExporter` は、最も基本となる出力形式です。

グローバルセクションには、クラスタ概要、機器概要、システム設定、HA 設定、ログ・監視設定があります。VDOM/vsys 単位のセクションには、ネットワーク設定、オブジェクト定義、ファイアウォールポリシー、NAT、VPN、セキュリティプロファイルがあります。

HTML 出力は、ツールチップ、バッジ、VDOM/vsys ごとのフィルタリング、Internet Service 名の解決、印刷向け CSS などを含みます。オブジェクト名から詳細を引く lookup を構築し、ポリシー表の中でアドレス、サービス、セキュリティプロファイルなどの詳細を参照しやすくしています。

`for_pdf=True` の場合は、PDF 変換に不要な JavaScript などを削った HTML を生成します。PDFExporter はこのモードを利用します。

## 15. PDF 出力

`exporters/pdf.py` の `PDFExporter` は、HTMLExporter で PDF 用 HTML を生成し、WeasyPrint で PDF に変換します。

PDF 変換は重くなりやすいため、PDF 用 CSS、WeasyPrint の CSS オブジェクト、FontConfiguration をキャッシュしています。ヘッダーにはホスト名またはクラスタ名と作成日を入れるため、動的なヘッダー CSS は毎回生成されます。

WeasyPrint のネイティブ依存が読み込めない環境では PDFExporter の import が失敗します。その場合、Web アプリは任意依存読み込み層で PDF 利用不可として扱い、アプリ起動自体は継続します。

## 16. Excel 出力

`exporters/excel.py` の `ExcelExporter` は、openpyxl を使って編集可能な `.xlsx` を生成します。

HTML と同様に、グローバルセクションと VDOM/vsys 単位セクションを分けています。Excel 固有の処理は mixin に分割されており、共通処理、グローバルシート、VDOM/vsys シートが別ファイルに整理されています。

openpyxl がない環境では Excel 出力は利用できません。CLI では ExcelExporter が使えない場合に実行時エラーとなり、Web ではアップロード時の依存チェックで利用者向けエラーを返します。

## 17. Web アプリ初期化

`app.py` の `create_app()` は、Flask アプリを作る中心です。

主な処理は、設定適用、アップロードフォルダ設定、Swagger 設定、レート制限初期化、JobProcessor の生成、ルート登録、エラーハンドラ登録、リクエストフック登録、クリーンアップスレッド起動です。

任意依存は `web/dependencies.py` に集約されています。flask-limiter、WeasyPrint、openpyxl、Prometheus メトリクスがなくても、利用できない機能だけを無効化してアプリを起動できます。

module-level の `app = create_app()` も残っているため、Gunicorn などから `app:app` として起動できます。

## 18. メタデータと成果物保存

Web 経路では、アップロードされた入力ファイル、生成成果物、メタデータが `UPLOAD_FOLDER` 配下に保存されます。

`utils/storage.py` は、Flask の `current_app` に依存しない設計です。非同期ジョブのワーカースレッドからも使えるよう、アプリ初期化時に `set_upload_folder()` で保存先を注入します。

メタデータは `<file_id>.meta.json` として保存されます。保存時は一度テンポラリファイルに書き込み、`os.replace()` で置換します。これにより、読み込み側が書き込み途中の JSON を読むリスクを下げています。

進捗更新は `update_progress()` が担当します。進捗率は 0 から 100 に丸められ、ステージ名、メッセージ、追加情報がメタデータへ反映されます。

## 19. バリデーションと安全性

入力検証は、利用者に近い Web ルートで早めに行われます。

主な検証対象は、ファイル選択有無、拡張子、出力形式、任意依存の利用可否、HA モード、ファイルサイズ、ファイル内容です。出力先や入力保存先は `ensure_child_path()` によってアップロードフォルダ配下に制限されます。

Palo Alto XML の解析では、`defusedxml` が利用可能な場合に安全な XML パーサを使います。設定ファイルはネットワーク機器からの入力であっても、Web アプリから見ると利用者アップロードデータなので、XML パース時の安全性は重要です。

ファイル ID は UUID として発行され、メタデータ取得時にも `Path(file_id).name` と一致することを確認します。これにより、単純なパストラバーサルの混入を避けます。

## 20. エラー処理

利用者向けエラーは、Web ルートで JSON と HTTP ステータスに変換されます。

代表的なエラーコードは、ファイル未選択、未対応形式、出力形式不正、HA モード不正、依存不足、文字コードエラー、内部エラーです。非同期ジョブ中のエラーは、HTTP レスポンスではなくメタデータの `status: error` と進捗メッセージとして保存されます。

本番環境では、内部例外の詳細をそのまま利用者へ返さず、「詳細はログを確認してください」という表現に丸めます。開発環境ではデバッグしやすいように例外文字列が含まれる場合があります。

## 21. ログとメトリクス

ログ設定は `web/config.py` と `utils/logging_config.py` に整理されています。CLI は `main.py` で基本的な logging を設定し、`-v` によって DEBUG 相当の詳細ログを有効にします。

Prometheus メトリクスが利用可能な場合は、リクエスト、アップロード、処理結果、エラーなどを記録します。任意依存がない場合は no-op 実装に切り替わるため、メトリクスなしでもアプリ自体は動作します。

## 22. テストの見方

テストは `tests/` 配下に整理されています。

ルート系のテストは、Web API の入力検証、非同期処理、ジョブ進捗、ヘルスチェックを確認します。パーサ系のテストは、FortiGate、Palo Alto、機器識別、Internet Service などの抽出挙動を確認します。エクスポータ系のテストは、HTML、Excel、Excel 部品、スタイルを確認します。

PDF まわりはネイティブ依存に左右されるため、`pdf` marker で分けられています。Linux や Docker では PDF を含めて検証し、依存が揃わないローカル環境では `pytest -m "not pdf"` のように除外して実行できます。

## 23. 機能追加の進め方

新しい抽出項目を追加する場合は、次の順で考えると影響範囲を抑えやすくなります。

1. `models/config.py` に、その項目を表すフィールドまたは dataclass が既にあるか確認します。
2. 既存モデルに収まるならモデル追加を避け、該当 parser/converter だけを変更します。
3. FortiGate の場合は `parsers/fortigate/converters/` の該当カテゴリに抽出処理を追加します。
4. Palo Alto の場合は `parsers/paloalto.py` または set CLI 補助側に抽出処理を追加します。
5. HTML 出力が必要なら `exporters/html.py` の該当セクションに表示を追加します。
6. Excel 出力が必要なら `exporters/excel_parts/` の該当シート生成処理に列や行を追加します。
7. PDF は基本的に HTMLExporter を経由するため、PDF 専用表示差分が必要かだけ確認します。
8. パーサ、モデル、エクスポータのテストを追加または更新します。
9. `docs/SPECIFICATION.md` の抽出項目や出力仕様に反映します。

新しいベンダーや大きく異なる形式を追加する場合は、`BaseConfigParser` を継承したパーサを追加し、機器識別と `get_parser_for_content()` の選択対象に加えるのが基本です。そのうえで、既存の `ConfigModel` に入る形へ変換します。

## 24. 出力形式追加の進め方

新しい出力形式を追加する場合は、`services/conversion.py` の `extension_for_format()` と `export_config()` に形式を追加します。

出力クラスは、`ConfigModel` と `ClusterConfig` の両方を受け取れるようにするのが望ましいです。少なくとも、ClusterConfig を受け取った場合に primary_config を使うのか、クラスタ全体情報を独自に表示するのかを明確にしてください。

Web から使う場合は、出力形式のバリデーション、任意依存チェック、UI の選択肢、ダウンロード MIME type も合わせて見直します。

## 25. API 追加の進め方

新しい HTTP エンドポイントを追加する場合は、機能に近い `routes/` モジュールに `register(app, ...)` 形式でルート登録関数を置き、`app.py` の `create_app()` から呼び出すのが既存パターンです。

入力値の検証や共通エラー応答は、既存の `routes/upload_common.py` や `utils/validation.py` の考え方に合わせます。長時間処理になる場合は、同期レスポンスではなく JobProcessor とメタデータ進捗を使う構成を優先してください。

## 26. 運用時の確認ポイント

アプリが起動しない場合は、まず任意依存の import 失敗か、Flask 設定の問題かを分けます。WeasyPrint のネイティブ依存が壊れていても、PDF だけを無効にして起動できる設計なので、起動全体が落ちる場合は設定、ルート登録、テンプレート、静的ファイル、権限の問題を疑います。

アップロードが失敗する場合は、拡張子、ファイルサイズ、出力形式、HA モード、任意依存、文字コードを確認します。非同期 API の場合、受付に成功してもジョブ内で失敗することがあるため、`file_id` のメタデータとアプリログを合わせて確認します。

出力ファイルが見つからない場合は、`UPLOAD_FOLDER`、メタデータの `path`、クリーンアップスレッドの削除タイミングを確認します。Docker ではホストとコンテナのボリュームマウントも確認対象です。

PDF 生成だけが失敗する場合は、WeasyPrint と OS 側のフォント・ネイティブライブラリを確認します。Excel 生成だけが失敗する場合は、openpyxl の有無と workbook 生成時の例外を確認します。

## 27. 設計上の重要な前提

HTML が標準出力形式です。PDF は HTML を印刷向けに変換した派生形式で、Excel は編集可能な別表現です。

統一モデルは、ベンダー固有の設定を完全に失わずに共通表示へ寄せるための中心です。出力の都合だけでモデルに表示用文字列を詰めると、別出力形式やテストが扱いにくくなるため、表示整形は exporter 側へ寄せるのが自然です。

Web と CLI の変換挙動は、なるべく `services/conversion.py` を通して共有します。入口ごとに別々の解析ロジックを増やすと、同じ設定ファイルで結果がずれる原因になります。

任意依存は「ないとアプリが落ちるもの」ではなく「ないと一部機能が使えないもの」として扱います。この設計により、軽量な環境でも HTML 変換や基本 UI は動かせます。

## 28. ドキュメント更新ルール

仕様項目、対応機器、抽出項目、出力レイアウトが変わった場合は [SPECIFICATION.md](SPECIFICATION.md) を更新します。

コード構造、処理フロー、拡張方法、運用観点が変わった場合は、この `ARCHITECTURE.md` を更新します。

アーキテクチャ図を更新する場合は、`wallscribe-architecture.architecture.json` を変更し、Archify の `validate` と `deliver` を再実行して `wallscribe-architecture.html` を更新します。図の HTML は生成物ですが、読み手がブラウザで構造を追えるように `docs/` に置いています。

## 29. 今回生成した図の検証情報

Archify の `deliver` は成功しています。

- 種別: `architecture`
- 品質プロファイル: `showcase`
- 検証結果: 9 / 9 checks passed、composition pass、errors 0、warnings 0
- 仕様 SHA-256: `017e33c51c39f40842cb740e8ebfd5fcd8caf8776aca7033891c7e15e68e2435`
- 成果物 SHA-256: `e867bf9fce5b63a3cdca22f979822012ad3318436d8fbbbe511fe5020a74b0bb`

visual-check は Chrome で実行でき、読みやすさ、Viewer Chrome、スクリーンショット取得は成功しました。ただし、1440x900 と 1600x1000 の light/dark 一部条件で縦方向に小さな overflow が残ったため、visual-check 全体の status は `fail` です。一時的なスクリーンショットと検証ログは配布資料に含めません。図のレイアウトを変更する際は visual-check を再実行してください。
