# Phase 2G-19B-1R: Real v2 Action-Surface Response Correspondence Validation

## Purpose

Phase 2G-19B-1R validates how explicit validation-only `ActionFrame` probes appear in the real PseudoReality v2 action-effect trace after application to the existing v2 asymmetric game world.  The goal is correspondence observation, not clean alignment and not action tuning.

## Difference from Phase 2G-19B-1

Phase 2G-19B-1 fixed the channel-level response-map shape with a test-local v2-style adapter.  Phase 2G-19B-1R keeps the same response-map intent but replaces that local formula with a real v2 connection:

1. build an external probe row with `action_channel`, `action_strength`, and `action_primitive`;
2. apply the probe through `AsymmetricGamePseudoRealitySystem.step()`;
3. read `emit_trace()` output returned by `step()`;
4. extract `v2_action_effect_trace`;
5. format the row into the response map.

This PR does not claim that Phase 2G-19B-1's test-local adapter is a real-v2 pass condition.

## Difference from Phase 2G-19B-2

Phase 2G-19B-2 is reserved for action-pattern comparison such as `no_op`, current module output, continuous weak action, threshold insurance, and hybrid patterns.  Phase 2G-19B-1R does not compare action styles or tune policy; it only checks whether each required channel can be applied to real v2 and read back from `v2_action_effect_trace`.

## State bands

The validation attempts all four required bands:

- `stable`
- `medium`
- `high`
- `limit`

The current real v2 runner does not expose a dedicated state-band scenario generator.  The test helper therefore maps each label to bounded initial conditions before calling the existing v2 world dynamics and action application.  This mapping changes only test setup state; it does not modify v2 dynamics code.

## Action channels

The response map attempts all seven required channels:

- `no_op`
- `buffer_increase`
- `coupling_relief`
- `volatility_damping`
- `uncertainty_probe`
- `exploration_injection`
- `relation_unlock`

`no_op` is included as the per-state baseline with `action_strength = 0.0`.  Non-`no_op` probes use `action_strength = 0.12`.

## Real v2 runner, helper, and trace point

- Runner/helper used: `pseudo_reality.asymmetric_game_v2.AsymmetricGamePseudoRealitySystem`.
- Action application point: `AsymmetricGamePseudoRealitySystem.step(action_frame)`.
- Trace acquisition point: `step()` returns `emit_trace()` output.
- Trace table read: `v2_action_effect_trace`.

The helper is intentionally thin: it constructs initial conditions and probe rows, then calls the real v2 action application path and reads the emitted trace.

## Core fields read from `v2_action_effect_trace`

The response map reads these core fields when present:

- `exploration_delta`
- `reversibility_delta`
- `net_public_effect_score`
- `net_hidden_effect_score`
- `hidden_damage_delta`
- `fatigue_delta`
- `resource_inequality_delta`
- `action_cost_effect`

Missing fields are recorded in `missing_response_fields`; they are not silently ignored.

## Response-map columns

The map includes real-v2 provenance columns, core action-effect fields, no-op baseline deltas, scoring columns, and status columns:

- `real_v2_runner_used`
- `real_v2_trace_used`
- `real_v2_connection_status`
- `no_op_baseline_key`
- `delta_vs_no_op_*`
- `intended_effect_score`
- `side_effect_burden_score`
- `cost_burden_score`
- `response_alignment_score`
- `response_status`
- `side_effect_flags`
- `missing_response_fields`
- `unresolved_reason`

The map is exportable as a pandas DataFrame and CSV, including blocker/unresolved rows if a future runner cannot provide a field or channel.

## Score meanings

`intended_effect_score` is channel-specific.  Examples: `buffer_increase` primarily reads `reversibility_delta`; `exploration_injection` primarily reads `exploration_delta`; `relation_unlock` uses `reversibility_delta`, `net_public_effect_score`, and a resource-inequality proxy because no explicit relation-lock trace field exists in `v2_action_effect_trace`.

`side_effect_burden_score` uses hidden burden magnitude from `net_hidden_effect_score`, `hidden_damage_delta`, `fatigue_delta`, and `resource_inequality_delta`.  The current v2 trace exports these values as burden magnitudes in practice, so this validation treats positive magnitude as burden and documents that signed semantics are not inferred beyond the emitted field values.

`cost_burden_score` uses `action_cost_effect`.

`response_alignment_score` is calculated as:

```text
intended_effect_score - side_effect_burden_score - cost_burden_score
```

The aggregate score is not a runtime decision and is not the sole status criterion.

## Mixed or side-effect-heavy responses are allowed

A channel does not have to be cleanly aligned to pass this validation.  If real v2 produces mixed, weak, or side-effect-heavy responses, those outcomes are recorded as validation material for later analysis.  The status set includes `aligned`, `mixed`, `side_effect_heavy`, `weak_effect`, `unresolved`, and `blocker`.

## Unresolved and blocker handling

If real v2 cannot be connected, or if `v2_action_effect_trace` cannot be read, the validation records `real_v2_connection_status = blocker` and uses blocker/unresolved rows instead of claiming success.  If only fields are missing, the missing field names are written to `missing_response_fields` with `response_status = unresolved`.

No blocker was required for the current implementation because the existing real v2 runner accepted the probe rows and emitted `v2_action_effect_trace`.

## Runtime boundaries

This validation is external observation only.

It does not modify or tune:

- ActionModule runtime
- ActionPlanner runtime
- primitive library
- gains or multipliers
- v2 world dynamics
- PressureTranslation runtime
- ParameterBox or ParameterShadowBox
- canonical write paths
- six observation-window logic

The v2 trace is read only after action application for response-map construction.  It is not passed to ActionPlanner or ActionModule runtime.  Six observation-window outputs such as composite balance or v2 direct windows are not used as action runtime inputs.

## Next phase

The next Phase 2G-19B-2 should perform action-pattern comparison across `no_op`, current action module output, continuous weak, threshold insurance, and hybrid variants.  That comparison is intentionally not implemented in Phase 2G-19B-1R.
