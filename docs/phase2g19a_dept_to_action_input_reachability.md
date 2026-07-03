# Phase 2G-19A: DEPT-to-Action Input Reachability Validation

## Purpose

Phase 2G-19A validates whether DEPT/H-DEPT-side information reaches the action-planning surface before any later action-module tuning. The check is intentionally limited to input reachability: it asks whether stable, medium-risk, high-risk, and limit-system differences are visible in the DEPT-side inputs consumed by `ActionPlanner` and by the final gated inputs consumed by `ActionModule`.

This is **not** an actuation adjustment task. It does not tune action strength, action style, primitive multipliers, primitive definitions, v2 world dynamics, PressureTranslation, ParameterWindow, ParameterShadowBox, safety boundaries, or canonical write paths.

## Runtime boundary

The validation uses only these planner-facing inputs:

- `pressure_intents`
- `v8_affordance`
- `params`
- a test-local `final_gate` equivalent derived from planner output

The validation does not pass v2 hidden/resource/game/information/action-effect traces into `ActionPlanner` or `ActionModule`. It also does not feed six-observation-window outputs back into action runtime input. The reachability band and summary fields are test-only audit artifacts and are not runtime control inputs.

## Synthetic states

The test suite builds four synthetic DEPT-side states:

1. `stable_system`: low pressure, low conflict/unresolved/cost/need, high confidence, low rollback and intensity-brake signals.
2. `medium_risk_system`: medium pressure and terrain risk, with diagnostic, buffer, coupling-relief, and exploration-cost-relief materials becoming visible.
3. `high_risk_system`: high pressure and local terrain risk, with stronger rollback/intensity-brake signals and planner material shifting toward buffer, volatility damping, or coupling relief.
4. `limit_system`: very high pressure and terrain risk, low confidence, strong guard/brake material, and action-readiness leaning toward no-op, observe-only, buffer-first, volatility-damp-first, or collapse-management-compatible evidence.

The state labels are external test labels. They are not passed to `ActionPlanner` or `ActionModule` as control signals.

## Information groups validated

- **Pressure information:** total pressure signal, dominant pressure component, dominant semantic effect, rollback-guard signal, intensity-cap-brake signal, diagnostic signal, sandbox-probe signal, and component count.
- **Terrain/local observation information:** `v8_conflict`, `v8_unresolved`, `v8_confidence`, `estimated_action_cost`, and `target_need` carried in synthetic `v8_affordance` rows.
- **Action-surface candidate information:** available action channels, planned channel, action primitive, planner route, primitive sequence, and primitive stage.
- **Post-gate information:** final gate decision, gate score, planner raw strength, final action strength, and planner confidence.

## Reachability band

`input_reachability_band` is a test-only summary band. It is computed from continuous DEPT-side and gate-facing values, including pressure signal, local conflict, unresolvedness, cost, inverse confidence, rollback-guard signal, and intensity-cap-brake signal.

The band is not used by the action runtime. It is only used by tests and exported summaries to help reviewers confirm whether input differences are visible without reading v2 traces directly.

## Pressure-only and terrain/gate comparison

The validation compares three external audit views:

- `pressure_only_score`: pressure signal alone; useful but intentionally weaker.
- `pressure_plus_terrain_score`: pressure plus conflict, unresolvedness, action cost, and inverse confidence; improves stable/high/limit separation.
- `pressure_plus_terrain_plus_gate_score`: adds gate/action-readiness context so the reviewer can see whether post-gate materials remain auditable.

## Scenario-blind separation

A dedicated test rewrites all synthetic scenarios to `generic_reachability_probe` while keeping continuous DEPT-side values distinct. This verifies that basic separation does not depend on scenario names. Primitive choice may legitimately differ when scenario names are unavailable, but the reachability summary still separates low, medium, high, and limit bands from continuous quantities.

## Results

The added pytest coverage confirms:

- `stable_system` reaches the `low` band.
- `medium_risk_system` reaches the `medium` band.
- `high_risk_system` reaches the `high` band.
- `limit_system` reaches the `limit` band.
- The reachability score increases monotonically from stable to medium to high to limit.
- Pressure-only separation is present but weaker than pressure-plus-terrain separation.
- Scenario-blind inputs still separate the four reachability bands.
- Missing required fields are reported through `missing_input_flags` and produce an unresolved, low-confidence summary rather than a silent pass.
- Planner output and/or action frames retain audit fields such as planner route, primitive, primitive sequence, primitive stage, dominant semantic effect, dominant pressure component, action module contract, and `truth_used_for_action_planner == False`.
- Reachability summaries can be converted to a pandas `DataFrame` and exported to CSV.

## Untested scope

Phase 2G-19A does not evaluate whether the chosen action improves or worsens v2 outcomes. It does not validate v2 reaction correspondence, world-dynamics response, parameter adoption, canonical writeback, or production gate policy changes.

## Next phase

The next phase, Phase 2G-19B, should validate action-surface response correspondence with v2 reactions. That later phase should examine whether action candidates and effects align with observed v2 responses while preserving the runtime boundaries documented here.
