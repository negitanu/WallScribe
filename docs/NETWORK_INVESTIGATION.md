# ネットワーク調査と人による判断

WallScribe は設定を根拠に調査候補と不確実な点を示します。最終判断は担当者が行います。疎通を実証するツールではなく、実機へのプローブ、変更、削除は行いません。

## HTML レポート

出力項目の「通信候補の確認」「整理候補」「解析範囲・人の確認」を選択します。

「通信候補の確認」で、NAT 変換前の送信元 IP、宛先 IP、TCP/UDP、宛先ポート、VDOM/vsys を指定します。IF/ゾーン名を条件通りに入力すると候補を絞れます。未入力の場合は IF/ゾーン条件を確定しません。IPv4、IPv6、静的サブネット、IP 範囲、スコープ別グループ、TCP/UDP の宛先ポート範囲を照合します。

候補ポリシーは設定順に表示し、先行する候補も示します。FQDN、循環参照、組み込みサービス、application-default、App-ID、ユーザー、スケジュール、送信元ポート、未モデル化オプション、未検証の省略値は、情報不足として残します。「設定上の条件が一致」も実通信が可能という意味ではありません。暗黙ルール、上位/下位のルール、実効設定を含む完全なルール順序を保証しません。

ルートは宛先プレフィックスに該当する静的設定と IF から推定した直結候補です。プレフィックスの長い順に並べますが、Distance/Priority、VR の所属、実稼働の FIB、SD-WAN、PBR、戻り経路を含めた実効経路は確定しません。

NAT は変換前送信元・宛先アドレスを照合します。IF/ゾーン、サービス、ポート、適用順序の確定は人に委ねます。IP Pool は選択条件の不足した候補として表示されます。変換後のポリシー/ルートを自動評価しないため、候補がないことを不通の証明にしないでください。

通信照合はブラウザー内で完結します。HTML レポートに照合に必要な正規化設定を埋め込むため、レポートにはアドレス・ポリシー情報が含まれます。外部照合サービスへの送信はありません。VPN 秘密鍵やパスワード、未解析の原文は照合データに埋め込みません。

## 図から調査

高重要度の指摘に関連する IF と許可ルールは赤、他の確認事項は黄で表示します。関連ルールの図は通信条件の図であり物理配線ではありません。IF/ルールをクリックすると同じレポート内の設定概要、指摘、改善案へ移動します。色のない要素は安全の保証ではありません。

## 整理候補

解析済みポリシー、Local-in、NAT、グループを参照して、アドレスとアドレスグループの未参照候補を抽出します。無効なルールからの参照も保持します。全モデル通信条件の一致するルール、先行ルールの名前ベース条件集合に含まれる可能性があるルールも表示します。

サービスとサービスグループは、標準定義と独自定義を確実に区別できないため、未参照・同一定義の整理候補を表示しません。標準定義の整理判断をユーザーに求めず、通常の設定一覧には引き続き掲載します。この方針は HTML / PDF / Excel / 解析 JSON に共通です。

削除候補は削除推奨ではありません。VPN/PBR/外部管理設定等の未モデル化参照、ログ/ヒット数、動的評価、オブジェクト名の運用目的を人が確認してください。削除コマンドは生成しません。

## 解析範囲と人の判断

HTML / PDF / Excel の確認一覧には、未解決参照、参照循環、動的グループ、IF 所属/管理プロファイルの不明点、補った既定値を掲載します。大量に発生する未対応/部分解析の設定パスは表示しません。内部の解析記録と解析 JSON には保持し、通信評価の不確実性の判定にも引き続き使います。表示を省略しても全オプションの網羅を保証するものではありません。秘密情報保護のため、パース警告は件数を示し原文を再掲しません。

HTML の確認事項に「未確認」「保留」「対応予定」「確認済み・変更不要」と判断根拠を記入できます。「人の判断を JSON 保存」で一覧を保存します。画面を閉じると入力は失われ、自動保存・共有・設定反映は行いません。ダウンロードを扱えない環境では保存用 JSON の表示を開いてコピーして保存できます。JSON を再読込する機能はありません。Excel でも判断/根拠の記入列を用意しています。

## 既定値の公式資料と版

既定値カタログは `analyzers/review.py` にあります。登録値だけを対象版に照合します。公式資料の既定値は稼働機の実効値の証明ではありません。

初期カタログで確認した資料（確認日: 2026-09-30）:

