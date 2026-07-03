# Phase 2G-21B-A: Action Effect Direction Audit

## Purpose

Phase 2G-21B-A adds a test-local action-effect direction audit on top of the Phase 2G-21A-R3 branch execution route. Its purpose is to show, as tables, which action channel was applied to which target, with what effective/v2-applied strength, and how each audited v2 component moved relative to the matched no-op branch.

This phase only visualizes trace-derived action effects. It does not implement the functional insurance action policy, perform strength sweep, change production ActionPlanner or ActionModule behavior, change v2 dynamics, update ParameterBox/ShadowBox, or perform canonical writeback.

## Difference from R3

R3 validated fire-margin timing by comparing a no-op branch and an action branch from the same real-v2 initial state, then classifying `correct_fire`, `harmful_fire`, `early_fire`, `late_fire`, relation outcomes, suppression, and stop decisions.

21B-A reuses that branch route but decomposes the post-action evidence into component-level direction rows. It records expected channel directions, observed component deltas, `direction_match`, `directional_improvement_vs_no_op`, component judgements, side effects, and one-run effect-direction summaries.

## Input trace

The audit route is:

```text
real v2 initial state
  -> initial_trace = world.emit_trace()
  -> no_op branch: no_op_world.step(None) -> no_op_trace
  -> action branch: action_world.step(action_frame or None) -> action_trace
  -> compare initial_trace / no_op_trace / action_trace
  -> action_effect_component_delta_long
  -> action_effect_direction_summary
```

The required evidence is derived from `initial_trace`, `no_op_trace`, and `action_trace`; action-effect success is not accepted from scenario labels, fixed LocalCase deltas, hand-written component deltas, or action trace alone.

## Output summary table

`action_effect_direction_summary` is one row per audited action/run. It includes identity, source/target/relation fields, channel and mode, requested/effective/v2-applied strength, fire margins, timing context, before/no-op/action outcome scores, expected component sets, match/miss/side-effect/wrong-direction counts, effect scores, final `effect_direction_judgement`, missing-input flags, and runtime-boundary booleans.

The summary includes the inherited R3 cases: `stable`, `fatigue`, `irreversible`, `relation`, `resource`, `low_probe`, `high_probe`, and `recovery`, plus `harmful`, `early`, `late`, and `missed_relation` so side-effect-dominant, low-margin strong-action, no-op worsening, and missed relation-risk examples are visible.

## Output long table

`action_effect_component_delta_long` is one row per audited component per run. It records:

- run identity and action identity;
- `component_group` and `component_name`;
- channel-defined `expected_direction` and `effect_role`;
- `initial_value`, `no_op_value`, and `action_value`;
- `no_op_delta`, `action_delta`, and `action_vs_no_op_delta`;
- `directional_improvement_vs_no_op`;
- `direction_match`;
- side-effect/material-change flags;
- `component_effect_judgement`;
- timing and missing-input flags.

## Component groups

Minimum audited components are:

- surface state: `activity`, `volatility`, `uncertainty`, `relation_lock`, `coupling`, `exploration`, `reversibility`, `entropy`;
- hidden state: `latent_pressure`, `fatigue`, `private_resource`, `defensiveness`, `opportunism`, `cooperation_intent`, `information_quality`, `hidden_damage`;
- resource/shared: `shared_resource`, `commons_health`, `resource_inequality` where `resource_inequality` is read from the v2 resource trace and is derived from the private-resource spread;
- relation: `relation_strength`, `relation_rigidity`, `relation_flow` when `relation_trace` is available.

When relation trace is missing, relation components are not silently passed; rows carry `not_available_in_21B_A`/missing-input flags and unresolved component judgement.

## Expected directions by action channel

Expected directions are channel-defined, not scenario-defined:

- `exploration_injection`: primary `exploration: increase`; side effect `fatigue: increase`.
- `coupling_relief`: primary `coupling: decrease`, `relation_lock: decrease`, `latent_pressure: decrease`; if relation trace is available, `relation_rigidity: decrease` and `relation_strength: decrease_or_stabilize`.
- `volatility_damping`: primary `volatility: decrease`; secondary `fatigue: decrease_or_stabilize`.
- `uncertainty_probe`: primary `uncertainty: decrease`, `information_quality: increase`.
- `relation_unlock`: primary `relation_lock: decrease`; side effects `defensiveness: increase`, `fatigue: increase_or_stabilize`.
- `buffer_increase`: primary `reversibility: increase`; secondary `private_resource: increase`.
- `no_op`, `observe_only`, `cooldown`, and `hold_shadow`: no forced action component change; `effective_action_strength = 0.0`, `v2_applied_strength = 0.0`, and `action_frame = None`.

Supported expected-direction values are `increase`, `decrease`, `stable`, `decrease_or_stabilize`, `increase_or_stabilize`, and `not_applicable`.

## `direction_match` calculation

Using a small fixed tolerance, 21B-A calculates `direction_match` against `action_value` versus `no_op_value`:

- `increase`: `action_value > no_op_value + tolerance`.
- `decrease`: `action_value < no_op_value - tolerance`.
- `stable`: `abs(action_value - no_op_value) <= tolerance`.
- `decrease_or_stabilize`: `action_value <= no_op_value + tolerance`.
- `increase_or_stabilize`: `action_value >= no_op_value - tolerance`.
- `not_applicable`: `direction_match = not_applicable`.

