# PseudoReality v2-RC1 Validation Pack

## 1. Purpose

This document records the closed-loop validation package created for observing PseudoReality v2-RC1 behavior across world profiles, action profiles, and seeds. The package is an observation and audit package only: it is not performance validation, it is not a v2 world superiority claim, and it does not change runner, module, world-engine, profile, or acceptance behavior.

## 2. Relationship to v2-RC1

PseudoReality v2-RC1 was already integrated on `main`. This validation pack uses the existing v2-RC1 world/profile/action plumbing to broaden execution, auditability, and profile-difference observation. The v2-added traces remain audit/diagnostic outputs and are not directly connected to `G_t`, `O_t`, or `K_t`.

## 3. Created Matrix

Created matrix: `configs/matrices/matrix_v2_rc1_validation_pack.json`.

The matrix name is `matrix_v2_rc1_validation_pack`. It uses:

- world profiles: `pseudo_reality_v2_shrinking_equilibrium`, `pseudo_reality_v2_trust_collapse`, `pseudo_reality_v2_public_stability_hidden_decay`
- action profiles: `action_default`, `action_conservative`, `action_buffered`
- seeds: `701`, `702`, `703`
- steps: `24`
- validation profile: `stress_medium`

## 4. Run Design

The design is `3 profiles × 3 action_profiles × 3 seeds = 27 runs`. Run labels follow `v2_rc1_<profile_short>_<action_short>_seed<seed>`, for example `v2_rc1_shrinking_default_seed701`, `v2_rc1_trust_collapse_conservative_seed702`, and `v2_rc1_public_hidden_buffered_seed703`.

Each run uses minimal overrides containing only `steps` and `seed`.

## 5. Validation Commands Run

```bash
cd localprep1/dept
python -m json.tool configs/matrices/matrix_v2_rc1_validation_pack.json
python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_v2_rc1_validation_pack.json --output-dir validation_runs/v2_rc1_validation_pack
```

Additional local audit scripts read generated CSV files to verify required CSV presence, NaN/inf absence, and numeric range constraints for the v2 diagnostic metric columns.

## 6. Matrix Result

| Check | Status | Evidence | Notes |
|---|---|---|---|
| json validation | PASS | `python -m json.tool configs/matrices/matrix_v2_rc1_validation_pack.json` completed. | Matrix JSON parsed successfully. |
| compileall | PASS | `python -m compileall .` completed. | Python files compiled successfully. |
| existing smoke | PASS | `python scripts/run_smoke_validation.py` returned `overall_pass: true`. | Existing smoke remains passing. |
| matrix_v2_rc1_validation_pack | PASS | Matrix summary returned `overall_pass: true`. | 27-run validation pack passed. |
| run count | PASS | Matrix summary returned `runs: 27`. | Expected 27 runs. |
| boundary_violation_total | PASS | Matrix summary returned `boundary_violation_total: 0`. | No boundary violations. |
| dry_run_write_violation_count | PASS | Matrix summary returned `dry_run_write_violation_count: 0`. | No dry-run write violations. |
| forbidden_write_count | PASS | Matrix summary returned `forbidden_write_count: 0`. | No forbidden writes. |
| action_frame_min | PASS | Matrix summary returned `action_frame_min: 3157`. | Minimum action-frame count was greater than zero. |
| v2 trace CSV presence | PASS | Required CSV presence audit found `missing 0`. | All required CSV files existed for all runs. |
| NaN / inf | PASS | v2 metric-column audit found `v2 nan/inf 0`. | Empty audit CSVs are not interpreted as v2 metric failures. |
| numeric range | PASS | v2 metric-column audit found `v2 bad range 0`. | Checked requested v2 diagnostic metrics in the 0.0-1.0 range. |

## 7. Profile-Level Results

### shrinking_equilibrium

Observed internal degradation and resource pressure expansion over 24 steps. `hidden_damage`, `latent_pressure`, `fatigue`, and `defensiveness` rose sharply; `cooperation_intent`, `information_quality`, and `long_term_health_proxy` declined; `resource_pressure` rose while `shared_resource` declined. This is compatible with the intended observation target of internal degradation, resource pressure, and long-term-health decline.

### trust_collapse

Observed information-quality decline, increased misread probability, cooperation decline, and defense-oriented behavior. `information_quality` fell to 0.0, `misread_probability_mean` rose, `cooperate_tendency` declined, and `defend_tendency` rose. This is compatible with the intended observation target of trust collapse behavior.

### public_stability_hidden_decay

Observed a visible separation between public-facing continuity and hidden/internal degradation signals. `hidden_damage`, `latent_pressure`, `fatigue`, and `defensiveness` rose strongly, while v2 traces still emitted stable auditable outputs without boundary/write violations. This is compatible with the intended observation target of surface stability versus internal decay separation.

## 8. Action-Profile Results

Across this 24-step pack, the three action profiles produced very similar directions for the core v2 world metrics. The action profiles differed only slightly in the small action-effect deltas; no action profile is claimed to be superior. The pack should be read as a closed-loop behavior observation matrix, not as an optimization or performance comparison.

Average directional deltas across profiles for selected metrics:

