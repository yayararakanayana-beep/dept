# Task 3.1 Fixed PCA External Factor Projection Audit

This report audits external-factor projections into frozen Task 3 PCA bases.
It does not select the final PCA-G_t candidate. Final adoption decision is reserved for human review.

## Candidate-level summary
| candidate_name | candidate_role | residual_energy_ratio_mean | external_residual_gain_mean | external_score_displacement_mean | out_of_envelope_rate |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10 | audit_focus_candidate | 0.0196467 | 0.00471471 | 0.00405537 | 0.382284 |
| sqrt_static_pca_7 | continuity_baseline | 0.0506273 | 0.00521517 | 0.00341048 | 0.477855 |
| sqrt_static_pca_12 | higher_dimension_audit | 0.0166576 | 0.00462049 | 0.0041463 | 0.401709 |
| raw_static_pca_7 | numerical_reconstruction_baseline | 0.0027341 | 0.00140642 | 0.00035504 | 0.641803 |
| sqrt_sparse_temporal_lag_pca_10 | temporal_audit_candidate | 0.0223701 | 0.00475379 | 0.00384335 | 0.345765 |

## External factor response summary
| candidate_name | external_factor_name | mean_score_displacement | mean_residual_gain | out_of_envelope_rate |
| --- | --- | --- | --- | --- |
| raw_static_pca_7 | external_competition_pressure | 0.000314512 | 0.00209825 | 0.769231 |
| raw_static_pca_7 | external_competition_pressure+external_information_noise | 0.000443058 | 0.00408479 | 0.846154 |
| raw_static_pca_7 | external_constraint_pressure | 0.00022827 | 0.00159515 | 0.697436 |
| raw_static_pca_7 | external_demand | 0.000155655 | -8.17511e-06 | 0.461538 |
| raw_static_pca_7 | external_information_noise | 0.000155262 | 0.00141649 | 0.692308 |
| raw_static_pca_7 | external_resource_supply | 0.000221286 | 0.00113864 | 0.646154 |
| raw_static_pca_7 | external_resource_supply+external_demand | 0.000193019 | 0.000504867 | 0.461538 |
| raw_static_pca_7 | external_shock | 0.00093973 | 0.00161966 | 0.6 |
| raw_static_pca_7 | external_shock+external_constraint_pressure | 0.00132117 | 0.00462046 | 0.846154 |
| sqrt_sparse_temporal_lag_pca_10 | external_competition_pressure | 0.00460999 | 0.00664618 | 0.346154 |
| sqrt_sparse_temporal_lag_pca_10 | external_competition_pressure+external_information_noise | 0.00767233 | 0.0127968 | 0.230769 |
| sqrt_sparse_temporal_lag_pca_10 | external_constraint_pressure | 0.00161163 | 0.00550918 | 0.333333 |
| sqrt_sparse_temporal_lag_pca_10 | external_demand | 0.00123834 | -0.000433993 | 0.410256 |
| sqrt_sparse_temporal_lag_pca_10 | external_information_noise | 0.00168489 | 0.00560512 | 0.374359 |
| sqrt_sparse_temporal_lag_pca_10 | external_resource_supply | 0.00308329 | 0.00220078 | 0.389744 |
| sqrt_sparse_temporal_lag_pca_10 | external_resource_supply+external_demand | 0.00210924 | 0.00158335 | 0.384615 |
| sqrt_sparse_temporal_lag_pca_10 | external_shock | 0.00923685 | 0.00683502 | 0.251282 |
| sqrt_sparse_temporal_lag_pca_10 | external_shock+external_constraint_pressure | 0.014334 | 0.0173297 | 0.230769 |
| sqrt_static_pca_10 | external_competition_pressure | 0.00492159 | 0.0062295 | 0.384615 |
| sqrt_static_pca_10 | external_competition_pressure+external_information_noise | 0.00821412 | 0.0120835 | 0.384615 |

