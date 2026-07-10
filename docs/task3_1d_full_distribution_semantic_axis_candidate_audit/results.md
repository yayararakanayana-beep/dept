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
- Source data path: production PseudoReality path using `DistributionTerrainV322World`, `DistributionTerrainV322Config`, `world.set_external_factors(...)`, `world.step()`, and full `world.distribution` mass snapshots.
- Full distribution source: yes
- PCA used as primary log basis: no
- Fixed 5-axis Core selected: no
- Final Core dimensions selected: no
- Axis classifications are final decisions: no
- Detailed logs written by default: no
