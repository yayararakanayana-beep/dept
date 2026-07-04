# Action Module API v2 Alignment and Open-System Stress Audit RC1

## Purpose

This document describes the test-local RC1 audit for the consolidated `action_module_step(...)` API. The audit checks whether the one-step Action Module API remains compatible with the observed v2 action surface and whether it is more robust than visible short-term optimization under controlled pseudo-open-system drift.

The goal is not to optimize directly for the closed v2 action surface. The goal is to verify that the action module does not dangerously contradict v2, and that it is more robust than visible-surface greedy optimization when controlled pseudo-open-system drift is introduced.

## Position after Action Module API Consolidation RC1

Action Module API Consolidation RC1 introduced a test-local `action_module_step(...)` surface that builds an action context, computes a functional policy, proposes candidates, safety-projects candidates, selects a conservative decision, emits audit records, and returns history-update payloads. This audit does not replace that API and does not modify production runtime files.

## Why v2 Alignment Is Needed

The v2 action surface is the currently observed synthetic reference for safe ranges, harmful thresholds, preferred channels, acceptable channels, and visible short-term response. An action API that strongly contradicts v2 could execute harmful mass, ignore safe bounds, miss clear safe opportunities without justification, or choose channels that are inconsistent with observed response evidence.

The alignment audit therefore checks representative v2 cases for:

- selected decision type;
- selected channel and action mass;
- safe range compliance;
- harmful execute violations;
- missed safe opportunities;
- channel alignment class;
- cooldown, rollback, and hold-for-evidence reasonableness;
- no-write audit boundary pass status.

## Why v2 Alone Is a Closed-System Check

v2 is a closed synthetic action surface. A greedy optimizer that can see the current v2 response table can often maximize immediate visible gain. That makes v2 useful as a contradiction check, but insufficient as the sole success criterion for the Action Module.

If the module were judged only by short-term v2 gain, it could be pushed toward brittle over-action that performs well before drift but fails when the response surface shifts, hidden state appears, delayed side effects accumulate, safety boundaries tighten, or an external field shock enters the system.

## Why Short-Term Optimization Is Not the Goal

The Action Module should not merely be a short-term optimizer over a visible closed surface. It should preserve safety, recovery capacity, and audit boundaries when conditions shift. The audit therefore allows the greedy optimizer to be strong on closed v2 gain and evaluates whether `ACTION_MODULE_RC1` shows any robustness advantage under stress.

## Comparison Groups

### NO_ACTION

A no-intervention baseline:

- `decision_type = NO_OP`
- `selected_channel = None`
- `selected_action_mass = 0.0`

It should have low direct safety violation, but should miss safe positive opportunities and produce low short-term gain.

### V2_GREEDY_OPTIMIZER

A short-term optimizer over visible v2 information only. It chooses the channel with the highest visible short-term gain and a mass near the visible expected/safe mass. It cannot see hidden state, future surface shifts, delayed costs, future safety-boundary movement, or future external shocks.

This baseline is intentionally not weakened; it is expected to perform strongly on closed v2 immediate gain.

### ACTION_MODULE_RC1

The system under test. It calls `action_module_step(...)` and evaluates the returned decision and audit flags. It may have lower short-term gain than the greedy optimizer, but should reduce harmful execution, over-action, delayed side-effect cost, recovery failure, drift-after-shift damage, and audit boundary violations.

## Stress Types

The audit includes five controlled pseudo-open-system stress types:

1. `reaction_surface_shift` — changes channel gains after the visible v2 decision point.
2. `hidden_state_noise` — introduces hidden fragility or instability invisible to the greedy optimizer.
3. `delayed_side_effect` — subtracts delayed cost after initially positive action.
4. `safety_boundary_shift` — tightens the safe action-mass range after decision selection.
5. `external_field_shock` — raises instability or lowers recovery independently of selected action.

These are small deterministic scoring windows, not a full pseudo-open-system implementation.

## Output Tables

The audit returns an `ActionModuleOpenStressAuditResult` with seven DataFrames:

1. `action_module_v2_alignment_long`
2. `action_module_v2_alignment_summary`
3. `action_module_baseline_comparison_long`
4. `action_module_baseline_comparison_summary`
5. `action_module_open_stress_long`
6. `action_module_open_stress_summary`
7. `action_module_open_stress_decision_audit`

## Scoring Logic

### v2 Alignment Score

The v2 alignment score is bounded to `[0.0, 1.0]`. It strongly penalizes harmful execution, unsafe mass, severe channel mismatch, unjustified missed safe opportunity, and unjustified cooldown/rollback overuse. It does not require short-term optimality.

### Closed v2 Gain

Closed v2 gain uses the visible channel response table, scales by selected mass relative to expected mass, and penalizes visible safe-range or harmful-threshold violations.

### Stress-Adjusted Gain

Stress-adjusted gain starts from visible v2 gain and applies deterministic drift effects. These effects include shifted channel gains, hidden fragility penalties, delayed side-effect costs, tightened safety bounds, and external instability penalties.

### Recovery Score

Recovery score rewards non-overaction under stress, appropriate rollback under shock/fragility, cooldown or hold under tightened boundaries or weak evidence, and moderate execution under safe conditions.

### Robustness Score

Robustness score is bounded to `[0.0, 1.0]` and prioritizes low safety violation, low over-action, low delayed side-effect cost, lower performance drop, and high recovery after shock. It does not primarily reward pure short-term gain.

## Success Conditions

The audit succeeds when:

- v2 alignment tables exist;
- open-system stress tables exist;
- all three baselines are present;
- the greedy optimizer is not artificially weak;
- `ACTION_MODULE_RC1` does not show high harmful execute violation on v2;
- `ACTION_MODULE_RC1` shows at least one robustness advantage over the greedy baseline under stress;
- short-term gain is not the only success metric;
- no-write audit boundaries pass;
- production runtime files remain unchanged;
- canonical writeback is not performed;
- no full closed-loop runner is implemented.

## Failure Conditions

The audit should fail if:

- the task only optimizes `action_module_step(...)` to v2;
- the greedy optimizer is artificially weakened;
- short-term gain is the only metric;
- pseudo-open-system stress is absent;
- harmful execute violation rate is high;
- fixed update candidates become runtime coefficients;
- shadow adjustment values become runtime defaults;
- scenario labels control logic;
- production runtime files are modified;
- canonical state is written;
- a full closed-loop runner is implemented in this task.

## What Is Not Included

This task does not implement the full closed-loop runner, the full v3 pseudo-open system, production runtime changes, ActionPlanner changes, ActionModule changes, ParameterBox changes, ShadowBox changes, v2 dynamics changes, real coefficient updates, canonical writeback, or production pseudo-reality state updates.

## Next Phase: Closed Loop Runner Integration

If the audit passes, the next phase can proceed to Closed Loop Runner Integration. That future phase should use the audit as evidence that `action_module_step(...)` is reasonably aligned with v2, avoids dangerous v2 contradictions, allows greedy optimization to win closed-v2 short-term gain where appropriate, and provides robustness advantages under controlled pseudo-open-system drift.