## sqrt_static_pca_10 vs sqrt_static_pca_7
| candidate_name | candidate_role | external_residual_gain_mean | external_score_displacement_mean | out_of_envelope_rate | review_status |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10 | audit_focus_candidate | 0.00471471 | 0.00405537 | 0.382284 | requires_human_review |
| sqrt_static_pca_7 | continuity_baseline | 0.00521517 | 0.00341048 | 0.477855 | requires_human_review |

## sqrt_static_pca_10 vs raw_static_pca_7
| candidate_name | candidate_role | external_residual_gain_mean | external_score_displacement_mean | out_of_envelope_rate | review_status |
| --- | --- | --- | --- | --- | --- |
| raw_static_pca_7 | numerical_reconstruction_baseline | 0.00140642 | 0.00035504 | 0.641803 | requires_human_review |
| sqrt_static_pca_10 | audit_focus_candidate | 0.00471471 | 0.00405537 | 0.382284 | requires_human_review |

## sqrt_static_pca_10 vs sqrt_static_pca_12
| candidate_name | candidate_role | external_residual_gain_mean | external_score_displacement_mean | out_of_envelope_rate | review_status |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10 | audit_focus_candidate | 0.00471471 | 0.00405537 | 0.382284 | requires_human_review |
| sqrt_static_pca_12 | higher_dimension_audit | 0.00462049 | 0.0041463 | 0.401709 | requires_human_review |

## Out-of-envelope rates by candidate
| candidate_name | candidate_role | out_of_envelope_rate | score_range_violation_count |
| --- | --- | --- | --- |
| raw_static_pca_7 | numerical_reconstruction_baseline | 0.641803 | 513 |
| sqrt_static_pca_7 | continuity_baseline | 0.477855 | 454 |
| sqrt_static_pca_12 | higher_dimension_audit | 0.401709 | 466 |
| sqrt_static_pca_10 | audit_focus_candidate | 0.382284 | 466 |
| sqrt_sparse_temporal_lag_pca_10 | temporal_audit_candidate | 0.345765 | 430 |

## Residual gain by factor (sqrt_static_pca_10 audit focus)
| external_factor_name | mean_residual_gain | mean_mahalanobis_distance | out_of_envelope_rate |
| --- | --- | --- | --- |
| external_shock+external_constraint_pressure | 0.0171161 | 2.96008 | 0.384615 |
| external_competition_pressure+external_information_noise | 0.0120835 | 3.2595 | 0.384615 |
| external_shock | 0.00695171 | 2.97139 | 0.338462 |
| external_competition_pressure | 0.0062295 | 3.19129 | 0.384615 |
| external_information_noise | 0.00555202 | 3.1079 | 0.384615 |
| external_constraint_pressure | 0.00532677 | 3.1183 | 0.379487 |
| external_resource_supply | 0.00272278 | 3.04887 | 0.389744 |
| external_resource_supply+external_demand | 0.00151337 | 3.14709 | 0.384615 |
| external_demand | -0.000562361 | 3.11762 | 0.415385 |

## Score displacement by factor (sqrt_static_pca_10 audit focus)
| external_factor_name | mean_score_displacement | mean_residual_factor_signal_ratio | out_of_envelope_rate |
| --- | --- | --- | --- |
| external_shock+external_constraint_pressure | 0.0144556 | 0.815729 | 0.384615 |
| external_shock | 0.00929687 | 0.379917 | 0.338462 |
| external_competition_pressure+external_information_noise | 0.00821412 | 1.04374 | 0.384615 |
| external_competition_pressure | 0.00492159 | 0.748482 | 0.384615 |
| external_resource_supply | 0.0036536 | 0.567632 | 0.389744 |
| external_resource_supply+external_demand | 0.00236616 | 0.50554 | 0.384615 |
| external_constraint_pressure | 0.00179702 | 1.63129 | 0.379487 |
| external_information_noise | 0.00172062 | 1.73098 | 0.384615 |
| external_demand | 0.00135289 | -0.119714 | 0.415385 |

Human review required before candidate adoption.