- [FortiOS 7.4.8 config system global](https://docs.fortinet.com/document/fortigate/7.4.8/cli-reference/339914554/config-system-global): HTTPS 管理ポート 443、SSH 管理ポート 22。パッチ版 7.4.8 のみ照合。
- [PAN-OS 11.1 Security Policy](https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-admin/policy/security-policy): 暗黙 intrazone は allow、interzone は deny。11.1 系の資料として表示し、パッチ個別の検証と実機上書きの確認が必要。疎通判定には流用しない。

未登録の版・項目・版不明の場合は「既定値未検証」として、該当版の公式資料と実効設定の取得を促します。別版の値は流用しません。従来の版に依存しない FortiGuard DNS/NTP 等の補完表示は停止しました。資料は実行時に自動取得せず、未検証の値を黙って採用しません。

Palo Alto XML の `detail-version` と `version` を区別します。`version` のみの場合は設定スキーマ版として扱い、ファームウェアとの照合を保留します。実機で確認した版は CLI の `--firmware-version` で指定できます（HA は代表機への指定）。クラスタ解析も代表機の設定を対象とするためメンバー差分は別途確認してください。

## CLI / JSON / Excel / PDF

```bash
python main.py config.conf -o report.html \
  --flow 192.0.2.5 198.51.100.7 TCP 443 --flow-scope root \
  --source-interface lan --destination-interface wan \
  --analysis-json investigation.json

python main.py firewall.xml -o report.html \
  --firmware-version 11.1.4-h7 --flow-scope vsys1 \
  --flow 192.0.2.5 198.51.100.7 TCP 443 --analysis-json investigation.json
```

`--analysis-json` には従来の security/topology と cleanup/review を格納し、`--flow` 指定時に flow を追加します。JSON 未指定の通信照合結果は標準出力に表示します。入力 IP/ポート等のエラーは失敗として扱います。

Excel は整理候補・確認一覧を含みます。Excel/PDF の通信入力は HTML または CLI を利用します。PDF には図と確認事項を静的に掲載し、ブラウザーの入力機能は含めません。

Docker は変更後に `docker compose up -d --build` で再ビルドしてください。

## 2026-10-01: バージョン系列を踏まえた条件の拡張

FortiOS 7.2 以降の `firewall security-policy` を通常のポリシーに加えて読み取り、Application・URL カテゴリ・送信元/宛先 Internet Service 有効状態を保持します。ISDB が有効な方向では通常のアドレス照合で候補を除外せず、宛先 ISDB ではサービスも未確定として扱います。ISDB 自体の内容や実効評価は静的設定では確定しません。

PAN-OS 10.0 以降のルール形式について、`rule-type`（universal / intrazone / interzone）、URL カテゴリを保持します。入力ゾーンがある場合は同一/異なるゾーンを評価し、ない場合は未確定を返します。intrazone の宛先ゾーン省略にも対応します。reset-client/server/both は通信を通過させないアクションとして DROP に正規化します（リセット方式の区別はモデルでは保持しません）。HTML 内の JavaScript と Python の照合結果を同じ追加ケースで比較します。

整理候補の同条件比較にも新しい条件を含め、先行するゾーン限定・カテゴリ限定・ISDB ルールから広い包含関係を断定しません。広すぎる許可の診断では ISDB と URL カテゴリの制約を考慮します。

検証ケースは FortiOS 7.2.2 / 7.4.8 / 7.6.2、PAN-OS 10.0 / 10.2 / 11.1 の形式を明示した合成設定です。実機設定の全オプション・全リリースの完全対応を保証するものではありません。Panorama の継承・pre/post rulebase、NGFW の pre-match、App-ID、動的情報、NAT 適用後の評価は引き続き実効順序・実行時情報の確認が必要です。XML の config version はファームウェアバージョンの証明には使いません。

参照した公式資料:
- [FortiOS 7.2.2 firewall policy CLI](https://docs.fortinet.com/document/fortigate/7.2.2/cli-reference/325620/config-firewall-policy): ISDB 有効時は宛先アドレスとサービスを使用しないこと、送信元 ISDB のアドレス扱い。
- [FortiOS 7.2.2 security-policy CLI](https://docs.fortinet.com/document/fortigate/7.2.2/cli-reference/324620/config-firewall-security-policy): ISDB、アプリ条件と送信元アドレスの扱い。
- [FortiOS 7.4.8 NGFW policy](https://docs.fortinet.com/document/fortigate/7.4.8/administration-guide/243446/ngfw-policy): policy-based NGFW、pre-match、Central NAT。
- [PAN-OS 10.2 Security rule building blocks](https://docs.paloaltonetworks.com/ngfw/help/10-2/policies/policies-security/building-blocks-in-a-security-policy-rule): ゾーン種別、URL カテゴリ、application-default、拒否アクション。
- [PAN-OS 10.0 VM-Series ガイド](https://docs.paloaltonetworks.com/content/dam/techdocs/ja_JP/pdf/vm-series/10-0/vm-series-deployment-10-0-ja-jp.pdf): universal / intrazone / interzone のルール形式。

出力では許可ルールを「どこから、どこへ、何を許可する設定か」と説明し、日本語の対象・追加条件で表示します。実際の通信可否を示すものではなく、許可範囲が意図通りかの確認に利用します。判断記録の保存は任意の折り畳みメニューに移し、引き継ぎに必要な場合だけ JSON をダウンロードできます。入力した判断は自動保存されません。

許可ルールの通信条件一覧は既存のポリシー一覧と重複するため、推定ネットワーク構造から削除しました（HTML / PDF / Excel）。構造図、指摘に関連するポリシー図、元のポリシー一覧、通信候補の照合は継続して利用できます。

「整理候補」「解析範囲・人の確認」は、人間側の操作フローが未定義のためパラメータシートと生成画面の選択肢から削除しました。既存の保存済み選択や明示的な旧セクション指定でも出力されません。分析内部と CLI の分析 JSON は継続します。
