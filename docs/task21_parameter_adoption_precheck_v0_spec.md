# Task21 Parameter Adoption Precheck v0 Spec

## Purpose

Task21 reads the Task20J frozen no-write contract and classifies existing lower-parameter update candidates from Task20F/G/H/I. It is a classifier only: it records the candidate decision, reasons, missing evidence, and validation needed before any future shadow trial or formal review.

Task21 is not a parameter updater, commit gate, rollback gate, controller, actuator, or ActionModule bridge.

## Read-only Inputs

- `results/task20j_gate_contract_freeze/gate_contract_freeze.json`
- `results/task20f_no_write_dry_run/proposal_summary.json`
- `results/task20g_pre_commit_readiness/readiness_summary.json`
- `results/task20h_minimal_evidence/evidence_index.json`
- `results/task20i_readiness_rerun/readiness_rerun_summary.json`

Task21 must not overwrite these inputs.

## Outputs

- `results/task21_parameter_adoption_precheck_v0/precheck_decision_summary.json`
- `results/task21_parameter_adoption_precheck_v0/precheck_decision_summary.md`
- `results/task21_parameter_adoption_precheck_v0/precheck_validation_summary.json`
- `results/task21_parameter_adoption_precheck_v0/precheck_validation_summary.md`

## Classification Meanings

- `blocked`: adoption is unavailable because a hard blocker exists, such as a boundary violation, broken no-write condition, dangerous unknown target, strong counter-evidence, missing rollback path, irreversible write request, or suspected hidden parameter update.
- `watch_only`: continued observation is appropriate. The signal has review value, but target, direction, expected effect, evidence, or bounded trial details are too weak for shadow-trial classification.
- `shadow_trial_candidate`: canonical update remains forbidden, but a future no-write Parameter Shadow Box trial may be worth review because the target, direction, effect, minimum evidence, bounded update, rollback path, do-nothing risk, boundaries, and shadow-trial path are sufficiently supported.
- `commit_candidate`: future formal ParameterBox update review candidate only. Even here, Task21 remains no-write and cannot update parameters.

## Adoption Criteria

Each decision evaluates the Task20J criteria with `true`, `false`, or `unknown`:

- `target_parameter_is_clear`
- `update_direction_is_clear`
- `expected_effect_is_explainable`
- `minimum_evidence_exists`
- `counter_evidence_is_not_strong`
- `update_size_is_bounded`
- `rollback_path_exists`
- `do_nothing_risk_is_nontrivial`
- `boundary_violation_absent`
- `shadow_trial_is_possible`

Information gaps alone should usually produce `watch_only`, not `blocked`, unless they combine with a hard blocker or dangerous ambiguity.

## No-write Boundary

Task21 outputs must preserve:

- `no_write: true`
- `can_update_parameter: false`
- `can_write_gk: false`
- `can_write_world: false`
- `can_trigger_action_module: false`
- `parameter_update_implemented: false`
- `commit_gate_implemented: false`
- `rollback_gate_implemented: false`
- `action_frame_generation_implemented: false`

## Forbidden Behavior

Task21 must not update the canonical ParameterBox, write back to G/K, write world state, execute rollback, connect to ActionModule internals, generate ActionFrames, convert readiness into action, or implement a hidden threshold-based parameter update.

## Validation Viewpoints

Validation must confirm that the Task20J contract loads, all Task20F candidates appear, the decision enum is exactly `blocked`, `watch_only`, `shadow_trial_candidate`, and `commit_candidate`, no-write boundaries are held for every candidate, blocked decisions are based on hard blockers rather than missing evidence alone, commit candidates are not emitted without required safeguards, and the specification still leaves reachable paths for `shadow_trial_candidate` and `commit_candidate` when synthetic evidence satisfies their criteria.
