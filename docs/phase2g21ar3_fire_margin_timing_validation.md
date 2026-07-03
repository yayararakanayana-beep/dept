# Phase 2G-21A-R3: Fire-margin timing validation

## Purpose

Phase 2G-21A-R3 validates whether the R2 local fire-margin material is directionally useful for action timing. It compares a no-op baseline, a proposed action branch, and an observe-only/cooldown branch from the same test-local initial state, then classifies timing as no-fire, early, late, correct, harmful, stopped, suppressed, weak-probe, or relation-aware.

R3 is a validation patch only. It does not tune or redesign production runtime behavior.

## Difference from R2

R2 created local estimates for `local_no_action_risk_estimate`, `local_action_side_effect_cost_estimate`, `local_fire_margin`, `recommended_action_channel`, and `suppression_reason`. R2 did not validate whether acting at that margin was actually better than not acting.

R3 adds two pieces:

1. **R3-A: input patch** for test-local non-action decisions and relation-aware local input.
2. **R3-B: timing validation** using no-op baseline outcomes and post-action audit traces.

## R3-A: non-action / relation-aware input patch

### Non-action decision window

R3 keeps non-action decisions explicit in the test-local final gate:

- `no_op`: no action and no extra probe.
- `observe_only`: no action, but observation/audit continues.
- `cooldown`: stop additional action after action or under high load.
- `hold_shadow`: keep a candidate but do not expose it to the action surface now.

When `recommended_action_channel` is `observe_only`, the final gate preserves `final_gate_decision = observe_only` and sets `effective_action_strength = 0.0`. It is not mapped to `buffer_increase`.

### Relation-aware local input

R3 may read real-v2 `relation_trace` only in the DEPT-side test-local helper or post-action audit layer. The helper transforms it into relation-aware local input before planner/action-surface validation. ActionPlanner and ActionModule do not directly read v2 relation traces.

The relation-aware rows preserve:

- `source_relation_id`
- `source_entity_id`
- `target_entity_id`
- `relation_pair`
- `relation_strength`
- `relation_rigidity`
- `relation_flow`
- `pair_relation_lock_proxy`
- `pair_coupling_proxy`
- `pair_no_action_risk_estimate`
- `pair_action_side_effect_cost_estimate`
- `pair_fire_margin`
- `pair_fire_band`
- `relation_suppression_reason`

This is not full relation graph governance. It only checks that pair-level B-C risk is not lost in entity averages.

## R3-B: fire-margin / no-op baseline / action trace timing validation

R3 compares, from the same real-v2 initial state:

- `no_op baseline`, advanced with `v2.step(None)` or an equivalent no-action branch;
- `proposed action`, advanced with an ActionFrame-like row passed to `v2.step(action_frame)`;
- `observe_only / cooldown`, represented by a zero-strength final-gate branch.

After each branch advances, R3 reads `emit_trace()` output as post-action audit evidence. The comparison records:

- `no_op_outcome_delta`
- `action_outcome_delta`
- `outcome_improvement_vs_no_op`
- `net_public_effect_score`
- `net_hidden_effect_score`
- `side_effect_score`
- `hidden_damage_delta`
- `fatigue_delta`
- `resource_inequality_delta`
- `reversibility_delta`
- `exploration_delta`
- `action_cost_effect`

## Runtime boundary

R3 does not change production runtime. The following remain forbidden:

- ActionPlanner reading v2 traces, v2 relation traces, or raw v2 internals as runtime input.
- ActionModule reading v2 traces, relation traces, world internals, raw `G/K/O_t`, ParameterBox, ShadowBox, or six observation windows.
- Changing v2 dynamics, production ActionPlanner logic, production ActionModule logic, primitives, gains, PressureTranslation, ParameterBox, or ShadowBox.
- Canonical writeback.

The validated route is:

```text
real v2 initial state
  -> DEPT-side local / relation observation helper
  -> local_fire_margin / pair_fire_margin
  -> non_action_decision / recommended_action_channel
  -> test-local final_gate
  -> branch execution: no_op, proposed_action, observe_only/cooldown
  -> v2 action-effect trace / state delta read as post-action external audit
  -> timing_judgement
```

## Post-action audit boundary

v2 traces are used only as post-action audit evidence after the no-op/action branches have stepped and emitted traces. They are not runtime inputs to ActionPlanner or ActionModule. Relation traces are transformed before planner-side validation and are not read directly by ActionModule. `v2_trace_used_as_post_action_audit=True` is valid only when the helper actually reads branch `emit_trace()` / step trace output.

## Validated state series

R3 validates these minimum state series:

