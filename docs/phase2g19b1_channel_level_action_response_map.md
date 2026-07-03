# Phase 2G-19B-1: Channel-Level Action-Surface Response Map

日本語名: **作用チャネル別・作用面反応対応地図**

## Purpose

Phase 2G-19B-1 records how each action channel responds on a v2-style action surface by comparing each probe with a `no_op` baseline across four validation state bands. This is a verification map, not an action-module tuning task.

Phase 2G-19A showed that stable / medium / high / limit DEPT-side distinctions can reach the ActionPlanner / ActionModule input surface without passing raw v2 traces into those runtimes. Phase 2G-19B-1 is the next external validation layer: it probes channel-specific response signatures after action application and keeps the observed response fields as review evidence.

## Scope Split from Phase 2G-19B-2

This phase is **not** an action-pattern comparison. It does not compare `no_op`, current behavior, continuous weak action, threshold insurance, or hybrid patterns. It does not choose policies, optimize goals, or specialize which action style should be used in a given risk band.

The next Phase 2G-19B-2 should perform that action-pattern comparison after this channel-level response map is available.

## State Bands

The response map covers these external validation labels:

- `stable`
- `medium`
- `high`
- `limit`

These labels select synthetic initial-condition profiles for the validation probe. They are not ActionModule runtime inputs.

## Action Channels

The response map covers:

- `no_op`
- `buffer_increase`
- `coupling_relief`
- `volatility_damping`
- `uncertainty_probe`
- `exploration_injection`
- `relation_unlock`

`no_op` is included as the natural-drift / zero-action baseline. Non-`no_op` rows are compared against the matching state-band and seed baseline.

## Probe Construction

The test builds ActionFrame-like rows with the required fields: `entity_id`, `action_channel`, `action_strength`, `direction`, `source_gate_decision`, `planner_route`, `action_primitive`, `primitive_sequence`, `primitive_stage`, `action_scope`, `duration_steps`, `rollback_condition`, `dominant_semantic_effect`, `dominant_pressure_component`, and `action_module_contract`.

`no_op` uses `action_strength = 0.0`. Other channels use the medium probe strength `0.12`.

The repository scaffold does not expose a stable production runner that can independently probe every required channel across every required state band. Therefore the new test uses a test-local v2 action-effect adapter. The adapter emits v2-style action-effect fields and state-sensitive channel signatures while leaving production v2 dynamics and runtime modules unchanged.

## v2 Response Fields

Each response row keeps these core fields:

- `exploration_delta`
- `reversibility_delta`
- `net_public_effect_score`
- `net_hidden_effect_score`
- `hidden_damage_delta`
- `fatigue_delta`
- `resource_inequality_delta`
- `action_cost_effect`

Rows also retain action metadata such as `action_channel`, `action_intensity`, `target_count`, `direct_effect_score`, `side_effect_score`, `exploitation_risk_delta`, and `trust_delta`.

Missing core fields are not silently ignored. They are recorded in `missing_response_fields`, and unresolved rows receive `response_status = unresolved`.

## Scores

The validation map emits:

- `intended_effect_score`: channel-specific intended-direction score.
- `side_effect_burden_score`: burden from hidden effect magnitude, hidden damage, fatigue, and resource inequality.
- `cost_burden_score`: burden from `action_cost_effect`.
- `response_alignment_score`: intended effect minus side-effect and cost burdens.
- `response_status`: one of `aligned`, `mixed`, `side_effect_heavy`, `weak_effect`, or `unresolved`.
- `side_effect_flags`: explicit flags for elevated hidden burden, resource inequality, or action cost.

The aggregate alignment score is review evidence only. It is not a runtime policy input and is not fed back into ActionPlanner or ActionModule.

## Channel Expectations Recorded as Map Context

- `no_op`: action intensity and action-derived deltas should remain zero or near zero.
- `buffer_increase`: intended to improve reversibility without excessive hidden damage, fatigue, or cost.
- `coupling_relief`: intended to loosen coupling / lock pressure without worsening inequality or hidden burden.
- `volatility_damping`: intended to protect high / limit states from worsening while preserving reversibility.
- `uncertainty_probe`: intended to be a low-cost information probe with limited hidden burden.
- `exploration_injection`: intended to increase exploration, especially in stable / medium states.
- `relation_unlock`: intended to loosen fixed relations, but may be risky in high / limit states.

Side effects are not test failures by themselves. The purpose is to expose weak effects, mixed effects, and side-effect-heavy responses as inputs for later review.

## Runtime Boundaries

This PR does not tune or modify:

- ActionModule runtime
- ActionPlanner runtime
- action primitive library
- gains or multipliers
- v2 world dynamics
- PressureTranslation runtime
- ParameterBox / ParameterShadowBox
- canonical write path
- six observation-window judgment logic

The v2-style response trace is read only by the external validation map after probe application. It is not passed into ActionPlanner or ActionModule runtime calls.

Six observation-window outputs such as observation summaries, composite balance, direct benefit, direct growth, risk-band, or H11 action-effect windows are not returned to ActionPlanner or ActionModule as runtime inputs.

## Export

The response map is a pandas `DataFrame` and can be exported as CSV. Required export columns include state band, action channel, action strength, core v2 effect fields, and response status.

## Next Step

Phase 2G-19B-2 should use this channel-level map as background evidence for action-pattern comparison. Phase 2G-19B-2 is where `no_op`, current behavior, continuous weak action, threshold insurance, and hybrid patterns should be compared; that comparison is intentionally not implemented here.
