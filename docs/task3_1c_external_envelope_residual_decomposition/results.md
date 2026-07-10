# Task 3.1c External-Envelope Residual Decomposition Audit

This report does not select, reject, or adopt any PCA-G_t candidate.
This report only decomposes residuals and automatic audit flags for human review.
Automatic audit flags are diagnostic signals, not final validity judgments.

このレポートはPCA-G_t候補を採用・不採用にするものではない。
残差と自動監査フラグの理由を分解し、人間が判断するための材料を出すだけである。
自動監査フラグは診断信号であり、最終的な有効・無効判断ではない。

## Artifact provenance

- Generation command: `python scripts/pseudoreality_v3_3_external_envelope_residual_decomposition_audit.py`
- Source data path: Task 3.1b production generator via `fit_bases(...)`, `build_external_envelope_fit_corpus(...)`, `build_holdout_corpus(...)`, `DistributionTerrainV322World`, `world.set_external_factors(...)`, `world.step()`, `snapshot_to_mass_vector(world.distribution)`, and `build_full_envelope_corpus(...)`
- Task 3.1b generator reused: yes
- PCA candidate count: 5
- Dataset splits: fit_external, holdout_external, no_external_reference
- Detailed logs written by default: no
- Candidate decision made: no

## Candidate residual decomposition
| candidate_name | dataset | residual_energy_ratio_mean | residual_energy_ratio_p90 | residual_energy_ratio_p95 | auto_audit_flag_rate |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | 0.0724749 | 0.184966 | 0.238648 | 0.025641 |
| sqrt_static_pca_10_external_envelope | holdout_external | 0.214543 | 0.474012 | 0.52969 | 0.343434 |
| sqrt_static_pca_10_external_envelope | no_external_reference | 0.0129277 | 0.0204757 | 0.0773465 | 0.504132 |
| sqrt_static_pca_12_external_envelope | fit_external | 0.0434285 | 0.106813 | 0.128427 | 0.0264423 |
| sqrt_static_pca_12_external_envelope | holdout_external | 0.177193 | 0.434116 | 0.464804 | 0.454545 |
| sqrt_static_pca_12_external_envelope | no_external_reference | 0.0118929 | 0.0193075 | 0.0698371 | 0.504132 |
| sqrt_static_pca_15_external_envelope | fit_external | 0.0125164 | 0.0295477 | 0.0384591 | 0.03125 |
| sqrt_static_pca_15_external_envelope | holdout_external | 0.143311 | 0.359327 | 0.374873 | 0.79798 |
| sqrt_static_pca_15_external_envelope | no_external_reference | 0.00518082 | 0.0130749 | 0.0143875 | 0.305785 |
| raw_static_pca_10_external_envelope | fit_external | 0.0112518 | 0.0262684 | 0.0429808 | 0.0200321 |
| raw_static_pca_10_external_envelope | holdout_external | 0.0176074 | 0.0458187 | 0.0556666 | 0.176768 |
| raw_static_pca_10_external_envelope | no_external_reference | 0.0019135 | 0.00337583 | 0.0106535 | 0.305785 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | fit_external | 0.0725544 | 0.185181 | 0.238844 | 0.025641 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | holdout_external | 0.214692 | 0.473784 | 0.528939 | 0.343434 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | no_external_reference | 0.0136909 | 0.0246053 | 0.077294 | 0.504132 |