The tolerance is fixed for the helper and is not varied by scenario.

## `directional_improvement_vs_no_op` calculation

21B-A computes improvement with expected direction considered:

- `decrease`: `no_op_value - action_value`.
- `increase`: `action_value - no_op_value`.
- `stable`: `abs(no_op_value - initial_value) - abs(action_value - initial_value)`.
- `decrease_or_stabilize`: `no_op_value - action_value`.
- `increase_or_stabilize`: `action_value - no_op_value`.
- `not_applicable`: `0.0`.

## `component_effect_judgement`

Per-component judgements are selected from:

- `primary_effect_matched`;
- `secondary_effect_matched`;
- `side_effect_detected`;
- `wrong_direction`;
- `no_material_effect`;
- `mixed_effect`;
- `harmful_side_effect_dominant`;
- `not_applicable`;
- `unresolved`.

Primary and secondary matches require direction match plus material movement. Side effects are detected for components such as fatigue, hidden damage, resource inequality, and defensiveness when they worsen materially. Wrong direction requires material movement opposite the expected direction. Missing relation/component evidence is unresolved.

## `effect_direction_judgement`

The one-action summary judgement is selected from:

- `clean_primary_effect`;
- `mixed_but_acceptable`;
- `side_effect_dominant`;
- `wrong_direction_dominant`;
- `no_material_effect`;
- `relation_effect_matched`;
- `correct_non_action`;
- `unresolved`.

It is computed from component judgements, side-effect counts, wrong-direction counts, no-op/action outcome comparison, non-action zero-strength preservation, and missing inputs. Scenario labels are audit-only and do not control this judgement.

## Runtime boundary

21B-A does not change production runtime. It keeps these boundaries closed:

- ActionPlanner does not read v2 traces as runtime input.
- ActionModule does not read v2 traces, relation traces, world internals, raw `G/K/O_t`, ParameterBox, ShadowBox, or six observation window outputs.
- ActionModule receives only the final-gate/action-frame style signal in the test-local branch route.
- Production ActionPlanner, ActionModule, primitive library, gains, multipliers, PressureTranslation runtime, ParameterBox/ShadowBox, and v2 dynamics are not changed.

## Post-action audit boundary

v2 traces are used only after branch stepping as external post-action audit evidence. `v2_trace_used_as_post_action_audit=True` is valid only for helpers that actually read branch traces after `step(None)` and `step(action_frame)`. `v2_trace_used_as_action_runtime_input=False` remains mandatory.

Relation traces may be transformed by DEPT-side test-local helpers for relation-aware audit input, but ActionPlanner/ActionModule do not directly read relation traces.

## Success conditions

21B-A succeeds when it:

1. derives component deltas from `initial_trace`, `no_op_trace`, and `action_trace`;
2. avoids fixed/component hand-written deltas and scenario-label-controlled success;
3. exports `action_effect_direction_summary`;
4. exports `action_effect_component_delta_long`;
5. defines expected directions by action channel;
6. computes `direction_match` for components;
7. computes direction-aware improvement versus no-op;
8. distinguishes primary effects, secondary effects, side effects, wrong-direction movement, and no-material effects;
9. preserves `no_op`, `observe_only`, `cooldown`, and `hold_shadow` as zero-strength non-actions;
10. records relation component deltas when relation trace is available;
11. marks missing relation trace instead of silently passing;
12. includes `harmful`, `early`, `late`, and `missed_relation` in the summary;
13. keeps v2 traces post-action-audit-only;
14. keeps ActionPlanner/ActionModule runtime input boundaries closed;
15. changes no production runtime file;
16. reports missing fields in `missing_input_flags`.

## Failure conditions

The audit must not be accepted as successful if component deltas are fixed or hand-written, scenario labels control judgements, initial/no-op/action traces are not read, no-op comparison is skipped, expected directions are undefined, `direction_match` or `directional_improvement_vs_no_op` is absent, side-effect components are ignored, relation components are silently dropped, non-action decisions are mapped to `buffer_increase`, v2 traces become ActionPlanner/ActionModule runtime input, production runtime/v2 dynamics are changed, or missing fields silently pass.

## Unverified scope

21B-A does not validate optimal action strength, strength sweeps, v2 risk/cost consistency, long-term policy performance, production planner/module integration, functional insurance policy design, full relation graph governance, production threshold tuning, ParameterBox/ShadowBox updates, or canonical writeback.

## 21B-B handoff

21B-A hands off these audit artifacts for later 21B-B policy design:

- `action_effect_direction_summary`;
- `action_effect_component_delta_long`;
- `effect_direction_judgement`;
- `component_effect_judgement`;
- `side_effect_detected_count`;
- `primary_effect_match_count`;
- `wrong_direction_count`.

21B-B may use these to design upper pressure groups, lower distribution groups, action-history groups, `fire_permission_score`, `action_mass_cap`, `channel_weights`, `non_action_decision`, `cooldown_score`, and `suppression_reason`. 21B-A does not implement those functions.
