# AGENTS.md

## Repository Purpose

This repository is intended to serve as a closed-loop verification codebase for DEPT2 / H-DEPT.

At the current stage, the repository should be treated as a minimal scaffold. Do not assume that the runtime architecture, module boundaries, or verification protocol are fully implemented unless they are explicitly documented in committed files.

## General Working Rules

- Do not break existing specifications or documented behavior.
- Do not introduce large redesigns without first proposing the design and waiting for approval.
- Keep changes small, explicit, and compatible with the current scaffold stage.
- When changing implementation behavior, add or update tests that cover the change.
- If Python tests are added, use `pytest`.

## Canonical Codex Instruction Rule

- `CODEX_INSTRUCTION_STANDARD.md` is the single source of truth for drafting Codex implementation instructions for this repository.
- Before producing any Codex instruction, implementation contract, repair instruction, or Codex handoff, read that file and instantiate its required sections for the current task.
- Do not draft a Codex instruction from memory, from a previous task, or from an abbreviated local pattern.
- Do not deliver the instruction until the mandatory shortcut audit in that file is complete.

## Task 3.1f Frozen Contract

- `docs/task3_1f_stable_structure_extraction/TASK3_1F_SCOPE_FREEZE.md` and its listed companion files are the source of truth for Task 3.1f.
- Do not change Task 3.1f methods, rank grid, seeds, thresholds, weighting, split roles, holdout procedure, outputs, validation gates, or scope without explicit user approval.
- When a change appears necessary, stop and report the conflict, the smallest proposed change, and its effect before editing the frozen contract or implementation.
- Do not use holdout data before an independently validated `selection_lock.json` exists.
- Do not switch rank, model family, threshold, or preprocessing after seeing holdout results.
- Task 3.1f structures remain unnamed geometric structures until Task 3.1g semantic auditing.

## RC1 Freeze Archive Handling

- Keep `DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip` as a frozen reference archive unless a task explicitly says to replace it.
- Do not expand the archive into the repository as part of archive-registration or documentation-only work.
- Do not commit bulk-expanded archive contents; avoid giant diffs by migrating only small, reviewed slices in future PRs.
- Read `DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Handoff.md` when it is present before planning implementation work derived from the archive.
- Treat archive extraction as a local review/planning step unless the requested task explicitly includes migrating selected files into the active codebase.

## DEPT2 / H-DEPT Closed-Loop Constraints

- Exploration modules must not update the Parameter Box directly.
- Parameter Box updates are limited to pressure from an upper layer.
- Exploration modules are limited to candidate generation, sandbox evaluation, and adoption judgment.
- Exploration module update frequency must be determined functionally from system state, entropy, residuals, and ambiguity.
- Fixed reference values must be read from the Parameter Box.
- Action modules must not directly access DEPT internals.
- Action modules must be treated as one-way actuators / translators.
- Watch audit work is an observation and analysis layer only; it must not become a controller, gate, actuator, or parameter update path.
- Task20f no-write dry-run proposals are proposal-only summaries and must not become controllers.
- Task20G pre-commit readiness audits are no-write evidence checks only and must not become controllers, gates, rollback mechanisms, or parameter update paths.
- No-write dry-run proposal generation is not a commit gate.
- Proposal candidates and readiness audits must not write to canonical parameters, G/K, world state, or ActionModule internals.

## Documentation and Implementation Discipline

- Prefer documenting assumptions before encoding them in implementation.
- Avoid over-specifying behavior that is not yet implemented.
- Keep README updates aligned with the actual repository state.
- Do not create `src/` or `tests/` contents unless the requested task explicitly includes implementation or tests.

## Task20H / Task20I Boundaries

- Task20H minimal evidence extraction is evidence-only and must not migrate RC1 runtime code.
- Task20I readiness re-run is not a commit gate and must not enable parameter updates.
- Extracted evidence must remain small, bounded, and reviewable.
## Task20J Boundary

- Task20J freezes the no-write parameter-adoption precheck contract.
- It classifies lower-parameter update candidates into blocked / watch_only / shadow_trial_candidate / commit_candidate without allowing canonical ParameterBox writes.
- Task21 may read the contract but must remain no-write unless a later explicit task changes that boundary.
## Task22 Boundary

- Task22 may run `python validation/task22_controlled_canonical_parameter_update_rc1.py` to attempt existing-runner execution before comparing `update_off`, `controlled_update_on`, `forced_bad_update_rollback`, and `real_watch_only_candidates`.
- Task22 declares `pandas` in `requirements.txt` for frozen RC1 runner execution, but must still report `passed: false` when the existing runner cannot execute; synthetic metrics or fixed-zero boundary flags must not produce a passing validation.
- Task22's intended canonical update scope is limited to bounded in-run lower ParameterBox state only.
- G/K writeback, world direct write, ActionModule internal DEPT connection, and ActionFrame direct generation boundaries remain closed.
- Task22 is not a Parameter Shadow Box redesign or Task21 classifier rebuild; Task21 real `watch_only` candidates must not be canonically updated.

## Task 3.2 Macro-Dynamics Exploration Boundaries

- `docs/task3_2_macro_dynamics_exploration/TASK3_2_1_SCOPE_FREEZE.md` and `configs/task3_2_1_macro_dynamics_contract.json` are the Task 3.2-1 source of truth.
- Task 3.2 is an exploratory six-task sequence. Keep the task count and order fixed unless the user explicitly changes them.
- Task 3.2-1 freezes the data boundary only: prediction input is `X_t + L_t`, raw logs are canonical, future truth is separated, and dataset splits are trajectory-level.
- Do not freeze terrain, flow, circulation, viscosity, diffusion, external-force, or other macro-dynamics components before the exploration results justify them.
- Full next-state reconstruction is secondary. The primary prediction purpose is early high-risk detection, irreversibility, risk depth, and actionable time-window estimation.
- Task 3.2-1 must not construct formal G_t/K_t, classify game structures, connect the Action Module, or claim that a macro-dynamics representation is validated.
- Task 3.2-2 may generate small continuous v3.3 trajectory corpora, but it must not modify the world dynamics to manufacture target outcomes.
- Task 3.2-2 scenario IDs are provenance only and must not be included in model input or copied directly into truth labels.
- Task 3.2-2 provisional risk scores and outcome labels are exploratory diagnostics, not frozen risk definitions or game-structure classes.
- Task 3.2-2 must preserve full raw state arrays, observed external inputs, future-truth isolation, and trajectory-level split integrity.
