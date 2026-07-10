# Task 3.1b External-Envelope Fixed PCA Audit

This report does not select the final PCA-G_t candidate. Final adoption decision is reserved for human review.

Lower out-of-envelope rate alone is not sufficient. G_t displacement and factor-response separation must also be preserved.

## Candidate-level summary: fit_external
| candidate_name | candidate_role | dataset | reconstruction_error_mean | residual_energy_ratio_mean | mahalanobis_distance_mean | out_of_envelope_rate | external_score_displacement_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | focus_candidate | fit_external | 6.62881e-05 | 0.00256841 | 1.82948 | 0 | 0.0491795 |
| sqrt_static_pca_12_external_envelope | higher_dimension_audit | fit_external | 6.48941e-05 | 0.0024786 | 1.83264 | 0.0234375 | 0.0491884 |
| sqrt_static_pca_15_external_envelope | extended_dimension_audit | fit_external | 6.01013e-05 | 0.00225273 | 1.88858 | 0.0572917 | 0.0492324 |
| raw_static_pca_10_external_envelope | numerical_reconstruction_baseline | fit_external | 2.41399e-06 | 0.0004113 | 1.9489 | 0.0416667 | 0.00508731 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | temporal_audit_candidate | fit_external | 6.77231e-05 | 0.00266537 | 1.82944 | 0 | 0.0491767 |

## Candidate-level summary: holdout_external
| candidate_name | candidate_role | dataset | reconstruction_error_mean | residual_energy_ratio_mean | mahalanobis_distance_mean | out_of_envelope_rate | external_score_displacement_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | focus_candidate | holdout_external | 0.00114879 | 0.207115 | 2.95638 | 1 | 0.147143 |
| sqrt_static_pca_12_external_envelope | higher_dimension_audit | holdout_external | 0.00113069 | 0.203921 | 3.28204 | 1 | 0.147354 |
| sqrt_static_pca_15_external_envelope | extended_dimension_audit | holdout_external | 0.00101909 | 0.190452 | 8.56624 | 1 | 0.149099 |
| raw_static_pca_10_external_envelope | numerical_reconstruction_baseline | holdout_external | 3.74597e-05 | 0.0119194 | 11.4229 | 0.977778 | 0.014761 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | temporal_audit_candidate | holdout_external | 0.00112726 | 0.206769 | 2.9553 | 1 | 0.147135 |

## Candidate-level summary: no_external_reference
| candidate_name | candidate_role | dataset | reconstruction_error_mean | residual_energy_ratio_mean | mahalanobis_distance_mean | out_of_envelope_rate | external_score_displacement_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | focus_candidate | no_external_reference | 0.000399425 | 0.00583407 | 4.93483 | 0.115702 | 0.16502 |
| sqrt_static_pca_12_external_envelope | higher_dimension_audit | no_external_reference | 0.000291475 | 0.00349425 | 5.48978 | 0.107438 | 0.165143 |
| sqrt_static_pca_15_external_envelope | extended_dimension_audit | no_external_reference | 0.000182675 | 0.00124308 | 6.26058 | 0.0826446 | 0.165399 |
| raw_static_pca_10_external_envelope | numerical_reconstruction_baseline | no_external_reference | 1.93431e-06 | 4.67367e-05 | 4.75203 | 0.0743802 | 0.00632365 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | temporal_audit_candidate | no_external_reference | 0.000451356 | 0.00669087 | 4.93767 | 0.107438 | 0.097155 |

## Candidate comparison vs Task 3.1 no-external-only PCA baseline
| candidate_name | dataset | delta_out_of_envelope_rate_vs_task3_1 | delta_residual_gain_vs_task3_1 | delta_score_displacement_vs_task3_1 | review_status |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | -1 | 0.0104179 | 0.260301 | requires_human_review |
| sqrt_static_pca_10_external_envelope | holdout_external | 0 | -0.218378 | 0.308126 | requires_human_review |
| sqrt_static_pca_10_external_envelope | no_external_reference | -0.884298 | 0.000478058 | 0.140693 | requires_human_review |
| sqrt_static_pca_12_external_envelope | fit_external | -0.976562 | 0.00468012 | 0.261183 | requires_human_review |
| sqrt_static_pca_12_external_envelope | holdout_external | 0 | -0.217713 | 0.30801 | requires_human_review |
| sqrt_static_pca_12_external_envelope | no_external_reference | -0.892562 | 6.31523e-05 | 0.140833 | requires_human_review |
| sqrt_static_pca_15_external_envelope | fit_external | -0.942708 | -0.000778821 | 0.262071 | requires_human_review |
| sqrt_static_pca_15_external_envelope | holdout_external | 0 | -0.223527 | 0.308864 | requires_human_review |
| sqrt_static_pca_15_external_envelope | no_external_reference | -0.917355 | -0.000130112 | 0.141133 | requires_human_review |
| raw_static_pca_10_external_envelope | fit_external | -0.958333 | 4.81581e-05 | 0.0299071 | requires_human_review |
| raw_static_pca_10_external_envelope | holdout_external | -0.0222222 | 0.000565731 | 0.0361139 | requires_human_review |
| raw_static_pca_10_external_envelope | no_external_reference | -0.917355 | -3.32747e-05 | 0.0139722 | requires_human_review |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | fit_external | -1 | 0.0105781 | 0.260818 | requires_human_review |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | holdout_external | 0 | -0.214987 | 0.308141 | requires_human_review |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | no_external_reference | -0.892562 | 0.000259724 | 0.073959 | requires_human_review |

