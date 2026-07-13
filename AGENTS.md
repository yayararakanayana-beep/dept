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
- Task 3.2-3 is limited to five simple baselines: always-safe, current-risk threshold, current-state logistic, trend extrapolation, and history logistic.
- Task 3.2-3 may use same-seed stable trajectories only on the truth-calibration side; stable-reference future data must never enter model features.
- Task 3.2-3 feature matrices must exclude scenario ID, seed, split, future inputs, future states, truth labels, and outcome fields.
- Task 3.2-3 must create and validate `selection_lock.json` before opening any holdout state or metrics file.
- After holdout evaluation, Task 3.2-3 model family, feature set, history width, horizon, threshold, and alarm persistence must not change.
- Task 3.2-3 results are comparison baselines for Task 3.2-4; they do not validate macro-dynamics, irreversibility, game structures, or action readiness.
- Task 3.2-4 challenge schedules must vary by seed in disturbance timing, duration, magnitude, composition, residual burden, or relapse; repeating one fixed schedule across seeds is not a valid challenge corpus.
- Task 3.2-4 preprocessing, random projections, PCA bases, delay bases, and dynamics matrices must be fitted on fit data only. Validation and holdout may only be transformed.
- Task 3.2-4 may use only observed external inputs through time t. Multi-step DMDc forecasts must use an explicitly documented current-input persistence assumption, never actual future inputs.
- Task 3.2-4 must keep DMD/DMDc/Hankel residual modes neutrally named. Do not rename modes as terrain, circulation, viscosity, diffusion, or external force without later evidence.
- Task 3.2-4 unexplained residuals must remain in a residual ledger and must not be forced into known macro-dynamics components.
- Task 3.2-4 must compare against both the original Task 3 locked structure and a fair Task 3 structure retrained on challenge fit data.
- Task 3.2-4 must create and validate its own selection lock before opening challenge holdout state files. Post-holdout candidate switching is forbidden.
- Task 3.2-4 is a minimal feasibility probe only. It must not construct formal G_t/K_t, freeze the dynamic relation field, classify game structures, prove irreversibility, or connect the Action Module.
- Task 3.2-4.1 is an internal extension of Task 3.2-4; it does not add a seventh top-level Task 3.2 stage.
- Task 3.2-4.1 counterfactual branches must be created as new world instances from immutable persisted snapshots. They must not write back to source trajectories, canonical world state, G/K, the Parameter Box, or ActionModule internals.
- Task 3.2-4.1 probes may use only the existing observed external-factor interface. Direct state-array manipulation is allowed only while restoring the saved snapshot into a new branch world, never as an intervention.
- Task 3.2-4.1 safe-region calibration must use fit-split stable-reference trajectories only. Validation and holdout must not redefine the safe region.
- Task 3.2-4.1 irreversibility levels are conditional on the tested probe set, action budget, time horizon, and recovery threshold. They are not universal or real-world irreversibility proofs.
- Task 3.2-4.1 may use simultaneous changed input axes as a coordination-scale proxy, but must not call it a measured player count.
- Task 3.2-4.1 branch outcomes, escape costs, recovery probabilities, reachable values, reachable ranges, action windows, refixation, and shrinking-equilibrium labels are future-side truth only and must not enter predictor features.
- Task 3.2-4.1 must create and independently validate its selection lock before opening holdout snapshot state files or running holdout branches. Post-holdout predictor switching is forbidden.
- If PseudoReality v3.3 does not generate structural variation or shrinking equilibrium under the tested probes, Task 3.2-4.1 must report world-model/probe-set insufficiency rather than manufacturing positive labels.

## Task 3.2-3 Rev1 Phase 1 Boundary

- `configs/task3_2_3_rev1_contract.json` and `docs/task3_2_macro_dynamics_exploration/TASK3_2_3_REV1_PHASE1_CONTRACT.md` are the source of truth for Task 3.2-3 Rev1 Phase 1.
- Phase 1 is contract-only. It must not generate a new corpus, implement or train a model, select a candidate, or read validation/holdout state data.
- Task 3 Rev1 remains a local/history early-warning probe. It must not import Task 4 macro features, use Task 4.1 counterfactual truth for fitting or selection, construct formal G_t or a relation field, classify game structures, prove irreversibility, or select actions.
- Information levels I0 through I4 must differ only by their declared currently observed information groups. Scenario ID, trajectory ID, seed, split, absolute step/time, generator regime names, future information, truth, and final outcomes are forbidden model inputs.
- Unknown-condition evaluation must split schedule templates, background regimes, and world-parameter profiles across fit/validation/holdout. A seed-only split with repeated schedules is not an out-of-distribution test.
- Information levels must be compared on identical eligible windows and each prediction horizon must be evaluated separately. A weighted scalar score must not select across different horizons.
- Task 4.1 truth may be used only by a later blind post-selection audit under a separately approved contract.
- Stable selection identity must exclude metrics, timestamps, workflow/artifact IDs, and absolute paths. Two identical pre-holdout reruns must produce the same selection identity before holdout can be opened.

## Task 3.2-3 Rev1 Phase 2 Boundary

- `configs/task3_2_3_rev1_phase2_pilot.json` and `docs/task3_2_macro_dynamics_exploration/TASK3_2_3_REV1_PHASE2_PILOT_AUDIT.md` are the source of truth for Task 3.2-3 Rev1 Phase 2.
- Phase 2 is a pilot-corpus feasibility audit only. It may generate disposable pilot trajectories and inspect all pilot splits, but those trajectories, seeds, schedules, backgrounds, and world-parameter profiles must not be reused in later formal fit, validation, or holdout data.
- Phase 2 observed outcomes must be recomputed from persisted raw state arrays against a raw stable reference with matching split, seed, background regime, and world-parameter profile. Generator scenario names, intended families, `summary.json`, `truth.jsonl`, and `metrics.jsonl` must not define or change recomputed outcomes.
- Source provisional labels may be compared only after the recomputed outcome payload is frozen and hashed. That comparison is diagnostic only.
- Schedule templates, background regimes, world-parameter profiles, and seeds must be disjoint across pilot splits. A seed-only split is invalid.
- Same-current/opposite-future pairs must have identical raw state-array content at the frozen cutoff. Failure to produce different observed futures is a corpus/world insufficiency result and must not be repaired by changing labels.
- Windows from one trajectory must not count as independent samples. Prevalence, variance, bootstrap intervals, and formal-count recommendations use trajectory units.
- Phase 2 must preserve unresolved outcomes and missing support. It must not insert sentinel counts, force missing outcome families, or declare formal-corpus readiness when a required family or anchor/horizon support is absent.
- Phase 2 must not implement predictor features, train or select models, create a selection lock, generate a formal corpus, import Task 4 features, use Task 4.1 truth, construct formal G_t or a relation field, classify game structures, prove irreversibility, or connect the Action Module.
