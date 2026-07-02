# Phase 2G-8 v2 Metric Export Repair for Cause-side Validation

## 1. Scope

This pack is a **Metric Export Repair** for cause-side validation readiness. It is not a v2 world dynamics repair, not ActionModule tuning, and not a cause-side parameterized v2.1 implementation. The change is limited to validation export, trace aggregation, summary CSV generation, matrix summary fields, a lightweight readiness matrix, and documentation.

No superiority claim, safety proof, final v2 evidence claim, or real-world deployment claim is made.

## 2. Background

Phase 2G-5 established preliminary v2 comparability: repaired relaxed preserved action mass and boundary/write violations remained zero, while state metrics were mixed. Phase 2G-6 extended the validation and found action mass remained observable, but longer horizons showed hidden damage/fatigue/latent pressure increases and information/cooperation declines. Phase 2G-7 froze a cause-side parameterization design and identified metric export repair as the next prerequisite.

This pack repairs the ability to read required cause-side metrics from existing traces without adapting the validation result to success conditions.

## 3. Frozen Surfaces

The following surfaces are unchanged:

- v2 world dynamics unchanged.
- v2 state update unchanged.
- v2 action effect formula unchanged.
- v2 profile json dynamics unchanged.
- ActionModule unchanged.
- action primitives unchanged.
- PressureTranslation unchanged.
- ParameterWindow registry unchanged.
- ParameterShadowBox unchanged.
- hard safety unchanged.
- block/defer unchanged.
- write path unchanged.
- acceptance unchanged.
- flat remains an upper-bound comparator only.
- repaired relaxed is maintained.
- relaxed_legacy_dampen_075 is maintained as the legacy comparator.

## 4. Metric Inventory

Core exact metrics are exported from existing traces where columns exist: hidden_damage, fatigue, information_quality, cooperation_intent, defensiveness, private_resource, and latent_pressure. Secondary metrics are classified as proxy, row_count_only, not_available, or deferred_requires_semantic_design.

The availability CSVs explicitly distinguish exact_available, proxy_available, row_count_only, export_repaired, not_available, and deferred_requires_semantic_design. Proxy rows are not exact claims.

## 5. Export Repair Implemented

Implemented in `scripts/run_matrix_validation.py`:

- Per-run v2 trace column detection.
- `v2_metric_export_repair_summary.csv`.
- `v2_metric_availability_by_run.csv`.
- `v2_metric_classification_summary.csv`.
- `v2_private_resource_latent_pressure_summary.csv`.
- `v2_recovery_collapse_proxy_summary.csv`.
- `v2_hidden_decay_gap_summary.csv`.
- `v2_relation_lock_proxy_summary.csv`.
- `v2_action_effect_by_channel_summary.csv`.
- `v2_action_cost_intervention_fatigue_proxy_summary.csv`.
- `v2_cause_side_metric_readiness_summary.csv`.
- missing-evidence and next-task CSVs.
- matrix_summary presence/count/readiness fields.

No read-only trace exposure in the v2 world file was required because the existing v2 traces already expose hidden, resource, information, game, and action-effect traces.

## 6. Per-metric Details

### private_resource / latent_pressure

`private_resource` is read from `v2_resource_trace` using available private-resource aggregate columns. `latent_pressure` is read from `v2_hidden_trace`. The summary reports mean, final, delta, and worst values when value columns are available. Missing columns are reported instead of inferred.

### recovery_after_shock / collapse_delay

`recovery_after_shock_proxy` is available only when a run has shock metadata and sufficient post-shock hidden/cooperation rows. `collapse_delay_proxy` is a threshold-crossing proxy using `hidden_damage >= 0.70`. Both are proxy-only; exact claims are prohibited.

### hidden_decay_gap / public_stability_hidden_decay_gap

These are visible/public minus hidden deterioration proxies when visible information/game metrics and hidden metrics are present. If the public/visible metric is absent, the metric is not promoted to exact and is left missing or deferred.

### relation_lock_proxy

The relation-lock proxy uses `entity_trace.relation_lock` and relation_unlock action rows/mass where available. It is not an exact relation-lock-strength metric.

### action_effect_by_channel

The channel summary covers exploration_injection, coupling_relief, volatility_damping, uncertainty_probe, relation_unlock, and buffer_increase. It reports rows, action mass, action-result rows, effect rows, and state-delta proxies from existing action/effect traces.

### action_cost_effect / intervention_fatigue

These are correlation/proxy summaries based on action mass/count/repeated-intervention counts and fatigue, defensiveness, and latent-pressure deltas. They do not assert causality.

## 7. Cause-side Readiness

The readiness summary classifies cause-side parameters as:

- `ready_for_one_axis_probe`
- `ready_with_proxy_only`
- `blocked_by_missing_export`
- `deferred_requires_semantic_design`

Current expected interpretation is that core metrics can support cautious one-axis skeleton work, while recovery/collapse/channel-cost claims remain proxy-only or require further repair/design.

## 8. Validation Results

Validation commands for this pack are:

```bash
python -m json.tool configs/matrices/matrix_phase2g8_v2_metric_export_repair_cause_side_validation.json > /tmp/matrix_phase2g8_v2_metric_export_repair_cause_side_validation.validated.json
python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2g8_v2_metric_export_repair_cause_side_validation.json --output-dir validation_runs/phase2g8_v2_metric_export_repair_cause_side_validation
cat validation_runs/phase2g8_v2_metric_export_repair_cause_side_validation/matrix_summary.json
```

Expected boundary/write criteria are boundary_violation_total = 0, dry_run_write_violation_count = 0, and forbidden_write_count = 0.

## 9. Missing Evidence

Missing evidence is intentionally exported in `v2_metric_export_missing_evidence.csv`. Exact secondary claims remain prohibited for shock recovery, collapse delay, hidden-decay gap variants, channel-level effects, action-cost effects, and intervention fatigue unless the relevant exact semantics and exports are added later.

## 10. Interpretation

Metric export readiness is improved for cause-side validation planning. This supports a cautious cause-side one-axis matrix skeleton or proxy-only implementation probe where readiness rows allow it. It does not prove superiority, safety, deployment readiness, final v2 evidence, ActionModule mismatch, or completed cause-side validation.

## 11. Recommended Next Task

Recommended next tasks:

1. Phase 2G-9 Cause-side Matrix Skeleton Pack.
2. Phase 2G-9 Cause-side Parameterized v2.1 Implementation Probe after metric readiness review.
3. Phase 2G-9 Additional Metric Export Repair for exact secondary metrics.
4. Phase 2G-9 ActionModule v2 Tuning Probe only after export and cause-side skeleton work.
5. Phase 2G-9 Freeze Decision Pack only after bounded cause-side evidence exists.

## 12. Conclusion

Phase 2G-8 repairs v2 metric export aggregation for cause-side validation readiness while keeping runtime dynamics, ActionModule behavior, safety boundaries, and write paths frozen. Exact/proxy/missing classifications are explicit, missing evidence is preserved, and next-task recommendations are recorded.
