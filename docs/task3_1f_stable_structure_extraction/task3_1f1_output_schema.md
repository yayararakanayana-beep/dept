# Task 3.1f-1 出力仕様

## 0. 基本方針

Task 3.1fの成果物は、モデル結果だけでなく、入力固定、run条件、構造対応、構造数選択、holdout開封順序、独立再計算の証拠を保存する。

生成器が合格値を自己申告するだけの出力は禁止する。

全CSVはUTF-8、header付き、indexなしとする。全NPY／NPZはpickleを使用しない。浮動小数点配列は個別指定がない限り`float64`とする。

正式成果物root：

```text
artifacts/task3_1f_stable_structure_extraction/
```

再構成行列は基底と活性度から再計算できるため、各runについて保存しない。これにより成果物の不要な肥大化を避け、独立検証器が必ず再構成を再計算する。

---

## 1. 契約・環境・入力固定

### 1.1 `contract_snapshot.json`

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

### 1.2 `environment_manifest.json`

必須項目：

- Python version
- OS
- architecture
- NumPy version
- SciPy version
- pandas version
- scikit-learn version
- BLAS／LAPACK情報
- Git commit SHA
- workflow run ID
- workflow job ID

### 1.3 `input_manifest.json`

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

### 1.4 分離bundle

- `bundles/fit_bundle.npz`
- `bundles/validation_bundle.npz`
- `bundles/holdout_bundle.npz`

各bundle member：

- `mass_matrix`
- `analysis_weight`
- `matrix_row_index`
- `snapshot_id_hash`

fit／validation選択jobはholdout bundleを取得しない。

### 1.5 row map

- `bundles/fit_row_map.csv`
- `bundles/validation_row_map.csv`
- `bundles/holdout_row_map.csv`

列：

| 列 | 型 | 説明 |
|---|---|---|
| bundle_row_index | int | bundle内行番号 |
| matrix_row_index | int | Task 3.1eの行番号 |
| snapshot_id | str | snapshot ID |
| dataset_split | str | split |
| distribution_group | str | base／external |
| source_run_id | str | 持続run ID |
| external_vector_id | str | 外部ベクトルID |
| seed | int | world seed |
| source_step | int | step |
| active_factor_count | int | 活性外部要因数 |
| vector_origin | str | ベクトル生成由来 |
| analysis_weight | float | 分析重み |

---

## 2. model run成果物

### 2.1 `model_runs.csv`

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
| subset_id | 摂動subset。通常runは空 |
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
| fit_activation_path | fit活性度path |
| validation_activation_path | validation活性度path |
| basis_sha256 | 基底hash |
| fit_activation_sha256 | fit活性度hash |
| validation_activation_sha256 | validation活性度hash |

固定`converged=true`は禁止する。収束判定根拠をrun metadataへ残す。

### 2.2 run別配列

```text
models/<run_id>/basis.npy
models/<run_id>/fit_activations.npy
models/<run_id>/validation_activations.npy
models/<run_id>/run_metadata.json
```

- `basis.npy`：`(rank, 3125)`、非負、各行総和1
- `fit_activations.npy`：`(1082, rank)`、非負
- `validation_activations.npy`：`(256, rank)`、非負

再構成は次で独立再計算する。

```text
X_hat_fit = fit_activations @ basis
X_hat_validation = validation_activations @ basis
```

runごとの完全再構成行列は保存禁止とする。デバッグ用に一時生成しても正式成果物へ含めない。

---

## 3. 再構成評価

### 3.1 `reconstruction_metrics.csv`

1行＝1 run×split×subgroup×metric×weighting。

列：

- run_id
- method
- rank
- split
- subgroup_type
- subgroup_value
- weighting
- metric
- aggregation
- value
- row_count
- weight_sum
- evidence_basis_path
- evidence_activation_path
- independently_recomputed

`subgroup_type`：

- `all`
- `distribution_group`
- `source_step`
- `active_factor_count`
- `vector_origin`

metric：

- `rmse_raw`
- `mae_raw`
- `js_distance`
- `total_variation`
- `raw_row_sum_absolute_error`
- `negative_value_count`
- `nonfinite_value_count`

aggregation：

- `mean`
- `median`
- `p95`
- `max`

全指標でweighted／unweightedを分離する。

### 3.2 `pair_deformation_metrics.csv`

1行＝1 run×split×層別条件×指標。

列：

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

### 4.1 `component_matches.csv`

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

### 4.2 `rank_stability_summary.csv`

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

### 4.3 `structure_summary.csv`

1行＝選択代表runの1構造。

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
- handoff_status

`handoff_status`：