## Automatic audit flag reason decomposition
| candidate_name | dataset | residual_exceed_rate | mahalanobis_exceed_rate | score_range_exceed_rate | all_three_exceed_rate | no_flag_rate |
| --- | --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | 0.025641 | 0 | 0 | 0 | 0.974359 |
| sqrt_static_pca_10_external_envelope | holdout_external | 0.262626 | 0 | 0.0808081 | 0 | 0.656566 |
| sqrt_static_pca_10_external_envelope | no_external_reference | 0 | 0.504132 | 0 | 0 | 0.495868 |
| sqrt_static_pca_12_external_envelope | fit_external | 0.0264423 | 0 | 0 | 0 | 0.973558 |
| sqrt_static_pca_12_external_envelope | holdout_external | 0.373737 | 0.00505051 | 0.0808081 | 0 | 0.545455 |
| sqrt_static_pca_12_external_envelope | no_external_reference | 0 | 0.504132 | 0 | 0 | 0.495868 |
| sqrt_static_pca_15_external_envelope | fit_external | 0.03125 | 0 | 0 | 0 | 0.96875 |
| sqrt_static_pca_15_external_envelope | holdout_external | 0.747475 | 0.0252525 | 0.0808081 | 0.0252525 | 0.20202 |
| sqrt_static_pca_15_external_envelope | no_external_reference | 0 | 0.305785 | 0 | 0 | 0.694215 |
| raw_static_pca_10_external_envelope | fit_external | 0.0200321 | 0 | 0 | 0 | 0.979968 |
| raw_static_pca_10_external_envelope | holdout_external | 0.0707071 | 0.040404 | 0.106061 | 0 | 0.823232 |
| raw_static_pca_10_external_envelope | no_external_reference | 0 | 0.305785 | 0 | 0 | 0.694215 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | fit_external | 0.025641 | 0 | 0 | 0 | 0.974359 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | holdout_external | 0.262626 | 0 | 0.0808081 | 0 | 0.656566 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | no_external_reference | 0 | 0.504132 | 0 | 0 | 0.495868 |

## External factor residual decomposition
| external_factor_name | scenario_id | candidate_name | dataset | residual_energy_ratio_mean | auto_audit_flag_rate |
| --- | --- | --- | --- | --- | --- |
| external_resource_supply | fit_single_external_resource_supply_-1.00 | sqrt_static_pca_10_external_envelope | fit_external | 0.0482361 | 0 |
| external_resource_supply | fit_single_external_resource_supply_-0.50 | sqrt_static_pca_10_external_envelope | fit_external | 0.0364743 | 0 |
| external_resource_supply | fit_single_external_resource_supply_+0.50 | sqrt_static_pca_10_external_envelope | fit_external | 0.0504319 | 0 |
| external_resource_supply | fit_single_external_resource_supply_+1.00 | sqrt_static_pca_10_external_envelope | fit_external | 0.110573 | 0.025641 |
| external_demand | fit_single_external_demand_-1.00 | sqrt_static_pca_10_external_envelope | fit_external | 0.0426903 | 0 |
| external_demand | fit_single_external_demand_-0.50 | sqrt_static_pca_10_external_envelope | fit_external | 0.0406504 | 0 |
| external_demand | fit_single_external_demand_+0.50 | sqrt_static_pca_10_external_envelope | fit_external | 0.0359033 | 0 |
| external_demand | fit_single_external_demand_+1.00 | sqrt_static_pca_10_external_envelope | fit_external | 0.0415888 | 0 |
| external_competition_pressure | fit_single_external_competition_pressure_0.25 | sqrt_static_pca_10_external_envelope | fit_external | 0.0351761 | 0 |
| external_competition_pressure | fit_single_external_competition_pressure_0.50 | sqrt_static_pca_10_external_envelope | fit_external | 0.0581096 | 0 |
| external_competition_pressure | fit_single_external_competition_pressure_0.75 | sqrt_static_pca_10_external_envelope | fit_external | 0.0984975 | 0 |
| external_competition_pressure | fit_single_external_competition_pressure_1.00 | sqrt_static_pca_10_external_envelope | fit_external | 0.146412 | 0.0769231 |
| external_information_noise | fit_single_external_information_noise_0.25 | sqrt_static_pca_10_external_envelope | fit_external | 0.0416919 | 0 |
| external_information_noise | fit_single_external_information_noise_0.50 | sqrt_static_pca_10_external_envelope | fit_external | 0.0638263 | 0 |
| external_information_noise | fit_single_external_information_noise_0.75 | sqrt_static_pca_10_external_envelope | fit_external | 0.0971051 | 0 |
| external_information_noise | fit_single_external_information_noise_1.00 | sqrt_static_pca_10_external_envelope | fit_external | 0.134733 | 0.128205 |
| external_shock | fit_single_external_shock_0.25 | sqrt_static_pca_10_external_envelope | fit_external | 0.0331259 | 0 |
| external_shock | fit_single_external_shock_0.50 | sqrt_static_pca_10_external_envelope | fit_external | 0.0483677 | 0 |
| external_shock | fit_single_external_shock_0.75 | sqrt_static_pca_10_external_envelope | fit_external | 0.0960599 | 0 |
| external_shock | fit_single_external_shock_1.00 | sqrt_static_pca_10_external_envelope | fit_external | 0.15011 | 0.153846 |
| external_constraint_pressure | fit_single_external_constraint_pressure_0.25 | sqrt_static_pca_10_external_envelope | fit_external | 0.0465216 | 0 |
| external_constraint_pressure | fit_single_external_constraint_pressure_0.50 | sqrt_static_pca_10_external_envelope | fit_external | 0.0712942 | 0 |
| external_constraint_pressure | fit_single_external_constraint_pressure_0.75 | sqrt_static_pca_10_external_envelope | fit_external | 0.103859 | 0 |
| external_constraint_pressure | fit_single_external_constraint_pressure_1.00 | sqrt_static_pca_10_external_envelope | fit_external | 0.138578 | 0.153846 |
| external_shock | fit_pulse_external_shock_t4 | sqrt_static_pca_10_external_envelope | fit_external | 0.0360705 | 0 |
| external_information_noise | fit_pulse_external_information_noise_t4 | sqrt_static_pca_10_external_envelope | fit_external | 0.0366025 | 0 |
| external_constraint_pressure | fit_pulse_external_constraint_pressure_t4 | sqrt_static_pca_10_external_envelope | fit_external | 0.0383603 | 0 |
| external_resource_supply | fit_reversal_resource_supply | sqrt_static_pca_10_external_envelope | fit_external | 0.0905205 | 0.025641 |
| external_demand | fit_reversal_demand | sqrt_static_pca_10_external_envelope | fit_external | 0.0345158 | 0 |
| external_competition_pressure+external_information_noise | fit_competition_plus_noise | sqrt_static_pca_10_external_envelope | fit_external | 0.116134 | 0.0512821 |

