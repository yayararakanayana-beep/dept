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

- There is no implementation code yet.
- There are no test files yet.
- There is no runtime entrypoint yet.
- There is no dependency file yet.
- The current focus is to establish repository-level working rules and a human-readable project overview.

## RC1 Freeze Archive

`DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip` is registered in this repository as a frozen RC1 archive for DEPT2 FullSpec Integrated Closed Loop Runner work.

The zip is a reference artifact only. The expanded code from the archive has not been imported as the canonical working-tree implementation, and this scaffold should not treat extracted files as authoritative until they are reviewed and migrated deliberately.

`DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Handoff.md`, when present, records the human-readable handoff notes for the archive and should be read before planning follow-up implementation work.

In the next phase, any verification or migration from the archive should happen through small, reviewable PRs that select a limited scope, add or update tests where behavior changes, and avoid bulk archive extraction in the committed diff.

`docs/task20b_watch_audit_design.md` documents the design-only Task20b watch audit for decomposing Task17 and Task18 watch items before any commit proposal or commit gate work.

Run the minimal Task20b watch audit with `python validation/task20b_watch_audit.py`; it writes compact summaries under `results/task20b_watch_audit/` and reports `missing_input` instead of failing when Task17 / Task18 result files are not present.

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