1. stable series: low entity risk, `local_fire_margin <= 0`, expecting `correct_no_fire`.
2. high-fatigue local series: high fatigue/hidden damage and high action cost, expecting `correct_suppression` or `correct_no_fire`.
3. irreversibility-approach series: entity B reversibility loss and positive margin, expecting `correct_fire` if action suppresses no-op worsening.
4. B-C relation-fixed series: high pair rigidity/coupling and positive `pair_fire_margin`, expecting `relation_correct_fire`.
5. resource-imbalance series: entity C resource gap, expecting no strong immediate action or capped insurance.
6. low-burden exploration-loss series: weak probe improves exploration with low side effects, expecting `correct_weak_probe`.
7. high-burden exploration-loss series: exploration is suppressed under high burden/collapse risk, expecting `correct_suppression`.
8. recovery series: falling margin returns to stop/cooldown/observe/no-op, expecting `correct_stop`.

## no_op baseline

The no-op baseline estimates what happens if the local state is left alone by advancing a matched v2 branch with `step(None)`. A worsening baseline is derived from the branch trace as a positive `no_op_outcome_delta`. This value is compared against the proposed action branch trace.

## proposed action

The proposed action branch uses DEPT-side local and relation-aware inputs to select a test-local action mode such as `defensive_buffer`, `coupling_relief`, `weak_probe`, `capped_insurance`, or `none`. For acting branches, the helper builds an ActionFrame-like row and passes it to `v2.step(action_frame)`. The branch records action outcome and side effects from the resulting `v2_action_effect_trace`, `v2_hidden_trace`, `v2_resource_trace`, and entity trace audit values.

## observe_only / cooldown

`observe_only` and `cooldown` are final-gate decisions with zero effective action strength. They are not aliases for `buffer_increase`.

## local_fire_margin

`local_fire_margin = local_no_action_risk_estimate - local_action_side_effect_cost_estimate`. It is banded into non-positive, weak, medium, and strong ranges for timing checks.

## pair_fire_margin

`pair_fire_margin = pair_no_action_risk_estimate - pair_action_side_effect_cost_estimate`. It preserves relation risk at the pair level and can support relation-aware action candidates when entity averages would hide the risk.

## timing_judgement

R3 supports these classifications:

- `correct_no_fire`
- `early_fire`
- `late_fire`
- `correct_fire`
- `harmful_fire`
- `correct_suppression`
- `correct_weak_probe`
- `correct_stop`
- `missed_relation_fire`
- `relation_correct_fire`
- `spurious_relation_fire`
- `unresolved`

The judgement is not controlled by scenario label and is not determined from fixed LocalCase outcome constants. It is computed from margins, branch outcomes read from v2 post-action traces, side effects, non-action decisions, burden/collapse/confidence, relation pair risk, and missing-input flags.

## Summary table

The exported table is named `real_v2_fire_margin_timing_validation_summary` and contains the requested audit identity, local margin, pair margin, final-gate, branch outcome, post-action audit, runtime-boundary, and `missing_input_flags` columns.

## Success conditions

R3 succeeds when:

- non-action decisions remain non-action and do not map to `buffer_increase`;
- local and pair fire margins influence candidate strength and timing classification;
- non-positive margins prefer no-fire/observe/cooldown;
- high fatigue/high burden suppresses strong action and exploration injection;
- sufficiently positive margin can produce defensive candidates;
- no-op and proposed-action outcomes are compared;
- correct, harmful, early, late, suppression, weak-probe, stop, and relation-aware outcomes can be classified;
- v2 traces remain post-action audit only;
- production ActionPlanner, ActionModule, v2 dynamics, and canonical state are unchanged;
- missing fields are surfaced in `missing_input_flags` and become unresolved.

## Failure conditions

R3 must not be treated as successful if:

- `observe_only` is mapped to `buffer_increase`;
- `fire_margin <= 0` produces strong action;
- high fatigue/high burden produces exploration injection merely because exploration is low;
- no-op and action outcomes are not compared;
- v2 traces or relation traces become ActionPlanner/ActionModule runtime inputs;
- relation identity or `pair_fire_margin` is dropped;
- scenario labels control `timing_judgement`;
- worsening action outcomes are labeled `correct_fire`;
- missing fields silently pass.

## Unverified scope

R3 does not validate an optimal firing policy, long-term optimization, production runtime integration, full relation graph governance, region inference, real-world data connectivity, production threshold tuning, PressureTranslation changes, ParameterBox/ShadowBox updates, or canonical writeback.

## R4 or 21C handoff

R3 hands off these validation artifacts for a later insurance-style action policy layer or 21C implementation:

- `local_fire_margin`
- `pair_fire_margin`
- `non_action_decision`
- `recommended_action_channel`
- `suppression_reason`
- `timing_judgement`
- `outcome_improvement_vs_no_op`
- `side_effect_score`

A later phase may decide whether to formalize non-action runtime integration, relation-aware action surfaces, cooldown/stop conditions, or threshold tuning. R3 does not claim that those policies are complete.
