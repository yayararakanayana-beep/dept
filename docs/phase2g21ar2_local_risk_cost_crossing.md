# Phase 2G-21A-R2: Local risk / cost crossing from real v2 state

## Purpose

Phase 2G-21A-R2 validates, with test-local helpers only, whether real v2 state can be preserved at an entity/local level instead of being collapsed into a whole-system average. The R2 target is to estimate:

- `local_no_action_risk_estimate`
- `local_action_side_effect_cost_estimate`
- `local_fire_margin`

R2 asks where risk is located, what type of risk is visible, whether no action looks riskier than acting, and whether acting looks more costly or disruptive than observation.

## Difference from R1

R1 validated reachability from real v2 state snapshots into DEPT-side `pressure_intents`, `v8_affordance`, `ActionPlanner`, and `ActionModule` input shape. R1 primarily used whole-system proxy values.

R2 adds local preservation:

- entity-specific fatigue or hidden damage can remain attached to `source_entity_id`;
- entity-specific reversibility loss can remain distinct from a moderate global average;
- a thin relation proxy can preserve a risky `relation_pair` / `source_relation_id` where available;
- local resource gaps can remain visible even when the global resource average looks acceptable.

## R2-A: real v2 local state preservation

The test-local helper creates a real `AsymmetricGamePseudoRealitySystem` v2 instance and writes bounded scenario values into its entity/hidden state for audit snapshots. It then extracts a local row per entity with at least:

- `source_entity_id`
- `local_fatigue`
- `local_hidden_damage`
- `local_reversibility`
- `local_exploration`
- `local_volatility`
- `local_uncertainty`
- `local_relation_lock`
- `local_coupling`
- `local_private_resource`
- `local_resource_gap`

A thin relation proxy is included for the B/C coupling scenario:

- `source_relation_id`
- `relation_pair`

Where relation or region identity is not available in R2, the summary uses `not_available_in_r2`. `source_entity_id` is mandatory and is not replaced by a global average.

## R2-B: no-action risk / action side-effect-cost crossing

For each local row, R2 computes local proxies, then estimates the crossing between no-action risk and action cost.

### Local no-action risk estimate

`local_no_action_risk_estimate` is the weighted sum below, clipped to `[0, 1]`:

| Component | Weight |
| --- | ---: |
| `local_risk_proxy` | 0.20 |
| `local_unresolved_proxy` | 0.14 |
| `local_reversibility_need` | 0.20 |
| `local_relation_lock_proxy` | 0.14 |
| `local_coupling_proxy` | 0.12 |
| `local_collapse_proximity_proxy` | 0.10 |
| `local_resource_inequality_risk_proxy` | 0.10 |

This estimates how much the local state may worsen if it is left alone.

### Local action side-effect cost estimate

`local_action_side_effect_cost_estimate` is the weighted sum below, clipped to `[0, 1]`:

| Component | Weight |
| --- | ---: |
| `local_burden_proxy` | 0.24 |
| `local_hidden_burden_proxy` | 0.16 |
| `local_fatigue_risk_proxy` | 0.18 |
| `local_action_cost_estimate` | 0.20 |
| `local_low_confidence_penalty` | 0.12 |
| `local_resource_inequality_risk_proxy` | 0.10 |

This estimates the side-effect/cost burden of acting on the local state.

### Local fire margin

```text
local_fire_margin =
  local_no_action_risk_estimate
  - local_action_side_effect_cost_estimate
```

Interpretation:

- `local_fire_margin > 0`: no-action risk may exceed action side-effect/cost.
- `local_fire_margin <= 0`: `no_op`, `observe_only`, cooldown, or suppression may be more appropriate.

R2 treats this as an estimate only. It does not claim that firing timing is correct.

### Local fire band

`local_fire_margin` is mapped to:

- `suppressed_or_no_op`: `local_fire_margin <= 0`
- `weak_probe_or_buffer`: small positive margin, `0 < margin <= 0.08`
- `capped_insurance_candidate`: medium margin, `0.08 < margin <= 0.20`
- `defensive_candidate`: large margin, `margin > 0.20`

High margin does not imply stronger exploration. If local burden, collapse proximity, fatigue, or low confidence is high, exploratory channels are suppressed and buffer/observation material is preferred.

## Runtime boundary

R2 is test-local and does not change production runtime. The forbidden boundaries remain closed:

- `ActionPlanner` does not read `v2_action_effect_trace`, `v2_hidden_trace`, `v2_resource_trace`, `v2_game_trace`, or `v2_information_trace`.
- `ActionModule` does not read v2 traces, world internals, raw `G/K/O_t`, `ParameterBox`, `ShadowBox`, or six observation-window outputs.
- v2 dynamics are not changed.
- production `ActionPlanner`, `ActionModule`, primitive library, gains, pressure translation, `ParameterBox`, and `ShadowBox` are not changed.
- no canonical writeback is performed.

