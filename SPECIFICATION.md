# WallScribe 仕様書

**バージョン 1.0**  
**最終更新日: 2026-01-20**

## 1. 概要

### 1.1 目的

#FortiGate と #PA-Series ファイアウォールの設定ファイルから、統一フォーマットのパラメータシートを自動生成するツール。

### 1.2 対象機器

| ベンダー           | 機種                    | 設定ファイル形式       |
| ------------------ | ----------------------- | ---------------------- |
| Fortinet           | FortiGate シリーズ      | `.conf` (テキスト形式) |
| Palo Alto Networks | PA シリーズ (PA-440 等) | `.xml` (XML 形式)      |

### 1.3 出力形式

- **HTML**: スタイル付きの見やすいレポート（印刷対応、インタラクティブツールチップ付き）
- **PDF**: 印刷に最適化されたPDF形式（章がページをまたがない）
- **Excel (.xlsx)**: 編集可能なスプレッドシート形式

---

## 2. 機能要件

### 2.1 入力処理

#### 2.1.1 FortiGate 設定ファイル (.conf)

- FortiOS 6.x / 7.x 形式に対応
- VDOM（Virtual Domain）構成に対応
- UTF-8 エンコーディング

#### 2.1.2 Palo Alto 設定ファイル (.xml)

- PAN-OS 10.x / 11.x 形式に対応
- vsys（Virtual System）構成に対応
- UTF-8 エンコーディング

### 2.2 抽出項目

両機種で共通の情報を抽出し、統一フォーマットで出力する。

#### カテゴリ 1: 機器概要

| 項目          | FortiGate                  | Palo Alto                      | 説明                       |
| ------------- | -------------------------- | ------------------------------ | -------------------------- |
| ホスト名      | `system global > hostname` | `deviceconfig/system/hostname` | 機器名                     |
| モデル名      | ヘッダから抽出             | -                              | 機種名                     |
| OS バージョン | ヘッダから抽出             | XML 属性 `version`             | ファームウェアバージョン   |
| シリアル番号  | -                          | -                              | 設定ファイルからは取得不可 |
| 動作モード    | `opmode`                   | -                              | NAT/Route, Transparent     |

#### カテゴリ 2: システム設定

| 項目             | FortiGate          | Palo Alto                        | 説明                |
| ---------------- | ------------------ | -------------------------------- | ------------------- |
| 管理 IP          | `system interface` | `deviceconfig/system/ip-address` | 管理用 IP アドレス  |
| 許可プロトコル   | `allowaccess`      | `service`                        | HTTPS, SSH, Ping 等 |
| NTP サーバー     | `system ntp`       | `ntp-servers`                    | 時刻同期先          |
| DNS サーバー     | `system dns`       | `dns-setting/servers`            | 名前解決先          |
| タイムゾーン     | `timezone`         | `timezone`                       | タイムゾーン設定    |
| 管理者アカウント | `system admin`     | `mgt-config/users`               | 管理ユーザー一覧    |

#### カテゴリ 3: ネットワーク設定

| 項目                  | FortiGate                 | Palo Alto                                      | 説明                   |
| --------------------- | ------------------------- | ---------------------------------------------- | ---------------------- |
| 物理インターフェース  | `system interface`        | `network/interface/ethernet`                   | 物理ポート設定         |
| VLAN インターフェース | `system interface (vlan)` | `network/interface/vlan`                       | VLAN 設定              |
| LAG インターフェース  | `system interface (lag)`  | `network/interface/aggregate-ethernet`         | リンクアグリゲーション |
| ゾーン                | -                         | `zone`                                         | セキュリティゾーン     |
| スタティックルート    | `router static`           | `virtual-router/routing-table/ip/static-route` | ルーティング設定       |
| DHCP サーバー         | `system dhcp server`      | `network/dhcp`                                 | DHCP 設定              |

#### カテゴリ 4: オブジェクト定義

| 項目                 | FortiGate                 | Palo Alto       | 説明                  |
| -------------------- | ------------------------- | --------------- | --------------------- |
| アドレスオブジェクト | `firewall address`        | `address`       | IP アドレス/FQDN 定義 |
| アドレスグループ     | `firewall addrgrp`        | `address-group` | アドレスのグループ化  |
| サービスオブジェクト | `firewall service custom` | `service`       | ポート/プロトコル定義 |
| サービスグループ     | `firewall service group`  | `service-group` | サービスのグループ化  |

#### カテゴリ 5: ファイアウォールポリシー