## sqrt_static_pca_10_external_envelope vs sqrt_static_pca_12_external_envelope
| candidate_name | candidate_role | out_of_envelope_rate | external_residual_gain_mean | external_score_displacement_mean | review_status |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | focus_candidate | 1 | -0.0549676 | 0.147143 | requires_human_review |
| sqrt_static_pca_12_external_envelope | higher_dimension_audit | 1 | -0.0571102 | 0.147354 | requires_human_review |

## sqrt_static_pca_10_external_envelope vs sqrt_static_pca_15_external_envelope
| candidate_name | candidate_role | out_of_envelope_rate | external_residual_gain_mean | external_score_displacement_mean | review_status |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | focus_candidate | 1 | -0.0549676 | 0.147143 | requires_human_review |
| sqrt_static_pca_15_external_envelope | extended_dimension_audit | 1 | -0.0700142 | 0.149099 | requires_human_review |

## sqrt_static_pca_10_external_envelope vs raw_static_pca_10_external_envelope
| candidate_name | candidate_role | out_of_envelope_rate | external_residual_gain_mean | external_score_displacement_mean | review_status |
| --- | --- | --- | --- | --- | --- |
| raw_static_pca_10_external_envelope | numerical_reconstruction_baseline | 0.977778 | 0.008107 | 0.014761 | requires_human_review |
| sqrt_static_pca_10_external_envelope | focus_candidate | 1 | -0.0549676 | 0.147143 | requires_human_review |

## Factor response summary
| candidate_name | dataset | external_factor_name | external_score_displacement_mean | external_residual_gain_mean | out_of_envelope_rate |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | 0.0499608 | -0.000118436 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | 0.0503589 | 0.000621123 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | 0.0506729 | 0.00178751 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | 0.050872 | 0.00331348 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure+external_information_noise | 0.0501519 | 0.00338073 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | 0.0495563 | -0.000321413 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | 0.0493518 | -3.11279e-05 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | 0.0491814 | 0.000950362 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | 0.0490552 | 0.00249973 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | 0.048962 | 0.00451177 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | 0.0498402 | -0.000139662 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | 0.0496938 | -0.000284889 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | 0.0498402 | -0.000139662 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | 0.0492496 | -0.000343185 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | 0.0489566 | -0.000342608 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | 0.0495563 | -0.000321413 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | 0.0493828 | -6.50089e-05 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | 0.0492109 | 0.000881115 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | 0.049041 | 0.00243112 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | 0.048874 | 0.00449932 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_resource_supply | 0.0491148 | 0.00129296 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_resource_supply | 0.0493402 | -2.43815e-05 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_resource_supply | 0.0491148 | 0.00129296 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_resource_supply | 0.0493115 | -0.000337372 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_resource_supply | 0.0490754 | -0.000276998 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_resource_supply+external_demand | 0.0493817 | -0.000135847 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock | 0.0495563 | -0.000321413 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock | 0.0486217 | -0.000386951 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock | 0.0478304 | -0.000249267 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock | 0.0471457 | 0.000339979 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock | 0.0465384 | 0.00167998 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_shock+external_constraint_pressure | 0.0469449 | 0.00326248 | 0 |
| sqrt_static_pca_10_external_envelope | holdout_external | external_competition_pressure | 0.0493475 | -0.00364877 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_external | external_constraint_pressure | 0.260726 | -0.117408 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_external | external_information_noise | 0.0479951 | -0.000881621 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_external | external_information_noise+external_constraint_pressure | 0.0476691 | 0.000352877 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_external | external_resource_supply | 0.0479551 | -0.000875005 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_external | external_shock | 0.0484012 | -0.00318921 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_external | external_shock+external_constraint_pressure | 0.0451761 | 0.00624725 | 1 |
| sqrt_static_pca_12_external_envelope | fit_external | external_competition_pressure | 0.0499714 | -0.00014499 | 0 |

