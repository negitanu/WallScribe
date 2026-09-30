# セキュリティ診断と推定ネットワーク構造

設定からパラメータシートを生成する際に、診断結果と論理構造を追加出力できます。FortiGate / Palo Alto の共通モデルを使い、装置への接続や設定データの外部送信を行わずに分析します。

## 使い方

Web 画面の「診断・構造図」で、**セキュリティ診断**と**推定ネットワーク構造**を選択してください。両項目は初期状態で選択されています。

- HTML: 重要度・根拠・改善案・確信度を含む診断一覧、SVG の構造図、許可ポリシーの通信条件。
- Excel: 「セキュリティ診断」「推定ネットワーク構造」シート。構造はノード・接続・根拠の一覧として保存します。
- PDF: HTML と共通の診断・図を出力します。WeasyPrint のネイティブ依存関係が必要です。

CLI では既定のレポートに両機能が含まれます。JSON を併せて保存する例:

```sh
python main.py firewall.conf -o report.html --analysis-json analysis.json
python main.py firewall.xml -f excel -o report.xlsx --analysis-json analysis.json
```

Python からは出力対象を指定できます。

```python
from exporters.html import HTMLExporter
HTMLExporter(config, sections=["security_analysis", "topology"]).export("analysis.html")
```

JSON は `schema_version: 1` で、`security`（findings / checks / limitations）と `topology`（nodes / edges / flows / limitations）を含みます。入力設定・出力レポートと同じ保存先は指定できません。

## 診断項目

- `MGMT-CLEARTEXT`: 有効な IF に HTTP / Telnet の管理アクセスが設定されている。
- `MGMT-PUBLIC`: 公開 IP の IF に管理サービスが設定されている。IF の接続元制限の有無に応じて重要度を調整する。
- `ADMIN-SOURCE`: 解析された管理者に限定された trusted hosts / permitted IP がない。
- `POLICY-BROAD`: 有効な許可ルールが送信元・宛先・サービスを広く許可している。Palo Alto はアプリケーションの `any` も確認する。
- `POLICY-LOG`: 許可ルールのモデル上でログ取得が無効。
- `POLICY-PROFILE`: 脅威検査プロファイルの参照がない。内部通信など検査不要のケースもあるため、確認項目として表示する。
- `SNMP-LEGACY`: SNMP v1 / v2c が有効。
- `DATA-PARTIAL` / `DATA-MGMT`: 未対応の入力行や、実設定を取得できない管理プロファイルを通知する。

指摘は「高」「中」「確認」に分類し、対象・設定の根拠・改善案・確信度を表示します。`ADMIN-SOURCE` や公開 IP の指摘は、他の ACL / local-in policy で保護されている可能性があるため、実際の外部露出を断定しません。

拒否・無効ルールや無効 IF は危険判定の対象から除外します。アドレス否定、Internet Service 指定、限定アプリケーション、`application-default` を単純な any-any ルールとして扱いません。静的アドレスグループは区画と shared の名前解決を区別し、循環参照や深い入れ子にも対応します。

Palo Alto のデータプレーン IF は、参照している Interface Management Profile を解決し、実際の許可プロトコル・permitted IP を取り込みます。未解決のプロファイル名からサービスの有効性を推測しません。専用 MGT インターフェースのサービス設定や SNMPv3 の認証・暗号化強度など、共通モデルで解析していない項目は診断しません。

参照する公式資料:

- [FortiOS Hardening](https://docs.fortinet.com/document/fortigate/7.6.0/best-practices/555436/hardening)
- [PAN-OS Interface Management Profiles](https://docs.paloaltonetworks.com/ngfw/networking/configure-interfaces/use-interface-management-profiles-to-restrict-access)

## 構造図の読み方

VDOM / vsys ごとに、直結ネットワーク → IF → 同一装置内の論理区画 → 静的ルートを並べます。

- 実線: 設定上の IF 所属、静的ルート。
- 破線: IF アドレスとプレフィックスから導いた直結ネットワークの推定。
- 赤いルート: blackhole / 破棄経路。
- 所属が判断できない Palo Alto の IF / virtual-router は「所属未確定」の区画として表示。

図が大きくなる場合は 4 行ごとに分割し、長い名称・IPv6 アドレスは折り返します。ノードは省略せず、接続根拠は JSON / Excel に保存します。

デフォルトルートからインターネット接続を断定しません。許可ポリシーは図の下に通信条件として別記し、物理配線として扱いません。スイッチ、隣接機器、VPN 対向の実配線、動的経路の稼働状態、実際の到達性はこの図では確認できません。

HA クラスタ入力では代表機 (`primary_config`) の診断・論理構造を出力します。メンバーごとの設定差分や HA の物理接続は対象外です。

## 判断の限界と検証

設定の静的診断であり、CVE 照合、侵入テスト、稼働状態の検証ではありません。未対応のパース行・省略値・動的オブジェクト・ルール順序によって診断範囲が制限されます。指摘がないことは安全性の証明ではありません。

`tests/test_insights.py` で、実設定のパース、診断の誤検知抑制、区画・shared の参照、深いグループ、図の分割、文字エスケープ、HTML/PDF 向け HTML、Excel 再読み込み、CLI JSON 出力を検証します。ブラウザでは合成設定による診断一覧と構造図を視覚確認しています。PDF 実生成はネイティブ依存が利用可能な環境で別途確認してください。
