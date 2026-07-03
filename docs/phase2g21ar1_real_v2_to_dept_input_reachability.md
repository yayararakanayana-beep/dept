# Phase 2G-21A-R1: Real v2 State to DEPT Input Reachability

## Purpose

Phase 2G-21A-R1 is an independent reachability/audit validation. It checks whether differences in real PseudoReality v2 state snapshots can be observed by a DEPT-side test-local observation/translation helper, transformed into DEPT-side pressure intents, v8 affordance rows, and proxy fields, then carried through ActionPlanner, a test-local final-gate equivalent, and ActionModule input shape.

R1 validates the path:

```text
real v2 initial/step-equivalent state snapshot
  -> DEPT-side observation/translation helper
  -> pressure_intents / v8_affordance / proxy group
  -> ActionPlanner
  -> test-local final_gate equivalent
  -> ActionModule.build_action_frame
```

The validation is reachability-only. It does not claim that action firing timing is correct and does not evaluate post-action improvement.

## Difference from PR #81 / Phase 2G-19A

Phase 2G-19A validated that synthetic DEPT-side pressure intents and v8 affordance rows can reach ActionPlanner and ActionModule. R1 complements that work by starting from real PseudoReality v2 state snapshots instead of prebuilt synthetic DEPT-side input.

R1 keeps the 19A reachability boundary: it does not tune ActionPlanner, ActionModule, primitive gains, pressure translation, ParameterBox, or ShadowBox behavior.

## Difference from PR #83 / Phase 2G-19B-1R

Phase 2G-19B-1R validated whether ActionFrames injected into real v2 produce readable `v2_action_effect_trace` correspondence. R1 does not use v2 action traces as runtime input to ActionPlanner or ActionModule. Any v2 trace would be external audit evidence only; the R1 test path uses state snapshots and DEPT-side proxy translation.

## Runtime boundary

R1 explicitly preserves these runtime boundaries:

- ActionPlanner receives only DEPT-side `pressure_intents`, `v8_affordance`, and params.
- ActionModule receives only the test-local final-gate equivalent and params.
- ActionPlanner does not read `v2_action_effect_trace`, `v2_hidden_trace`, `v2_resource_trace`, `v2_game_trace`, or `v2_information_trace`.
- ActionModule does not read v2 traces, direct world internals, G/K/O_t raw data, ParameterBox, ShadowBox, or six observation-window outputs.
- Six observation-window outputs are not runtime inputs.
- The scenario label is audit-only and is not allowed to determine reachability bands by itself.
- Missing v2 fields become `missing_input_flags` and `input_reachability_band == unresolved`; they are not silent passes.

R1 is test-local and does not modify v2 dynamics, production ActionPlanner logic, production ActionModule logic, primitive libraries, gains, multipliers, PressureTranslation runtime, ParameterBox/ShadowBox, or canonical writeback paths.

## v2 state series under validation

The test creates bounded real v2 state snapshots through `AsymmetricGamePseudoRealitySystem` setup helpers for these audit-only labels:

1. `stable`
   - Expected low `risk_proxy`, low `unresolved_proxy`, low `burden_proxy`, low-to-medium `action_cost_estimate`, low-to-medium `reversibility_need`, and no-op/observe-leaning material.
2. `worsening`
   - Expected higher risk than stable, rising reversibility need, slightly higher burden, and visible buffer/probe/coupling-relief material.
3. `high_risk`
   - Expected high risk, high unresolved, high reversibility need, medium-to-high burden, and defensive buffer/damping/coupling-relief material without unbounded exploration injection.
4. `limit`
   - Expected high collapse proximity, high risk, high burden, high low-confidence penalty, and exploration suppression material favoring no-op/observe/buffer/damping.
5. `exploration_loss`
   - Expected elevated exploration need and residual/novelty-gap-like proxy, while still allowing burden to suppress exploration material when burden is high.
6. `recovery`
   - Expected lower risk, lower reversibility need, lower burden, lower action-need material, and movement back toward observe/no-op material.

## Generated DEPT-side proxies

R1 generates these proxy columns from state snapshots in test-local helpers:

- `risk_proxy`
- `residual_proxy`
- `unresolved_proxy`
- `reversibility_need`
- `burden_proxy`
- `hidden_burden_proxy`
- `fatigue_risk_proxy`
- `resource_inequality_risk_proxy`
- `coupling_proxy`
- `relation_lock_proxy`
- `exploration_need`
- `action_cost_estimate`
- `low_confidence_penalty`
- `collapse_proximity_proxy`

The core audit focus is `risk_proxy`, `unresolved_proxy`, `reversibility_need`, `burden_proxy`, `action_cost_estimate`, and `exploration_need`.

## ActionPlanner / ActionModule reachability confirmation

The summary table is named `real_v2_to_dept_input_reachability_summary` in the test module. It includes:

- run metadata and audit-only scenario label
- v2 state source and DEPT helper identifiers
- all proxy columns
- pressure intent / v8 affordance / action candidate counts
- dominant pressure and semantic effect
- available and planned action channels
- primitive metadata
- reachability score, band, confidence, and missing-input flags
- boundary flags showing v2 traces and observation windows were not action runtime inputs
- boundary flags showing ActionPlanner received only DEPT inputs and ActionModule received only final-gate input

## Success conditions

R1 succeeds when:

1. Real v2 state snapshots generate DEPT-side inputs.
2. `pressure_intents` is non-empty.
3. `v8_affordance` is non-empty.
4. Stable / worsening / high-risk / limit / exploration-loss / recovery differences appear in proxies.
5. `risk_proxy` follows the expected stable < worsening < high-risk < limit trend.
6. `burden_proxy` and `action_cost_estimate` rise in high-load states.
7. `reversibility_need` rises near less-recoverable states.
8. `exploration_need` rises in the exploration-loss state.
9. High-risk and limit states do not produce unbounded exploration-injection material.
10. Inputs reach ActionPlanner.
11. A final-gate equivalent is produced.
12. ActionModule can receive the final-gate shape.
13. v2 traces are not ActionPlanner/ActionModule runtime inputs.
14. Six observation-window outputs are not runtime inputs.
15. Missing fields surface in `missing_input_flags` instead of passing silently.

## Failure conditions / blockers

The validation must not be considered passing if any of these occur:

- Real v2 states cannot generate DEPT-side inputs.
- `pressure_intents` or `v8_affordance` is empty for valid states.
- State differences barely appear in proxies.
- `risk_proxy` appears but `burden_proxy` or `action_cost_estimate` does not.
- `exploration_need` is constant across states.
- High-load states produce unbounded exploration injection.
- Bands are determined by scenario names rather than proxy values.
- v2 traces are passed into ActionPlanner or ActionModule runtime input.
- Six observation-window output is mixed into runtime input.
- Missing fields still produce a success band.

## Unvalidated scope

R1 does not validate:

- firing timing correctness,
- no-op baseline superiority or inferiority,
- post-action v2 trace improvement,
- capped insurance-hybrid policy behavior,
- production tuning of ActionPlanner or ActionModule,
- primitive-library changes,
- gains or multiplier changes,
- PressureTranslation runtime changes,
- ParameterBox/ShadowBox updates,
- canonical writeback.

## R2/R3 handoff

R1 establishes whether real v2 state differences can reach the DEPT action input surface as risk, burden, cost, reversibility, unresolvedness, and exploration-need material. R2 should use this reachability evidence to study the estimated intersection between unattended risk and action side effects/cost. R3 should separately evaluate firing timing, no-op baseline comparisons, and post-action trace correspondence.
