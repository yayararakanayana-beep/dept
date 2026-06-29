# Task20j Next Evidence Request Manifest

## 1. Purpose

Task20j defines the next minimal evidence request needed before re-running guard readiness with more detailed RC1 validation evidence. This task creates a manifest only; it does not extract files from the RC1 archive.

## 2. Why More Evidence Is Needed

Task20b, Task20c, and Task20f currently rely on compact Task17 / Task18 summaries. Those summaries are enough for design discussion, but Task20g and Task20i conservatively treat them as insufficient for gate readiness because they lack per-case, per-cycle, and contribution-level detail.

## 3. Extraction Target Candidates

The next PR should consider extracting only small CSV/JSON summaries, preferably fewer than 10 files total:

- Task17 per-case stress matrix.
- Task17 per-cycle metric timeline.
- Task17 watchlist rows.
- Task18 ablation matrix.
- Task18 delta vs baseline.
- Task18 interpretation summary.

## 4. Needed Evidence by Watch Item

- `coactivation_dampen_zone`: per-cycle coactivation gate rows, action candidate rows, shadow confirmation rows, and audit correlation rows.
- `residual_noise_high`: residual/noise ledger per-cycle rows, sustained versus transient noise classification, and unresolved residual carryover rows.
- `shock_recovery_window`: shock onset, shock peak, return-to-baseline, and recovery stability window rows.
- `noise_ledger_exploration_gate_relationship`: per-case ablation rows, noise ledger contribution rows, exploration projection contribution rows, coactivation gate modulation rows, and sidecar boundary confirmation rows.

## 5. Needed Evidence by Proposal Candidate

- `T20F-P01-coactivation_dampen_zone`: Task17 coactivation gate and action candidate evidence.
- `T20F-P02-residual_noise_high`: Task17 residual/noise ledger and carryover evidence.
- `T20F-P03-shock_recovery_window`: Task17 shock timing and recovery stability evidence.
- `T20F-P04-noise_ledger_exploration_gate_relationship`: Task18 ablation contribution and sidecar boundary evidence.

## 6. Extraction File Count Limit

The next extraction should stay within 10 files total. Prefer CSV or JSON summary files. If a candidate file is very large, extract a smaller reviewed slice instead of importing the full artifact.

## 7. Do Not Extract

- RC1 runtime/body code.
- Bulk-expanded zip contents.
- Large intermediate generated artifacts.
- Full execution logs.
- Files that imply canonical writes, G/K writeback, world writes, or ActionModule internal coupling.

## 8. Recommended Next PR Tasks

- Task20k: minimal evidence extraction from this manifest.
- Task20l: guard readiness re-run with extracted detail.
- Task20m: candidate pruning / retention report.

## 9. Boundary Rules

Task20j is a manifest-only planning step. It does not extract RC1 files, implement commit gate logic, enable rollback, update parameters, write to G/K, write to world state, connect ActionModule internals, or act as a controller.
