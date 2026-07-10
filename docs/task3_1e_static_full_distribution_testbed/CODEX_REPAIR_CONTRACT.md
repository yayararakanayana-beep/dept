# Codex Repair Contract — PR #142 / Task 3.1e

## Task identity

- **Task type:** Existing Task 3.1e repair
- **Repository:** `yayararakanayana-beep/dept`
- **Existing pull request:** `#142`
- **Base branch:** `main`
- **Working branch:** `vnzq5f-codex/build-static-full-distribution-testbed`
- **Do not create a new task, new PR, or replacement branch.**

## Objective

Repair PR #142 so that the Task 3.1e testbed computes real coverage evidence and independently validates persisted artifacts. The repair must remove all placeholder, self-certifying, and smoke-path bypasses.

Do not redesign Task 3.1e. Keep the already-approved external-factor, static-G_t, 5-bin, and 3125-cell contracts.

## Read first

Read and obey:

```text
AGENTS.md
docs/development/CODEX_EXECUTION_INTEGRITY.md
docs/development/CODEX_TASK_CONTRACT_TEMPLATE.md
```

## Existing defects that must be removed

1. `coverage_summary.csv` currently writes zero-valued placeholder statistics.
2. `quality_checks.json` currently initializes checks to constant `true` values.
3. Smoke currently skips adaptive maximin selection.
4. The formal configuration file is not the single execution source for seeds, steps, allocations, and adaptive counts.
5. Existing tests check key/file existence but do not prove that corrupted outputs fail.
6. The generator produces and certifies evidence used to judge its own correctness.
7. `results.md` and `artifact_manifest.json` do not contain the required measured evidence.

## Required architecture

Use separate responsibilities.

### Generator

The generator may write only raw Task 3.1e artifacts and adaptive-selection evidence:

```text
external_vectors.csv
snapshot_metadata.csv
discovery_manifest.csv
matched_pairs.csv
cell_coordinates.csv
terrain_field_catalog.csv
mass_matrix.npy
terrain_reference.npz
coverage_additions.csv
```

The generator must not write:

```text
coverage_summary.csv
quality_checks.json
results.md
artifact_manifest.json
```

### Independent coverage audit

Create:

```text
scripts/pseudoreality_v3_3_static_full_distribution_coverage_audit.py
```

It must re-read persisted raw artifacts and compute real Jensen–Shannon nearest-neighbor statistics. It must write `coverage_summary.csv`.

It must independently replay the deterministic adaptive maximin selection from configuration and verify:

- candidate-pool count
- selected count
- selected candidate order
- selected candidate values
- minimum JS distance recorded at each selection

A mismatch must exit non-zero.

### Independent validator

Create:

```text
scripts/pseudoreality_v3_3_static_full_distribution_validator.py
```

It must re-read persisted artifacts and independently recompute all checks. It is the only component allowed to write:

```text
quality_checks.json
results.md
artifact_manifest.json
```

Strict mode must exit non-zero when any check fails.

## Configuration source

Replace the current partially decorative configuration with one configuration file containing both profiles:

```text
configs/task3_1e_static_full_distribution_testbed.json
```

The implementation must read all of the following from that file:

- capture steps
- world seeds
- Sobol seeds
- fit allocation
- validation allocation
- holdout boundary count
- holdout full-6D count
- adaptive-pool allocation
- adaptive selected count

Do not duplicate these formal values in Python branches.

A test must modify a temporary configuration file and prove that the generated source steps change accordingly.

## Smoke and formal paths

Smoke must execute the same logical route as formal:

```text
configuration load
→ stratified Sobol generation
→ real DistributionTerrainV322World execution
→ adaptive candidate generation
→ Jensen–Shannon maximin selection
→ raw artifact serialization
→ independent coverage audit
→ independent validation
```

Only scale may differ.

Fixed smoke requirements:

```text
adaptive candidate pool = 8
adaptive selected count = 2
```

Fixed formal requirements:

```text
fit non-base before adaptive = 147
validation non-base = 84
holdout non-base = 80
adaptive candidate pool = 178
adaptive selected count = 32
```

## Evidence-rich validation format

A bare boolean is not sufficient. Each quality check must include measured evidence.

Example:

```json
{
  "mass_sum_valid": {
    "passed": true,
    "checked_rows": 120,
    "invalid_rows": 0,
    "maximum_absolute_error": 2.2e-16,
    "tolerance": 1e-8,
    "evidence_source": "mass_matrix.npy"
  }
}
```

At minimum validate from persisted artifacts:

