# 統合ネットワーク図

「推定ネットワーク構造」の出力を、全 VDOM / vsys をまとめた一つの SVG に変更した。HTML は外部ライブラリやネットワーク通信を必要とせず、オフラインでも操作できる。「接続」プリセットに含め、カスタム出力でも選択できる。

- 全体表示、拡大縮小、空白のドラッグ、図内検索、区画絞り込み、全画面表示。
- ノード・接続のクリックまたは Enter / Space で、設定の詳細、接続の根拠、関連ポリシー、診断を表示。
- VDOM の送信元・宛先とパケット条件を指定し、構造上の接続と区画別の通信候補を同じ図で確認。入口・出口の IF / ゾーンも任意指定できる。
- SVG 保存は、絞り込みや選択を解除した図全体を出力。生成した HTML も単一ファイルで配布できる。
- PDF は一つの静的図、Excel は同じモデルに基づくノード・接続の一覧。PDF は操作できず、大規模構成の探索には HTML を使用する。

## 接続の根拠

FortiGate の `system vdom-link` に明示されたペア、公式形式の `npuN_vlink0/1`、対になる親 IF と同じ VLAN ID に基づくサブインターフェースをモデル化する。片側欠落・所属未確定・対応の曖昧なペアは結ばない。同じ IP 帯や似た IF 名だけでは VDOM 間リンクを作らない。Palo Alto は external ゾーン・visible-vsys に基づく vsys 接続、VR 所属、next-vr を表示する。詳細は `CONSTRUCTION_LAB.md` を参照。

青線は設定上の VDOM 間リンク。IF・ルート・直結ネットワークは別の線で区別する。無効 IF を含むリンクは表示するが、追跡には使用しない。IF の up は管理設定上の状態であり、実リンクの稼働を検証したものではない。

## 動作確認の限界

追跡は既知リンクの最少ホップ経路の一例であり、実効ルーティングのシミュレーションではない。各区画で NAT 変換前の入力を照合し、NAT 有効ポリシー・NAT 候補がある場合は変換後の再確認を求める。拒否候補・先行候補・不足条件も示し、通信成功を断定しない。経路なしも疎通不可の断定ではない。SD-WAN、PBR、外部機器、VPN、動的経路、稼働状態、App-ID 等は実機確認が必要。

## 公式資料

- [FortiOS 7.2.8 Inter-VDOM routing](https://docs.fortinet.com/document/fortigate/7.2.8/administration-guide/32293): 内部リンクとインターフェースの設定。
- [FortiOS 7.2.10 system vdom-link](https://docs.fortinet.com/document/fortigate/7.2.10/cli-reference/232114316/config-system-vdom-link): PPP / Ethernet / NPU pair。
- [FortiOS 7.6.3 NP6 VDOM link](https://docs.fortinet.com/document/fortigate/7.6.3/hardware-acceleration/851990/configuring-inter-vdom-link-acceleration-with-np6-processors): NPU ペアの命名と所属。
- [FortiOS 7.0.7 VLAN VDOM links](https://docs.fortinet.com/document/fortigate/7.0.7/hardware-acceleration/327022/using-vlans-to-add-more-accelerated-inter-vdom-link-interfaces): 親 IF と VLAN 条件。

## 検証用データ

`examples/fortigate-vdom.conf` は秘密情報を含まない合成設定。branch → root の二つの VDOM とリンク、経路、許可ポリシーを持つ。CLI で HTML を生成して操作できる。パーサーのリンク抽出、欠落・曖昧なペア、無効リンク、NPU/VLAN、複数ホップ、同じ IF 名を持つ別区画、単一 SVG、HTML エスケープを回帰テストで検証する。
