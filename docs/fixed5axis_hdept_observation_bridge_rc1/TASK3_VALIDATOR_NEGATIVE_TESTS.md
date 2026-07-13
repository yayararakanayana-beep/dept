# 固定5軸上位観測翻訳層 RC1 — 接続タスク3 validator・否定試験

## 状態

- validator版: `fixed5axis_hdept_observation_bridge_validator_task3_rc1`
- 対象builder版: `fixed5axis_hdept_observation_bridge_task2_rc1`
- 基礎契約: `fixed5axis_hdept_observation_bridge_rc1`
- 工学的位置づけ: `A_independent_integrity_validator_for_task2_artifacts`
- 科学的位置づけ: `B_limited_integrity_only_no_h11_scientific_validity_claim`

Task 1の接続契約およびTask 2のbuilder仕様は変更していない。

## 目的

Task 3は、Task 2成果物が次を満たすかを独立に検証する。

1. 正本G/Kと成果物の同一性
2. 未来接尾部を読まない因果境界
3. 47特徴の完全再計算一致
4. H11全11軸の完全再計算一致
5. 利用不能・信頼度・中立転送値の契約
6. manifestと成果物の完全性
7. 校正・特徴台帳・証拠対応表の版同一性
8. validatorによる正本非変更

## 独立性

validatorは次を呼ばない。

- `build_observation`
- Task 2の `extract_feature_records`
- Task 2の `construct_h11`

固定5軸の生の分布と因果的履歴から、次を別実装で再計算する。

- G_tハッシュ
- K_t履歴鎖
- 分布幾何
- 固定格子近傍密度
- 連結成分
- 移動・加速度・曲率・振動
- 47特徴の利用可能性と値
- 凍結校正変換
- H11の基礎成分・合成軸
- 軸信頼度と証拠被覆率
- 全体観測状態

浮動小数点比較はvalidator profileの絶対・相対許容差を使用する。

## 因果境界

validatorは `history_ledger.csv` を `current_t` で読み止める。

`gt_mass.npy` はメモリマップで開き、現在までのフレームだけを数値参照する。未来フレームを含むファイル全体のハッシュは計算しない。

正本のmanifestは契約版と宣言値だけを確認し、未来数値を読む完全ハッシュ照合は行わない。これは検証の弱体化ではなく、未来漏洩を防ぐための境界である。

同じ接頭部を持ち未来接尾部だけが異なる正本に対して、同じ現在成果物が検証を通ることを否定試験で確認する。

## validatorの検査門

1. `artifact_exact_file_set`
2. `artifact_manifest_integrity`
3. `contract_and_version_identity`
4. `canonical_prefix_integrity`
5. `input_identity_match`
6. `feature_schema_and_full_recomputation`
7. `h11_schema_and_full_recomputation`
8. `audit_claim_boundary`
9. `provenance_identity`
10. `source_non_writeback`

いずれか一つでも失敗した場合はfail-closedとする。

## 実行例

```bash
python scripts/fixed5axis_hdept_observation_bridge_validator_rc1.py \
  --trajectory-dir path/to/fixed5/trajectory \
  --current-t 20 \
  --artifact-dir output/fixed5_hdept_t20 \
  --calibration path/to/frozen_calibration.json \
  --output output/fixed5_hdept_t20.validation.json
```

校正なしで生成されたHOLD成果物は `--calibration` を省略して検証する。

## 否定試験

実装した主な否定試験は次のとおり。

- 成果物の余分なファイル・欠落ファイル
- manifestハッシュ不一致
- manifestを再生成した後のpayload改ざん
- 予約特徴のゼロ埋め
- 中立転送値0.5の観測値化
- 未知の契約版
- 固定5軸の軸順変更
- 負の質量
- NaN等の非有限質量
- 質量非正規化
- 履歴の重複・連続性偽装
- G_t/K_tハッシュ鎖改ざん
- 校正と特徴台帳の不一致
- 校正版の不一致
- CLIのfail-closed終了コード

正常系として次も確認する。

- 校正あり限定H11成果物
- 校正なしHOLD成果物
- 初期1フレームの履歴不足成果物
- 同一接頭部・異なる未来接尾部
- validator実行前後の正本バイト同一性

## 主張限界

Task 3が確認するのは、**Task 1契約に対するTask 2成果物の工学的整合性**である。

Task 3だけでは次を主張しない。

- 47特徴の科学的意味が正しい
- H11方向が現実の健全性を正しく表す
- 校正値が妥当
- H11が上位圧生成に十分
- 閉ループで性能または安全性が向上する

これらはTask 4「単体科学検証と校正固定」で扱う。
