# 設定解析・出力の拡充

WallScribe はベンダー別パーサーで設定を `ConfigModel` に統一し、HTML・Excel・PDF に出力します。今回の変更はこの流れを維持して解析漏れと出力漏れを修正しています。

## FortiGate

- `config global` / `config vdom` を入れ子構造として解析し、複数 VDOM の設定と順序を保持。
- 同一セクション・エントリーの再登場、`append` / `unselect` / `unset` を反映。
- 引用符内の空白、エスケープされた引用符、複数行の文字列を保持。
- 閉じていない引用符、ブロック終端の欠落・不一致を解析エラーとして通知。
- ポリシーのスケジュール、送信元・宛先否定、ユーザー・グループ、開始ログ、プロファイルグループを追加。

## Palo Alto

XML と CLI set 形式を共通のモデル変換処理で扱います。CLI は以下のパスに対応しています。

- `deviceconfig system`: hostname、管理 IP・netmask、timezone、DNS primary/secondary。
- `vsys <name>` / `shared`: address、address-group（static / dynamic filter）、service（TCP/UDP destination port）、service-group。
- `vsys <name> rulebase security rules`: ゾーン、アドレス、サービス、アプリケーション、ユーザー、アクション、有効状態、否定条件、スケジュール、ログ、タグ、説明、個別セキュリティプロファイル／プロファイルグループ。
- vsys を省略したオブジェクト・セキュリティルールは `vsys1` に所属。
- 引用符付き名称・値、角括弧によるリスト、複数行での同一ルール追記を保持。

CLI の network、NAT、VPN、Panorama device-group/pre-rulebase/post-rulebase、複数フィールドを連結した一行コマンドなどは今回の対応範囲外です。未対応行・不正な構文は行番号付きで `parse_errors` に記録します。完全な CLI エミュレーターではありません。XML には既存の network/NAT/VPN 解析機能があります。

XML は shared オブジェクト、動的アドレスグループのフィルター、shared/vsys の Syslog 実送信先を追加・修正しました。単一デバイスの名前が `localhost.localdomain` 以外でも解析し、XML エンティティの二重デコードを防ぎます。

## 出力と不具合修正

- HTML / Excel にポリシーの詳細条件を追加。Excel にアプリケーションも出力。
- shared オブジェクトを独立した出力区画に表示し、HTML の参照先ツールチップでも解決。
- HTML のアドレス／サービス一覧を 100 件で打ち切る処理を廃止し、グループ定義も表示。
- 動的アドレスグループのフィルターを HTML / Excel に表示。
- Excel の設定値は文字列として保存し、`=` で始まる値を数式として実行させない。
- 同一パーサーの `parse_content` を再利用しても前回の設定・エラーを引き継がない。

PDF は共通の HTML 出力を使用しますが、幅の広いポリシー表のページレイアウトは実環境での確認が必要です。

## 検証

`tests/test_parser_hardening.py` に、複数 VDOM・再解析・引用符・更新コマンド・CLI ルール・shared オブジェクト・Syslog・HTML 全件出力・Excel の再読み込みによる回帰テストを追加しています。

```sh
python -m pytest -q
```

設定項目の参照先：

- [FortiOS firewall policy CLI reference](https://docs.fortinet.com/document/fortigate/7.6.0/cli-reference/333889629/config-firewall-policy)
- [PAN-OS Configuration API](https://docs.paloaltonetworks.com/ngfw/api/pan-os-xml-api-request-types-and-actions/configuration-api)
