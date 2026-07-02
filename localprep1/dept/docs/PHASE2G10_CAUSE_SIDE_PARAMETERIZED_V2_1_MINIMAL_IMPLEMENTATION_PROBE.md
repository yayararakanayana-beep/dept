# Phase 2G-10 Cause-side Parameterized v2.1 Minimal Implementation Probe

## 1. Scope

This task is a minimal implementation probe for cause-side parameterized v2.1. It is not a full v2.1 implementation, not full cause-side validation, not ActionModule tuning, not a superiority claim, not a safety proof, and not a real-world deployment claim.

## 2. Background

Phase 2G-5 established comparable v2 preliminary validation with repaired relaxed action mass, zero boundary/write violations, and mixed state metrics. Phase 2G-6 extended the validation and found maintained action mass and zero boundary/write violations, while longer horizons showed hidden damage/fatigue growth and quality/cooperation declines. Phase 2G-7 froze cause-side parameterization design. Phase 2G-8 repaired metric exports/proxy evidence for cause-side validation. Phase 2G-9 added the non-executable matrix skeleton and fixed one-axis sweep, baseline, metric, and blocking-condition structure. Phase 2G-10 enters minimal implementation only because the skeleton needs a small executable v2.1 namespace before preliminary one-axis validation.

The implementation is deliberately limited to two axes rather than all six primary axes so that compatibility, loading, and smoke-readiness can be checked before broader dynamics are introduced.

## 3. Frozen Surfaces

The following surfaces remain frozen in this task:

- ActionModule unchanged.
- Action primitives unchanged.
- PressureTranslation unchanged.
- ParameterWindow registry unchanged.
- ParameterShadowBox update equations unchanged.
- CoactivationGate hard safety unchanged.
- Block/defer behavior unchanged.
- Write path unchanged.
- Acceptance unchanged.
- Flat remains an upper-bound comparator only.
- Repaired relaxed is maintained.
- `relaxed_legacy_dampen_075` is maintained as a comparator.
- Existing result-named v2 profiles remain unchanged.

## 4. Implemented Axes

### information_asymmetry

- Implementation location: `DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py` reads `profile_config.cause_side_parameters.information_asymmetry` only when the axis is listed in `implemented_axes`.
- Intended effect: light world-side pressure on information quality, hidden damage, cooperation intent, and defensiveness.
- Expected metrics: `information_quality_mean`, `hidden_damage_mean`, `cooperation_intent_mean`, `defensiveness_mean`, and `observed_vs_hidden_gap_proxy`.
- Compatibility rule: missing axis values and existing v2 result-named profiles use default-zero cause-side influence.
- Limitation: the observed/hidden gap is a proxy, not an exact proof of hidden-state observability.

### action_cost

- Implementation location: `DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py` reads `profile_config.cause_side_parameters.action_cost` only when the axis is listed in `implemented_axes`.
- Intended effect: minimal world-side cost proxy after an ActionFrame reaches the world, increasing fatigue/defensiveness/latent pressure on targeted entities without changing the ActionModule.
- Expected metrics: `fatigue_mean`, `defensiveness_mean`, `latent_pressure_mean`, `action_cost_effect`, and channel-level action-effect rows.
- Compatibility rule: missing axis values and existing v2 profiles use default-zero cause-side influence.
- Limitation: this is a cost proxy, not ActionModule tuning and not a change to action primitives.

## 5. Deferred Axes

The following axes are deferred because Phase 2G-10 is only a minimal probe: `hidden_state_visibility`, `short_term_gain_pressure`, `relation_lock_strength`, `recovery_delay`, `misread_probability`, `information_delay`, `information_distortion`, `resource_inequality`, `commons_dependency`, `private_information_rate`, `fatigue_accumulation_rate`, `intervention_fatigue`, `exploration_cost`, `repair_friction`, `trust_decay_rate`, `cooperation_decay_rate`, and `public_metric_bias`.

## 6. Profile Namespace and Schema

A new generated namespace was added under `configs/world_profiles/cause_side_v2_1/`. Existing result-named v2 profile JSON files were not edited.

Schema shape:

```json
{
  "world_engine": "asymmetric_game_v2",
  "profile_family": "pseudo_reality_v2_1_cause_side",
  "profile_role": "minimal_implementation_probe",
  "cause_side_parameters": {
    "information_asymmetry": 0.6,
    "action_cost": 0.1
  },
  "implemented_axes": ["information_asymmetry", "action_cost"],
  "deferred_axes": ["hidden_state_visibility", "short_term_gain_pressure", "relation_lock_strength", "recovery_delay"],
  "compatibility_note": "Existing v2 result-named profiles remain unchanged."
}
```

The profile loader now accepts subdirectory-qualified profile names such as `cause_side_v2_1/pseudo_reality_v2_1_cause_side_minimal_action_cost_high` while preserving flat existing profile names.

## 7. Validation Matrix

The Phase 2G-10 matrix is `configs/matrices/matrix_phase2g10_cause_side_v2_1_minimal_implementation_probe.json`. It contains 10 lightweight runs: seven v2.1 cause-side readiness runs and three compatibility/sanity runs. Baselines include repaired relaxed, `relaxed_legacy_dampen_075`, near-zero-action, and flat. Near-zero-action is treated only as a minimal-action approximation, not a perfect no-action claim.

## 8. Validation Results

Validation commands passed:

- `find configs/world_profiles/cause_side_v2_1 -name "*.json" -print -exec python -m json.tool {} \; > /tmp/v2_1_cause_side_profiles.validated.txt`
- `python -m json.tool configs/matrices/matrix_phase2g10_cause_side_v2_1_minimal_implementation_probe.json > /tmp/matrix_phase2g10_cause_side_v2_1_minimal_implementation_probe.validated.json`
- `python -m compileall .`
- `python scripts/run_smoke_validation.py`
- `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2g10_cause_side_v2_1_minimal_implementation_probe.json --output-dir validation_runs/phase2g10_cause_side_v2_1_minimal_implementation_probe`

Matrix summary:

- runs: 10
- overall_pass: true
- v2_1_minimal_implementation_probe_pass: true
- existing_v2_compatibility_pass: true
- boundary_violation_total: 0
- dry_run_write_violation_count: 0
- forbidden_write_count: 0

## 9. Metric Readiness

`information_asymmetry` has exported hidden-state means plus a proxy observed/hidden gap. `action_cost` has exported fatigue/defensiveness/latent-pressure means plus an action-cost proxy in the v2 action-effect trace. Proxy metrics remain labelled as proxies and are not treated as exact evidence.

## 10. Interpretation

The v2.1 minimal cause-side profile namespace loads and runs. The implemented axes are readable in the minimal probe. Existing v2 compatibility smoke checks pass. This supports moving to Phase 2G-11 cause-side preliminary validation for the two implemented axes only.

This does not prove superiority, prove safety, complete v2.1 implementation, complete cause-side validation, or establish deployment readiness.

## 11. Recommended Next Task

Recommended next task: Phase 2G-11 Cause-side Preliminary Validation Pack for `information_asymmetry` and `action_cost`.

Secondary candidates if needed: Phase 2G-11 Additional v2.1 Axis Implementation Probe, Additional Metric Export Repair, ActionModule v2 Tuning Decision Pack, or Freeze Decision Pack.

## 12. Conclusion

Phase 2G-10 adds a small separated cause-side v2.1 namespace and minimal two-axis world-side parameter reading while preserving existing v2 profile compatibility and frozen safety/write surfaces. It is ready for cautious preliminary one-axis validation, not for full validation or tuning decisions.