## Temporal residual decomposition
| scenario_id | candidate_name | seed | dataset | residual_peak | residual_slope | residual_persistence_rate | flag_persistence_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fit_single_external_resource_supply_-1.00 | sqrt_static_pca_10_external_envelope | 0 | fit_external | 0.0981248 | 0.0894097 | 0 | 0 |
| fit_single_external_resource_supply_-1.00 | sqrt_static_pca_10_external_envelope | 1 | fit_external | 0.0991373 | 0.0882832 | 0 | 0 |
| fit_single_external_resource_supply_-1.00 | sqrt_static_pca_10_external_envelope | 2 | fit_external | 0.0985483 | 0.0883128 | 0 | 0 |
| fit_single_external_resource_supply_-0.50 | sqrt_static_pca_10_external_envelope | 0 | fit_external | 0.109597 | 0.0416204 | 0 | 0 |
| fit_single_external_resource_supply_-0.50 | sqrt_static_pca_10_external_envelope | 1 | fit_external | 0.0955497 | 0.0402032 | 0 | 0 |
| fit_single_external_resource_supply_-0.50 | sqrt_static_pca_10_external_envelope | 2 | fit_external | 0.101712 | 0.04016 | 0 | 0 |
| fit_single_external_resource_supply_+0.50 | sqrt_static_pca_10_external_envelope | 0 | fit_external | 0.169437 | 0.0322333 | 0 | 0 |
| fit_single_external_resource_supply_+0.50 | sqrt_static_pca_10_external_envelope | 1 | fit_external | 0.148512 | 0.0299732 | 0 | 0 |
| fit_single_external_resource_supply_+0.50 | sqrt_static_pca_10_external_envelope | 2 | fit_external | 0.156359 | 0.0302565 | 0 | 0 |
| fit_single_external_resource_supply_+1.00 | sqrt_static_pca_10_external_envelope | 0 | fit_external | 0.289392 | 0.113152 | 0.0769231 | 0.0769231 |
| fit_single_external_resource_supply_+1.00 | sqrt_static_pca_10_external_envelope | 1 | fit_external | 0.263373 | 0.110598 | 0 | 0 |
| fit_single_external_resource_supply_+1.00 | sqrt_static_pca_10_external_envelope | 2 | fit_external | 0.274371 | 0.111146 | 0 | 0 |
| fit_single_external_demand_-1.00 | sqrt_static_pca_10_external_envelope | 0 | fit_external | 0.134191 | 0.0376616 | 0 | 0 |
| fit_single_external_demand_-1.00 | sqrt_static_pca_10_external_envelope | 1 | fit_external | 0.118415 | 0.0359835 | 0 | 0 |
| fit_single_external_demand_-1.00 | sqrt_static_pca_10_external_envelope | 2 | fit_external | 0.125931 | 0.0357225 | 0 | 0 |
| fit_single_external_demand_-0.50 | sqrt_static_pca_10_external_envelope | 0 | fit_external | 0.130468 | 0.0312469 | 0 | 0 |
| fit_single_external_demand_-0.50 | sqrt_static_pca_10_external_envelope | 1 | fit_external | 0.114347 | 0.0296105 | 0 | 0 |
| fit_single_external_demand_-0.50 | sqrt_static_pca_10_external_envelope | 2 | fit_external | 0.121272 | 0.0295231 | 0 | 0 |
| fit_single_external_demand_+0.50 | sqrt_static_pca_10_external_envelope | 0 | fit_external | 0.127556 | 0.0237289 | 0 | 0 |
| fit_single_external_demand_+0.50 | sqrt_static_pca_10_external_envelope | 1 | fit_external | 0.111077 | 0.0216995 | 0 | 0 |
| fit_single_external_demand_+0.50 | sqrt_static_pca_10_external_envelope | 2 | fit_external | 0.117973 | 0.0218974 | 0 | 0 |
| fit_single_external_demand_+1.00 | sqrt_static_pca_10_external_envelope | 0 | fit_external | 0.129919 | 0.040502 | 0 | 0 |
| fit_single_external_demand_+1.00 | sqrt_static_pca_10_external_envelope | 1 | fit_external | 0.113878 | 0.0381869 | 0 | 0 |
| fit_single_external_demand_+1.00 | sqrt_static_pca_10_external_envelope | 2 | fit_external | 0.121418 | 0.0386349 | 0 | 0 |
| fit_single_external_competition_pressure_0.25 | sqrt_static_pca_10_external_envelope | 0 | fit_external | 0.129856 | 0.0148006 | 0 | 0 |
| fit_single_external_competition_pressure_0.25 | sqrt_static_pca_10_external_envelope | 1 | fit_external | 0.113856 | 0.0128691 | 0 | 0 |
| fit_single_external_competition_pressure_0.25 | sqrt_static_pca_10_external_envelope | 2 | fit_external | 0.122033 | 0.0133525 | 0 | 0 |
| fit_single_external_competition_pressure_0.50 | sqrt_static_pca_10_external_envelope | 0 | fit_external | 0.175607 | 0.0537478 | 0 | 0 |
| fit_single_external_competition_pressure_0.50 | sqrt_static_pca_10_external_envelope | 1 | fit_external | 0.159476 | 0.0517031 | 0 | 0 |
| fit_single_external_competition_pressure_0.50 | sqrt_static_pca_10_external_envelope | 2 | fit_external | 0.170522 | 0.052485 | 0 | 0 |