- five axes / five bins / 3125 cells
- mass shape, dtype, finiteness, non-negativity, and row sums
- exact six-factor schema and allowed ranges
- base/external separation
- exact four-column discovery manifest and no forbidden leakage
- required terrain members, shape, dtype, and finiteness
- excluded transition fields absent
- exact matched-base relationships
- no stored `combined_full`
- split external-vector values disjoint after 12-decimal rounding
- Sobol determinism
- configured seeds, steps, and vector counts actually applied
- analysis weights finite, positive, and mean 1 per split
- adaptive selection independently reproduced
- coverage summary exactly matches recomputation and contains positive measured distances
- artifact manifest contains hashes, sizes, and type-specific shape/row metadata

## Mandatory negative tests

Create:

```text
tests/test_pseudoreality_v3_3_static_full_distribution_negative.py
```

The tests must generate one valid smoke artifact set, copy it, corrupt it, and prove the independent validator fails the relevant check.

Required corruptions:

1. Change one mass row sum to 0.9.
2. Insert `NaN` into the mass matrix.
3. Duplicate a non-base external vector across splits.
4. Remove one required terrain field from the NPZ archive.
5. Replace all coverage-distance values with zero.
6. Remove one adaptive-selection row.

Do not mock the validator result. Run the real validator against the corrupted persisted files.

## Workflow

Update:

```text
.github/workflows/pseudoreality-v3-3-static-full-distribution-testbed.yml
```

Required order:

```text
positive tests
→ negative tests
→ generator
→ independent coverage audit
→ independent validator --strict
→ upload formal artifact only for manual formal execution
```

Do not validate by merely reading booleans written by the generator.

## Adversarial shortcut audit

| Critical requirement | Cheapest fake implementation | Required prevention | Required negative test |
|---|---|---|---|
| Coverage statistics | Fill all values with `0.0` | Audit recomputes from `mass_matrix.npy` | Zero the summary and require failure |
| Quality checks | Fill all values with `true` | Validator recomputes from persisted files | Corrupt mass and require failure |
| Adaptive selection | Return an empty list in smoke | Smoke runs same maximin path | Remove one selection row and require failure |
| Split isolation | Change IDs while reusing values | Compare six-factor values across splits | Duplicate a vector and require failure |
| Terrain completeness | Substitute zeros or omit a field | Read NPZ members and shapes | Delete one field and require failure |
| Configuration use | Hard-code values in Python | Temporary-config execution test | Change capture steps and require changed output |
| Artifact integrity | List files without evidence | Recompute SHA-256, sizes, rows, shapes, dtypes | Tamper with an artifact and require mismatch |

## Files allowed to change

```text
AGENTS.md
docs/development/CODEX_EXECUTION_INTEGRITY.md
docs/development/CODEX_TASK_CONTRACT_TEMPLATE.md
scripts/pseudoreality_v3_3_static_full_distribution_testbed.py
scripts/pseudoreality_v3_3_static_full_distribution_coverage_audit.py
scripts/pseudoreality_v3_3_static_full_distribution_validator.py
configs/task3_1e_static_full_distribution_testbed.json
tests/test_pseudoreality_v3_3_static_full_distribution_testbed.py
tests/test_pseudoreality_v3_3_static_full_distribution_negative.py
.github/workflows/pseudoreality-v3-3-static-full-distribution-testbed.yml
docs/task3_1e_static_full_distribution_testbed/**
```

## Files forbidden to change

```text
pseudo_reality/distribution_terrain_v3.py
pseudo_reality/distribution_terrain_v3_2.py
pseudo_reality/distribution_terrain_v3_2_2.py
```

Do not change v3.3 dynamics, dimensions, payoff formulas, terrain formulas, external deformation rates, thresholds, K_t, O_t, H-DEPT, or the Action Module.

## Required local/CI commands

```bash
python -m pytest tests/test_pseudoreality_v3_3_static_full_distribution_testbed.py -q
python -m pytest tests/test_pseudoreality_v3_3_static_full_distribution_negative.py -q

python scripts/pseudoreality_v3_3_static_full_distribution_testbed.py \
  --profile smoke --output-root artifacts

python scripts/pseudoreality_v3_3_static_full_distribution_coverage_audit.py \
  --profile smoke --artifact-root artifacts

python scripts/pseudoreality_v3_3_static_full_distribution_validator.py \
  --profile smoke --artifact-root artifacts --strict
```

## Stop conditions

Stop and report instead of weakening the task when:

- the real world path cannot satisfy 3125 cells
- a required terrain field is unavailable
- independent adaptive replay cannot match generation
- formal runtime cannot be supported without reducing the fixed specification
- a required check cannot be derived from persisted evidence

Do not open a replacement PR. Push the repair to PR #142's existing branch only.
