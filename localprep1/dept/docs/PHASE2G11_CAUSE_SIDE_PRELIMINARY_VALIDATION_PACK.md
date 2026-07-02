# Phase 2G-11 Cause-side Preliminary Validation Pack

## 1. Scope

Phase 2G-11 is a **preliminary validation** pack for the two cause-side v2.1 axes that were minimally implemented in Phase 2G-10:

- `information_asymmetry`
- `action_cost`

This is **not** final validation, **not** full v2.1 validation, **not** ActionModule tuning, **not** additional axis implementation, **not** a superiority claim, and **not** a safety proof. The matrix reads only bounded preliminary tendencies from existing runner traces and summary metrics.

## 2. Background

- Phase 2G-5 showed that repaired relaxed remained comparable, action mass was preserved, boundary/write violations were zero, and state metrics were mixed.
- Phase 2G-6 extended v2 validation and metric adequacy checks. Action mass remained available over multi-seed / longer-horizon settings and boundary/write violations remained zero, but longer horizons also showed mixed or worsening state metrics.
- Phase 2G-7 fixed the design direction: validate cause-side parameters rather than relying on result-named profiles.
- Phase 2G-8 repaired metric export/readability for cause-side validation and kept proxy/missing evidence distinctions visible.
- Phase 2G-9 fixed the matrix skeleton, including primary axes, baseline comparisons, metric assignment, blocking conditions, and Phase 2G-10 transition criteria.
- Phase 2G-10 minimally implemented only `information_asymmetry` and `action_cost` under the `cause_side_v2_1` namespace and confirmed existing-v2 compatibility in a readiness/smoke probe.
- Phase 2G-11 reads those same two axes with more baselines, multiple seeds on high settings, and 6-step cause-side runs rather than the 2-step Phase 2G-10 smoke probe.

## 3. Frozen Surfaces

The Phase 2G-11 pack keeps the following surfaces frozen:

- ActionModule unchanged.
- Action primitives unchanged.
- PressureTranslation unchanged.
- ParameterWindow registry unchanged.
- ParameterShadowBox unchanged.
- Hard safety unchanged.
- Block/defer behavior unchanged.
- Write path unchanged.
- Acceptance unchanged.
- Safety boundary unchanged.
- `flat` remains an upper-bound comparator only.
- Repaired relaxed is maintained as the continued investigation candidate.
- `relaxed_legacy_dampen_075` is maintained as a comparison/rollback baseline.
- Existing result-named v2 profiles are unchanged and are used only for compatibility smoke coverage.
- No new axes are implemented.

## 4. Validation Design

The executable matrix is `configs/matrices/matrix_phase2g11_cause_side_preliminary_validation.json`.

Design summary:

- Axes: `information_asymmetry`, `action_cost`.
- Axis values: low/high for each implemented axis.
- Cause-side profiles:
  - `cause_side_v2_1/pseudo_reality_v2_1_cause_side_minimal_information_asymmetry_low`
  - `cause_side_v2_1/pseudo_reality_v2_1_cause_side_minimal_information_asymmetry_high`
  - `cause_side_v2_1/pseudo_reality_v2_1_cause_side_minimal_action_cost_low`
  - `cause_side_v2_1/pseudo_reality_v2_1_cause_side_minimal_action_cost_high`
  - `cause_side_v2_1/pseudo_reality_v2_1_cause_side_minimal_combined_probe`
- Baselines: repaired relaxed, `relaxed_legacy_dampen_075`, current, near-zero-action, and flat.
- Near-zero-action is a very small action-strength approximation, not complete `no_action`.
- Cause-side steps: 6.
- Compatibility steps: 4.
- Runs: 36 total, including 32 cause-side preliminary runs and 4 compatibility runs.
- Seeds: 2 unique cause-side seeds, with high-axis settings run across seeds 42 and 43.

Compatibility runs cover:

- `pseudo_reality_v2_trust_collapse`
- `pseudo_reality_v2_shrinking_equilibrium`
- `pseudo_reality_v2_public_stability_hidden_decay`
- `pseudo_reality_default`

## 5. Metrics

Primary metrics include action mass and the exported v2 state metrics:

- `hidden_damage_mean/final/delta`
- `fatigue_mean/final/delta`
- `information_quality_mean/final/delta`
- `cooperation_intent_mean/final/delta`
- `defensiveness_mean/final/delta`
- `latent_pressure_mean/final/delta`
- `private_resource_mean/final`
- `action_mass_total`

Proxy metrics are explicitly marked as proxy-only:

- `observed_vs_hidden_gap_proxy`
- `action_cost_effect`
- `intervention_fatigue_proxy`

Safety/readability fields include:

- `boundary_violation_total`
- `dry_run_write_violation_count`
- `forbidden_write_count`
- `action_frame_rows`
- `action_result_rows`
- `v2_hidden_trace_rows`
- `v2_information_trace_rows`
- `v2_action_effect_trace_rows`
- `v2_1_profile_loaded`
- `existing_v2_compatibility_pass`

The CSV exports preserve exact/proxy/missing distinctions and do not convert proxy-only fields into exact claims.