## Residual and G_t movement relation
| candidate_name | dataset | correlation_residual_displacement | correlation_residual_velocity | correlation_residual_curvature |
| --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | 0.427941 | 0.114511 | 0.192032 |
| sqrt_static_pca_10_external_envelope | holdout_external | -0.135066 | 0.245964 | 0.286785 |
| sqrt_static_pca_10_external_envelope | no_external_reference | -0.228277 | -0.228318 | -0.148498 |
| sqrt_static_pca_12_external_envelope | fit_external | 0.336519 | 0.102106 | 0.133034 |
| sqrt_static_pca_12_external_envelope | holdout_external | -0.291471 | 0.177782 | -0.00841224 |
| sqrt_static_pca_12_external_envelope | no_external_reference | -0.224879 | -0.224934 | -0.14638 |
| sqrt_static_pca_15_external_envelope | fit_external | 0.382567 | 0.0674664 | 0.297337 |
| sqrt_static_pca_15_external_envelope | holdout_external | -0.40857 | 0.148244 | 0.120061 |
| sqrt_static_pca_15_external_envelope | no_external_reference | -0.223225 | -0.223756 | -0.147205 |
| raw_static_pca_10_external_envelope | fit_external | 0.26197 | 0.0449792 | 0.206121 |
| raw_static_pca_10_external_envelope | holdout_external | 0.255962 | 0.047306 | 0.129235 |
| raw_static_pca_10_external_envelope | no_external_reference | -0.221014 | -0.221001 | -0.144464 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | fit_external | 0.4279 | 0.11441 | 0.197523 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | holdout_external | -0.134677 | 0.246613 | 0.288411 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | no_external_reference | -0.301265 | -0.315999 | -0.217746 |

