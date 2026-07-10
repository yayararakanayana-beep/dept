# Task 3.1c External-Envelope Residual Decomposition Audit

This report does not select, reject, or adopt any PCA-G_t candidate.
This report only decomposes residuals and automatic audit flags for human review.
Automatic audit flags are diagnostic signals, not final validity judgments.

このレポートはPCA-G_t候補を採用・不採用にするものではない。
残差と自動監査フラグの理由を分解し、人間が判断するための材料を出すだけである。
自動監査フラグは診断信号であり、最終的な有効・無効判断ではない。

## Candidate residual decomposition
| candidate_name | dataset | residual_energy_ratio_mean | residual_energy_ratio_p90 | residual_energy_ratio_p95 | auto_audit_flag_rate |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | 0.0333333 | 0.08 | 0.09 | 0 |
| sqrt_static_pca_10_external_envelope | holdout_external | 0.0666667 | 0.1 | 0.1 | 0 |
| sqrt_static_pca_10_external_envelope | no_external_reference | 0.0333333 | 0.08 | 0.09 | 0.333333 |

## Automatic audit flag reason decomposition
| candidate_name | dataset | residual_exceed_rate | mahalanobis_exceed_rate | score_range_exceed_rate | all_three_exceed_rate | no_flag_rate |
| --- | --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | 0 | 0 | 0 | 0 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_external | 0 | 0 | 0 | 0 | 1 |
| sqrt_static_pca_10_external_envelope | no_external_reference | 0.333333 | 0 | 0 | 0 | 0.666667 |

## External factor residual decomposition
| external_factor_name | scenario_id | candidate_name | dataset | residual_energy_ratio_mean | auto_audit_flag_rate |
| --- | --- | --- | --- | --- | --- |
| external_shock | fit_unit | sqrt_static_pca_10_external_envelope | fit_external | 0.0333333 | 0 |
| external_shock | holdout_unit | sqrt_static_pca_10_external_envelope | holdout_external | 0.0666667 | 0 |

## Temporal residual decomposition
| scenario_id | candidate_name | seed | dataset | residual_peak | residual_slope | residual_persistence_rate | flag_persistence_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fit_unit | sqrt_static_pca_10_external_envelope | 0 | fit_external | 0.1 | 0.1 | 0 | 0 |
| holdout_unit | sqrt_static_pca_10_external_envelope | 0 | holdout_external | 0.1 | 0.1 | 0 | 0 |
| no_ext | sqrt_static_pca_10_external_envelope | 0 | no_external_reference | 0.1 | 0.1 | 0.333333 | 0.333333 |

## Residual and G_t movement relation
| candidate_name | dataset | correlation_residual_displacement | correlation_residual_velocity | correlation_residual_curvature |
| --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | 0.673455 | -0.181273 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_external | 0.950721 | 0.851108 | 0.5 |
| sqrt_static_pca_10_external_envelope | no_external_reference | 0.52956 | -0.356681 | 1 |

## Residual terrain summary
| candidate_name | dataset | external_factor_name | scenario_id | top_residual_mass_share | residual_concentration_score |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock | fit_unit | 1 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_external | external_shock | holdout_unit | 1 | 1 |

No candidate decision is made in this report.
