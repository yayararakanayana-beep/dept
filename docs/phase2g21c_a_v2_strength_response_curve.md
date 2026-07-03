# Phase 2G-21C-A: V2 Strength Response Curve Measurement

## Purpose

Phase 2G-21C-A measures v2 strength response curves for insurance-action channels.  From one real v2 initial state per case, it creates a no-op branch and multiple action branches, then derives risk reduction, side effects, and net benefit from post-action traces.

## Difference from 21B-B

21B-B defines a functional insurance policy that emits `fire_permission_score`, `action_mass_cap`, `channel_weights`, non-action handling, cooldown, suppression, and evidence.  21C-A does not tune or validate those coefficients.  It produces an empirical v2 response map that 21C-B can compare against 21B-B outputs.

## What 21C-A does

- Builds same-initial-state no-op and action branches.
- Sweeps action strength for each action channel.
- Reads `initial_trace`, `no_op_trace`, `action_trace`, `v2_action_effect_trace`, `v2_hidden_trace`, `v2_resource_trace`, `entity_trace`, and `relation_trace` as post-action audit evidence.
- Exports `v2_strength_response_curve_long` and `v2_strength_response_summary`.

## What 21C-A does not do

It does not perform final 21B-B comparison, coefficient adjustment, dynamic pressure-conditioned coefficient modulation, production ActionPlanner integration, production ActionModule integration, v2 dynamics changes, ParameterBox or ShadowBox updates, canonical writeback, or long-term closed-loop validation.

## Input cases

The audit inherits the R3 / 21B-A cases: `stable`, `fatigue`, `irreversible`, `relation`, `resource`, `low_probe`, `high_probe`, `recovery`, `harmful`, `early`, `late`, and `missed_relation`.  `scenario_label_for_audit_only` is audit metadata only.

## Action channels

Swept action channels are `buffer_increase`, `coupling_relief`, `volatility_damping`, `uncertainty_probe`, `exploration_injection`, and `relation_unlock`.  Non-action channels `no_op`, `observe_only`, `cooldown`, and `hold_shadow` remain baselines and are not strength-swept in 21C-A.

## Strength grid

The fixed grid is `0.00`, `0.02`, `0.04`, `0.08`, `0.12`, `0.16`, and `0.24`.  `0.00` may be represented in the curve rows, but the explicit no-op branch remains mandatory.

## Branch execution method

For each case, the helper creates a real v2 initial world and records `initial_trace = initial_world.emit_trace()`.  It then deep-copies the same initial world into `no_op_world` and `action_world`.  `no_op_world.step(None)` provides the baseline; `action_world.step(action_frame)` provides each channel/strength branch.

## No-op baseline

Every action strength is compared with the same-initial-state no-op branch.  Action-only measurements are not sufficient for net benefit.

## Measured values

Rows record initial/no-op/action risk scores, no-op/action outcome deltas, risk reduction versus no-op, outcome improvement versus no-op, side-effect score, side-effect cost, action cost, fatigue, hidden damage, resource inequality, reversibility, exploration, coupling, relation lock, uncertainty, information quality, relation rigidity, and relation flow deltas.

## Net benefit definition

`net_benefit = risk_reduction_vs_no_op - side_effect_cost`.  A supplemental `net_benefit_from_outcome = outcome_improvement_vs_no_op - side_effect_score` is also exported.

## Output long table

`v2_strength_response_curve_long` has one row per case × action channel × strength and contains identifiers, strength values, measured scores, component deltas, `response_judgement`, missing flags, and runtime-boundary flags.

## Output summary table

`v2_strength_response_summary` has one row per case × action channel and contains observed best strength, safe range, harmful threshold, no-effect range, max risk reduction, max side effect, positive/negative net-benefit counts, curve shape, summary judgement, and missing flags.

## response_judgement

Strength-level judgements include `beneficial_strength`, `safe_but_weak`, `no_material_effect`, `mixed_effect`, `side_effect_dominant`, `harmful_strength`, `wrong_direction`, and `unresolved`.  Judgements are derived from measured net benefit, risk movement, side effects, expected-direction component deltas, and missing inputs, not scenario labels.

## curve_shape_judgement

Curve-level judgements include `monotone_beneficial`, `single_peak_safe`, `overfire_after_threshold`, `mostly_harmful`, `mostly_no_effect`, `mixed_unstable`, and `unresolved`.  These are derived from curve rows.

## observed_safe_strength_range

Safe strength means positive net benefit with side effects and fatigue/hidden-damage/resource-inequality deltas within tolerances.  If no safe rows exist, min/max are `None` and range is `none`.

## observed_harmful_threshold

The harmful threshold is the first strength whose response is `harmful_strength` or `side_effect_dominant`.  If no such row exists, it is `None`.

## Runtime boundary

v2 traces are not ActionPlanner or ActionModule runtime inputs.  They are read only after branch execution for audit measurement.  Production runtime files are not changed.

## Post-action audit boundary

The audit may read branch traces to derive metrics.  It must not become a controller, gate, actuator, parameter update path, or canonical writeback mechanism.

## Success conditions

21C-A succeeds when it uses same-initial-state no-op/action branches, runs `v2.step(action_frame)` for each strength, derives metrics from branch traces, exports both tables, computes net benefit, best strength, safe range, harmful threshold, response judgement, and curve shape, keeps scenario labels audit-only, keeps v2 traces out of runtime inputs, and avoids production runtime changes.

## Failure conditions

It fails if strengths use separate initial states, no-op baseline is absent, action-only comparison is used, fixed deltas or scenario names control results, best/safe/harmful outputs are not derived from curve rows, side effects are ignored, relation components silently pass when missing, v2 traces become runtime inputs, production runtime changes, or canonical writeback occurs.

## 21C-B handoff

21C-B should compare 21B-B `fire_permission_score`, `action_mass_cap`, `channel_weights`, `non_action_decision`, and `cooldown_score` with 21C-A `observed_safe_strength_range`, `observed_best_strength`, `observed_harmful_threshold`, net-benefit curves, and `curve_shape_judgement`.  21C-A does not perform that comparison or adjustment.
