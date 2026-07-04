# Closed Loop Runner Integration RC1

## Purpose

The goal of Closed Loop Runner Integration RC1 is not to maximize short-term gain on a closed v2 surface. The goal is to connect the action module to a multi-step pseudo-reality loop and produce interpretable comparisons showing where no action, visible-surface greedy optimization, and ACTION_MODULE_RC1 differ in safety, over-action, recovery, robustness, exploration retention, and auditability.

This is a test-local integration runner. It checks whether the consolidated `action_module_step(...)` API can be used as a one-step decision source inside a bounded pseudo-reality transition loop without modifying production runtime code, canonical state, real coefficients, v2 dynamics, ActionPlanner, ActionModule, ParameterBox, or ShadowBox.

## Position after PR #98 and PR #99

PR #98 froze the Action Module API Consolidation RC1 path around `action_module_step(...)` as a prepared-input, no-write, test-local action API. PR #99 added v2 alignment and pseudo-open stress auditing with three baselines and stress cases, but it remained primarily a one-step audit layer. Closed Loop Runner Integration RC1 starts from those frozen pieces and adds multi-step state evolution so decisions can accumulate consequences.

## More than “runner executes”

This runner is not a smoke test. It produces comparison tables for repeated episodes and evaluates tradeoffs across cumulative gain, safety violations, over-action, recovery, relation-lock growth, delayed side-effect cost, exploration-capacity retention, and audit boundary pass rate. A passing run must show interpretable behavioral differences among baselines.

## Three baselines

- `NO_ACTION`: always emits `NO_OP`, no channel, and zero action mass.
- `V2_GREEDY_OPTIMIZER`: selects the visible channel and action mass that maximize immediate visible gain. It does not see future drift, hidden fragility, delayed side effects, safety-boundary shifts, or external shocks.
- `ACTION_MODULE_RC1`: calls `action_module_step(...)` using only prepared upper pressure, lower state, observation view, action history, parameter snapshot, and guardrail snapshot.

## Pseudo-reality state

Each step tracks bounded values in `[0.0, 1.0]`: stability, risk, opportunity, exploration capacity, recovery capacity, fatigue, relation lock, hidden fragility, external pressure, safe mass upper, harmful threshold, and response-surface shift.

## Scenario types

The RC1 runner covers at least seven scenarios:

1. `stable_closed_v2`
2. `shock_recovery`
3. `delayed_side_effect`
4. `safety_boundary_shift`
5. `reaction_surface_drift`
6. `hidden_fragility`
7. `high_opportunity_high_risk`

Each scenario runs for at least ten steps for all three baselines and all requested seeds.

## Transition logic

Moderate appropriate execution can improve stability and reduce risk. Over-action increases fatigue, risk, relation lock, and hidden fragility. Repeated stabilize-like action can grow relation lock and reduce exploration capacity. Cooldown and rollback reduce risk or fatigue but may sacrifice short-term gain. No action avoids direct safety violations but can miss opportunities and allow pressure-driven risk accumulation. Scenario-specific shocks, safety-boundary shifts, delayed side effects, and reaction-surface drift are applied through bounded state updates.

## Evaluation metrics

The runner reports short-term gain, safety violation, over-action, missed opportunity, delayed side-effect cost, recovery score, time to recover, relation lock, exploration-capacity retention, and audit pass rate. Robustness scoring is bounded in `[0.0, 1.0]` and prioritizes low safety violation, low over-action, low final risk, high recovery, low relation lock, high exploration retention, and high audit pass rate rather than cumulative gain.

## Output tables

The main result object contains six DataFrames:

- `closed_loop_step_long`
- `closed_loop_episode_summary`
- `closed_loop_baseline_comparison_summary`
- `closed_loop_scenario_breakdown`
- `closed_loop_audit_boundary_summary`
- `closed_loop_preflight_summary`

## Expected result patterns

`NO_ACTION` should show low direct safety violation, low or zero action mass, high missed opportunity in safe opportunity cases, and weak recovery under shock or external pressure.

`V2_GREEDY_OPTIMIZER` should show strong short-term gain in stable/closed conditions, with higher risk of over-action under drift, delayed side effects, and safety-boundary shifts, plus possible fatigue and relation-lock growth.

`ACTION_MODULE_RC1` may have lower short-term gain, but should reduce harmful execution and over-action, preserve recovery capacity better under shock, reduce delayed side-effect cost, preserve exploration capacity better than greedy, and pass no-write audit boundaries.

## Success conditions

- Closed-loop runner executes multiple steps.
- All three baselines run on the same scenarios.
- At least seven scenario types are covered.
- Greedy is not artificially weak.
- `NO_ACTION` is meaningful as a baseline.
- `ACTION_MODULE_RC1` shows at least one robustness advantage under stress.
- Results are interpretable from output tables.
- Safety, over-action, recovery, relation lock, exploration retention, and audit metrics are reported.
- Production runtime is unchanged.
- Canonical writeback is not performed.
- No real coefficient update is performed.

## Failure conditions

- The runner only checks that code executes.
- There is no baseline comparison.
- Greedy is artificially weak.
- `NO_ACTION` is not meaningful.
- No drift, shock, delayed side effect, or safety-boundary shift exists.
- Only short-term gain is measured.
- Safety violation and over-action are not measured.
- Recovery is not measured.
- Exploration-capacity retention is not measured.
- No-write audit boundaries are missing.
- Production files are modified.
- Canonical state is written.
- The task turns into a full v3 implementation.

## No-write boundaries

This task remains test-local. It does not update production runtime files, real coefficients, canonical state, v2 dynamics files, ActionPlanner, ActionModule, ParameterBox, or ShadowBox. The audit summary explicitly reports coefficient changes, production runtime changes, canonical writeback, fixed-candidate runtime coefficient use, shadow-adjustment runtime default use, scenario-label-controlled logic, and production runtime modification.

## Excluded scope

This is not the full v3 pseudo-open system. It includes controlled RC1 drift and stress in a minimal pseudo-reality loop only. It does not add new production architecture, controllers, gates, rollback mechanisms, parameter update paths, canonical writeback, or ActionModule internals.

## Next phase options

After this task, we should know whether `action_module_step(...)` can be connected to a pseudo-reality transition loop, whether the loop can run multiple steps, whether `NO_ACTION`, `V2_GREEDY_OPTIMIZER`, and `ACTION_MODULE_RC1` can be compared fairly, whether greedy wins or ties short-term gain where expected, and whether `ACTION_MODULE_RC1` shows safety/recovery/robustness advantages under stress.

If results are meaningful, proceed toward Closed Loop Runner RC1 Freeze. If the results show that richer open-system dynamics are needed, proceed toward v3 Pseudo-Open System Design.