| 項目                           | FortiGate                         | Palo Alto                    | 説明           |
| ------------------------------ | --------------------------------- | ---------------------------- | -------------- |
| セキュリティポリシー           | `firewall policy`                 | `security/rules`             | FW ルール      |
| Internet Service               | `internet-service-name`           | -                            | FortiGate 固有 |
| NAT ポリシー                   | `firewall vip`, `firewall ippool` | `nat/rules`                  | SNAT/DNAT 設定 |
| Local-in ポリシー              | `firewall local-in-policy`        | -                            | FortiGate 固有 |
| アプリケーションオーバーライド | -                                 | `application-override/rules` | PA 固有        |

#### カテゴリ 6: VPN 設定

| 項目      | FortiGate                 | Palo Alto                       | 説明                 |
| --------- | ------------------------- | ------------------------------- | -------------------- |
| IPsec VPN | `vpn ipsec phase1/phase2` | `network/tunnel/ipsec`          | Site-to-Site VPN     |
| SSL-VPN   | `vpn ssl settings`        | `network/tunnel/global-protect` | リモートアクセス VPN |

#### カテゴリ 7: セキュリティプロファイル

| 項目                       | FortiGate                  | Palo Alto                | 説明               |
| -------------------------- | -------------------------- | ------------------------ | ------------------ |
| アンチウイルス             | `antivirus profile`        | `profiles/virus`         | AV 設定            |
| Web フィルタ               | `webfilter profile`        | `profiles/url-filtering` | URL フィルタリング |
| アプリケーションコントロール | `application list`         | `profiles/application`   | アプリ制御         |
| IPS                        | `ips sensor`               | `profiles/vulnerability` | 侵入防御           |
| SSL インスペクション       | `firewall ssl-ssh-profile` | `profiles/decryption`    | SSL 復号設定       |

##### アプリケーションID解決機能

FortiGateのアプリケーションコントロールプロファイルでは、アプリケーションIDが使用されます。
本ツールでは`static/data/appid.csv`を参照し、IDからアプリケーション名・カテゴリ・リスクレベルを自動解決します。

| フィールド | 説明 |
| ---------- | ---- |
| app_id | アプリケーションID（数値） |
| app_name | アプリケーション名（例: Facebook, Skype） |
| category | カテゴリ（例: Social.Media, Collaboration） |
| risk | リスクレベル（1-5） |
| description | 説明 |

##### Internet Service対応

FortiGateのファイアウォールポリシーで使用されるInternet Service（ISDB）に対応しています。
`internet-service-name`で指定されたサービス名を、`static/data/appid.csv`から解決し、アプリケーション名として表示します。

- Internet Service名はバッジ形式で表示
- ツールチップでサービス名、ISDB ID、アプリケーション名を表示
- 通常のアドレスオブジェクトと区別して表示

#### カテゴリ 8: 高可用性（HA）設定

| 項目                 | FortiGate          | Palo Alto                      | 説明               |
| -------------------- | ------------------ | ------------------------------ | ------------------ |
| HA モード            | `system ha > mode` | `high-availability/group/mode` | A-P / A-A          |
| グループ ID          | `group-id`         | `group-id`                     | HA グループ識別子  |
| 優先度               | `priority`         | `election-option/priority`     | マスター選出優先度 |
| 監視インターフェース | `monitor`          | `link-monitoring`              | 障害検知対象       |

#### カテゴリ 9: ログ・監視設定

| 項目                   | FortiGate             | Palo Alto                  | 説明         |
| ---------------------- | --------------------- | -------------------------- | ------------ |
| Syslog 転送            | `log syslogd setting` | `syslog`                   | ログ転送先   |
| SNMP                   | `system snmp`         | `snmp-trap-server`         | 監視設定     |
| FortiAnalyzer/Panorama | `log fortianalyzer`   | `panorama/panorama-server` | 集中管理連携 |

---

## 3. 出力仕様

### 3.1 HTML 出力

#### 3.1.1 レイアウト構成

