# Phase 2G-21B-B: Functional Insurance Policy

## Purpose

Phase 2G-21B-B defines a **test-local / validation-local functional insurance policy**.  The policy combines upper-layer pressure groups, lower-layer distribution terrain, and recent action-history evidence to produce:

- `fire_permission_score`;
- `action_mass_cap`;
- `channel_weights`;
- `non_action_decision`;
- `cooldown_score`;
- `suppression_reason`;
- `evidence_trace`;
- `input_boundary_flags`.

The policy is a bounded continuous-style scoring function over numeric bundles.  It is not a scenario table, does not use scenario labels, and does not choose actions by case name.

## Difference from 21B-A

21B-A is a post-action direction audit.  It reads matched initial/no-op/action branch traces after branch execution and records action-effect direction summaries and component-level deltas.

21B-B is earlier in the decision shape: it defines a functional policy that maps numeric pressure, terrain, and history bundles into permission, mass cap, channel weights, and non-action handling.  It does not perform v2 strength sweeps, does not infer an optimal v2 strength, and does not integrate into production ActionPlanner or ActionModule runtime.

## Input schema

The test-local function signature is:

```python
def functional_insurance_policy(
    upper: UpperPressureBundle,
    lower: LowerDistributionBundle,
    history: ActionHistoryBundle,
) -> InsurancePolicyOutput:
    ...
```

Only these three bundles are policy inputs.  `scenario_label`, `case_name`, and `run_id` are intentionally absent.

### Upper pressure bundle

`UpperPressureBundle` contains upper-layer pressure values in the range `0.0..1.0`:

- `stabilize_pressure` — pressure to stabilize;
- `explore_pressure` — pressure to explore;
- `buffer_pressure` — pressure to increase slack or buffer;
- `relation_relief_pressure` — pressure to loosen relation fixation or over-coupling;
- `reversibility_pressure` — pressure to preserve or restore reversibility;
- `cooldown_pressure` — pressure to cool down or suppress;
- `observe_pressure` — pressure to observe without acting;
- `de_risk_pressure` — pressure to reduce danger;
- `overconvergence_avoidance_pressure` — pressure to avoid over-convergence.

### Lower distribution bundle

`LowerDistributionBundle` contains lower-layer distribution and local terrain values.  Most values are bounded to `0.0..1.0`; `local_fire_margin` and `pair_fire_margin` may be `-1.0..1.0`.

- `local_no_action_risk_estimate`;
- `local_action_side_effect_cost_estimate`;
- `local_fire_margin`;
- `pair_no_action_risk_estimate`;
- `pair_action_side_effect_cost_estimate`;
- `pair_fire_margin`;
- `confidence`;
- `burden`;
- `fatigue`;
- `collapse_proximity`;
- `reversibility_need`;
- `relation_lock_proxy`;
- `coupling_proxy`;
- `exploration_need`;
- `unresolved_proxy`;
- `side_effect_risk`.

### Action history bundle

`ActionHistoryBundle` contains recent action-history values in the range `0.0..1.0`:

- `recent_correct_fire_rate`;
- `recent_harmful_fire_rate`;
- `recent_side_effect_score`;
- `recent_cooldown_state`;
- `recent_no_op_worsening`;
- `recent_wrong_direction_rate`.

## Output schema

`InsurancePolicyOutput` contains:

- `fire_permission_score: float`;
- `action_mass_cap: float`;
- `channel_weights: dict[str, float]`;
- `non_action_decision: str`;
- `cooldown_score: float`;
- `suppression_reason: str`;
- `evidence_trace: dict`;
- `input_boundary_flags: list[str]`.

All scalar scores and all channel weights are bounded to `0.0..1.0`.

## `fire_permission_score`

`fire_permission_score` is the current degree to which action is permitted.  It increases with local and pair fire margins, confidence, recent correct fire, upper need, and recent no-op worsening.  It decreases with side-effect risk, burden, fatigue, collapse proximity, recent harmful fire, wrong-direction history, and explicit side-effect costs.

## `action_mass_cap`

`action_mass_cap` is the maximum allowed insurance-action mass.  It is deliberately conservative: even with high permission, the cap is reduced by low confidence, high burden, high fatigue, high side-effect risk, collapse proximity, and recent harmful fire.  If upper pressure is zero, the cap remains low.  If terrain is dangerous, high upper pressure does not produce strong action.

## `channel_weights`

The policy exports these channels:

- `buffer_increase`;
- `coupling_relief`;
- `volatility_damping`;
- `uncertainty_probe`;
- `exploration_injection`;
- `relation_unlock`;
- `observe_only`;
- `cooldown`;
- `no_op`;
- `hold_shadow`.

