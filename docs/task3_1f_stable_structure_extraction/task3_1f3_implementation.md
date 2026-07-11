# Task 3.1f-3 Implementation

Task 3.1f-3 adds a Stage B/C fit-validation batch path on top of the Task 3.1f-2 minimal extraction scaffold.

## Implemented path

- Formal run-plan construction reads the frozen rank grid and initialization seeds from `configs/task3_1f_structure_extraction_contract.json` and expands them to 49 primary KL-NMF runs.
- The Stage B/C smoke runner accepts only fit and validation bundles plus row maps; it has no holdout bundle or holdout row-map argument.
- Evaluation-only metadata is preserved in `evaluation_metadata.csv` and remains separate from the mass feature matrix.
- Smoke execution uses the same code path as the Stage B/C batch logic, reduced to the first two frozen ranks and a lower iteration cap.
- The batch path persists KL-NMF runs, weighted PCA references, weighted mean baseline metrics, component matches, rank summaries, structure summaries, perturbation diagnostics, Frobenius sensitivity metadata, and a selection candidate.
- The producer writes `selection_candidate.json` only. It does not certify the selection lock.
- A separate independent validator recomputes rank/seed coverage, hashes, convergence evidence, rank summaries, medoid/selection evidence, perturbation diagnostics, and lock eligibility before writing `selection_lock.json`.

## Smoke scale

Smoke profile:

- ranks: first two frozen ranks, 5 and 8;
- initializations per smoke rank: deterministic anchor plus all six frozen random seeds;
- maximum KL-NMF iterations: reduced for CI;
- formal scientific result: false;
- holdout accessed: false.

## Formal readiness

Formal run-plan construction is available and verifies the frozen 7 × 7 primary KL-NMF plan. The full 1,582-row formal run is intentionally not executed in pull-request CI and remains a Task 3.1f-4 GitHub Actions execution concern.

## Boundaries

- No holdout evaluation is implemented or executed.
- No Task 3.1g semantic naming is implemented.
- PCA and Frobenius references are persisted as references/diagnostics and do not affect primary rank selection.
- The frozen contract file is not modified.
