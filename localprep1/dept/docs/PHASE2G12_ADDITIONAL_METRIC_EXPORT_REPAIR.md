# Phase 2G-12 Additional Metric Export Repair

## 1. Scope

Phase 2G-12 is an additional metric export repair pack. It improves how existing Phase 2G-10/2G-11 v2.1 traces are summarized for proxy-only or ambiguous metrics.

This pack is not ActionModule tuning, not additional axis implementation, not cause-side extended validation, not final validation, not a superiority claim, and not a safety proof.

## 2. Background

Phase 2G-10 added the `cause_side_v2_1` namespace and minimally implemented only two axes: `information_asymmetry` and `action_cost`. Existing v2 compatibility passed and boundary/write violations remained zero, but the probe was intentionally thin.

Phase 2G-11 ran preliminary validation for those two axes across repaired relaxed, legacy, current, near-zero-action, and flat comparator baselines. It kept existing v2 compatibility passing and boundary/write violations at zero, but left `observed_vs_hidden_gap_proxy`, `action_cost_effect`, and `intervention_fatigue_proxy` as proxy-only evidence.

Phase 2G-12 therefore repairs readability by adding stricter CSV summaries, explicit metric classifications, missing-evidence disclosure, and a tuning-decision metric-readiness summary.

## 3. Frozen Surfaces

The following surfaces remain frozen:

- ActionModule unchanged.
- action primitives unchanged.
- PressureTranslation unchanged.
- ParameterWindow registry unchanged.
- ShadowBox unchanged.
- hard safety unchanged.
- block/defer unchanged.
- write path unchanged.
- acceptance unchanged.
- safety boundary unchanged.
- existing v2 profiles unchanged.
- no new cause-side axes implemented.
- repaired relaxed maintained.
- `relaxed_legacy_dampen_075` maintained.
- flat remains comparator only.

## 4. Repair Targets

The repair targets are:

- `observed_vs_hidden_gap`
- `action_cost_effect`
- `intervention_fatigue`
- `action_effect_by_channel`
- `information_asymmetry_effect`
- `action_cost_state_response`

## 5. Metric Classification

Phase 2G-12 uses the following classifications:

- `exact_exported`: directly readable from existing traces, such as hidden damage, fatigue, information quality, cooperation intent, defensiveness, latent pressure, and private resource.
- `derived_from_exact`: computed only from exact exported fields, such as cumulative action mass.
- `proxy`: semantic approximation.
- `derived_proxy`: a derived value that includes proxy semantics, such as observed/hidden gap summaries or action-cost/channel associations.
- `not_available`: not currently readable from traces.
- `deferred_requires_semantic_design`: the metric requires future semantic design rather than export-only repair.

Proxy or derived-proxy metrics must not be treated as exact causal evidence.

## 6. Export Repair Implementation

`scripts/run_matrix_validation.py` now emits the following Phase 2G-12 CSVs:

1. `v2_1_additional_metric_export_repair_summary.csv`
2. `v2_1_observed_vs_hidden_gap_repair_summary.csv`
3. `v2_1_action_cost_effect_repair_summary.csv`
4. `v2_1_intervention_fatigue_repair_summary.csv`
5. `v2_1_action_effect_by_channel_repair_summary.csv`
6. `v2_1_information_asymmetry_effect_summary.csv`
7. `v2_1_action_cost_state_response_summary.csv`
8. `v2_1_metric_classification_summary.csv`
9. `v2_1_tuning_decision_metric_readiness_summary.csv`
10. `v2_1_additional_metric_export_missing_evidence.csv`
11. `v2_1_additional_metric_export_next_task_recommendation.csv`

No read-only export was added to `asymmetric_game_v2.py`; the repair uses existing exported traces and existing per-run summary rows only. Dynamics, state updates, action application, and action-effect formulas are unchanged.

## 7. Validation Matrix

`configs/matrices/matrix_phase2g12_additional_metric_export_repair.json` is a lightweight 24-run repair matrix. It covers high/low `information_asymmetry`, high/low `action_cost`, a combined probe, and existing-v2/default compatibility smoke checks. It uses seed 42 and 6-step cause-side runs.

The matrix is a metric export repair check only. It is not a performance comparison and does not support superiority claims.

## 8. Results

Expected evidence is produced by:

- `python -m json.tool configs/matrices/matrix_phase2g12_additional_metric_export_repair.json`
- `python -m compileall .`
- `python scripts/run_smoke_validation.py`
- `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2g12_additional_metric_export_repair.json --output-dir validation_runs/phase2g12_additional_metric_export_repair`
- `cat validation_runs/phase2g12_additional_metric_export_repair/matrix_summary.json`

The matrix summary records run count, CSV presence, metric repair pass, readiness classes, boundary violations, dry-run write violations, forbidden writes, and recommended next task.

## 9. Tuning Decision Readiness

Readiness is classified as one of:

- `tuning_metric_ready`
- `tuning_metric_proxy_only`
- `tuning_metric_blocked`
- `additional_metric_repair_needed`

Phase 2G-12 allows a future ActionModule v2 Tuning Decision Pack to be discussed only when channel effects, action-cost effect, and intervention-fatigue summaries are readable and boundary/write counts remain zero. It does not execute tuning.

## 10. Missing Evidence and Limits

Exact public/visible-state evidence is still not exported as a separate semantic metric. Therefore `observed_vs_hidden_gap` remains `derived_proxy`, not exact.

`action_cost_effect`, `intervention_fatigue`, and `action_effect_by_channel` are short-run associations from action mass, repeated action rows, and state deltas. They are not causal proof.

Hidden-state visibility and other non-implemented axes remain deferred and require future semantic design.

## 11. Interpretation

Metric readability is improved. Observed/hidden gap is now better classified, action-cost response is better summarized, repeated-intervention fatigue is easier to inspect, and channel-level action effect summaries are exported.

This does not prove ActionModule mismatch, superiority, safety, final v2.1 validity, or deployment readiness.

## 12. Recommended Next Task

Recommended next task: Phase 2G-13 ActionModule v2 Tuning Decision Pack, discussion-only unless later instructions explicitly permit tuning. If exact visible/public-state evidence is required first, choose Phase 2G-13 Additional Metric Repair instead.

Other possible Phase 2G-13 paths remain Additional v2.1 Axis Implementation Probe, Cause-side Extended Validation Pack, or Freeze Decision Pack.

## 13. Conclusion

Phase 2G-12 repairs additional metric export readability without changing world dynamics, ActionModule behavior, action primitives, pressure translation, registry values, ShadowBox updates, safety boundaries, acceptance, write paths, existing profiles, or cause-side axes. The result is a clearer metric-readiness basis for deciding whether the next task should discuss ActionModule v2 tuning or repair metrics further.
