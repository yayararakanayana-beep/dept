# Phase 2G-21C-B: Functional Policy × V2 Response Curve Alignment

## Purpose

Phase 2G-21C-B is a test-local alignment phase. It compares the Phase 2G-21B-B functional insurance policy output with the Phase 2G-21C-A measured v2 strength response curve and reports where the policy is aligned, over-firing, under-firing, over-suppressing, or selecting the wrong channel.

This phase does **not** tune coefficients, change formulas, change v2 dynamics, integrate with production runtime, or perform canonical writeback.

## Difference from 21C-A

21C-A measures v2 action-channel response curves by sweeping requested strength and summarizing observed best strength, safe strength range, harmful threshold, net benefit, and curve shape.

21C-B consumes those measured 21C-A long and summary tables. It does not redesign or recreate the response curve. It only aligns policy output against the measured rows.

## Relationship to 21B-B

21B-B defines the test-local `functional_insurance_policy(...)` output:

- `fire_permission_score`
- `action_mass_cap`
- `channel_weights`
- `non_action_decision`
- `cooldown_score`
- `suppression_reason`
- `evidence_trace`
- `input_boundary_flags`

21C-B imports and executes that policy test-locally. It does not modify 21B-B coefficients or expressions.

## Inputs

21C-B has two input streams:

1. **21B-B policy output** from `functional_insurance_policy(upper_pressure_bundle, lower_distribution_bundle, action_history_bundle)`.
2. **21C-A v2 measured response output** from `measure_v2_strength_response_curve()`, especially `v2_strength_response_curve_long` and `v2_strength_response_summary`.

Policy input bundles are derived from measured numeric v2 summary properties only. `scenario_label_for_audit_only` remains audit metadata and does not control policy input, alignment judgement, or misalignment reason.

## Outputs

21C-B emits two test-local tables:

1. `functional_policy_v2_alignment_long`: one row per case × action channel.
2. `functional_policy_v2_alignment_summary`: one row per case.

The schema is shaped for 21C-C coefficient drift diagnosis by preserving policy scores, observed v2 metrics, rank deltas, alignment scores, judgements, reasons, and evidence traces.

## Alignment Items

### `action_mass_cap` vs `observed_safe_strength_range`

21C-B computes `policy_cap_within_safe_range` from `observed_safe_strength_min`, `observed_safe_strength_max`, and `action_mass_cap`.

`cap_alignment_score` rewards caps inside the measured safe range, partially rewards conservative caps below the safe minimum, penalizes caps above the safe range but below harmful threshold, and assigns zero when the cap reaches or exceeds the measured harmful threshold.

### `action_mass_cap` vs `observed_harmful_threshold`

21C-B computes `policy_cap_above_harmful_threshold` directly from the measured `observed_harmful_threshold`. If the policy cap is at or above that measured threshold, the channel is treated as unsafe over-firing evidence.

### `channel_weights` vs observed net-benefit rank

21C-B ranks policy action channels by `channel_weights` and ranks observed channels by measured `observed_best_net_benefit`. It emits:

- `policy_channel_rank`
- `observed_channel_rank`
- `channel_rank_delta`
- `channel_alignment_score`

A matching top channel receives the strongest alignment score. A policy top channel within the observed top three receives partial credit. A channel with positive measured net benefit receives weak partial credit. Negative or harmful observed channels receive no channel-alignment credit.

### `fire_permission_score` vs safe action availability

`permission_alignment_score` compares policy fire permission with measured safe-channel availability and harmful-channel prevalence. High permission is aligned when safe channels exist and the measured response is not mostly harmful. Low permission is aligned when safe channels are absent. High permission with mostly harmful measured rows is over-permission. Low permission despite multiple safe channels is under-permission.

### `cooldown_score` / `non_action_decision` vs v2 harmful tendency