## Residual terrain summary
| candidate_name | dataset | external_factor_name | scenario_id | top_residual_mass_share | residual_concentration_score |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | external_resource_supply | fit_single_external_resource_supply_-1.00 | 0.0207675 | 0.0879392 |
| sqrt_static_pca_10_external_envelope | fit_external | external_resource_supply | fit_single_external_resource_supply_-0.50 | 0.0192293 | 0.0819522 |
| sqrt_static_pca_10_external_envelope | fit_external | external_resource_supply | fit_single_external_resource_supply_+0.50 | 0.0130779 | 0.0475877 |
| sqrt_static_pca_10_external_envelope | fit_external | external_resource_supply | fit_single_external_resource_supply_+1.00 | 0.0154361 | 0.0629603 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | fit_single_external_demand_-1.00 | 0.0200802 | 0.0826316 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | fit_single_external_demand_-0.50 | 0.0203253 | 0.0858359 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | fit_single_external_demand_+0.50 | 0.0172464 | 0.0649634 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | fit_single_external_demand_+1.00 | 0.0274554 | 0.149519 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | fit_single_external_competition_pressure_0.25 | 0.0181243 | 0.0704263 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | fit_single_external_competition_pressure_0.50 | 0.0136399 | 0.0459209 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | fit_single_external_competition_pressure_0.75 | 0.0130531 | 0.0438222 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | fit_single_external_competition_pressure_1.00 | 0.0134304 | 0.046635 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | fit_single_external_information_noise_0.25 | 0.0170138 | 0.0652608 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | fit_single_external_information_noise_0.50 | 0.0189633 | 0.0762244 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | fit_single_external_information_noise_0.75 | 0.0196444 | 0.08172 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | fit_single_external_information_noise_1.00 | 0.0195875 | 0.0826092 |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock | fit_single_external_shock_0.25 | 0.0234906 | 0.123182 |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock | fit_single_external_shock_0.50 | 0.015421 | 0.0608088 |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock | fit_single_external_shock_0.75 | 0.0174805 | 0.0703379 |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock | fit_single_external_shock_1.00 | 0.0180555 | 0.0805709 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | fit_single_external_constraint_pressure_0.25 | 0.0192984 | 0.0774812 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | fit_single_external_constraint_pressure_0.50 | 0.019159 | 0.0759732 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | fit_single_external_constraint_pressure_0.75 | 0.020355 | 0.0841264 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | fit_single_external_constraint_pressure_1.00 | 0.0206836 | 0.0859049 |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock | fit_pulse_external_shock_t4 | 0.0203662 | 0.0848832 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | fit_pulse_external_information_noise_t4 | 0.0217783 | 0.104518 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | fit_pulse_external_constraint_pressure_t4 | 0.0216043 | 0.101862 |
| sqrt_static_pca_10_external_envelope | fit_external | external_resource_supply | fit_reversal_resource_supply | 0.016171 | 0.0684731 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | fit_reversal_demand | 0.0188418 | 0.0825688 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure+external_information_noise | fit_competition_plus_noise | 0.0133567 | 0.0434753 |

No candidate decision is made in this report.
