# 構築テスト

パラメータシートの生成に加えて、`/lab` に独立した机上テストを追加。設定ファイルを解析してケースを生成・編集・選択実行し、許可候補、明示拒否、経路不備、未確定を表示する。設定はこの機能では保存しない。パラメータシートの HTML / PDF / XLSX 出力フローは独立して維持する。

## 入力と判断

FortiGate `.conf`、Palo Alto XML / set 形式。2 MB、5000 ポリシー、10000 ルート、5000 IF、10000 オブジェクト、200 ケースが上限。大規模設定は代表ケースに絞って生成し、画面に省略を表示する。全ケース網羅や実機同等の評価は保証しない。

- **代表条件**: ポリシーのアドレス、IF / ゾーン、サービス、App-ID から代表値を作る。生成元のポリシーが許可でも、先行拒否・未確定ルールを優先して確認する。
- **境界条件**: 非標準ポートなどを指定し、設定上は許可が広すぎないかを確認する。拒否の期待値はレビュー用の仮説。業務要件に合わせて編集する。
- **攻撃条件**: 管理・横展開サービスへの到達条件、取得した C2 の宛先・ポート、KEV の認証境界・入力検査などの確認仮説。攻撃ペイロードや IPS シグネチャは実行しない。

各結果は候補ポリシーの順序・区画・ID・名称と一致条件を表示。不一致ポリシーにはアドレス、IF / ゾーン、App-ID、サービスの不一致条件を示す。候補の表示・評価件数を制限しても、先行する未確定候補を無視して後続許可を確定しない。

## vsys と仮想ルーター

Palo Alto の IF import / Layer3 ゾーン、VR 所属 IF、external ゾーン、visible-vsys、next-vr、IPv4 / IPv6 静的ルートを解析。グラフでは VR を独立ノードとして表示し、vsys 境界と転送コンテキストを区別する。未確認の visible-vsys は接続を作らない。next-vr は方向を持つ。IF 所属競合は解析警告にする。

机上テストは入口 VR から最長一致で経路を探索。破棄経路、無効 IF、未定義の出口 IF / VR、next-vr 循環、同順位の経路、出口ゾーンとの不一致、next-hop のネットワーク外を表示。PAN の admin-dist と metric を分離する。省略された優先度を勝手に補完して経路競合を解決しない。

別 vsys への出口は両側のポリシーを確認する対象。external / visible-vsys が双方にある場合は接続先のポリシーも提示するが、境界をまたぐ疎通の確定判定はしない。動的ルーティング、PBR、NAT、VPN、shared gateway、Advanced Routing / logical-router、Panorama の実効 pre / post 順序、戻り経路、稼働状態は未確定として扱う。

## ISDB / App-ID

FortiGate の宛先・送信元 ISDB 名 / ID と否定条件を保持。未モデル化された custom / group / IPv6 固有の条件は未確定として扱う。App-ID は具体的な識別値をケースに仮定して評価し、設定内の custom application と application-group、application-default のポートを参照する。application-filter、未解決グループ、識別中の変化・依存アプリは実通信の確認が必要。

実機の ISDB / App-ID の動的 DB 自体は設定バックアップに含まれない。必要なら補助 DB を入力する。これは仮定した DB 全体のスナップショットとして評価するため、部分的なサンプルを入れて実機と同じ判定だと解釈しない。未指定の項目は未確定になる。補助データは provenance（出典・バージョン・取得日時）を必須にする。

```json
{
  "provenance": "実機の DB バージョンと取得日時を記入",
  "applications": {"custom-app": ["tcp/8443"]},
  "internet_services": {
    "12345": [{"network": "198.51.100.0/24", "ports": ["tcp/443"]}]
  }
}
```

## Feed

「Feed を取得・確認」で固定の HTTPS 配信元からサーバー側で取得する。ユーザー指定 URL は受け付けず、リダイレクトを拒否し、受信サイズは 5 MB、接続タイムアウトは 8 秒、キャッシュは 15 分。成功取得日時、配信日時、取得失敗を分離する。24 時間を超えたキャッシュはケース生成に使用しない。C2 は online かつ観測が 30 日以内の公開 IP のみ。0 件の場合も指標を作り足さない。全件一覧ではなく、KEV は最新 100 件、C2 は最大 100 件をレビューに使用する。KEV は同一の確認条件を増やし過ぎないようカテゴリ別に代表ケースを作る。

取得した情報は攻撃実績・通信条件の参考であり、本設定や機器が脆弱であることの証明ではない。実行可能な攻撃コードの取得、C2 への接続、機器設定の変更は行わない。

## API

- `POST /api/lab/generate`: multipart `config`、任意の `catalog` JSON。
- `POST /api/lab/run`: 同じ設定・補助 DB と `cases` JSON。クライアントの期待値を判定根拠として使わず、条件を再検証して評価する。
- `POST /api/lab/feeds/cisa-kev` と `/feodo`: 公開 Feed を取得。

それぞれ毎分 10 リクエスト。各リクエストは状態を共有せず設定を再解析。公開 Feed のキャッシュのみプロセス内で共有。マルチワーカー間では Feed キャッシュが独立する。

## 検証

既存機能の回帰に加え、XXE、不正 IP / ポート / DB、存在しない区画・VR、ISDB 否定と未解決参照、App-ID グループ循環、優先拒否、無効 IF、破棄経路、VR 循環、NAT / PBR の誤った成功判定、古い Feed、受信サイズ上限、5000 ポリシー × 200 ケースの未一致負荷、参照の循環とダイヤモンド型のグループが指数的に展開しないことを検証する。

## 公式資料

- [PAN: Communication Between Virtual Systems](https://origin-docs.paloaltonetworks.com/ngfw/administration/virtual-systems/communication-between-virtual-systems)
- [PAN: Configure Inter-Virtual System Communication](https://docs.paloaltonetworks.com/ngfw/administration/virtual-systems/configure-inter-virtual-system-communication-within-the-firewall)
- [PAN: Application-default](https://docs.paloaltonetworks.com/ngfw/administration/app-id/application-default)
- [FortiOS 7.2.9: Using Internet Service in a policy](https://docs.fortinet.com/document/fortigate/7.2.9/administration-guide/179236/using-internet-service-in-a-policy)
- [CISA KEV JSON](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json)
- [Feodo Tracker の公開 Feed と更新条件](https://feodotracker.abuse.ch/blocklist/)
