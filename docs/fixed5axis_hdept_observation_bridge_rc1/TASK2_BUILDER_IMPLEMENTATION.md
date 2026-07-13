# 固定5軸上位観測翻訳層 RC1 — 接続タスク2 builder実装

## 状態

- 実装版: `fixed5axis_hdept_observation_bridge_task2_rc1`
- 基礎契約: `fixed5axis_hdept_observation_bridge_rc1`
- 科学的位置づけ: `B_limited_task2_builder_implementation_without_calibration_or_scientific_validation`
- Task 1契約は変更していない。

## 実装範囲

Task 2では次を実装した。

1. 固定5軸正本成果物の読込み
2. `current_t` までの台帳だけを読む因果的接頭部処理
3. 現在時点で終わる連続履歴接尾部の選択
4. 47特徴の決定論的生成
5. 利用可能性・信頼度・証拠数・理由の記録
6. 凍結済み校正成果物の読込みと `transform` のみの適用
7. H11_STRUCTURED 11軸の生成
8. 中立転送値と観測値の分離
9. 監査・出所・manifestの原子的生成
10. CLIと基本単体試験
11. 正本読込み・幾何特徴・H11生成・成果物書込みを内部モジュールへ分離

独立validatorと本格的な否定試験はTask 3へ残す。

## 実行例

校正なしでは特徴と監査を生成するが、H11は通常圧に使える観測として扱わない。

```bash
python scripts/fixed5axis_hdept_observation_bridge_rc1.py \
  --trajectory-dir path/to/fixed5/trajectory \
  --current-t 20 \
  --output-dir output/fixed5_hdept_t20
```

凍結校正成果物を使う場合:

```bash
python scripts/fixed5axis_hdept_observation_bridge_rc1.py \
  --trajectory-dir path/to/fixed5/trajectory \
  --current-t 20 \
  --calibration path/to/frozen_calibration.json \
  --output-dir output/fixed5_hdept_t20
```

## 校正なしの挙動

- 47特徴は生成する。
- 予測契約待ち・回復契約待ち特徴は `value=null` のまま保持する。
- H11は `available=false`, `confidence=0` とする。
- 形式上必要な `transport_value=0.5` は中立観測ではなく仮値として明示する。
- 履歴1時点なら `INSUFFICIENT_HISTORY`。
- 履歴があっても校正なしなら `HOLD_RECOMMENDED`。

## 校正ありの挙動

- 特徴順・特徴台帳ハッシュが一致する校正だけを受理する。
- 実行時のfitは行わない。
- 利用可能な証拠からH11を生成する。
- Task 2では軸状態と全体状態に `READY` を出さない。
- 予測・回復の予約特徴が未実装なので `Predictability` と `Recoverability` は利用不能のままである。

## 因果境界

builderは台帳を `current_t` で読み止め、`gt_mass.npy` はメモリマップから必要な接頭部フレームだけを取得する。

完全manifestのファイルハッシュ再検査は、未来フレームの数値バイトを読む可能性があるためbuilder内では行わない。独立した正本validatorとTask 3の否定試験で扱う。

## 固定格子代理量

以下は代理量であり、強い物理意味を付けない。

- 1軸周辺分布Wasserstein距離の5軸合成
- 固定格子1近傍密度
- 境界質量によるtail代理
- 閾値連結成分によるmode代理
- 重心軌道による曲率・振動代理

代理特徴は特徴台帳の信頼度上限を超えない。

## 成果物

```text
identity.json
features.json
m_observation.json
audit.json
provenance.json
manifest.json
```

## Task 2完了判定

- 同じ正本接頭部・同じ校正から同一バイト出力を生成する。
- 未来接尾部だけを変えても現在出力が変わらない。
- 47特徴の順序と利用可能性を保持する。
- 校正なしの0.5を観測証拠にしない。
- H11全11軸を固定順で出力する。
- Task 2段階で `READY` を主張しない。
- 正本への書戻しを行わない。