## 6. Results

Latest local matrix output summary:

| field | value |
|---|---:|
| runs | 36 |
| overall_pass | true |
| v2_1_cause_side_preliminary_run_count | 32 |
| v2_1_cause_side_axis_count | 2 |
| v2_1_cause_side_baseline_count | 5 |
| v2_1_cause_side_seed_count | 2 |
| v2_1_cause_side_preliminary_validation_pass | true |
| existing_v2_compatibility_pass | true |
| boundary_violation_total | 0 |
| dry_run_write_violation_count | 0 |
| forbidden_write_count | 0 |

All requested Phase 2G-11 CSV exports were present in `matrix_summary.json`.

## 7. Axis-wise Reading

### information_asymmetry

For repaired relaxed, high-minus-low showed preliminary movement in exported deltas:

- `information_quality_delta`: high was about `-0.0243` below low.
- `cooperation_intent_delta`: high was about `-0.0487` below low.
- `hidden_damage_delta`: high was about `-0.0942` below low in this short matrix.
- `defensiveness_delta`: high was about `-0.0198` below low.

This is a preliminary tendency only. It suggests `information_asymmetry` is readable through information quality, cooperation, defensiveness, hidden damage, and the observed/hidden proxy, but this pack does not claim causal proof.

### action_cost

For repaired relaxed, high-minus-low showed preliminary movement in exported deltas:

- `fatigue_delta`: high was about `+0.0009` above low.
- `cooperation_intent_delta`: high was about `-0.0379` below low.
- `defensiveness_delta`: high was about `-0.0298` below low.
- `latent_pressure_delta`: high was about `-0.0404` below low.

This is proxy-supported preliminary reading only. It does not prove an ActionModule mismatch and does not start tuning.

### combined probe

The combined probe is included only as a bounded readability check against the same repaired/legacy/near-zero/flat comparators. It is not a pair sweep and not scenario composition.

## 8. Baseline Comparison

The baseline comparison CSV compares repaired relaxed against legacy, current, near-zero-action, and flat when available for each axis/profile/seed.

Preliminary action-mass reading:

- Repaired relaxed and `relaxed_legacy_dampen_075` were equal in the observed high-axis action-mass comparisons.
- Repaired relaxed produced higher action mass than current for the high-axis current rows.
- Repaired relaxed produced higher action mass than near-zero-action.
- Flat stayed slightly above repaired relaxed and remains an upper-bound comparator only.

No superiority claim is made from these comparisons.

## 9. Seed Stability

The seed stability summary reports per-axis, per-baseline variation proxies. High-axis settings have two seeds; low-axis and combined-probe rows are more limited and should be treated as single-seed or partial seed-stability evidence. The matrix is intentionally stronger than Phase 2G-10 smoke coverage but is not longer-horizon full validation.

## 10. Missing Evidence and Limits

Known limits are exported in `v2_1_cause_side_missing_evidence.csv`:

- `observed_vs_hidden_gap_proxy` is proxy-only.
- `action_cost_effect` is proxy-only.
- Secondary/additional axes are out of scope and not implemented in this pack.

Unavailable or proxy-only fields are not hidden and cannot support exact claims.

## 11. Interpretation

Allowed interpretation:

- preliminary tendency;
- proxy-only tendency;
- repaired relaxed is comparable or not comparable within this bounded matrix;
- repaired relaxed changes a specific proxy in this matrix;
- `action_cost` appears to affect fatigue/defensiveness/latent-pressure-related readings in this preliminary setting;
- `information_asymmetry` appears to affect information quality/cooperation/defensiveness/hidden-damage-related readings in this preliminary setting.

Prohibited interpretation:

- superiority proved;
- safety proved;
- deployment-ready;
- final v2.1 validation;
- cause-side validation completed;
- ActionModule mismatch proved;
- ActionModule tuning required as a final conclusion;
- real-world evidence.

## 12. Recommended Next Task

Recommended next task from `matrix_summary.json`:

`Phase 2G-12 Additional Metric Export Repair before any ActionModule v2 tuning decision, with additional v2.1 axis implementation as a parallel option.`

Candidate next tasks remain:

- Phase 2G-12 ActionModule v2 Tuning Decision Pack.
- Phase 2G-12 Additional v2.1 Axis Implementation Probe.
- Phase 2G-12 Additional Metric Export Repair.
- Phase 2G-12 Cause-side Extended Validation Pack.
- Phase 2G-12 Freeze Decision Pack.

Given the proxy-only limits, metric export repair is the preferred next step before relying on exact observed-hidden/action-cost claims.

## 13. Conclusion

Phase 2G-11 adds a bounded cause-side preliminary validation pack for the two Phase 2G-10 axes only. The matrix thickens baseline comparison, uses multiple seeds for high-axis settings, extends cause-side runs to 6 steps, keeps existing v2 compatibility passing, and preserves zero boundary/write violations. The result remains preliminary and does not alter ActionModule behavior, action primitives, PressureTranslation, ParameterWindow registry, ShadowBox updates, hard safety, block/defer behavior, acceptance, safety boundaries, or write paths.