```text
[ヘッダー]
  - ドキュメントタイトル
  - 機器名、OSバージョン、作成日

[目次]
  - 各セクションへのページ内リンク

[セクション1: 機器概要]
  - 基本情報（ホスト名、モデル名、シリアル番号、OSバージョン、動作モード、VDOM/vsys）
  - ライセンス情報（サポート、UTM Bundle、AV、Web、IPS有効期限）
  - サマリー（インターフェース数、ルート数、ポリシー数、オブジェクト数、HA状態）

[セクション2: システム設定]
  - 管理アクセス（管理用IPアドレス/サブネットマスク、管理インターフェース、許可プロトコル、HTTPS/SSHポート）
  - 基本設定（DNS、NTP、タイムゾーン）
  - 管理者アカウント（ユーザー名、権限プロファイル、VDOM、信頼ホスト）

[セクション3: ネットワーク設定]
  - インターフェース（物理・VLAN・LAG: 名前、タイプ、役割、IPアドレス、VLAN ID、ゾーン、VDOM、許可アクセス）
  - スタティックルート（名前、宛先ネットワーク、ゲートウェイ、デバイス、VDOM）
  - DHCPサーバー（インターフェース、IP払い出し範囲、サブネットマスク、除外IP、ゲートウェイ、DNS、リース時間）

[セクション4: オブジェクト定義]
  - アドレスオブジェクト（オブジェクト名、タイプ、値、VDOM）
  - アドレスグループ（オブジェクト名、メンバー、VDOM）
  - サービスオブジェクト（オブジェクト名、プロトコル、ポート、VDOM）
  - サービスグループ（オブジェクト名、メンバー、VDOM）

[セクション5: ファイアウォールポリシー]
  - ポリシー一覧（No、ID、ポリシー名、送信元IF、宛先IF、送信元アドレス、宛先アドレス、Internet Service、サービス、アクション、NAT、セキュリティプロファイル、ログ、備考）
  - インタラクティブツールチップ（インターフェース、アドレス、サービス、セキュリティプロファイル、Internet Serviceの詳細情報を表示）
  - Local-in ポリシー（No、ID、ポリシー名、送信元IF、送信元アドレス、宛先アドレス、サービス、アクション、備考）

[セクション6: NAT設定]
  - VIP/DNAT（ルール名、外部インターフェース、外部IP、内部IP、ポートフォワーディング、VDOM、備考）
  - SNAT/IP Pool（ルール名、変換後送信元、インターフェース、VDOM、備考）

[セクション7: VPN設定]
  - IPsec-VPN Phase1（VPN名、対向機器IP、インターフェース、暗号化/認証、DHグループ、ライフタイム、事前共有鍵）
  - IPsec-VPN Phase2（VPN名、Phase1名、ローカルセグメント、リモートセグメント、暗号化/認証、PFS、ライフタイム）
  - SSL-VPN/GlobalProtect（レルム/ポータル名、リスニングポート、インターフェース、認証、払い出しIPプール、許可ユーザーグループ、モード）

[セクション8: セキュリティプロファイル（UTM）]
  - プロファイル一覧（プロファイル名、タイプ、有効/無効、VDOM、説明）
  - アンチウイルスプロファイル（プロファイル名、有効/無効、スキャンモード、スキャン対象プロトコル、アクション）
  - Webフィルタプロファイル（プロファイル名、有効/無効、適用カテゴリ、アクション）
  - アプリケーションコントロールプロファイル（プロファイル名、有効/無効、適用カテゴリ/シグネチャ、アクション）
  - IPSプロファイル（プロファイル名、有効/無効、適用シグネチャ、アクション）
  - SSLインスペクションプロファイル（プロファイル名、有効/無効、モード）

[セクション9: HA設定]
  - HA基本設定（HAモード、グループID、優先度、プリエンプト）
  - 監視設定（監視インターフェース、HAインターフェース）

[セクション10: ログ・監視設定]
  - ログ転送（サーバーIPアドレス、ポート、転送ログ種別、状態）
  - 集中管理（FortiAnalyzer/Panoramaサーバー）
  - SNMP（SNMP有効化、バージョン、コミュニティ名/ユーザー名、ホスト、トラップ送信先IPアドレス）
[フッター]
  - ファイル名、生成情報
```

#### 3.1.2 スタイル仕様

- レスポンシブデザイン対応
- 印刷用スタイル（@media print）対応
- アクション表示の色分け
  - allow/accept: 緑色
  - deny: 赤色
  - drop: 暗赤色
- ゾーンタグの視覚的表示
  - Trust 系: 緑背景
  - Untrust 系: 赤背景
  - DMZ 系: 黄背景

#### 3.1.3 インタラクティブツールチップ機能

HTML出力では、以下のオブジェクトにマウスオーバーで詳細情報を表示するツールチップ機能を提供します：

- **インターフェース**: IPアドレス、サブネットマスク、ゾーン、役割、許可アクセス
- **アドレスオブジェクト**: タイプ、値、CIDR表記、説明
- **サービスオブジェクト**: プロトコル、ポート範囲、説明
- **セキュリティプロファイル**: タイプ、名前、設定内容
- **Internet Service**: サービス名、ISDB ID、アプリケーション名

ツールチップは表の境界を越えて表示され、画面端で自動的に位置調整されます。