- `stable_structure`
- `conditional_structure`
- `excluded_duplicate`
- `excluded_inactive`
- `unstable`

`effective_cell_count = exp(entropy)` とし、entropyは自然対数で計算する。

### 4.4 `internal_structure_similarity.csv`

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

### 5.1 `rank_summary.csv`

固定gridの各rankについて必ず1行を出力する。7行未満は不合格。

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

### 5.2 `selection_lock.json`

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
- selected fit activation path／SHA-256
- selected validation activation path／SHA-256
- contract SHA-256
- input artifact SHA-256
- fit bundle SHA-256
- validation bundle SHA-256
- holdout accessed: `false`
- independent selection audit: `passed`

`holdout accessed`がtrue、欠落、または文字列の場合はlock無効とする。

### 5.3 `selection_audit.json`

独立検証器による再計算結果。

- recomputed selected rank
- stored selected rank
- match
- gate-by-gate results
- hash checks
- failed checks
- passed

---

## 6. holdout成果物

### 6.1 配列

```text
selected_model/holdout_activations.npy
```

形状：`(244, selected_rank)`。

holdout再構成行列は保存しない。次で独立再計算する。

```text
X_hat_holdout = holdout_activations @ selected_basis
```

### 6.2 `holdout_metrics.csv`

`reconstruction_metrics.csv` と同じ形式でholdout指標を保存する。

### 6.3 `holdout_outcome.json`

必須項目：

- selected rank
- selected representative run ID
- selection lock SHA-256
- holdout activation SHA-256
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

outcomeを独立再計算できなければ無効とする。

---

## 7. PCA参照

```text
references/pca_rank_summary.csv
references/pca_rank_<rank>/weighted_mean.npy
references/pca_rank_<rank>/components.npy
references/pca_rank_<rank>/fit_scores.npy
references/pca_rank_<rank>/validation_scores.npy
references/pca_validation_metrics.csv
references/pca_holdout_metrics.csv
```

必須記録：

- explained variance ratio
- cumulative explained variance
- raw reconstruction RMSE／MAE
- negative value rate
- raw row sum error
- simplex projected JS／TV

PCA成分を `structure_summary.csv` へ混ぜない。

---

## 8. 感度監査

### 8.1 Frobenius NMF

- `sensitivity/frobenius_model_runs.csv`
- `sensitivity/frobenius_structure_matches.csv`
- `sensitivity/frobenius_summary.csv`
- `sensitivity/frobenius_models/<run_id>/basis.npy`
- `sensitivity/frobenius_models/<run_id>/*_activations.npy`

選択rankと固定grid上の隣接rankだけを含める。

### 8.2 grouped subset

- `sensitivity/subset_definitions.csv`
- `sensitivity/subset_structure_matches.csv`
- `sensitivity/subset_summary.csv`
- `sensitivity/subset_models/<subset_id>/basis.npy`

### 8.3 world seed

- `sensitivity/world_seed_structure_matches.csv`
- `sensitivity/world_seed_summary.csv`
- `sensitivity/world_seed_models/<seed>/basis.npy`

---

## 9. 品質検査・報告

### 9.1 `quality_checks.json`

各checkをobject形式で保存する。

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

### 9.2 `mutation_test_results.json`

各破壊ケースについて：

- mutation ID
- mutated artifact
- expected failed check
- actual failed check
- failure message
- passed

### 9.3 `results.md`

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

### 9.4 `artifact_manifest.json`

各ファイルについて：

- relative path
- type
- size bytes
- SHA-256
- CSV row count and columns
- NPY shape and dtype
- NPZ member names, shapes, dtypes
- JSON top-level schema

manifest自身は自己hash対象外とする。最終archive digestを別に記録する。

---

## 10. 保存量の上限管理

正式成果物へ保存するのは、再現・独立検証・後続解析に必要な最小集合とする。

保存する：

- 入力bundle
- 基底
- 活性度
- run metadata
- 指標表
- 対応表
- selection lock
- 監査結果

保存しない：

- 全runの完全再構成行列
- 一時作業配列
- solver内部状態
- 重複した入力コピー
- デバッグ画像の大量出力

独立検証に必要なら基底と活性度から再生成する。

---

## 11. PR完了報告

Task 3.1f-2以降のPR本文へ記録する。

- 新規タスク／既存タスク
- base branch
- working branch
- 実装した固定要件
- 正常系テスト
- 破壊系テスト
- smoke結果
- formal Actions run ID
- artifact ID／digest
- selected rank
- holdout outcome
- Task 3.1g handoff status
- 未実装・未解決項目
- placeholder、固定pass、自己証明が残っていないこと