The tested path is:

```text
real v2 state
  -> entity/local state extraction
  -> local proxy generation
  -> global proxy comparison
  -> local_no_action_risk_estimate / local_action_side_effect_cost_estimate / local_fire_margin
  -> test-local pressure_intents / v8_affordance / action candidates
  -> ActionPlanner
  -> test-local final_gate equivalent
  -> ActionModule input shape
```

## Validated local state series

R2 validates these local series:

1. whole system stable / local stable: all local margins remain low and observe/no-op material dominates;
2. whole-system medium risk with `entity_A` high fatigue: burden and action cost rise, so high fatigue does not automatically fire;
3. `entity_B` approaching irreversibility: no-action risk and positive fire margin rise, favoring buffer/coupling/volatility defensive material;
4. B/C relation coupling risk: `source_relation_id` / `relation_pair` preserves the risky relation while global average can hide it;
5. `entity_C` resource imbalance: `local_resource_gap`, inequality risk, and local action cost rise;
6. low-burden exploration loss: weak probe material can appear;
7. high-burden exploration loss: exploration need remains visible but exploration injection is suppressed;
8. recovering local state: no-action risk and fire margin fall back toward observe/no-op.

## Generated global proxy and local proxy

The summary table keeps global columns separate from local columns:

- `global_risk_proxy`
- `global_burden_proxy`
- `global_action_cost_estimate`
- `global_exploration_need`
- `global_reversibility_need`

Local proxy columns include:

- `local_risk_proxy`
- `local_unresolved_proxy`
- `local_reversibility_need`
- `local_burden_proxy`
- `local_hidden_burden_proxy`
- `local_fatigue_risk_proxy`
- `local_resource_inequality_risk_proxy`
- `local_relation_lock_proxy`
- `local_coupling_proxy`
- `local_exploration_need`
- `local_action_cost_estimate`
- `local_low_confidence_penalty`
- `local_collapse_proximity_proxy`

## Summary table

The exported test-local table is named `real_v2_local_risk_cost_crossing_summary`. It includes audit identity, global proxies, local state, local proxies, crossing estimates, recommendations, planner/material fields, final-gate shape, runtime-boundary booleans, and `missing_input_flags`.

`source_relation_id` and `source_region_id` use `not_available_in_r2` where no real relation or region id is available. This is a limitation, not a silent pass. `source_entity_id` is always required.

## Success conditions

R2 succeeds when:

- real v2 snapshots produce entity/local rows;
- `source_entity_id` is preserved;
- global and local proxies are stored separately;
- local risk, burden, action cost, no-action risk, action side-effect cost, and fire margin are computed per entity;
- local high risk survives global aggregation;
- high fatigue increases cost/burden rather than automatically firing;
- irreversibility raises no-action risk;
- low-burden exploration loss can produce weak probe material;
- high-burden exploration loss suppresses exploration injection;
- ActionPlanner and ActionModule receive only DEPT/final-gate inputs, not v2 traces;
- missing local fields are reported in `missing_input_flags` and marked unresolved.

## Failure conditions / blockers

R2 must not be considered successful if:

- `source_entity_id` is missing;
- local proxy values are identical to global proxy values only;
- entity differences are absent from the summary;
- local high risk is hidden by a global average;
- no-action risk, action cost, or fire margin cannot be computed;
- only risk is considered while burden/cost is ignored;
- exploration loss always strengthens `exploration_injection` even under high burden/collapse/low confidence;
- v2 traces or observation windows are runtime inputs to `ActionPlanner` or `ActionModule`;
- scenario labels control fire margin or band;
- missing fields silently pass.

## Unverified scope

R2 does not validate:

- firing timing correctness;
- no-op baseline outcomes;
- post-action v2 trace improvement;
- whether acting was actually beneficial;
- long time-series timing quality;
- production planner/module tuning;
- v2 dynamics changes;
- pressure translation runtime changes;
- ParameterBox / ShadowBox updates;
- canonical writeback.

## R3 handoff

R2 outputs the following material for R3:

- `local_no_action_risk_estimate`
- `local_action_side_effect_cost_estimate`
- `local_fire_margin`
- `recommended_action_channel`
- `suppression_reason`

R3 should use these to test whether positive fire margins should have fired, whether no-op baselines worsen, whether action side effects appear, whether firing was early or late, and whether stopping/suppression happened when it should.