#### 3.1.4 CIDR表記への自動変換

IPアドレスとサブネットマスクの組み合わせを、自動的にCIDR表記（例: `192.168.1.0/24`）に変換します。

- アドレスオブジェクト（subnetタイプ）
- インターフェースのIPアドレス
- ルーティング情報の宛先ネットワーク

### 3.2 PDF 出力

#### 3.2.1 概要

HTML出力をベースに、WeasyPrintを使用してPDF形式で出力します。
章（セクション）がページをまたがないよう、CSSの `page-break-inside: avoid` を適用しています。

#### 3.2.2 ページ設定

- 用紙サイズ: A3 横向き（landscape）
- 余白: 1.5cm（上下左右）
- ヘッダー: 「パラメータシート」
- フッター: ページ番号（「ページ X / Y」形式）
- フォントサイズ: ベース9pt、テーブル7pt（折り返しを減らすため最適化）

#### 3.2.3 ページ分割ルール

- **章（section）**: ページをまたがない（`page-break-inside: avoid`）
- **セクション見出し（h2）**: ページの先頭に配置されるよう調整
- **テーブル行（tr）**: 可能な限りページをまたがない
- **目次**: 独立したページに配置（`page-break-after: always`）
- **ヘッダー・フッター**: ページ分割時に適切に配置

#### 3.2.4 日本語フォント対応

- **フォント**: Noto Sans CJK JP（日本語フォント）を使用
- **フォントサイズ最適化**: 折り返しを減らすため、ベース9pt、テーブル7ptに調整
- **文字化け対策**: Dockerイメージに`fonts-noto-cjk`パッケージをインストール

#### 3.2.5 レイアウト

HTML出力と同じレイアウト構成を維持し、印刷に最適化されたスタイルを適用します。

### 3.3 Excel 出力

#### 3.3.1 シート構成

Excel出力は、**グローバル設定**と**VDOM/vsys単位の設定**に分けて出力されます。

##### グローバル設定シート（VDOM横断の共通設定）

| シート名         | 内容                             |
| ---------------- | -------------------------------- |
| クラスタ概要     | HAクラスタ情報（クラスタ構成時のみ） |
| 機器概要         | 機器基本情報、設定統計           |
| システム設定     | 管理設定、NTP、DNS、管理者アカウント等 |
| HA設定           | 高可用性設定                     |
| ログ・監視設定   | Syslog、SNMP、集中管理設定       |

##### VDOM/vsys単位のシート

各VDOM/vsysごとに、以下のシートが作成されます（シート名は「タイトル (VDOM名)」形式）：

| シート名         | 内容                             |
| ---------------- | -------------------------------- |
| IF (VDOM名)      | ネットワークインターフェース一覧 |
| ルート (VDOM名)  | スタティックルート一覧           |
| オブジェクト (VDOM名) | アドレス/サービスオブジェクト    |
| ポリシー (VDOM名) | ファイアウォールポリシー、Local-inポリシー |
| NAT (VDOM名)     | NAT設定                          |
| VPN (VDOM名)     | IPsec VPN、SSL-VPN設定           |
| セキュリティ (VDOM名) | セキュリティプロファイル         |

**注意**: データが存在しないVDOMのシートは作成されません。

#### 3.3.2 スタイリング機能

##### モダンカラーパレット

- **VDOMごとの色テーマ**: 各VDOM/vsysに異なる色テーマを自動割り当て（最大10個のカラーパレット）
  - Indigo（デフォルト/root）、Emerald、Amber、Rose、Cyan、Violet、Orange、Teal、Pink、Sky
- **タブ色**: 各シートのタブにVDOMごとの色を設定
- **ヘッダー**: VDOMごとの色テーマに合わせたヘッダー背景色
- **ゼブラストライプ**: 交互行の背景色で視認性を向上

##### 視覚的区別

- **アクション表示**: Allow（緑）、Deny（赤）、Drop（暗赤）を色分け
- **ステータス表示**: 有効/無効を色とテキストで明確に区別
- **セクションタイトル**: 各セクションに色付きタイトル行を配置

#### 3.3.3 機能

- **自動列幅調整**: 日本語文字を考慮した列幅の自動調整
- **フリーズペイン**: ヘッダー行を固定してスクロール時も見出しを表示
- **セル結合**: セクションタイトルや見出しのセル結合による見やすいレイアウト
- **中央揃え**: 数値やステータス項目を中央揃えで表示
- **セクション指定**: 出力するセクションを指定可能（部分出力対応）

---

## 4. アーキテクチャ設計

### 4.1 モジュール構成

