# Task 3.1b External-Envelope Fixed PCA Audit

This report does not select the final PCA-G_t candidate. Final adoption decision is reserved for human review.

Lower out-of-envelope rate alone is not sufficient. G_t displacement and factor-response separation must also be preserved.

## Candidate-level summary
| candidate_name | candidate_role | dataset | reconstruction_error_mean | residual_energy_ratio_mean | mahalanobis_distance_mean | out_of_envelope_rate | external_score_displacement_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | focus_candidate | fit_external | 0.000243304 | 0.0974922 | 1.76805 | 0 | 0.0919686 |
| sqrt_static_pca_10_external_envelope | focus_candidate | holdout_external | 0.000359904 | 0.131051 | 1.72233 | 0 | 0.102729 |
| sqrt_static_pca_10_external_envelope | focus_candidate | no_external_reference | 0.00143756 | 0.170657 | 5.53009 | 0.121212 | 0 |
| sqrt_static_pca_12_external_envelope | higher_dimension_audit | fit_external | 0.000242696 | 0.0972662 | 1.76966 | 0 | 0.0919747 |
| sqrt_static_pca_12_external_envelope | higher_dimension_audit | holdout_external | 0.000359002 | 0.130778 | 1.72541 | 0 | 0.102745 |
| sqrt_static_pca_12_external_envelope | higher_dimension_audit | no_external_reference | 0.000971304 | 0.148582 | 6.15144 | 0.121212 | 0 |
| sqrt_static_pca_15_external_envelope | extended_dimension_audit | fit_external | 0.000129804 | 0.0773732 | 1.98972 | 0 | 0.0926506 |
| sqrt_static_pca_15_external_envelope | extended_dimension_audit | holdout_external | 0.000200402 | 0.1033 | 2.16408 | 0 | 0.104654 |
| sqrt_static_pca_15_external_envelope | extended_dimension_audit | no_external_reference | 0.000183528 | 0.00507476 | 8.9218 | 0.363636 | 0 |
| raw_static_pca_10_external_envelope | numerical_reconstruction_baseline | fit_external | 7.83325e-06 | 0.0773708 | 1.88507 | 0 | 0.00374604 |
| raw_static_pca_10_external_envelope | numerical_reconstruction_baseline | holdout_external | 9.48967e-06 | 0.0906475 | 1.97917 | 0 | 0.00458322 |
| raw_static_pca_10_external_envelope | numerical_reconstruction_baseline | no_external_reference | 5.89368e-05 | 0.15929 | 5.48473 | 0.121212 | 0 |

## Candidate comparison vs Task 3.1 no-external-only PCA baseline
| candidate_name | dataset | delta_out_of_envelope_rate_vs_task3_1 | delta_residual_gain_vs_task3_1 | delta_score_displacement_vs_task3_1 | review_status |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | -1 | 0.163232 | 0.127904 | requires_human_review |
| sqrt_static_pca_10_external_envelope | holdout_external | -1 | 0.0745344 | 0.153781 | requires_human_review |
| sqrt_static_pca_10_external_envelope | no_external_reference | -0.878788 | -0.0568843 | 0.0135926 | requires_human_review |
| sqrt_static_pca_12_external_envelope | fit_external | -1 | 0.0884331 | 0.13337 | requires_human_review |
| sqrt_static_pca_12_external_envelope | holdout_external | -1 | 0.0208343 | 0.158597 | requires_human_review |
| sqrt_static_pca_12_external_envelope | no_external_reference | -0.878788 | -0.143215 | 0.0145413 | requires_human_review |
| sqrt_static_pca_15_external_envelope | fit_external | -0.8125 | 0.148926 | 0.133912 | requires_human_review |
| sqrt_static_pca_15_external_envelope | holdout_external | -0.818182 | 0.0806498 | 0.159979 | requires_human_review |
| sqrt_static_pca_15_external_envelope | no_external_reference | 0.363636 | -0.00507476 | 0.0003908 | requires_human_review |
| raw_static_pca_10_external_envelope | fit_external | -1 | 0.228989 | 0.0049675 | requires_human_review |
| raw_static_pca_10_external_envelope | holdout_external | -1 | 0.122959 | 0.00642559 | requires_human_review |
| raw_static_pca_10_external_envelope | no_external_reference | -0.878788 | -0.0376377 | 0.000536568 | requires_human_review |

## sqrt_static_pca_10_external_envelope vs sqrt_static_pca_12_external_envelope
| candidate_name | candidate_role | out_of_envelope_rate | external_residual_gain_mean | external_score_displacement_mean | review_status |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | focus_candidate | 0 | 0.0567164 | 0.102729 | requires_human_review |
| sqrt_static_pca_12_external_envelope | higher_dimension_audit | 0 | 0.0569814 | 0.102745 | requires_human_review |

## sqrt_static_pca_10_external_envelope vs sqrt_static_pca_15_external_envelope
| candidate_name | candidate_role | out_of_envelope_rate | external_residual_gain_mean | external_score_displacement_mean | review_status |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | focus_candidate | 0 | 0.0567164 | 0.102729 | requires_human_review |
| sqrt_static_pca_15_external_envelope | extended_dimension_audit | 0 | 0.0971279 | 0.104654 | requires_human_review |