| action_profile | hidden_damage Δ | fatigue Δ | cooperation_intent Δ | long_term_health_proxy Δ | resource_pressure Δ | net_hidden_effect_score Δ |
|---|---:|---:|---:|---:|---:|---:|
| action_default | +0.7296 | +0.6154 | -0.4219 | -0.3656 | +0.2016 | +0.0003 |
| action_conservative | +0.7296 | +0.6154 | -0.4219 | -0.3663 | +0.2016 | +0.0002 |
| action_buffered | +0.7296 | +0.6154 | -0.4219 | -0.3659 | +0.2016 | +0.0002 |

## 9. Seed Stability Quick Check

For profile × action_profile groups, seed variance on final v2 metric values was effectively zero for the summarized metric columns in this deterministic 24-step setup. This indicates seed-stable observations for the tested seeds (`701`, `702`, `703`) within this pack, not general stochastic robustness.

## 10. v2 Trace Output Confirmation

Every run emitted the required CSV files:

- `entity_trace.csv`
- `relation_trace.csv`
- `v2_hidden_trace.csv`
- `v2_game_trace.csv`
- `v2_resource_trace.csv`
- `v2_information_trace.csv`
- `v2_action_effect_trace.csv`
- `action_frame.csv`
- `action_execution_audit.csv`
- `coactivation_gate.csv`
- `boundary_violation_report.csv`
- `canonical_write_audit.csv`

## 11. Boundary / Write Safety Confirmation

The pack preserved the expected no-write and boundary constraints:

- `boundary_violation_total: 0`
- `dry_run_write_violation_count: 0`
- `forbidden_write_count: 0`
- `action_frame_min: 3157`

No runner, module, world engine, v1 engine, v2 engine, profile, config profile, or acceptance-condition code was changed.

## 12. Interpretation

This validation pack expands audit coverage for v2-RC1 by running the existing closed loop over a broader profile/action/seed matrix. The main interpretation is that the v2 traces are executable, audit-visible, and directionally distinct enough to support profile-difference observation. It does not establish performance superiority, does not rank action profiles, and does not authorize wiring v2 traces into canonical DEPT state.

## 13. What May Be Said

- This is a PseudoReality v2-RC1 closed-loop behavior observation package.
- The created matrix ran 27 profile × action_profile × seed combinations.
- The run produced required v2 diagnostic CSV traces for every run.
- The matrix passed with no boundary/write safety violations.
- The pack broadens v2-RC1 executability, auditability, and profile-difference observation.

## 14. What Must Not Be Said

- Do not call this performance validation.
- Do not claim v2 world superiority.
- Do not claim action-profile superiority from this pack.
- Do not claim v2 trace columns are connected directly to `G_t`, `O_t`, or `K_t`.
- Do not treat this matrix as changing acceptance conditions or as a commit gate.

## 15. Metric Aggregation

The table below reports `first_mean`, `last_mean`, `delta = last_mean - first_mean`, direction, and final-value seed variance for each requested metric by profile × action_profile.