Weights are numeric tendencies, not scenario labels.  For example, `buffer_increase` rises with buffer/reversibility/de-risk pressure and reversibility/collapse terrain; `coupling_relief` and `relation_unlock` rise with relation pressure, pair margin, relation lock, and coupling proxies; `exploration_injection` rises with explore pressure and exploration need only when the safety gate is favorable.

## `non_action_decision`

`non_action_decision` is one of:

- `no_op`;
- `observe_only`;
- `cooldown`;
- `hold_shadow`;
- `none`.

The function preserves non-action types.  `observe_only`, `cooldown`, and `hold_shadow` are not mapped into `buffer_increase`; when a non-action decision is selected, `action_mass_cap` is kept low.

## `cooldown_score`

`cooldown_score` rises with cooldown pressure, burden, fatigue, side-effect risk, recent harmful fire, recent side-effect score, and current cooldown state.

## `suppression_reason`

`suppression_reason` is `none` or a `+`-joined combination of reasons such as:

- `low_fire_permission`;
- `low_confidence`;
- `high_burden`;
- `high_fatigue`;
- `high_side_effect_risk`;
- `recent_harmful_fire`;
- `cooldown_state`;
- `unresolved_high`;
- `mixed_risk`.

## `evidence_trace`

`evidence_trace` records why the output was produced.  It includes:

- `positive_fire_evidence`;
- `negative_fire_evidence`;
- `channel_evidence`;
- `suppression_evidence`;
- `history_evidence`.

This is explanatory evidence only; it is not a production controller and does not update canonical state.

## Function design principles

The function interprets:

- upper pressures as *which direction the upper layer wants to push*;
- lower distributions as *whether the local terrain can tolerate that push*;
- recent history as *whether this style of push has recently been dangerous*.

The core shape is:

```text
permission ~= upper need
           + lower terrain allowance * confidence
           + recent correct/no-op-worsening evidence
           - side-effect prediction
           - burden/fatigue/collapse penalty
           - recent harmful or wrong-direction penalty
```

The implementation uses fixed coefficients for the functional policy.  Coefficients are not varied by scenario or case.

## Monotonicity constraints

The contract tests require, at minimum:

- local and pair fire-margin increases do not decrease `fire_permission_score`;
- side-effect cost and side-effect risk increases do not increase `fire_permission_score`;
- lower confidence, higher burden, higher fatigue, and higher harmful-fire history do not increase `action_mass_cap`;
- harmful-fire and side-effect history do not decrease `cooldown_score`;
- pair fire margin does not decrease `coupling_relief`;
- relation lock does not decrease `relation_unlock`;
- reversibility need does not decrease `buffer_increase`;
- exploration need does not decrease safe exploration weight;
- fatigue, burden, and side-effect risk do not increase exploration weight;
- zero upper pressure suppresses action mass;
- dangerous lower terrain suppresses action mass even under high upper pressure.

## Runtime boundary

21B-B does not change production runtime.  It does not integrate with production ActionPlanner, production ActionModule, v2 dynamics, primitive libraries, gains, multipliers, PressureTranslation runtime, ParameterBox, ShadowBox, or canonical writeback.

The implementation is test-local in `tests/test_phase2g21b_b_functional_insurance_policy.py`.

## Post-action audit boundary

21B-A post-action summaries may be converted into the three policy bundles by a lightweight helper, but the scenario label remains audit-only and is not read.  v2 traces remain post-action audit evidence only and are not runtime inputs to ActionPlanner or ActionModule.

## Success conditions

21B-B succeeds when the test-local policy:

1. accepts upper, lower, and history bundles;
2. excludes scenario labels and case names from policy inputs;
3. emits permission, cap, channel weights, non-action decision, cooldown score, suppression reason, evidence trace, and boundary flags;
4. keeps scores and channel weights bounded;
5. satisfies monotonicity and boundary tests;
6. preserves non-action decisions;
7. keeps production runtime unchanged;
8. documents unverified scope and 21C handoff.

## Failure conditions

21B-B fails if scenario names or case names control policy decisions, if coefficients vary by validation case, if monotonicity tests are absent, if `evidence_trace` is absent, if channel weights or non-action decisions are absent, if non-actions are remapped to `buffer_increase`, if dangerous terrain does not suppress action mass, if v2 traces become runtime inputs, or if production ActionPlanner/ActionModule/v2 dynamics/ParameterBox/ShadowBox/canonical writeback are changed.

## Unverified scope

This phase does not validate optimal action strength, v2 strength sweep behavior, v2 risk/cost crossing consistency, long-term closed-loop performance, production planner/module integration, primitive changes, full relation graph governance, ParameterBox or ShadowBox updates, or canonical writeback.

## 21C handoff

21C should compare the 21B-B outputs (`fire_permission_score`, `action_mass_cap`, and `channel_weights`) with v2 measured strength-sweep evidence such as observed safe strength range, observed best strength, harmful threshold, net benefit, and side-effect cost.  21B-B intentionally stops before that comparison.