```text
WallScribe/
├── main.py                    # エントリーポイント（CLI）
├── app.py                     # Web アプリケーション（Flask）
├── SPECIFICATION.md           # 本仕様書
├── README.md                  # 使用方法
├── requirements.txt           # 依存パッケージ
│
├── parsers/                   # パーサーモジュール
│   ├── __init__.py
│   ├── base.py               # 基底パーサークラス
│   ├── cluster.py            # HAクラスタ構成パーサー（複数ファイル統合）
│   ├── fortigate/            # FortiGate用パーサー（パッケージ）
│   │   ├── __init__.py
│   │   └── converters/       # 変換ロジック（device/network/objects/policies/...）
│   └── paloalto.py           # Palo Alto用パーサー
│
├── models/                    # データモデル
│   ├── __init__.py
│   ├── config.py             # 設定データ構造の定義
│   └── cluster.py            # HAクラスタ統合データモデル
│
├── exporters/                 # 出力モジュール
│   ├── __init__.py
│   ├── html.py               # HTML出力
│   ├── pdf.py                # PDF出力
│   └── excel.py              # Excel出力（オプション）
│
├── web/                       # Web インターフェース
│   ├── __init__.py
│   └── templates/            # Web UI テンプレート
│       ├── index.html        # メインページ
│       ├── result.html       # 結果表示ページ
│       └── error.html        # エラーページ
│
├── static/                    # 静的ファイル
│   ├── css/
│   │   └── style.css         # スタイルシート
│   ├── js/
│   │   └── main.js           # JavaScript
│   └── data/
│       └── appid.csv         # アプリケーションIDマッピングデータ
│
└── tests/                     # テストコード
    ├── __init__.py
    ├── test_parsers.py
    ├── test_exporters.py
    ├── test_app.py
    └── ...（他）
```

### 4.2 クラス設計

#### 4.2.1 基底パーサークラス

```python
class BaseConfigParser(ABC):
    """設定パーサーの基底クラス"""

    @abstractmethod
    def parse(self, file_path: str) -> ConfigModel:
        """設定ファイルをパースする"""
        pass

    @abstractmethod
    def detect_file_type(self, file_path: str) -> bool:
        """ファイル形式を判定する"""
        pass
```

#### 4.2.2 データモデル

```python
@dataclass
class ConfigModel:
    """統一設定データモデル"""
    device_info: DeviceInfo           # 機器概要
    system_settings: SystemSettings   # システム設定
    interfaces: List[Interface]       # インターフェース
    routes: List[Route]               # ルーティング
    objects: Objects                  # オブジェクト定義
    policies: List[Policy]            # ポリシー
    vpn: VPNSettings                  # VPN設定
    ha: HASettings                    # HA設定
    logging: LoggingSettings          # ログ設定
```

### 4.3 処理フロー

```text
1. ファイル読み込み
   ↓
2. ファイル形式判定（.conf / .xml）
   ↓
3. 対応パーサーで解析
   ↓
4. 統一データモデルに変換
   ↓
5. 指定形式で出力（HTML / PDF / Excel）
```

---

## 5. CLI 仕様

### 5.1 コマンド構文

```bash
python main.py <input_file> [options]
```

### 5.2 オプション

| オプション  | 短縮形 | 説明                  | デフォルト      |
| ----------- | ------ | --------------------- | --------------- |
| `--output`  | `-o`   | 出力ファイルパス      | `./output.html` |
| `--format`  | `-f`   | 出力形式 (html/excel) | `html`          |
| `--ha-mode` |        | HAモード (auto/single/cluster) | `auto` |
| `--verbose` | `-v`   | 詳細ログ出力          | `false`         |
| `--help`    | `-h`   | ヘルプ表示            | -               |
| `--version` |        | バージョン表示        | -               |

### 5.3 使用例

```bash
# FortiGate設定からHTML生成
python main.py fortigate.conf -o fortigate_param.html

# Palo Alto設定からExcel生成
python main.py pa440.xml -f excel -o pa440_param.xlsx

# HA構成（複数ファイル）をクラスタとして処理（自動判定）
python main.py primary.conf secondary.conf --ha-mode auto -o ha_cluster.html

# 詳細ログ付きで実行
python main.py config.conf -v
```

---

## 6. Web インターフェース仕様

### 6.1 概要

ブラウザから設定ファイルをアップロードし、パラメータシートを生成・ダウンロードできる Web アプリケーション。

### 6.2 画面構成

#### 6.2.1 メインページ（アップロード画面）

