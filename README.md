# dept

## Overview

This repository is intended to become a closed-loop verification codebase for DEPT2 / H-DEPT.

The goal is to provide a place where assumptions, candidate behaviors, evaluation procedures, and adoption decisions can be checked in a controlled loop before being treated as part of a stable system.

## Position of DEPT2 / H-DEPT

DEPT2 / H-DEPT is treated here as the target system family for closed-loop verification work. This repository is not yet a complete implementation of DEPT2 or H-DEPT. Instead, it is the minimal foundation for organizing the verification code, documentation, and future tests around that purpose.

The repository should therefore avoid premature architectural commitments. Specifications should be documented before they are encoded in implementation.

## Current Stage

This repository is currently in a scaffold / minimal foundation stage.

At this stage:

- The repository contains small validation scripts and pytest coverage for documented audit tasks.
- There is no runtime entrypoint yet.
- There is no dependency file yet.
- The current focus is to keep audit behavior explicit and no-write while documenting repository-level working rules.

## RC1 Freeze Archive

`DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip` is registered in this repository as a frozen RC1 archive for DEPT2 FullSpec Integrated Closed Loop Runner work.

The zip is a reference artifact only. The expanded code from the archive has not been imported as the canonical working-tree implementation, and this scaffold should not treat extracted files as authoritative until they are reviewed and migrated deliberately.

`DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Handoff.md`, when present, records the human-readable handoff notes for the archive and should be read before planning follow-up implementation work.

In the next phase, any verification or migration from the archive should happen through small, reviewable PRs that select a limited scope, add or update tests where behavior changes, and avoid bulk archive extraction in the committed diff.

`docs/task20b_watch_audit_design.md` documents the design-only Task20b watch audit for decomposing Task17 and Task18 watch items before any commit proposal or commit gate work.

Run the minimal Task20b watch audit with `python validation/task20b_watch_audit.py`; it writes compact summaries under `results/task20b_watch_audit/` and reports `missing_input` instead of failing when Task17 / Task18 result files are not present.

Task20d documents a watch-audit interpretation report in `docs/task20d_watch_audit_interpretation_report.md`, and Task20e documents proposal-only commit proposal candidate design in `docs/task20e_commit_proposal_candidate_design.md`. These documents prepare future review without implementing commit gates, rollback gates, parameter updates, or actuator connections.

Run the Task20f no-write dry-run proposal summary with `python validation/task20f_no_write_dry_run_proposal.py`; it reads `results/task20b_watch_audit/watch_audit_summary.json`, writes proposal-only summaries under `results/task20f_no_write_dry_run/`, keeps `no_write` true, and leaves all boundary checks false.

Run the Task20G pre-commit readiness audit with `python validation/task20g_pre_commit_readiness_audit.py`; it reads `results/task20f_no_write_dry_run/proposal_summary.json`, writes readiness summaries under `results/task20g_pre_commit_readiness/`, records that compact summaries are insufficient for commit-gate implementation, keeps every candidate `gate_ready` false, and lists the next minimum evidence required for review.

Run the Task20H minimal evidence extraction with `python validation/task20h_minimal_evidence_extraction.py`; it scans the RC1 freeze archive without bulk extraction and writes a bounded evidence index under `results/task20h_minimal_evidence/`.

Run the Task20I readiness re-run with `python validation/task20i_readiness_rerun_with_evidence.py`; it reads the Task20G readiness summary and Task20H evidence index, writes conservative no-write results under `results/task20i_readiness_rerun/`, and does not implement a commit gate or parameter update.

## Purpose of Closed-Loop Verification

Closed-loop verification is intended to check how a system behaves when outputs, evaluations, and adoption decisions feed back into later steps.

For this repository, the verification loop is expected to remain controlled and explicit. In particular, exploration-related logic should be separated from direct Parameter Box updates, and action-related logic should be treated as one-way actuator / translator behavior rather than direct access to DEPT internals.

## Planned Structure

Future changes may introduce a small structure such as:

```text
src/        # implementation modules, once the minimal interfaces are defined
tests/      # pytest-based tests for implemented behavior
examples/   # small runnable examples for closed-loop verification flows
docs/       # additional design notes or protocol descriptions, if needed
```

This structure is only a planned direction. It should not be treated as a finalized architecture until the relevant files and interfaces are introduced explicitly.

## Development Notes

- Keep changes small and compatible with the current scaffold stage.
- Avoid large redesigns without proposing them first.
- Add or update tests when implementation behavior changes.
- Use `pytest` for Python tests when tests are introduced.
Run the Task20J gate contract freeze with `python validation/task20j_gate_contract_freeze.py`; it freezes the no-write parameter-adoption precheck contract and classifies lower-parameter update candidates into `blocked` / `watch_only` / `shadow_trial_candidate` / `commit_candidate` without allowing canonical ParameterBox writes.
## Task22 Controlled Canonical Parameter Update RC1

Run Task22 with `python validation/task22_controlled_canonical_parameter_update_rc1.py`. The current Task22 report attempts to execute the existing RC1 closed-loop runner from the frozen archive before any bounded canonical lower-ParameterBox update can be validated; `requirements.txt` declares `pandas` as the minimal dependency needed by that runner path. If runner execution is blocked by missing dependencies or import/runtime issues, Task22 records `task22_status: blocked_by_runner_execution` and `passed: false` instead of using synthetic metrics. G/K writeback, world direct writes, ActionModule internal DEPT access, and ActionFrame direct generation remain closed. Task22 is not a Parameter Shadow Box redesign or Task21 classifier rebuild, and Task21 real `watch_only` candidates are not canonically updated.