`cooldown_alignment_score` checks whether cooldown or non-action decisions are safety-preserving. Suppression is aligned when safe ranges are absent or harmful channels dominate. Suppression is penalized when weak safe beneficial actions exist. Low cooldown is aligned when safe ranges exist and penalized when harmful thresholds are low or harmful channels dominate.

## `alignment_judgement`

Channel-level judgements include:

- `aligned`
- `over_firing`
- `under_firing`
- `wrong_channel`
- `correct_suppression`
- `missed_opportunity`
- `over_permission`
- `under_permission`
- `inconclusive`
- `unresolved`

These judgements are derived from policy outputs and measured v2 response rows, not from scenario or case names.

## `misalignment_reason`

Misalignment reasons include:

- `policy_cap_too_high`
- `policy_cap_too_low`
- `policy_channel_weight_mismatch`
- `policy_permission_too_high`
- `policy_permission_too_low`
- `cooldown_too_strong`
- `cooldown_too_weak`
- `safe_range_absent`
- `harmful_threshold_low`
- `v2_curve_mostly_harmful`
- `v2_curve_mostly_no_effect`
- `missing_v2_response`
- `missing_policy_output`

Multiple reasons may be joined to support 21C-C diagnosis.

## Alignment Score

21C-B emits four component scores:

- `cap_alignment_score`
- `channel_alignment_score`
- `permission_alignment_score`
- `cooldown_alignment_score`

The summary table computes `overall_alignment_score` as the mean of component scores across case channels, then maps it to an `overall_alignment_judgement` such as `well_aligned`, `mostly_aligned`, `over_firing_bias`, `wrong_channel_bias`, `over_suppression_bias`, `mixed_alignment`, or `unresolved`.

## Runtime Boundary

21C-B is post-action audit and validation work only.

- v2 traces are marked `v2_trace_used_as_post_action_audit = True`.
- v2 traces are marked `v2_trace_used_as_action_runtime_input = False`.
- `production_runtime_changed = False`.
- No ActionPlanner, ActionModule, PressureTranslation, v2 dynamics, primitive library, ParameterBox, ShadowBox, or canonical state path is modified.

## Coefficient-Change Boundary

21C-B does not tune 21B-B coefficients, does not change 21B-B formulas, and does not add dynamic pressure-conditioned coefficient modulation. Coefficient drift diagnosis is deferred to 21C-C.

## Success Conditions

21C-B succeeds when it:

1. Executes the 21B-B functional policy.
2. Reads the 21C-A measured v2 response summary and long curve.
3. Compares policy cap to measured safe ranges and harmful thresholds.
4. Compares policy channel weights to observed net-benefit ranks.
5. Compares fire permission to measured safe-action availability.
6. Compares cooldown and non-action decisions to measured harmful tendency.
7. Emits long and summary alignment tables.
8. Emits alignment judgements, misalignment reasons, and component/overall scores.
9. Keeps scenario labels audit-only.
10. Leaves 21B-B coefficients and production runtime unchanged.

## Failure Conditions

The phase fails if it changes 21B-B coefficients or formulas, recreates fixed safe ranges or harmful thresholds, ignores the measured v2 response curve, derives judgements from scenario names, changes production runtime or v2 dynamics, updates ParameterBox/ShadowBox, or performs canonical writeback.

## 21C-C Handoff

21C-C can consume the alignment tables to diagnose coefficient drift directions:

- `policy_cap_too_high`: review danger suppression or cap coefficients.
- `policy_cap_too_low`: review permission, safe-terrain, or confidence coefficients.
- `policy_channel_weight_mismatch`: review channel sensitivity coefficients.
- `policy_permission_too_high`: review negative-fire, side-effect, or harmful-history coefficients.
- `policy_permission_too_low`: review fire-margin, no-op-worsening, or confidence coefficients.
- `cooldown_too_strong`: review cooldown pressure or history penalties.
- `cooldown_too_weak`: review side-effect and harmful-threshold sensitivity.

21C-B only quantifies where and in what direction alignment differs; it does not apply the coefficient changes.