```text
┌─────────────────────────────────────────────────────────────┐
│  [Logo] WallScribe                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  │     設定ファイルをドラッグ＆ドロップ                  │  │
│  │            または                                     │  │
│  │        [ファイルを選択（複数可）]                     │  │
│  │                                                       │  │
│  │     対応形式: .conf (FortiGate), .xml (Palo Alto)     │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  選択済みファイル: primary.conf / secondary.conf ...         │
│  HA構成オプション: ○ auto (推奨) ○ cluster ○ single          │
│                                                             │
│  出力形式:  ○ HTML (推奨)   ○ PDF   ○ Excel               │
│                                                             │
│              [パラメータシートを生成]                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 6.2.2 結果ページ（ダウンロード画面）

```text
┌─────────────────────────────────────────────────────────────┐
│  [Logo] WallScribe                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ✓ パラメータシートの生成が完了しました                     │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ ファイル名: fortigate_param.html                      │  │
│  │ 機器タイプ: FortiGate                                 │  │
│  │ ホスト名: FW-PRIMARY                                  │  │
│  │ OS バージョン: 7.6.2                                  │  │
│  │ ポリシー数: 120                                       │  │
│  │ オブジェクト数: 45                                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│   [ダウンロード]     [プレビュー]     [別のファイルを変換]  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 API エンドポイント

| メソッド | パス                   | 説明                             |
| -------- | ---------------------- | -------------------------------- |
| GET      | `/`                    | メインページ表示                 |
| POST     | `/upload`              | ファイルアップロード・変換処理（同期） |
| POST     | `/upload_async`        | ファイルアップロード・変換処理（非同期・複数ファイル/HA対応） |
| GET      | `/download/<file_id>`  | 生成ファイルのダウンロード       |
| GET      | `/preview/<file_id>`   | 生成ファイルのプレビュー表示     |
| GET      | `/api/status/<file_id>` | 生成結果のサマリー取得（メタデータ） |
| GET      | `/api/progress/<file_id>` | 生成中の進捗取得（非同期用）     |

### 6.4 ファイルアップロード仕様

#### 6.4.1 リクエスト

```http
POST /upload_async HTTP/1.1
Content-Type: multipart/form-data

------WebKitFormBoundary
Content-Disposition: form-data; name="config_files[]"; filename="primary.conf"
Content-Type: application/octet-stream

[ファイル内容]
------WebKitFormBoundary
Content-Disposition: form-data; name="config_files[]"; filename="secondary.conf"
Content-Type: application/octet-stream

[ファイル内容]
------WebKitFormBoundary
Content-Disposition: form-data; name="output_format"

html
------WebKitFormBoundary
Content-Disposition: form-data; name="ha_mode"

auto
------WebKitFormBoundary--
```

#### 6.4.2 レスポンス（成功時・非同期受付）

```json
{
  "success": true,
  "file_id": "abc123",
  "file_count": 2,
  "progress_url": "/api/progress/abc123",
  "result_url": "/result/abc123"
}
```

#### 6.4.3 進捗取得（非同期）

```json
{
  "success": true,
  "file_id": "abc123",
  "status": "processing",
  "progress": {
    "percent": 35,
    "message": "設定ファイルを解析しています...",
    "stage": "parsing"
  },
  "result_url": "/result/abc123"
}
```

#### 6.4.3 レスポンス（エラー時）

```json
{
  "success": false,
  "error": {
    "code": "UNSUPPORTED_FORMAT",
    "message": "サポートされていないファイル形式です",
    "details": "対応形式: .conf (FortiGate), .xml (Palo Alto)"
  }
}
```

### 6.5 セキュリティ要件

#### 6.5.1 ファイルアップロード制限

| 項目               | 制限値                    |
| ------------------ | ------------------------- |
| 最大ファイルサイズ | 50MB                      |
| 許可拡張子         | `.conf`, `.xml`           |
| 同時アップロード数 | 複数ファイル（HA構成を想定、合計サイズは最大ファイルサイズに従う） |
| 保持期間           | 1 時間（自動削除）        |

#### 6.5.2 セキュリティ対策（現状実装）

- アップロードファイルのサニタイズ
- ファイル名のランダム化（UUID 使用）
- 一時ファイルの自動クリーンアップ
- パストラバーサル対策（パス正規化と検証）
- UUID形式チェック（download/preview/status/progress）

### 6.6 UI/UX 要件

#### 6.6.1 ドラッグ＆ドロップ

- ファイルをドロップエリアにドラッグすると視覚的フィードバック
- ドロップ後にファイル選択として反映（その後「生成」ボタンで送信）
- 進捗表示（プログレスバー）

#### 6.6.2 レスポンシブデザイン

