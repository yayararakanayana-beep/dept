# Task 3.1f-1 出力仕様

## 0. 基本方針

Task 3.1fの成果物は、モデルの結果だけでなく、入力固定、run条件、構造対応、構造数選択、holdout開封順序、独立再計算の証拠を保存する。

生成器が合格判定を自己申告するだけの出力は禁止する。

全CSVはUTF-8、header付き、indexなしとする。全NPY/NPZはpickleを使わない。浮動小数点配列の型は個別指定がない限り`float64`とする。

正式成果物root：

```text
artifacts/task3_1f_stable_structure_extraction/
```

---

## 1. 契約・入力固定成果物

## 1.1 `contract_snapshot.json`

実行時に使用したmachine-readable contractの完全コピー。

必須項目：

- contract version
- contract SHA-256
- rank grid
- method settings
- seed lists
- thresholds
- split roles
- holdout policy
- output schema version

## 1.2 `environment_manifest.json`

必須項目：

- Python version
- OS
- architecture
- NumPy version
- SciPy version
- pandas version
- scikit-learn version
- BLAS/LAPACK情報
- Git commit SHA
- workflow run ID
- workflow job ID

## 1.3 `input_manifest.json`

必須項目：

- Task 3.1e artifact digest
- Task 3.1e config digest
- 各入力ファイルのSHA-256
- file size
- row count／shape／dtype
- fit／validation／holdout行数
- snapshot ID count
- matched pair count
- input validation result

## 1.4 bundle

- `fit_bundle.npz`
- `validation_bundle.npz`
- `holdout_bundle.npz`

各bundle member：

- `mass_matrix`
- `analysis_weight`
- `matrix_row_index`
- `snapshot_id_hash`

文字列ID本体はrow map CSVへ保存する。

## 1.5 row map

- `fit_row_map.csv`
- `validation_row_map.csv`
- `holdout_row_map.csv`

列：

| 列 | 型 | 説明 |
|---|---|---|
| bundle_row_index | int | bundle内行番号 |
| matrix_row_index | int | Task 3.1e mass行番号 |
| snapshot_id | str | snapshot ID |
| dataset_split | str | split |
| distribution_group | str | base／external |
| source_run_id | str | 持続run ID |
| external_vector_id | str | 外部ベクトルID |
| seed | int | world seed |
| source_step | int | step |
| active_factor_count | int | 外部要因活性数 |
| vector_origin | str | ベクトル生成由来 |
| analysis_weight | float | 分析重み |

---

## 2. run一覧

## 2.1 `model_runs.csv`

1行＝1 model run。

必須列：

| 列 | 説明 |
|---|---|
| run_id | 決定論的run ID |
| method | `nmf_kl`, `nmf_frobenius`, `weighted_pca`, `mean_baseline` |
| rank | 構造数。mean baselineは0 |
| run_role | `anchor`, `random_init`, `subset`, `world_seed_sensitivity`, `reference` |
| init_method | 初期化方法 |
| init_seed | seed。anchorは0 |
| subset_id | 摂動subset ID。通常runは空 |
| world_seed_filter | seed感度条件。通常runは空 |
| solver | solver名 |
| loss | loss名 |
| max_iter | 最大反復数 |
| tolerance | 許容値 |
| n_iter | 実反復数 |
| converged | 実測収束結果 |
| status | `completed`, `failed`, `rejected` |
| failure_reason | 失敗理由 |
| fit_started_at | UTC timestamp |
| fit_completed_at | UTC timestamp |
| basis_path | 基底path |
| activation_path | 活性度path |
| basis_sha256 | 基底hash |
| activation_sha256 | 活性度hash |

固定`converged=true`は禁止する。収束判定根拠をrun logへ残す。

## 2.2 run別モデル配列

path：

```text
models/<run_id>/basis.npy
models/<run_id>/fit_activations.npy
models/<run_id>/validation_activations.npy
models/<run_id>/fit_reconstruction.npy
models/<run_id>/validation_reconstruction.npy
models/<run_id>/run_metadata.json
```

`basis.npy`：`(rank, 3125)`、各行非負、総和1。

`*_activations.npy`：`(split_rows, rank)`、非負。

`*_reconstruction.npy` は生再構成を保存する。分布用正規化再構成は独立再計算可能なため、必須保存対象としない。

---

## 3. 再構成評価