## Holdout external scenario summary
| candidate_name | scenario_id | external_factor_name | external_score_displacement_mean | external_residual_gain_mean | out_of_envelope_rate |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | holdout_unseen_intensity_competition | external_competition_pressure | 0.0493475 | -0.00364877 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_long_sustained_constraint | external_constraint_pressure | 0.260726 | -0.117408 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_unseen_intensity_noise | external_information_noise | 0.0479951 | -0.000881621 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_compound_unseen | external_information_noise+external_constraint_pressure | 0.0476691 | 0.000352877 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_delayed_reversal_resource | external_resource_supply | 0.0479551 | -0.000875005 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_late_pulse_shock | external_shock | 0.0484012 | -0.00318921 | 1 |
| sqrt_static_pca_10_external_envelope | holdout_stronger_shock | external_shock+external_constraint_pressure | 0.0451761 | 0.00624725 | 1 |
| sqrt_static_pca_12_external_envelope | holdout_unseen_intensity_competition | external_competition_pressure | 0.0493492 | -0.00457011 | 1 |
| sqrt_static_pca_12_external_envelope | holdout_long_sustained_constraint | external_constraint_pressure | 0.261176 | -0.121386 | 1 |
| sqrt_static_pca_12_external_envelope | holdout_unseen_intensity_noise | external_information_noise | 0.0479957 | -0.00135607 | 1 |
| sqrt_static_pca_12_external_envelope | holdout_compound_unseen | external_information_noise+external_constraint_pressure | 0.0476702 | -0.000175031 | 1 |
| sqrt_static_pca_12_external_envelope | holdout_delayed_reversal_resource | external_resource_supply | 0.0479569 | -0.001101 | 1 |
| sqrt_static_pca_12_external_envelope | holdout_late_pulse_shock | external_shock | 0.0484017 | -0.00366082 | 1 |
| sqrt_static_pca_12_external_envelope | holdout_stronger_shock | external_shock+external_constraint_pressure | 0.0451776 | 0.0056489 | 1 |
| sqrt_static_pca_15_external_envelope | holdout_unseen_intensity_competition | external_competition_pressure | 0.0493808 | -0.00566567 | 1 |
| sqrt_static_pca_15_external_envelope | holdout_long_sustained_constraint | external_constraint_pressure | 0.264886 | -0.148022 | 1 |
| sqrt_static_pca_15_external_envelope | holdout_unseen_intensity_noise | external_information_noise | 0.048015 | -0.00207543 | 1 |
| sqrt_static_pca_15_external_envelope | holdout_compound_unseen | external_information_noise+external_constraint_pressure | 0.0476926 | -0.00096668 | 1 |
| sqrt_static_pca_15_external_envelope | holdout_delayed_reversal_resource | external_resource_supply | 0.0479956 | -0.00240648 | 1 |
| sqrt_static_pca_15_external_envelope | holdout_late_pulse_shock | external_shock | 0.0484206 | -0.00427267 | 1 |
| sqrt_static_pca_15_external_envelope | holdout_stronger_shock | external_shock+external_constraint_pressure | 0.0452045 | 0.00484038 | 1 |
| raw_static_pca_10_external_envelope | holdout_unseen_intensity_competition | external_competition_pressure | 0.00520244 | -0.000484448 | 1 |
| raw_static_pca_10_external_envelope | holdout_long_sustained_constraint | external_constraint_pressure | 0.0258579 | 0.0177239 | 1 |
| raw_static_pca_10_external_envelope | holdout_unseen_intensity_noise | external_information_noise | 0.00509279 | -0.000243278 | 1 |
| raw_static_pca_10_external_envelope | holdout_compound_unseen | external_information_noise+external_constraint_pressure | 0.0050195 | 0.000150828 | 1 |
| raw_static_pca_10_external_envelope | holdout_delayed_reversal_resource | external_resource_supply | 0.00512212 | -0.000466333 | 1 |
| raw_static_pca_10_external_envelope | holdout_late_pulse_shock | external_shock | 0.00514537 | -0.000838293 | 0.75 |
| raw_static_pca_10_external_envelope | holdout_stronger_shock | external_shock+external_constraint_pressure | 0.00472467 | 3.48205e-05 | 1 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | holdout_unseen_intensity_competition | external_competition_pressure | 0.0493485 | -0.00373901 | 1 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | holdout_long_sustained_constraint | external_constraint_pressure | 0.260708 | -0.116943 | 1 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | holdout_unseen_intensity_noise | external_information_noise | 0.0479961 | -0.000990846 | 1 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | holdout_compound_unseen | external_information_noise+external_constraint_pressure | 0.0476702 | 0.000234179 | 1 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | holdout_delayed_reversal_resource | external_resource_supply | 0.047956 | -0.000989009 | 1 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | holdout_late_pulse_shock | external_shock | 0.0484021 | -0.00329079 | 1 |
| sqrt_sparse_temporal_lag_pca_10_external_envelope | holdout_stronger_shock | external_shock+external_constraint_pressure | 0.0451772 | 0.00609429 | 1 |

Human review is required before any PCA-G_t candidate decision.