- デスクトップ / タブレット / モバイル対応
- 最小幅: 320px

#### 6.6.3 処理中の表示

```text
┌───────────────────────────────────────────────────┐
│                                                   │
│          ⏳ パラメータシートを生成中...           │
│                                                   │
│          [=========>          ] 45%               │
│                                                   │
│          設定ファイルを解析しています             │
│                                                   │
└───────────────────────────────────────────────────┘
```

### 6.7 エラーハンドリング

| エラーコード        | 説明                         | ユーザーへの表示                           |
| ------------------- | ---------------------------- | ------------------------------------------ |
| `FILE_TOO_LARGE`    | ファイルサイズ超過           | ファイルサイズが 50MB を超えています       |
| `UNSUPPORTED_FORMAT`| 非対応ファイル形式           | 対応形式: .conf, .xml                      |
| `PARSE_ERROR`       | パースエラー                 | 設定ファイルの解析に失敗しました           |
| `INTERNAL_ERROR`    | サーバー内部エラー           | 予期しないエラーが発生しました             |

### 6.8 Web サーバー起動

```bash
# 開発モード
python app.py

# 本番モード（Gunicorn使用）
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

### 6.9 環境変数

| 変数名              | 説明                  | デフォルト値      |
| ------------------- | --------------------- | ----------------- |
| `FLASK_ENV`         | 実行環境              | `production`      |
| `FLASK_PORT`        | リッスンポート        | `8080`            |
| `UPLOAD_FOLDER`     | アップロード先        | `./uploads`       |
| `MAX_CONTENT_LENGTH`| 最大アップロードサイズ| `52428800` (50MB) |
| `SECRET_KEY`        | セッション暗号化キー  | ランダム生成      |
| `CLEANUP_INTERVAL`  | クリーンアップ間隔    | `3600` (1時間)    |
| `TZ`                | タイムゾーン          | `Asia/Tokyo`      |

---

## 7. 技術仕様

### 7.1 動作環境

- Python 3.8 以上
- OS: Windows / Linux / macOS

### 7.2 依存パッケージ

```text
# requirements.txt
flask>=2.0.0         # Web フレームワーク
openpyxl>=3.0.0      # Excel出力用
weasyprint>=62.0     # PDF出力用
jinja2>=3.0.0        # HTMLテンプレート
gunicorn>=20.0.0     # 本番用WSGIサーバー（オプション）
```

### 7.3 文字エンコーディング

- 入力: UTF-8（自動検出でフォールバック）
- 出力: UTF-8

---

## 8. エラーハンドリング

### 8.1 想定エラー

| エラー種別         | 原因                 | 対処                           |
| ------------------ | -------------------- | ------------------------------ |
| FileNotFoundError  | ファイルが存在しない | エラーメッセージを表示して終了 |
| ParseError         | 設定ファイル形式不正 | 該当箇所をスキップして継続     |
| EncodingError      | 文字コード不正       | UTF-8 以外を試行               |
| UnsupportedVersion | 未対応バージョン     | 警告を出力して継続             |

### 8.2 ログ出力

```text
[INFO] ファイル読み込み: fortigate.conf
[INFO] FortiGate設定ファイルを検出
[INFO] FortiOS 7.6.2 を検出
[WARN] 未対応の設定セクション: config xxx - スキップします
[INFO] パース完了: 120ポリシー、45オブジェクト
[INFO] HTML出力: output.html
```

---

## 9. 制限事項

### 9.1 取得できない情報

- シリアル番号（設定ファイルに含まれない）
- ライセンス情報（設定ファイルに含まれない）
- パスワード（マスク化されている）
- 実行コンフィグと起動コンフィグの差分

### 9.2 対応バージョン

- FortiOS: 6.0 以上を推奨（6.x/7.x で動作確認）
- PAN-OS: 10.0 以上を推奨（10.x/11.x で動作確認）

### 9.3 パフォーマンス

- 大規模設定（10,000 ポリシー以上）では処理時間が増加する可能性あり

---

## 10. 今後の拡張予定

### 10.1 Phase 1（初期リリース）

- [x] FortiGate HTML パーサー（既存実装を統合）
- [x] Palo Alto HTML パーサー（既存実装を統合）
- [x] 統合 CLI ツール
- [x] 基本 HTML テンプレート
- [x] Web インターフェース（ファイルアップロード・ダウンロード）
- [x] 機器概要セクション（シリアル番号、ライセンス情報含む）
- [x] システム設定セクション（管理アクセス詳細含む）
- [x] ネットワーク設定セクション（インターフェース役割、DHCP除外IP含む）
- [x] ファイアウォールポリシーセクション（NAT、セキュリティプロファイル、Local-inポリシー含む）
- [x] NAT設定セクション（VIP/DNATポートフォワーディング詳細含む）
- [x] VPN設定セクション（IPsec Phase1/Phase2詳細、SSL-VPN認証方法含む）
- [x] セキュリティプロファイルセクション（UTM詳細情報含む）
- [x] ログ・監視設定セクション（ログ転送種別、SNMPトラップ送信先含む）

### 10.2 Phase 2

- [x] Excel 出力対応
- [x] Excel 出力: VDOM/vsys単位出力対応、モダンスタイリング（VDOMごとの色テーマ、タブ色、視覚的区別）
- [x] PDF 出力対応
- [x] Internet Service対応
- [x] CIDR表記への自動変換
- [x] インタラクティブツールチップ機能
- [x] 複数ファイルのHAクラスタ処理（Web/CLI）
- [ ] 差分比較機能
- [ ] バッチ処理（複数ファイル同時変換）

### 10.3 Phase 3

- [ ] 他ベンダー対応（Cisco ASA、Juniper SRX 等）
- [x] Docker コンテナ化
  - [x] マルチステージビルド対応
  - [x] 日本語フォント対応
  - [x] タイムゾーン設定（環境変数で指定可能、デフォルト: Asia/Tokyo）
  - [x] ファイルシステムベースのメタデータ管理（複数ワーカー対応）
- [ ] REST API 化

---

## 11. 付録

### 11.1 参照ドキュメント

- FortiOS CLI Reference
- PAN-OS CLI Reference Guide
- Flask Documentation
- 既存実装: `fg-parameter-sheet/`, `pa-parameter-sheet/`

### 11.2 更新履歴

| バージョン | 日付       | 変更内容                           |
| ---------- | ---------- | ---------------------------------- |
| 1.0        | 2026-01-20 | 現状版（v1.0）                     |
|            |            | - HTML / PDF / Excel 出力 |
|            |            | - Web: 非同期生成＋進捗表示（`/upload_async` + `/api/progress/<file_id>`） |
|            |            | - Web/CLI: 複数ファイル（HAクラスタ）対応（`ha_mode=auto/cluster/single`） |
|            |            | - FortiGate: IPv6（interface/route/address）対応 |
|            |            | - ルーティング: blackhole/discard対応 |
|            |            | - Excel出力機能実装（openpyxl使用） |
|            |            | - Excel出力: VDOM/vsys単位出力対応、モダンスタイリング（VDOMごとの色テーマ、タブ色、視覚的区別） |
|            |            | - Internet Service対応（FortiGateのinternet-service-name） |
|            |            | - CIDR表記への自動変換（アドレス、インターフェース、ルート） |
|            |            | - インタラクティブツールチップ機能（インターフェース、アドレス、サービス、セキュリティプロファイル、Internet Service） |
|            |            | - テストスイートの充実（pytest使用） |
|            |            | - FortiGate / Palo Alto設定ファイルパーサー実装 |
|            |            | - HTML / PDF出力機能実装 |
|            |            | - Web インターフェース実装（ファイルアップロード・ダウンロード） |
|            |            | - 機器概要セクション（シリアル番号、ライセンス情報含む） |
|            |            | - システム設定セクション（管理アクセス詳細含む） |
|            |            | - ネットワーク設定セクション（インターフェース役割、DHCP除外IP含む） |
|            |            | - ファイアウォールポリシーセクション（NAT、セキュリティプロファイル、Local-inポリシー含む） |
|            |            | - NAT設定セクション（VIP/DNATポートフォワーディング詳細含む） |
|            |            | - VPN設定セクション（IPsec Phase1/Phase2詳細、SSL-VPN認証方法含む） |
|            |            | - セキュリティプロファイルセクション（UTM詳細情報含む） |
|            |            | - ログ・監視設定セクション（ログ転送種別、SNMPトラップ送信先含む） |
|            |            | - PDF出力: A3横向き対応、フォントサイズ最適化（9pt/7pt）、日本語フォント対応 |
|            |            | - Docker: マルチステージビルド、日本語フォント対応、タイムゾーン設定、複数ワーカー対応 |
|            |            | - アプリケーションID解決機能（static/data/appid.csv によるマッピング） |
|            |            | - Internet Service 対応、CIDR表記への自動変換、インタラクティブツールチップ |
|            |            | - FortiGate: IPv6 対応、ルーティング: blackhole/discard 対応 |
|            |            | - pytest によるテスト、Docker 対応 |