## 3.1 `reconstruction_metrics.csv`

1行＝1 run×split×subgroup×metric×weighting。

必須列：

| 列 | 説明 |
|---|---|
| run_id | model run ID |
| method | 方法 |
| rank | 構造数 |
| split | fit／validation／holdout |
| subgroup_type | `all`, `distribution_group`, `source_step`, `active_factor_count`, `vector_origin` |
| subgroup_value | 群値 |
| weighting | `weighted`, `unweighted` |
| metric | 指標名 |
| aggregation | `mean`, `median`, `p95`, `max`等 |
| value | 実測値 |
| row_count | 対象行数 |
| weight_sum | weight合計。unweightedはrow count |
| evidence_path | 再計算元配列path |

metric候補：

- `rmse_raw`
- `mae_raw`
- `js_distance`
- `total_variation`
- `raw_row_sum_absolute_error`
- `negative_value_count`
- `nonfinite_value_count`

## 3.2 `pair_deformation_metrics.csv`

1行＝1 run×split×集計条件×指標。

必須列：

- run_id
- method
- rank
- split
- source_step
- active_factor_count
- weighting
- metric
- aggregation
- value
- pair_count

metric：

- `external_base_js_actual`
- `external_base_js_reconstructed`
- `external_base_js_preservation_absolute_error`
- `signed_delta_cosine_similarity`
- `signed_delta_relative_l1_error`

---

## 4. 構造対応・安定性

## 4.1 `component_matches.csv`

1行＝run pair内の対応構造1組。

列：

- rank
- run_id_a
- run_id_b
- component_id_a
- component_id_b
- js_distance
- js_similarity
- cosine_similarity
- matching_cost_rank

## 4.2 `rank_stability_summary.csv`

1行＝1 rank。

列：

- rank
- random_run_required
- random_run_completed
- random_run_converged
- convergence_rate
- representative_run_id
- median_matched_js_similarity
- p10_matched_js_similarity
- stable_component_count
- component_count
- stable_component_fraction
- grouped_subset_median_similarity
- grouped_subset_surviving_component_fraction
- world_seed_0_median_similarity
- world_seed_1_median_similarity
- initial_stability_passed
- grouped_subset_passed
- world_seed_status

## 4.3 `structure_summary.csv`

1行＝代表runの1構造。

列：

- structure_id (`S001`等)
- rank
- representative_run_id
- basis_row_index
- basis_mass_sum
- basis_min
- basis_max
- effective_cell_count
- basis_entropy
- fit_weighted_mean_activation_share
- fit_weighted_p95_activation_share
- fit_max_activation_share
- validation_weighted_mean_activation_share
- validation_weighted_p95_activation_share
- initial_survival_rate
- subset_survival_count
- world_seed_0_similarity
- world_seed_1_similarity
- maximum_internal_js_similarity
- maximum_internal_cosine_similarity
- duplicate_flag
- inactive_flag
- handoff_status (`stable_structure`, `conditional_structure`, `excluded_duplicate`, `excluded_inactive`, `unstable`)

`effective_cell_count` は `exp(entropy)` とする。entropyは自然対数で計算する。

## 4.4 `internal_structure_similarity.csv`

代表run内の全構造対。

列：

- rank
- structure_id_a
- structure_id_b
- js_distance
- js_similarity
- cosine_similarity
- duplicate_pair

---

## 5. rank比較・選択固定

## 5.1 `rank_summary.csv`

1行＝固定gridの1 rank。

列：

- rank
- required_run_count
- completed_run_count
- converged_random_run_count
- convergence_gate
- stability_gate
- redundancy_rate
- redundancy_gate
- inactive_rate
- inactive_gate
- validation_weighted_mean_js
- validation_weighted_mean_js_standard_error
- validation_weighted_median_js
- validation_weighted_p95_js
- validation_unweighted_mean_js
- mean_baseline_improvement_rate
- external_base_error_ratio
- admissible
- rejection_reasons
- representative_run_id
- one_standard_error_eligible
- selected

固定gridの7行が必須である。行欠落は禁止する。

## 5.2 `selection_lock.json`

必須項目：

- lock version
- created by stage
- selected rank
- selected representative run ID
- admissible ranks
- best error rank
- best error mean
- best error standard error
- one-standard-error threshold
- selected rank validation metrics
- rank summary SHA-256
- selected basis path／SHA-256
- selected activation path／SHA-256
- contract SHA-256
- input artifact SHA-256
- fit bundle SHA-256
- validation bundle SHA-256
- holdout accessed: `false`
- independent selection audit: `passed`

