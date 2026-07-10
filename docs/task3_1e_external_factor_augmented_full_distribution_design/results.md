# Task 3.1e External-Factor-Augmented Full Distribution Design Results

## Task purpose

- This task designs an external-factor-augmented full distribution target for later semantic structure extraction.
- This task does not select semantic axes.
- This task does not reduce candidates to 15 axes.
- This task does not perform structure extraction.
- This task does not use PCA as the primary log basis.

日本語: 本タスクは後続の意味構造抽出のための外部要因込みフル分布対象を設計します。意味論軸の選択、15軸への絞り込み、構造抽出、PCAの主ログ基盤化は行いません。

## Distribution group policy

- base_v3_3 and external_augmented are stored separately.
- combined_full is a later aggregation view, not a raw distribution_group.
- distribution_group is required for every distribution state.
- allowed raw distribution_group values are base_v3_3 and external_augmented only.

日本語: base_v3_3 と external_augmented は分離保存します。combined_full は後続集計ビューであり raw distribution_group ではありません。

## External factor policy

- External factors are not axes.
- External factor labels are metadata.
- External factors are included through the distribution states produced after they act on the world.
- Later tasks may evaluate how much of base_v3_3, external_augmented, and combined_full is covered by semantic structures.

日本語: 外部要因は軸ではなくメタデータです。外部要因が world に作用した後の分布状態として保存します。

## Mass matrix policy

- full_distribution_mass_matrix.jsonl stores the actual distribution mass rows used by later structure extraction tasks.
- full_distribution_state_index.csv maps JSONL mass rows to full_distribution_state_manifest.csv.
- CSV summaries alone are not treated as the full distribution.
- No binary docs artifact is used for Task 3.1e.

日本語: CSV要約だけをフル分布とは扱わず、実際の質量行列を JSONL テキストとして保存します。Task 3.1e ではバイナリdocs成果物を使いません。

## Non-goals

- No semantic axis selection.
- No 15-axis selection.
- No residual axis creation.
- No external-factor axis creation.
- No K_t connection.
- No O_t connection.
- No H-DEPT connection.
- No ActionModule connection.
- No world-core modification.

日本語: 意味論軸選択、15軸選択、残差軸作成、外部要因軸作成、K_t/O_t/H-DEPT/ActionModule への接続、world core 変更は行いません。

## Artifact scale

- n_bins: 4
- steps: 12
- base_v3_3 state count: 12
- external_augmented state count: 110
- combined full state count: 122
- external factor family count: 10
- external factor scenario count: 39
- mass matrix row count: 122
- mass matrix cell count: 1024
- base_pair_key unmatched external count: 0
- reduced run: false
- official docs artifact: true

日本語: 上記スケールの成果物は production world による非reducedの公式docs artifactです。
