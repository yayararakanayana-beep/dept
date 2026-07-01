# Phase 2G-2c Intermediate Conservatism Repair Probe

## 1. Scope

This is **not a production repair**. It is a probe-only comparison of intermediate-conservatism repair candidates. The default behavior and the existing `current`, `relaxed`, and `flat` meanings are not changed. Safety boundaries, write paths, acceptance criteria, ActionModule behavior, action primitives, and v2 integration are not changed.

All added variants include `probe` in the mode name and are enabled only when a matrix override explicitly requests that mode.

## 2. Background

Phase 2G-2b indicated that `relation_unlock_pressure` thinning was not primarily caused by gate row blocking. The stronger signal was reduced action mass from dampening and mode-dependent action-mass differences: `current < relaxed < flat`. This probe therefore separates dampen factor effects from guarded-unlock strength and candidate sparsity effects.

## 3. Probe Variants

| variant | purpose | behavior scope | production default? | safety boundary changed? |
|---|---|---|---|---|
| `relaxed_baseline` | Existing relaxed baseline | Existing `relaxed` mode | No | No |
| `relaxed_dampen_light_probe` | Test weaker dampen suppression | `relaxed` plus dampen factor `0.875` | No | No |
| `relaxed_dampen_neutral_probe` | Test near-neutral dampen action-strength reduction | `relaxed` plus dampen factor `1.0` | No | No |
| `relaxed_guarded_unlock_strength_probe` | Isolate guarded unlock strength factor | `relaxed` plus guarded unlock strength `1.0` | No | No |
| `relaxed_sparsity_light_probe` | Isolate lighter candidate sparsity | Experimental sparsity-only relaxation over `relaxed` | No | No |
| `flat_upper_bound` | Existing flat upper-bound comparison only | Existing `flat` mode | No | No |

These variants are not production candidates; they are diagnostic evidence for a later repair decision.

## 4. Matrix Design

Matrix: `configs/matrices/matrix_phase2g2c_intermediate_conservatism_repair_probe.json`.

The matrix runs 12 short validations with 4-6 steps. It compares `relation_unlock_pressure` across `current`, `relaxed`, `flat`, and probe-only variants, then checks `no_exploration`, `high_noise`, and `shock_recovery` safety under `relaxed_dampen_light_probe`. It also includes relaxed/current smoke baselines.

## 5. Validation Results

Commands completed successfully:

- `python -m json.tool configs/matrices/matrix_phase2g2c_intermediate_conservatism_repair_probe.json > /tmp/matrix_phase2g2c_intermediate_conservatism_repair_probe.validated.json`
- `python -m compileall .`
- `python scripts/run_smoke_validation.py`
- `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2g2c_intermediate_conservatism_repair_probe.json --output-dir validation_runs/phase2g2c_intermediate_conservatism_repair_probe`

Matrix result:

- `runs`: 12
- `overall_pass`: true
- `boundary_violation_total`: 0
- `dry_run_write_violation_count`: 0
- `forbidden_write_count`: 0
- `gate_defer_total`: 0
- `gate_block_total`: 0

## 6. Relation Unlock Pressure Comparison

| mode_or_variant | action_frame_rows | action_mass | relation_unlock_rows | relation_unlock_mass | gate_dampen | boundary/write | note |
|---|---:|---:|---:|---:|---:|---|---|
| `current` | 704 | 3.420649 | 242 | 1.054383 | 5 | 0/0 | Lowest mass among compared modes |
| `relaxed_baseline` | 836 | 6.259610 | 242 | 1.940366 | 2 | 0/0 | Existing relaxed behavior |
| `flat_upper_bound` | 836 | 6.970200 | 242 | 2.242544 | 0 | 0/0 | Upper bound only; not production candidate |
| `relaxed_dampen_light_probe` | 836 | 6.563894 | 242 | 2.040668 | 2 | 0/0 | Recovers part of relaxed-to-flat gap |
| `relaxed_dampen_neutral_probe` | 836 | 6.868149 | 242 | 2.140970 | 2 | 0/0 | Best probe mass, still below flat |
| `relaxed_guarded_unlock_strength_probe` | 836 | 6.350601 | 242 | 2.031380 | 2 | 0/0 | Smaller total-mass gain than dampen probes |
| `relaxed_sparsity_light_probe` | 836 | 6.259610 | 242 | 1.940366 | 2 | 0/0 | No change in this matrix |

## 7. Dampen Probe Findings

Weakening dampen recovered action mass without row-count changes in the `relation_unlock_pressure` runs:

- `relaxed_dampen_light_probe`: action mass improved by `+0.304284` vs relaxed and relation-unlock-family mass improved by `+0.100302`.
- `relaxed_dampen_neutral_probe`: action mass improved by `+0.608539` vs relaxed and relation-unlock-family mass improved by `+0.200604`.
- `relaxed_dampen_neutral_probe` remained `-0.102050` below flat action mass, meaning flat's remaining advantage is not exclusively dampen neutralization.

No boundary or write violations appeared in either dampen probe.

## 8. ParameterWindow / Guarded Unlock Findings

Guarded unlock strength at `1.0` produced a smaller total action-mass gain than dampen weakening (`+0.090991` vs relaxed), although relation-unlock-family mass improved by `+0.091014`. Candidate sparsity lightening did not change action mass or relation-unlock-family mass in this matrix.

The relaxed-to-flat gap appears mostly dampen-related in this setup, with a smaller guarded-unlock-strength component and no observed candidate-sparsity component.

## 9. Safety and Boundary Findings

Safety checks under `relaxed_dampen_light_probe` passed for `no_exploration`, `high_noise`, and `shock_recovery`. Aggregate safety totals were:

- `boundary_violation_total`: 0
- `dry_run_write_violation_count`: 0
- `forbidden_write_count`: 0
- direct ParameterBox input to ActionModule: 0
- G/K writeback detected: 0
- O_t writeback detected: 0
- canonical write detected: 0

## 10. Repair Implication

Classification:

- Dampen factor adjustment is the strongest repair family to probe next.
- Guarded unlock strength may be secondary and should not be combined with dampen repair until dampen-only evidence is sufficient.
- Candidate sparsity did not explain this matrix's mass gap.
- Gate hard safety should remain unchanged.
- `flat` is an upper-bound comparator only and is not a production candidate.
- Do not make a production repair from this probe alone.

## 11. Recommendation

Recommended next task: **Phase 2G-2d dampen-only minimal intermediate conservatism repair**, implemented as a small, explicit production proposal only after review. Alternative next tasks are a guarded-unlock-only probe if relation-unlock-family mass is prioritized, or an additional stress probe if broader safety coverage is required first.

## 12. Conclusion

Phase 2G-2c confirms that action-mass reduction in `relation_unlock_pressure` is most consistent with dampen strength rather than gate row blocking. Probe-only dampen weakening recovered a substantial share of the relaxed-to-flat gap while preserving zero boundary/write violations in this matrix. The best probe variant by action mass and relation-unlock-family mass was `relaxed_dampen_neutral_probe`, but it is **not a production adoption candidate**.