`holdout accessed`がtrue、欠落、または文字列の場合はlock無効とする。

## 5.3 `selection_audit.json`

独立検証器が再計算した選択結果。

- recomputed selected rank
- stored selected rank
- match
- gate-by-gate再計算
- hash checks
- failed checks
- passed

---

## 6. holdout成果物

## 6.1 `holdout_activations.npy`

形状：`(244, selected_rank)`。

## 6.2 `holdout_reconstruction.npy`

形状：`(244, 3125)`。

## 6.3 `holdout_metrics.csv`

`reconstruction_metrics.csv` と同じ形式のholdout行を保存する。

## 6.4 `holdout_outcome.json`

必須項目：

- selected rank
- selected representative run ID
- selection lock SHA-256
- NMF holdout weighted mean JS
- mean baseline holdout weighted mean JS
- baseline improvement rate
- validation weighted mean JS
- holdout／validation mean ratio
- validation p95 JS
- holdout p95 JS
- holdout／validation p95 ratio
- integrity audit result
- outcome (`confirmed`, `conditional`, `failed`)
- failed conditions

outcomeは独立検証器が再計算できなければ無効。

---

## 7. PCA参照成果物

- `references/pca_rank_summary.csv`
- `references/pca_components_rank_<rank>.npy`
- `references/pca_validation_metrics.csv`
- `references/pca_holdout_metrics.csv`

PCAについて必須記録：

- explained variance ratio
- cumulative explained variance
- raw reconstruction RMSE／MAE
- negative value rate
- raw row sum error
- simplex projected JS／TV

PCA成分を `structure_summary.csv` へ混ぜない。

---

## 8. 感度監査成果物

### Frobenius NMF

- `sensitivity/frobenius_model_runs.csv`
- `sensitivity/frobenius_structure_matches.csv`
- `sensitivity/frobenius_summary.csv`

選択rankと隣接grid rankだけを含める。

### grouped subset

- `sensitivity/subset_definitions.csv`
- `sensitivity/subset_structure_matches.csv`
- `sensitivity/subset_summary.csv`

### world seed

- `sensitivity/world_seed_structure_matches.csv`
- `sensitivity/world_seed_summary.csv`

---

## 9. 品質検査・報告

## 9.1 `quality_checks.json`

各checkを次のobject形式で保存する。

```json
{
  "passed": true,
  "measured_value": 0.0,
  "threshold": 0.0,
  "checked_count": 0,
  "evidence_paths": []
}
```

boolean単独は禁止する。

必須check群：

- input integrity
- split isolation
- probability mass validity
- weight validity
- model run completeness
- convergence evidence
- basis validity
- activation validity
- reconstruction reproducibility
- component matching reproducibility
- rank gate reproducibility
- selection lock validity
- holdout isolation
- holdout outcome reproducibility
- artifact manifest validity

## 9.2 `mutation_test_results.json`

各破壊ケースについて：

- mutation ID
- mutated artifact
- expected failed check
- actual failed check
- failure message
- passed

## 9.3 `results.md`

人間向け結果。

必須章：

1. 実行条件
2. 入力固定
3. rank比較
4. 選択rank
5. 構造安定性
6. 重複・未使用構造
7. validation性能
8. holdout結果
9. PCA参照
10. Frobenius感度
11. Task 3.1gへ渡す構造
12. 失敗・制限・未解決事項

## 9.4 `artifact_manifest.json`

各ファイルについて：

- relative path
- type
- size bytes
- SHA-256
- CSV row count and columns
- NPY shape and dtype
- NPZ member names, shapes, dtypes
- JSON top-level schema

manifest自身は自己hash対象外とし、最終archive digestを別に記録する。

---

## 10. 完了レポート

Task 3.1f-2以降の各PRでは、次をPR本文へ記録する。

- 新規タスク／既存タスク
- base branch
- working branch
- 実装したfrozen requirement
- 実行した正常系テスト
- 実行した破壊系テスト
- smoke結果
- formal Actions run ID
- artifact ID／digest
- selected rank
- holdout outcome
- Task 3.1g handoff status
- 未実装・未解決項目
- placeholder、固定pass、自己証明が残っていないこと