## sqrt_static_pca_10_external_envelope vs raw_static_pca_10_external_envelope
| candidate_name | candidate_role | out_of_envelope_rate | external_residual_gain_mean | external_score_displacement_mean | review_status |
| --- | --- | --- | --- | --- | --- |
| raw_static_pca_10_external_envelope | numerical_reconstruction_baseline | 0 | 0.0515857 | 0.00458322 | requires_human_review |
| sqrt_static_pca_10_external_envelope | focus_candidate | 0 | 0.0567164 | 0.102729 | requires_human_review |

## Factor response summary
| candidate_name | dataset | external_factor_name | external_score_displacement_mean | external_residual_gain_mean | out_of_envelope_rate |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | 0.0310967 | -0.0481565 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | 0.0561678 | -0.0624432 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | 0.0769128 | -0.0635919 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure | 0.0944267 | -0.0628332 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_competition_pressure+external_information_noise | 0.0739338 | 0.016913 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | 0.0151888 | -0.00316461 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | 0.0360302 | -0.0658979 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | 0.0778051 | -0.063301 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | 0.12625 | -0.0527046 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_constraint_pressure | 0.182265 | -0.0379753 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | 0.119868 | -0.0612783 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | 0.0603719 | -0.0563737 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | 0.119899 | -0.0620679 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | 0.0603565 | -0.0556208 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_demand | 0.119838 | -0.0604887 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | 0.00272516 | 0.0592071 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | 0.00933891 | 0.155998 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | 0.0179254 | 0.526121 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | 0.0258812 | 0.693071 | 0 |
| sqrt_static_pca_10_external_envelope | fit_external | external_information_noise | 0.0332949 | 0.702958 | 0 |

## Holdout external scenario summary
| candidate_name | scenario_id | external_factor_name | external_score_displacement_mean | external_residual_gain_mean | out_of_envelope_rate |
| --- | --- | --- | --- | --- | --- |
| sqrt_static_pca_10_external_envelope | holdout_unseen_intensity_competition | external_competition_pressure | 0.0649136 | -0.0633897 | 0 |
| sqrt_static_pca_10_external_envelope | holdout_long_sustained_constraint | external_constraint_pressure | 0.130258 | -0.0543778 | 0 |
| sqrt_static_pca_10_external_envelope | holdout_unseen_intensity_noise | external_information_noise | 0.0211054 | 0.627226 | 0 |
| sqrt_static_pca_10_external_envelope | holdout_compound_unseen | external_information_noise+external_constraint_pressure | 0.081252 | 0.0817512 | 0 |
| sqrt_static_pca_10_external_envelope | holdout_delayed_reversal_resource | external_resource_supply | 0.119849 | -0.0603363 | 0 |
| sqrt_static_pca_10_external_envelope | holdout_late_pulse_shock | external_shock | 0.0211783 | -0.00531658 | 0 |
| sqrt_static_pca_10_external_envelope | holdout_stronger_shock | external_shock+external_constraint_pressure | 0.263609 | -0.0601759 | 0 |
| sqrt_static_pca_12_external_envelope | holdout_unseen_intensity_competition | external_competition_pressure | 0.0649182 | -0.0628973 | 0 |
| sqrt_static_pca_12_external_envelope | holdout_long_sustained_constraint | external_constraint_pressure | 0.130281 | -0.0539892 | 0 |
| sqrt_static_pca_12_external_envelope | holdout_unseen_intensity_noise | external_information_noise | 0.0211131 | 0.627109 | 0 |
| sqrt_static_pca_12_external_envelope | holdout_compound_unseen | external_information_noise+external_constraint_pressure | 0.0813049 | 0.0818715 | 0 |
| sqrt_static_pca_12_external_envelope | holdout_delayed_reversal_resource | external_resource_supply | 0.119852 | -0.0599065 | 0 |
| sqrt_static_pca_12_external_envelope | holdout_late_pulse_shock | external_shock | 0.021179 | -0.00527789 | 0 |
| sqrt_static_pca_12_external_envelope | holdout_stronger_shock | external_shock+external_constraint_pressure | 0.263623 | -0.0597508 | 0 |
| sqrt_static_pca_15_external_envelope | holdout_unseen_intensity_competition | external_competition_pressure | 0.0654181 | -0.00532328 | 0 |
| sqrt_static_pca_15_external_envelope | holdout_long_sustained_constraint | external_constraint_pressure | 0.133232 | -0.00573941 | 0 |
| sqrt_static_pca_15_external_envelope | holdout_unseen_intensity_noise | external_information_noise | 0.0216134 | 0.671276 | 0 |
| sqrt_static_pca_15_external_envelope | holdout_compound_unseen | external_information_noise+external_constraint_pressure | 0.0886341 | 0.0891663 | 0 |
| sqrt_static_pca_15_external_envelope | holdout_delayed_reversal_resource | external_resource_supply | 0.119899 | -0.00220434 | 0 |
| sqrt_static_pca_15_external_envelope | holdout_late_pulse_shock | external_shock | 0.0212328 | -0.000288716 | 0 |

Human review is required before any PCA-G_t candidate decision.
