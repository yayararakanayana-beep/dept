# Task 3.1d Full-Distribution Semantic Axis Candidate Audit

This report does not select final Core dimensions.
This report does not compress the full distribution into a fixed 5-axis Core.
This report does not use PCA as the primary log basis.
This report only audits semantic axis candidates extracted from the full distribution.
Axis classifications are decision-support labels, not final adoption decisions.
The goal is to preserve information needed for later macro-dynamics extraction.

このレポートは最終Core次元を確定しない。
このレポートはフル分布を固定5軸Coreへ圧縮しない。
このレポートはPCAを主ログ基盤として採用しない。
このレポートはフル分布から抽出した意味論軸候補を監査するだけである。
軸分類は判断材料であり、最終採用判断ではない。
目的は、後段のマクロ力学抽出に必要な情報を保存することである。

## Artifact provenance

- Generation command: `python scripts/pseudoreality_v3_3_full_distribution_semantic_axis_candidate_audit.py`
- Source data path: production PseudoReality path using `DistributionTerrainV322World`, `DistributionTerrainV322Config`, `world.set_external_factors(...)`, `world.step()`, and full `world.distribution` mass snapshots; Task 3.1c compact residual artifacts are read but not overwritten.
- Full distribution source: yes
- PCA used as primary log basis: no
- Fixed 5-axis Core selected: no
- Final Core dimensions selected: no
- Axis classifications are final decisions: no
- Detailed logs written by default: no

## Artifact scale

- n_bins: 5
- steps: 12
- available fit scenario count: 32
- used fit scenario count: 32
- available holdout scenario count: 7
- used holdout scenario count: 7
- available fit seed count: 3
- used fit seed count: 3
- available holdout seed count: 2
- used holdout seed count: 2
- snapshot count: 1446
- reduced run: false
- official docs artifact: true

## Task 3.1c linkage

- residual decomposition file: `docs/task3_1c_external_envelope_residual_decomposition/compact_residual_decomposition_summary.csv`
- residual terrain file: `docs/task3_1c_external_envelope_residual_decomposition/compact_residual_terrain_summary.csv`
- auto audit flag reason file: `docs/task3_1c_external_envelope_residual_decomposition/compact_auto_audit_flag_reason_summary.csv`
- residual rows loaded: 15
- terrain rows loaded: 195
- flag reason rows loaded: 15
- join key: dataset
- matched relation rows: 78
- unmatched rate: 0.000000

## Classification note

- Axis classifications are decision-support labels only.
- Classification reasons are derived from measured external response, residual relation, macro-dynamics preservation, redundancy, and conditional separation.
- No Core dimensions are selected in this task.
