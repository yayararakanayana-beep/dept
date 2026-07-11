# Task 3.1f-3 Results

## Local validation

- Targeted Task 3.1f tests executed: 28 passed.
- Positive coverage includes formal 49-run plan expansion, multi-rank smoke execution, all seven initializations per smoke rank, independent lock creation, one-standard-error selection, deterministic grouped subsets, and required artifact production.
- Negative coverage includes missing seed, forged convergence, modified basis hash, and producer-created lock rejection.

## Smoke artifact

Local smoke artifact path during testing was generated under pytest temporary directories. GitHub Actions uploads the artifact as `task3-1f3-stage-bc-smoke` and includes `selection_audit.json`, `selection_lock.json`, `artifact_manifest.json`, and Stage B/C CSV/JSON outputs.

Artifact ID, workflow run ID, and GitHub artifact digest are not available from local execution; these are populated by the CI run after the pull request is opened.

## Holdout access

Holdout was not accessed. Stage B/C runner interfaces accept only fit and validation inputs, and the independent selection lock records `holdout_accessed: false`.

## Scientific status

No final scientific Task 3.1f rank result was produced. The smoke result is a reduced-scale workflow validation only and must not be interpreted as the formal Task 3.1f selected rank.

## Unresolved items

- Full formal Stage B/C execution on the full corpus is deferred to Task 3.1f-4.
- Holdout evaluation remains out of scope until after an independently validated formal `selection_lock.json` exists.
