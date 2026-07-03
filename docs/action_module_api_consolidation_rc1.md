# Action Module API Consolidation RC1

## Purpose

Action Module API Consolidation RC1 defines a test-local action-module API layer around already validated policy and audit helpers. Its central callable is `action_module_step(...)`, which accepts prepared inputs, builds an `ActionContext`, computes a functional policy, proposes action candidates, applies safety projection, selects one conservative action decision, emits an audit record, and returns a history-update payload.

## Position After 21C-E

Phase 2G-21C-E is frozen. It consumed 21C-D shadow validation outputs, converted only accepted shadow candidates into limited update proposal candidates, revalidated those proposals as fixed or blocked candidates, and emitted an Action Module API handoff contract. This RC1 layer reads that handoff contract as a boundary document only. Fixed update candidates remain review artifacts and are not runtime coefficients.

## Why This Is One Task

This task is the narrow consolidation step between frozen validation helpers and later closed-loop runner integration. It is intentionally one step because it only wraps validated, test-local helpers into a callable function group. It does not connect to pseudo reality, does not run repeated steps, and does not introduce production runtime behavior.

## Inputs and Outputs

Prepared inputs are:

- `prepared_upper_pressure`
- `prepared_lower_state`
- `prepared_observation_view`
- `action_history`
- optional `parameter_snapshot`
- optional `guardrail_snapshot`
- optional `handoff_contract`
- optional `label_override` for audit labeling only

The output is an `ActionModuleStepResult` containing:

- `ActionContext`
- `FunctionalPolicyOutput`
- action candidates
- projected action candidates
- `ActionDecision`
- `ActionAuditRecord`
- `ActionHistoryUpdate`

## Strict Boundaries

The RC1 API is test-local. It does not modify 21B-B coefficients, `functional_insurance_policy`, v2 dynamics, ActionPlanner, ActionModule, ParameterBox, ShadowBox, or production runtime files. It performs no canonical writeback and applies no real coefficient changes. Scenario labels are stored only as audit labels and never control action logic.

The layer also refuses to treat these artifacts as runtime defaults:

- 21C-E fixed update candidates
- 21C-D shadow adjustment values
- rejected candidates
- hold candidates
- artificial probe candidates

## Relationship to the 21C-E Handoff Contract

When a handoff contract is not supplied, `build_action_context(...)` loads `freeze_21c_verification_results().functional_policy_action_module_handoff_contract`. The contract is copied into the context and later summarized as handoff flags in the audit record. The contract can authorize wrapping the functional policy, but it cannot authorize coefficient writes, runtime writes, rejected-candidate use, hold-candidate use, artificial-probe defaults, or scenario-label control.

## Dataclasses

The API defines frozen dataclasses for the whole step:

- `ActionContext`
- `FunctionalPolicyOutput`
- `ActionCandidate`
- `ProjectedActionCandidate`
- `ActionDecision`
- `ActionAuditRecord`
- `ActionHistoryUpdate`
- `ActionModuleStepResult`

Frozen dataclasses make the test-local contract explicit and help verify that the function returns a payload rather than mutating caller-owned state.

## Function Flow

`action_module_step(...)` executes exactly one deterministic flow:

1. `build_action_context(...)`
2. `compute_functional_policy(...)`
3. `propose_action_candidates(...)`
4. `apply_action_safety_projection(...)`
5. `select_action_decision(...)`
6. `build_action_audit_record(...)`
7. `build_action_history_update(...)`
8. return `ActionModuleStepResult`

It does not contain a multi-step loop.

## Decision Priority

The decision layer is conservative:

1. strong rollback condition selects `ROLLBACK`
2. strong cooldown condition selects `COOLDOWN`
3. low fire permission selects `NO_OP`
4. safe projected execution candidate may select `EXECUTE`
5. missing or weak evidence selects `HOLD_FOR_EVIDENCE`
6. otherwise select `NO_OP`

Execution is never the default and requires a safe projected candidate.

## Safety Projection Rules

Safety projection keeps projected action mass within the functional policy cap and guardrail cap. It rejects blocked channels, weakens or blocks normal execution under cooldown pressure, blocks normal execution when rollback is prioritized, and rejects normal execution when evidence is missing or weak. Each projected candidate includes a projection reason.

## Audit Requirements

The audit record includes policy, candidate, projection, and decision summaries. It records no-write boundary flags:

- `coefficient_changed = False`
- `production_runtime_changed = False`
- `canonical_writeback_performed = False`
- `fixed_candidate_used_as_runtime_coefficient = False`
- `shadow_adjustment_used_as_runtime_default = False`
- `rejected_candidate_used = False`
- `hold_candidate_used = False`
- `artificial_probe_used = False`
- `scenario_label_controlled_logic = False`

`audit_passed` is true only when these boundary flags remain safe.

## History Update Behavior

`build_action_history_update(...)` returns a payload containing the latest decision type, selected channel, selected mass, cooldown-state update, rollback-state update, and audit trace id. It does not mutate the caller-provided `action_history`.

## What Is Not Included

This RC1 task does not include:

- multi-step closed-loop runner behavior
- pseudo-reality connection
- production runtime file changes
- canonical state writes
- real coefficient updates
- ParameterBox or ShadowBox changes
- ActionPlanner or ActionModule changes

## Success Conditions

Success means `action_module_step(...)` exists; all required dataclasses exist; prepared inputs become an `ActionContext`; `functional_insurance_policy` is wrapped without modification; candidates are generated and projected; final decision selection is conservative; an audit record and history-update payload are returned; 21C-E handoff boundaries are respected; production runtime files are unchanged; canonical writeback is not performed; and no multi-step runner is implemented.

## Failure Conditions

Failure includes missing `action_module_step(...)`, policy coefficient changes, use of fixed or shadow candidates as runtime coefficients, rejected/hold/artificial probe candidates entering action defaults, scenario labels controlling decisions, missing safety projection, `EXECUTE` without a safe projected candidate, missing audit or history update, production runtime modifications, canonical state writes, or embedding a multi-step closed-loop runner in this task.

## Next Phase: Closed Loop Runner Integration

The next task is **Closed Loop Runner Integration**. That later phase may connect `action_module_step(...)` to the pseudo-reality system and run one-step or multi-step closed-loop validation under explicitly approved boundaries.
