# Codex Execution Integrity

## Purpose

Codex is treated as an implementation worker that may choose the shortest path satisfying visible checks. Therefore, correctness must not depend on Codex inferring unstated intent.

## Mandatory pre-implementation audit

For every critical output, identify:

1. The cheapest fake implementation that satisfies the visible schema.
2. Any place where fixed values, empty values, `true`, or `0` could replace real computation.
3. Any self-certification path where a producer can declare its own output valid.
4. Any formal branch skipped by smoke.
5. Any critical check without a negative test.
6. Any configurable value duplicated outside the configuration source.
7. Any unimplemented result that could be emitted as a plausible default.
8. Whether the smallest fake implementation can pass the proposed tests.
9. Whether generation and independent validation are separated.
10. Whether unknown or uncomputed states fail closed.

## Required architecture for evidence-producing tasks

Use separate responsibilities:

- **Generator:** produces raw artifacts. It must not declare them valid.
- **Audit:** computes derived measurements from persisted raw artifacts.
- **Validator:** re-reads persisted artifacts, independently recomputes checks, writes evidence-rich validation output, and exits non-zero on failure in strict mode.
- **Negative tests:** corrupt or remove artifacts and prove that validation fails.

The validator must not trust summary values copied from generator memory. It must use persisted files as evidence.

## Smoke rule

Smoke must execute the same logical path as formal. It may reduce counts, seeds, candidate-pool size, or capture steps. It must not omit Sobol generation, world execution, adaptive selection, coverage computation, artifact serialization, or independent validation when those are part of formal.

## Validation evidence rule

A validation result must include measured evidence, not only a boolean. Example:

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

## Fail-closed rule

Missing files, missing fields, shape mismatches, non-finite data, uncomputed statistics, unsupported configuration, and unverifiable results are failures. Do not replace them with defaults.
