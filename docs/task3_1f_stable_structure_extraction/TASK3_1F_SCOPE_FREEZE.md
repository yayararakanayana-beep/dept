# Task 3.1f Scope Freeze

## 1. Status

Task 3.1f is frozen as the task **Stable Structure Extraction from the Full Distribution Corpus Including External-Factor Conditions**.

This document is the task-level source of truth. The following companion files define the frozen Task 3.1f-1 contract:

- `task3_1f1_comparison_design.md`
- `task3_1f1_validation_contract.md`
- `task3_1f1_output_schema.md`
- `../../../configs/task3_1f_structure_extraction_contract.json`

Task 3.1f-1 is a design-and-contract task only. It does not implement or execute the extraction pipeline.

## 2. Change-control rule

The following items must not be changed, weakened, removed, or expanded without explicit user approval:

- task purpose and success definition
- Task 3.1e input corpus and split roles
- primary analysis matrix
- model families and their roles
- rank grid
- initialization seeds and formal run counts
- weighting rule
- stability and redundancy definitions
- rank-selection rule
- holdout lock procedure
- required outputs
- positive and negative validation requirements
- stop conditions
- scope exclusions

When a change appears necessary, work must stop before the change is implemented. The proposed change must be reported with:

1. the conflicting requirement or observed failure;
2. why the frozen contract cannot be followed as written;
3. the smallest proposed change;
4. expected effects on comparability and prior results;
5. whether a new contract version and a new holdout protocol are required.

Silently changing a parameter, using a fallback model, opening the holdout early, or weakening a threshold is prohibited.

## 3. Frozen starting point

Task 3.1f consumes the formal Task 3.1e corpus produced from the merged implementation at:

- Task 3.1e merge commit: `b191f6d315caf0df72ed9dc718cb78c954775a93`
- formal artifact digest: `sha256:20060abf640504561e5988ad2068d79658b0c6247d35bc83b2cc32f818180a17`
- Task 3.1e configuration digest: `4125ed50cc4007c657e107e530a9969b979f496fc7fdb07093177a592240ac5a`

The validated corpus contains:

- 1,582 distribution snapshots;
- 3,125 cells per distribution;
- 1,082 fit rows;
- 256 validation rows;
- 244 holdout rows;
- 346 external vectors including three base vectors;
- 1,566 exact external/base snapshot pairs;
- 22 separately stored terrain fields.

The primary input is the probability-mass matrix. External-factor values and terrain fields remain audit and explanation information and are not model features in Task 3.1f.

## 4. Frozen task purpose

Task 3.1f determines whether the 3,125-cell distributions can be represented by a relatively small set of non-negative, repeatedly recoverable structures.

It must answer:

- how much of the distribution corpus can be reconstructed by each candidate structure count;
- whether the structures recur across initialization, grouped data perturbation, world seed, split, and external/base conditions;
- whether additional structures add genuinely distinct information or only duplicate existing structures;
- whether a validation-selected structure count generalizes once to the untouched holdout set;
- which structures are stable enough to pass to Task 3.1g for semantic auditing.

Task 3.1f does **not** determine the final number or names of Core semantic axes.

## 5. Frozen subtask sequence

### Task 3.1f-1 — Comparison design and validation contract

Define and freeze:

- the input and weighting rules;
- the primary and reference methods;
- the rank grid;
- stability, redundancy, inactivity, and reconstruction metrics;
- the validation-only selection rule;
- the one-time holdout procedure;
- output schemas and independent validation requirements.

### Task 3.1f-2 — Minimal extraction implementation

Implement the frozen primary route, references, artifact generation, independent validator, positive tests, negative tests, and smoke execution.

ChatGPT is the default implementer.

### Task 3.1f-3 — Fixed-condition batch execution

Run the already frozen rank and initialization grid. Codex may be used only as a single, judgment-free execution task. Codex must not change algorithms, ranks, thresholds, files, or acceptance criteria.

### Task 3.1f-4 — Formal stability and holdout validation

Use GitHub Actions for the formal fit/validation sweep, selection lock, grouped perturbation checks, one-time holdout evaluation, independent validation, and artifact retention.

### Task 3.1f-5 — Result audit and handoff

ChatGPT audits the formal artifacts, classifies the result, and selects the stable structures that may proceed to Task 3.1g.

## 6. Frozen exclusions

The following are outside Task 3.1f and require explicit approval before being added:

- assigning semantic names to extracted structures;
- using the six external factors as structure-extraction features;
- using the 22 terrain fields as structure-extraction features;
- replacing static distributions with trajectories;
- extracting independent factors from external-minus-base signed difference matrices;
- dynamic G_t update timing;
- K_t, O_t, H-DEPT, or Action Module integration;
- reinforcement learning or parameter control;
- automatic Core-axis adoption;
- extending the primary rank grid beyond `5, 8, 10, 12, 15, 20, 25`;
- activating dictionary learning as a fallback without approval;
- selecting another rank after seeing a failed holdout result.

Pairwise external/base deformation **evaluation** is in scope. A separate signed-difference factor model is not.

## 7. Frozen success definition

Success is not the lowest training error and is not obtaining approximately fifteen components.

Task 3.1f succeeds only when:

1. the fit/validation pipeline produces at least one admissible rank under the frozen integrity and stability rules;
2. the validation-only rule selects one provisional extraction rank without holdout access;
3. the selected representative basis is non-negative, non-degenerate, and independently reproducible from saved artifacts;
4. its structures are stable across required perturbation checks;
5. it improves meaningfully over the frozen mean-distribution baseline;
6. its one-time holdout outcome is `confirmed` or `conditional`, not `failed`;
7. all required mutation tests fail as expected;
8. stable structures can be handed to Task 3.1g without semantic naming being performed in Task 3.1f.

If no rank is admissible, that is a valid scientific result. It must be reported as a failed hypothesis rather than hidden by changing the contract.