| profile | action_profile | metric | first_mean | last_mean | delta | direction | seed_variance |
|---|---|---|---:|---:|---:|---|---:|
| public_hidden | buffered | commons_health | 0.6914 | 0.2288 | -0.4626 | down | 0.0000 |
| public_hidden | buffered | cooperate_tendency | 0.4924 | 0.1722 | -0.3201 | down | 0.0002 |
| public_hidden | buffered | cooperation_intent | 0.4239 | 0.0000 | -0.4239 | down | 0.0000 |
| public_hidden | buffered | coordination_lag_mean | 0.4349 | 0.5790 | 0.1441 | up | 0.0000 |
| public_hidden | buffered | defend_tendency | 0.5117 | 0.9548 | 0.4431 | up | 0.0002 |
| public_hidden | buffered | defensiveness | 0.5091 | 1.0000 | 0.4909 | up | 0.0000 |
| public_hidden | buffered | direct_effect_score | 0.0013 | 0.0014 | 0.0002 | stable | 0.0000 |
| public_hidden | buffered | exploration_delta | 0.0000 | 0.0008 | 0.0008 | stable | 0.0000 |
| public_hidden | buffered | explore_tendency | 0.4856 | 0.0680 | -0.4176 | down | 0.0008 |
| public_hidden | buffered | extract_tendency | 0.3673 | 0.7688 | 0.4015 | up | 0.0051 |
| public_hidden | buffered | fatigue | 0.3904 | 1.0000 | 0.6096 | up | 0.0000 |
| public_hidden | buffered | fatigue_delta | 0.0000 | 0.0002 | 0.0002 | stable | 0.0000 |
| public_hidden | buffered | hidden_damage | 0.2792 | 1.0000 | 0.7208 | up | 0.0000 |
| public_hidden | buffered | hidden_damage_delta | 0.0000 | 0.0710 | 0.0710 | up | 0.0000 |
| public_hidden | buffered | information_delay_mean | 0.3677 | 0.4500 | 0.0823 | up | 0.0000 |
| public_hidden | buffered | information_distortion_mean | 0.2241 | 0.4300 | 0.2059 | up | 0.0000 |
| public_hidden | buffered | information_quality | 0.6087 | 0.0000 | -0.6087 | down | 0.0000 |
| public_hidden | buffered | information_quality_mean | 0.5883 | 0.0000 | -0.5883 | down | 0.0000 |
| public_hidden | buffered | latent_pressure | 0.4584 | 1.0000 | 0.5416 | up | 0.0000 |
| public_hidden | buffered | long_term_health_proxy | 0.5462 | 0.1751 | -0.3712 | down | 0.0003 |
| public_hidden | buffered | misread_probability_mean | 0.2720 | 0.3750 | 0.1030 | up | 0.0000 |
| public_hidden | buffered | net_hidden_effect_score | 0.0001 | 0.0003 | 0.0002 | stable | 0.0000 |
| public_hidden | buffered | net_public_effect_score | 0.0000 | 0.0011 | 0.0011 | stable | 0.0000 |
| public_hidden | buffered | resource_inequality | 0.2425 | 0.3147 | 0.0723 | up | 0.0009 |
| public_hidden | buffered | resource_inequality_delta | 0.0000 | 0.0068 | 0.0068 | stable | 0.0000 |
| public_hidden | buffered | resource_pressure | 0.2619 | 0.4541 | 0.1921 | up | 0.0000 |
| public_hidden | buffered | reversibility_delta | 0.0000 | 0.0004 | 0.0004 | stable | 0.0000 |
| public_hidden | buffered | shared_resource | 0.7381 | 0.5459 | -0.1921 | down | 0.0000 |
| public_hidden | buffered | short_term_payoff | 0.4600 | 0.6651 | 0.2050 | up | 0.0001 |
| public_hidden | buffered | side_effect_score | 0.0004 | 0.0005 | 0.0001 | stable | 0.0000 |
| public_hidden | buffered | trust_delta | 0.0002 | 0.0002 | 0.0000 | stable | 0.0000 |
| public_hidden | conservative | commons_health | 0.6914 | 0.2288 | -0.4626 | down | 0.0000 |
| public_hidden | conservative | cooperate_tendency | 0.4924 | 0.1722 | -0.3201 | down | 0.0002 |
| public_hidden | conservative | cooperation_intent | 0.4239 | 0.0000 | -0.4239 | down | 0.0000 |
| public_hidden | conservative | coordination_lag_mean | 0.4349 | 0.5790 | 0.1441 | up | 0.0000 |
| public_hidden | conservative | defend_tendency | 0.5117 | 0.9548 | 0.4431 | up | 0.0002 |
| public_hidden | conservative | defensiveness | 0.5091 | 1.0000 | 0.4909 | up | 0.0000 |
| public_hidden | conservative | direct_effect_score | 0.0010 | 0.0011 | 0.0001 | stable | 0.0000 |
| public_hidden | conservative | exploration_delta | 0.0000 | 0.0006 | 0.0006 | stable | 0.0000 |
| public_hidden | conservative | explore_tendency | 0.4855 | 0.0672 | -0.4184 | down | 0.0008 |
| public_hidden | conservative | extract_tendency | 0.3673 | 0.7690 | 0.4017 | up | 0.0051 |
| public_hidden | conservative | fatigue | 0.3904 | 1.0000 | 0.6096 | up | 0.0000 |
| public_hidden | conservative | fatigue_delta | 0.0000 | 0.0002 | 0.0002 | stable | 0.0000 |
| public_hidden | conservative | hidden_damage | 0.2792 | 1.0000 | 0.7208 | up | 0.0000 |
| public_hidden | conservative | hidden_damage_delta | 0.0000 | 0.0710 | 0.0710 | up | 0.0000 |
| public_hidden | conservative | information_delay_mean | 0.3677 | 0.4500 | 0.0823 | up | 0.0000 |
| public_hidden | conservative | information_distortion_mean | 0.2241 | 0.4300 | 0.2059 | up | 0.0000 |
| public_hidden | conservative | information_quality | 0.6087 | 0.0000 | -0.6087 | down | 0.0000 |
| public_hidden | conservative | information_quality_mean | 0.5883 | 0.0000 | -0.5883 | down | 0.0000 |
| public_hidden | conservative | latent_pressure | 0.4584 | 1.0000 | 0.5416 | up | 0.0000 |
| public_hidden | conservative | long_term_health_proxy | 0.5462 | 0.1746 | -0.3716 | down | 0.0003 |
| public_hidden | conservative | misread_probability_mean | 0.2720 | 0.3750 | 0.1030 | up | 0.0000 |
| public_hidden | conservative | net_hidden_effect_score | 0.0000 | 0.0002 | 0.0002 | stable | 0.0000 |
| public_hidden | conservative | net_public_effect_score | 0.0000 | 0.0009 | 0.0009 | stable | 0.0000 |
| public_hidden | conservative | resource_inequality | 0.2425 | 0.3147 | 0.0722 | up | 0.0009 |
| public_hidden | conservative | resource_inequality_delta | 0.0000 | 0.0069 | 0.0069 | stable | 0.0000 |
| public_hidden | conservative | resource_pressure | 0.2619 | 0.4541 | 0.1921 | up | 0.0000 |
| public_hidden | conservative | reversibility_delta | 0.0000 | 0.0003 | 0.0003 | stable | 0.0000 |
| public_hidden | conservative | shared_resource | 0.7381 | 0.5459 | -0.1921 | down | 0.0000 |
| public_hidden | conservative | short_term_payoff | 0.4600 | 0.6651 | 0.2050 | up | 0.0001 |
| public_hidden | conservative | side_effect_score | 0.0003 | 0.0004 | 0.0000 | stable | 0.0000 |
| public_hidden | conservative | trust_delta | 0.0001 | 0.0001 | 0.0000 | stable | 0.0000 |
| public_hidden | default | commons_health | 0.6914 | 0.2288 | -0.4626 | down | 0.0000 |
| public_hidden | default | cooperate_tendency | 0.4924 | 0.1722 | -0.3201 | down | 0.0002 |
| public_hidden | default | cooperation_intent | 0.4239 | 0.0000 | -0.4239 | down | 0.0000 |
| public_hidden | default | coordination_lag_mean | 0.4349 | 0.5790 | 0.1441 | up | 0.0000 |
| public_hidden | default | defend_tendency | 0.5117 | 0.9548 | 0.4431 | up | 0.0002 |
| public_hidden | default | defensiveness | 0.5091 | 1.0000 | 0.4909 | up | 0.0000 |
| public_hidden | default | direct_effect_score | 0.0015 | 0.0017 | 0.0002 | stable | 0.0000 |
| public_hidden | default | exploration_delta | 0.0000 | 0.0009 | 0.0009 | stable | 0.0000 |
| public_hidden | default | explore_tendency | 0.4857 | 0.0686 | -0.4171 | down | 0.0008 |
| public_hidden | default | extract_tendency | 0.3673 | 0.7688 | 0.4015 | up | 0.0051 |
| public_hidden | default | fatigue | 0.3904 | 1.0000 | 0.6096 | up | 0.0000 |
| public_hidden | default | fatigue_delta | 0.0000 | 0.0003 | 0.0003 | stable | 0.0000 |
| public_hidden | default | hidden_damage | 0.2792 | 1.0000 | 0.7208 | up | 0.0000 |
| public_hidden | default | hidden_damage_delta | 0.0000 | 0.0710 | 0.0710 | up | 0.0000 |
| public_hidden | default | information_delay_mean | 0.3677 | 0.4500 | 0.0823 | up | 0.0000 |
| public_hidden | default | information_distortion_mean | 0.2241 | 0.4300 | 0.2059 | up | 0.0000 |
| public_hidden | default | information_quality | 0.6087 | 0.0000 | -0.6087 | down | 0.0000 |
| public_hidden | default | information_quality_mean | 0.5883 | 0.0000 | -0.5883 | down | 0.0000 |
| public_hidden | default | latent_pressure | 0.4584 | 1.0000 | 0.5416 | up | 0.0000 |
| public_hidden | default | long_term_health_proxy | 0.5463 | 0.1754 | -0.3709 | down | 0.0003 |
| public_hidden | default | misread_probability_mean | 0.2720 | 0.3750 | 0.1030 | up | 0.0000 |
| public_hidden | default | net_hidden_effect_score | 0.0001 | 0.0003 | 0.0003 | stable | 0.0000 |
| public_hidden | default | net_public_effect_score | 0.0000 | 0.0013 | 0.0013 | stable | 0.0000 |
| public_hidden | default | resource_inequality | 0.2425 | 0.3148 | 0.0723 | up | 0.0009 |
| public_hidden | default | resource_inequality_delta | 0.0000 | 0.0068 | 0.0068 | stable | 0.0000 |
| public_hidden | default | resource_pressure | 0.2619 | 0.4541 | 0.1921 | up | 0.0000 |
| public_hidden | default | reversibility_delta | 0.0000 | 0.0004 | 0.0004 | stable | 0.0000 |
| public_hidden | default | shared_resource | 0.7381 | 0.5459 | -0.1921 | down | 0.0000 |
| public_hidden | default | short_term_payoff | 0.4600 | 0.6651 | 0.2050 | up | 0.0001 |
| public_hidden | default | side_effect_score | 0.0005 | 0.0006 | 0.0001 | stable | 0.0000 |
| public_hidden | default | trust_delta | 0.0002 | 0.0002 | 0.0000 | stable | 0.0000 |
| shrinking | buffered | commons_health | 0.6940 | 0.4441 | -0.2498 | down | 0.0000 |
| shrinking | buffered | cooperate_tendency | 0.4942 | 0.1716 | -0.3225 | down | 0.0002 |
| shrinking | buffered | cooperation_intent | 0.4252 | 0.0000 | -0.4252 | down | 0.0000 |
| shrinking | buffered | coordination_lag_mean | 0.3263 | 0.4725 | 0.1462 | up | 0.0000 |
| shrinking | buffered | defend_tendency | 0.5079 | 0.9530 | 0.4451 | up | 0.0002 |
| shrinking | buffered | defensiveness | 0.5038 | 1.0000 | 0.4962 | up | 0.0000 |
| shrinking | buffered | direct_effect_score | 0.0013 | 0.0014 | 0.0002 | stable | 0.0000 |
| shrinking | buffered | exploration_delta | 0.0000 | 0.0008 | 0.0008 | stable | 0.0000 |
| shrinking | buffered | explore_tendency | 0.4889 | 0.0899 | -0.3989 | down | 0.0009 |
| shrinking | buffered | extract_tendency | 0.3677 | 0.7877 | 0.4200 | up | 0.0049 |
| shrinking | buffered | fatigue | 0.3798 | 0.9998 | 0.6200 | up | 0.0000 |
| shrinking | buffered | fatigue_delta | 0.0000 | 0.0002 | 0.0002 | stable | 0.0000 |
| shrinking | buffered | hidden_damage | 0.2630 | 1.0000 | 0.7370 | up | 0.0000 |
| shrinking | buffered | hidden_damage_delta | 0.0000 | 0.0546 | 0.0546 | up | 0.0000 |
| shrinking | buffered | information_delay_mean | 0.2672 | 0.3495 | 0.0823 | up | 0.0000 |
| shrinking | buffered | information_distortion_mean | 0.1971 | 0.4100 | 0.2129 | up | 0.0000 |
| shrinking | buffered | information_quality | 0.6287 | 0.0000 | -0.6287 | down | 0.0000 |
| shrinking | buffered | information_quality_mean | 0.6083 | 0.0000 | -0.6083 | down | 0.0000 |
| shrinking | buffered | latent_pressure | 0.4549 | 1.0000 | 0.5451 | up | 0.0000 |
| shrinking | buffered | long_term_health_proxy | 0.5502 | 0.1884 | -0.3618 | down | 0.0004 |
| shrinking | buffered | misread_probability_mean | 0.1985 | 0.3050 | 0.1065 | up | 0.0000 |
| shrinking | buffered | net_hidden_effect_score | 0.0000 | 0.0003 | 0.0002 | stable | 0.0000 |
| shrinking | buffered | net_public_effect_score | 0.0000 | 0.0011 | 0.0011 | stable | 0.0000 |
| shrinking | buffered | resource_inequality | 0.2423 | 0.2868 | 0.0444 | up | 0.0010 |
| shrinking | buffered | resource_inequality_delta | 0.0000 | 0.0306 | 0.0306 | up | 0.0000 |
| shrinking | buffered | resource_pressure | 0.2803 | 0.4233 | 0.1431 | up | 0.0000 |
| shrinking | buffered | reversibility_delta | 0.0000 | 0.0004 | 0.0004 | stable | 0.0000 |
| shrinking | buffered | shared_resource | 0.7197 | 0.5767 | -0.1431 | down | 0.0000 |
| shrinking | buffered | short_term_payoff | 0.4589 | 0.6640 | 0.2051 | up | 0.0001 |
| shrinking | buffered | side_effect_score | 0.0003 | 0.0003 | 0.0000 | stable | 0.0000 |
| shrinking | buffered | trust_delta | 0.0002 | 0.0002 | 0.0000 | stable | 0.0000 |
| shrinking | conservative | commons_health | 0.6940 | 0.4441 | -0.2498 | down | 0.0000 |
| shrinking | conservative | cooperate_tendency | 0.4942 | 0.1716 | -0.3225 | down | 0.0002 |
| shrinking | conservative | cooperation_intent | 0.4252 | 0.0000 | -0.4252 | down | 0.0000 |
| shrinking | conservative | coordination_lag_mean | 0.3263 | 0.4725 | 0.1462 | up | 0.0000 |
| shrinking | conservative | defend_tendency | 0.5079 | 0.9530 | 0.4451 | up | 0.0002 |
| shrinking | conservative | defensiveness | 0.5038 | 1.0000 | 0.4962 | up | 0.0000 |
| shrinking | conservative | direct_effect_score | 0.0010 | 0.0011 | 0.0001 | stable | 0.0000 |
| shrinking | conservative | exploration_delta | 0.0000 | 0.0006 | 0.0006 | stable | 0.0000 |
| shrinking | conservative | explore_tendency | 0.4888 | 0.0891 | -0.3997 | down | 0.0009 |
| shrinking | conservative | extract_tendency | 0.3677 | 0.7878 | 0.4201 | up | 0.0049 |
| shrinking | conservative | fatigue | 0.3798 | 0.9997 | 0.6199 | up | 0.0000 |
| shrinking | conservative | fatigue_delta | 0.0000 | 0.0002 | 0.0002 | stable | 0.0000 |
| shrinking | conservative | hidden_damage | 0.2630 | 1.0000 | 0.7370 | up | 0.0000 |
| shrinking | conservative | hidden_damage_delta | 0.0000 | 0.0546 | 0.0546 | up | 0.0000 |
| shrinking | conservative | information_delay_mean | 0.2672 | 0.3495 | 0.0823 | up | 0.0000 |
| shrinking | conservative | information_distortion_mean | 0.1971 | 0.4100 | 0.2129 | up | 0.0000 |
| shrinking | conservative | information_quality | 0.6287 | 0.0000 | -0.6287 | down | 0.0000 |
| shrinking | conservative | information_quality_mean | 0.6083 | 0.0000 | -0.6083 | down | 0.0000 |
| shrinking | conservative | latent_pressure | 0.4549 | 1.0000 | 0.5451 | up | 0.0000 |
| shrinking | conservative | long_term_health_proxy | 0.5501 | 0.1879 | -0.3622 | down | 0.0004 |
| shrinking | conservative | misread_probability_mean | 0.1985 | 0.3050 | 0.1065 | up | 0.0000 |
| shrinking | conservative | net_hidden_effect_score | 0.0000 | 0.0002 | 0.0002 | stable | 0.0000 |
| shrinking | conservative | net_public_effect_score | 0.0000 | 0.0009 | 0.0009 | stable | 0.0000 |
| shrinking | conservative | resource_inequality | 0.2423 | 0.2867 | 0.0443 | up | 0.0010 |
| shrinking | conservative | resource_inequality_delta | 0.0000 | 0.0307 | 0.0307 | up | 0.0000 |
| shrinking | conservative | resource_pressure | 0.2803 | 0.4234 | 0.1431 | up | 0.0000 |
| shrinking | conservative | reversibility_delta | 0.0000 | 0.0003 | 0.0003 | stable | 0.0000 |
| shrinking | conservative | shared_resource | 0.7197 | 0.5766 | -0.1431 | down | 0.0000 |
| shrinking | conservative | short_term_payoff | 0.4589 | 0.6640 | 0.2051 | up | 0.0001 |
| shrinking | conservative | side_effect_score | 0.0002 | 0.0003 | 0.0000 | stable | 0.0000 |
| shrinking | conservative | trust_delta | 0.0001 | 0.0001 | 0.0000 | stable | 0.0000 |
| shrinking | default | commons_health | 0.6940 | 0.4441 | -0.2498 | down | 0.0000 |
| shrinking | default | cooperate_tendency | 0.4942 | 0.1716 | -0.3225 | down | 0.0002 |
| shrinking | default | cooperation_intent | 0.4252 | 0.0000 | -0.4252 | down | 0.0000 |
| shrinking | default | coordination_lag_mean | 0.3263 | 0.4725 | 0.1462 | up | 0.0000 |
| shrinking | default | defend_tendency | 0.5079 | 0.9530 | 0.4451 | up | 0.0002 |
| shrinking | default | defensiveness | 0.5038 | 1.0000 | 0.4962 | up | 0.0000 |
| shrinking | default | direct_effect_score | 0.0015 | 0.0017 | 0.0002 | stable | 0.0000 |
| shrinking | default | exploration_delta | 0.0000 | 0.0009 | 0.0009 | stable | 0.0000 |
| shrinking | default | explore_tendency | 0.4889 | 0.0905 | -0.3984 | down | 0.0009 |
| shrinking | default | extract_tendency | 0.3677 | 0.7877 | 0.4200 | up | 0.0049 |
| shrinking | default | fatigue | 0.3799 | 0.9999 | 0.6201 | up | 0.0000 |
| shrinking | default | fatigue_delta | 0.0000 | 0.0003 | 0.0003 | stable | 0.0000 |
| shrinking | default | hidden_damage | 0.2630 | 1.0000 | 0.7370 | up | 0.0000 |
| shrinking | default | hidden_damage_delta | 0.0000 | 0.0546 | 0.0546 | up | 0.0000 |
| shrinking | default | information_delay_mean | 0.2672 | 0.3495 | 0.0823 | up | 0.0000 |
| shrinking | default | information_distortion_mean | 0.1971 | 0.4100 | 0.2129 | up | 0.0000 |
| shrinking | default | information_quality | 0.6287 | 0.0000 | -0.6287 | down | 0.0000 |
| shrinking | default | information_quality_mean | 0.6083 | 0.0000 | -0.6083 | down | 0.0000 |
| shrinking | default | latent_pressure | 0.4549 | 1.0000 | 0.5451 | up | 0.0000 |
| shrinking | default | long_term_health_proxy | 0.5502 | 0.1887 | -0.3615 | down | 0.0004 |
| shrinking | default | misread_probability_mean | 0.1985 | 0.3050 | 0.1065 | up | 0.0000 |
| shrinking | default | net_hidden_effect_score | 0.0000 | 0.0003 | 0.0003 | stable | 0.0000 |
| shrinking | default | net_public_effect_score | 0.0000 | 0.0013 | 0.0013 | stable | 0.0000 |
| shrinking | default | resource_inequality | 0.2423 | 0.2868 | 0.0445 | up | 0.0010 |
| shrinking | default | resource_inequality_delta | 0.0000 | 0.0306 | 0.0306 | up | 0.0000 |
| shrinking | default | resource_pressure | 0.2803 | 0.4233 | 0.1431 | up | 0.0000 |
| shrinking | default | reversibility_delta | 0.0000 | 0.0004 | 0.0004 | stable | 0.0000 |
| shrinking | default | shared_resource | 0.7197 | 0.5767 | -0.1431 | down | 0.0000 |
| shrinking | default | short_term_payoff | 0.4589 | 0.6640 | 0.2051 | up | 0.0001 |
| shrinking | default | side_effect_score | 0.0003 | 0.0004 | 0.0000 | stable | 0.0000 |
| shrinking | default | trust_delta | 0.0002 | 0.0002 | 0.0000 | stable | 0.0000 |
| trust_collapse | buffered | commons_health | 0.6926 | 0.3549 | -0.3377 | down | 0.0000 |
| trust_collapse | buffered | cooperate_tendency | 0.4890 | 0.1719 | -0.3171 | down | 0.0002 |
| trust_collapse | buffered | cooperation_intent | 0.4165 | 0.0000 | -0.4165 | down | 0.0000 |
| trust_collapse | buffered | coordination_lag_mean | 0.5508 | 0.6909 | 0.1402 | up | 0.0000 |
| trust_collapse | buffered | defend_tendency | 0.5092 | 0.9537 | 0.4445 | up | 0.0002 |
| trust_collapse | buffered | defensiveness | 0.5055 | 1.0000 | 0.4945 | up | 0.0000 |
| trust_collapse | buffered | direct_effect_score | 0.0013 | 0.0014 | 0.0002 | stable | 0.0000 |
| trust_collapse | buffered | exploration_delta | 0.0000 | 0.0008 | 0.0008 | stable | 0.0000 |
| trust_collapse | buffered | explore_tendency | 0.4878 | 0.0816 | -0.4062 | down | 0.0009 |
| trust_collapse | buffered | extract_tendency | 0.3681 | 0.8019 | 0.4337 | up | 0.0036 |
| trust_collapse | buffered | fatigue | 0.3834 | 1.0000 | 0.6166 | up | 0.0000 |
| trust_collapse | buffered | fatigue_delta | 0.0000 | 0.0002 | 0.0002 | stable | 0.0000 |
| trust_collapse | buffered | hidden_damage | 0.2690 | 1.0000 | 0.7310 | up | 0.0000 |
| trust_collapse | buffered | hidden_damage_delta | 0.0000 | 0.0608 | 0.0608 | up | 0.0000 |
| trust_collapse | buffered | information_delay_mean | 0.4674 | 0.5499 | 0.0826 | up | 0.0000 |
| trust_collapse | buffered | information_distortion_mean | 0.2781 | 0.4700 | 0.1919 | up | 0.0000 |
| trust_collapse | buffered | information_quality | 0.5687 | 0.0000 | -0.5687 | down | 0.0000 |
| trust_collapse | buffered | information_quality_mean | 0.5483 | 0.0000 | -0.5483 | down | 0.0000 |
| trust_collapse | buffered | latent_pressure | 0.4560 | 1.0000 | 0.5440 | up | 0.0000 |
| trust_collapse | buffered | long_term_health_proxy | 0.5471 | 0.1823 | -0.3648 | down | 0.0003 |
| trust_collapse | buffered | misread_probability_mean | 0.3590 | 0.4550 | 0.0960 | up | 0.0000 |
| trust_collapse | buffered | net_hidden_effect_score | 0.0000 | 0.0003 | 0.0002 | stable | 0.0000 |
| trust_collapse | buffered | net_public_effect_score | 0.0000 | 0.0011 | 0.0011 | stable | 0.0000 |
| trust_collapse | buffered | resource_inequality | 0.2422 | 0.2588 | 0.0166 | up | 0.0011 |
| trust_collapse | buffered | resource_inequality_delta | 0.0000 | 0.0383 | 0.0383 | up | 0.0000 |
| trust_collapse | buffered | resource_pressure | 0.3256 | 0.5951 | 0.2696 | up | 0.0000 |
| trust_collapse | buffered | reversibility_delta | 0.0000 | 0.0004 | 0.0004 | stable | 0.0000 |
| trust_collapse | buffered | shared_resource | 0.6744 | 0.4049 | -0.2696 | down | 0.0000 |
| trust_collapse | buffered | short_term_payoff | 0.4592 | 0.6641 | 0.2049 | up | 0.0002 |
| trust_collapse | buffered | side_effect_score | 0.0003 | 0.0004 | 0.0000 | stable | 0.0000 |
| trust_collapse | buffered | trust_delta | 0.0002 | 0.0002 | 0.0000 | stable | 0.0000 |
| trust_collapse | conservative | commons_health | 0.6926 | 0.3549 | -0.3377 | down | 0.0000 |
| trust_collapse | conservative | cooperate_tendency | 0.4890 | 0.1719 | -0.3171 | down | 0.0002 |
| trust_collapse | conservative | cooperation_intent | 0.4165 | 0.0000 | -0.4165 | down | 0.0000 |
| trust_collapse | conservative | coordination_lag_mean | 0.5508 | 0.6909 | 0.1402 | up | 0.0000 |
| trust_collapse | conservative | defend_tendency | 0.5092 | 0.9537 | 0.4445 | up | 0.0002 |
| trust_collapse | conservative | defensiveness | 0.5055 | 1.0000 | 0.4945 | up | 0.0000 |
| trust_collapse | conservative | direct_effect_score | 0.0010 | 0.0011 | 0.0001 | stable | 0.0000 |
| trust_collapse | conservative | exploration_delta | 0.0000 | 0.0006 | 0.0006 | stable | 0.0000 |
| trust_collapse | conservative | explore_tendency | 0.4877 | 0.0807 | -0.4070 | down | 0.0009 |
| trust_collapse | conservative | extract_tendency | 0.3682 | 0.8020 | 0.4338 | up | 0.0036 |
| trust_collapse | conservative | fatigue | 0.3833 | 1.0000 | 0.6167 | up | 0.0000 |
| trust_collapse | conservative | fatigue_delta | 0.0000 | 0.0002 | 0.0002 | stable | 0.0000 |
| trust_collapse | conservative | hidden_damage | 0.2690 | 1.0000 | 0.7310 | up | 0.0000 |
| trust_collapse | conservative | hidden_damage_delta | 0.0000 | 0.0608 | 0.0608 | up | 0.0000 |
| trust_collapse | conservative | information_delay_mean | 0.4674 | 0.5499 | 0.0826 | up | 0.0000 |
| trust_collapse | conservative | information_distortion_mean | 0.2781 | 0.4700 | 0.1919 | up | 0.0000 |
| trust_collapse | conservative | information_quality | 0.5687 | 0.0000 | -0.5687 | down | 0.0000 |
| trust_collapse | conservative | information_quality_mean | 0.5483 | 0.0000 | -0.5483 | down | 0.0000 |
| trust_collapse | conservative | latent_pressure | 0.4560 | 1.0000 | 0.5440 | up | 0.0000 |
| trust_collapse | conservative | long_term_health_proxy | 0.5471 | 0.1818 | -0.3652 | down | 0.0003 |
| trust_collapse | conservative | misread_probability_mean | 0.3590 | 0.4550 | 0.0960 | up | 0.0000 |
| trust_collapse | conservative | net_hidden_effect_score | 0.0000 | 0.0002 | 0.0002 | stable | 0.0000 |
| trust_collapse | conservative | net_public_effect_score | 0.0000 | 0.0009 | 0.0009 | stable | 0.0000 |
| trust_collapse | conservative | resource_inequality | 0.2422 | 0.2585 | 0.0163 | up | 0.0011 |
| trust_collapse | conservative | resource_inequality_delta | 0.0000 | 0.0383 | 0.0383 | up | 0.0000 |
| trust_collapse | conservative | resource_pressure | 0.3256 | 0.5952 | 0.2696 | up | 0.0000 |
| trust_collapse | conservative | reversibility_delta | 0.0000 | 0.0003 | 0.0003 | stable | 0.0000 |
| trust_collapse | conservative | shared_resource | 0.6744 | 0.4048 | -0.2696 | down | 0.0000 |
| trust_collapse | conservative | short_term_payoff | 0.4592 | 0.6641 | 0.2049 | up | 0.0002 |
| trust_collapse | conservative | side_effect_score | 0.0003 | 0.0003 | 0.0000 | stable | 0.0000 |
| trust_collapse | conservative | trust_delta | 0.0001 | 0.0001 | 0.0000 | stable | 0.0000 |
| trust_collapse | default | commons_health | 0.6926 | 0.3549 | -0.3377 | down | 0.0000 |
| trust_collapse | default | cooperate_tendency | 0.4890 | 0.1719 | -0.3171 | down | 0.0002 |
| trust_collapse | default | cooperation_intent | 0.4165 | 0.0000 | -0.4165 | down | 0.0000 |
| trust_collapse | default | coordination_lag_mean | 0.5508 | 0.6909 | 0.1402 | up | 0.0000 |
| trust_collapse | default | defend_tendency | 0.5092 | 0.9537 | 0.4445 | up | 0.0002 |
| trust_collapse | default | defensiveness | 0.5055 | 1.0000 | 0.4945 | up | 0.0000 |
| trust_collapse | default | direct_effect_score | 0.0015 | 0.0017 | 0.0002 | stable | 0.0000 |
| trust_collapse | default | exploration_delta | 0.0000 | 0.0009 | 0.0009 | stable | 0.0000 |
| trust_collapse | default | explore_tendency | 0.4878 | 0.0821 | -0.4057 | down | 0.0009 |
| trust_collapse | default | extract_tendency | 0.3681 | 0.8018 | 0.4337 | up | 0.0036 |
| trust_collapse | default | fatigue | 0.3834 | 1.0000 | 0.6166 | up | 0.0000 |
| trust_collapse | default | fatigue_delta | 0.0000 | 0.0003 | 0.0003 | stable | 0.0000 |
| trust_collapse | default | hidden_damage | 0.2690 | 1.0000 | 0.7310 | up | 0.0000 |
| trust_collapse | default | hidden_damage_delta | 0.0000 | 0.0608 | 0.0608 | up | 0.0000 |
| trust_collapse | default | information_delay_mean | 0.4674 | 0.5499 | 0.0826 | up | 0.0000 |
| trust_collapse | default | information_distortion_mean | 0.2781 | 0.4700 | 0.1919 | up | 0.0000 |
| trust_collapse | default | information_quality | 0.5687 | 0.0000 | -0.5687 | down | 0.0000 |
| trust_collapse | default | information_quality_mean | 0.5483 | 0.0000 | -0.5483 | down | 0.0000 |
| trust_collapse | default | latent_pressure | 0.4560 | 1.0000 | 0.5440 | up | 0.0000 |
| trust_collapse | default | long_term_health_proxy | 0.5472 | 0.1826 | -0.3645 | down | 0.0003 |
| trust_collapse | default | misread_probability_mean | 0.3590 | 0.4550 | 0.0960 | up | 0.0000 |
| trust_collapse | default | net_hidden_effect_score | 0.0000 | 0.0003 | 0.0003 | stable | 0.0000 |
| trust_collapse | default | net_public_effect_score | 0.0000 | 0.0013 | 0.0013 | stable | 0.0000 |
| trust_collapse | default | resource_inequality | 0.2422 | 0.2589 | 0.0167 | up | 0.0011 |
| trust_collapse | default | resource_inequality_delta | 0.0000 | 0.0383 | 0.0383 | up | 0.0000 |
| trust_collapse | default | resource_pressure | 0.3256 | 0.5951 | 0.2696 | up | 0.0000 |
| trust_collapse | default | reversibility_delta | 0.0000 | 0.0004 | 0.0004 | stable | 0.0000 |
| trust_collapse | default | shared_resource | 0.6744 | 0.4049 | -0.2696 | down | 0.0000 |
| trust_collapse | default | short_term_payoff | 0.4592 | 0.6641 | 0.2049 | up | 0.0002 |
| trust_collapse | default | side_effect_score | 0.0004 | 0.0004 | 0.0001 | stable | 0.0000 |
| trust_collapse | default | trust_delta | 0.0002 | 0.0002 | 0.0000 | stable | 0.0000 |
## 16. Next Phase Candidates

1. `matrix_v2_rc1_long_run_pack`
2. v2 cost / debt dynamics design
3. v2 compressed external trend field design
4. v2 residual classification report
5. v2 action side-effect deeper audit
