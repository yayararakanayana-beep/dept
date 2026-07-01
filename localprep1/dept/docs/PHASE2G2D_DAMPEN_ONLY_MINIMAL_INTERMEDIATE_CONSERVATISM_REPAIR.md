# Phase 2G-2d Dampen-only Minimal Intermediate Conservatism Repair

## 1. Scope

This is a dampen-only minimal repair. The only production behavior change is that `relaxed` mode now uses the Phase 2G-2c light-probe-equivalent gate dampening factor, `0.875`.

This task does not change `current`, `flat`, hard safety, block/defer conditions, monitor-only behavior, ActionModule behavior, action primitives, write paths, acceptance criteria, safety boundaries, v2 integration, candidate sparsity, guarded unlock strength, or ParameterWindowBinder registry values. The old relaxed behavior is retained explicitly as `relaxed_legacy_dampen_075` for comparison and rollback evidence.

## 2. Background

Phase 2G-2b found that relation-unlock-pressure thinning was not primarily gate row blocking. Gate-to-ActionFrame row retention stayed intact, while action mass was visibly reduced under dampen decisions.

Phase 2G-2c then isolated dampen, guarded-unlock-strength, and sparsity probes. The dampen-light probe recovered part of the relaxed-to-flat action-mass gap without boundary or write violations:

| variant | action_mass | relation_unlock_mass |
| --- | ---: | ---: |
| relaxed baseline | 6.259610 | 1.940366 |
| relaxed dampen light probe | 6.563894 | 2.040668 |
| relaxed dampen neutral probe | 6.868149 | 2.140970 |
| flat | 6.970200 | 2.242544 |

The neutral probe is not adopted because it is a stronger relaxation. This repair adopts only the light-probe-equivalent factor, preserving all other relaxed semantics.

## 3. Code Changes

| file | change | behavior scope | production effect |
| --- | --- | --- | --- |
| `dept2_fullspec_runner_rc1/modules/parameter_window_binder.py` | Added `relaxed_legacy_dampen_075`; changed repaired `relaxed` gate dampening factor from `0.75` to `0.875`; kept threshold, sparsity, relation-unlock gains, guarded unlock strength, and delay unchanged. | Relaxed-mode dampen strength only. | `relaxed` is the minimal dampen repair; legacy mode preserves old relaxed behavior. |
| `configs/matrices/matrix_phase2g2d_dampen_only_minimal_repair.json` | Added a 14-run lightweight matrix comparing current, legacy relaxed, repaired relaxed, flat, and safety slices. | Validation only. | No runtime default change beyond repaired relaxed semantics. |
| `scripts/run_matrix_validation.py` | Added report-only CSV exports and matrix summary fields for dampen-only repair comparison. | Diagnostics/export only. | No acceptance or runner behavior change. |
| `docs/PHASE2G2D_DAMPEN_ONLY_MINIMAL_INTERMEDIATE_CONSERVATISM_REPAIR.md` | Added this repair report. | Documentation. | Documents evidence and next task recommendation. |

## 4. Mode Semantics

| mode | meaning | changed? | use |
| --- | --- | --- | --- |
| `current` | old baseline | no | baseline |
| `relaxed_legacy_dampen_075` | old relaxed behavior with dampen factor `0.75` | new explicit legacy mode | comparison / rollback |
| `relaxed` | repaired relaxed, dampen factor `0.875` | yes, dampen factor only | default relaxed |
| `flat` | upper-bound comparator | no | validation only |

The repaired relaxed gate threshold mode is `relaxed_minimal_dampen_repair_0875`. The legacy gate threshold mode is `relaxed_legacy_dampen_075`.

## 5. Matrix Design

Matrix: `configs/matrices/matrix_phase2g2d_dampen_only_minimal_repair.json`.

The matrix has 14 short runs with 4-6 steps. Required comparison runs cover:

- `relation_unlock_pressure_current`
- `relation_unlock_pressure_relaxed_legacy_dampen_075`
- `relation_unlock_pressure_relaxed`
- `relation_unlock_pressure_flat`

Safety and smoke coverage includes:

- `no_exploration_relaxed`
- `high_noise_relaxed`
- `shock_recovery_relaxed`
- `default_relaxed_smoke`
- `explicit_current_smoke`
- `explicit_relaxed_legacy_smoke`
- `explicit_flat_smoke`

Additional stress slices include relation-unlock high noise, sparse projection, and high uncertainty.

## 6. Validation Results

Commands completed successfully:

- `python -m json.tool configs/matrices/matrix_phase2g2d_dampen_only_minimal_repair.json > /tmp/matrix_phase2g2d_dampen_only_minimal_repair.validated.json`
- `python -m compileall .`
- `python scripts/run_smoke_validation.py`
- `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2g2d_dampen_only_minimal_repair.json --output-dir validation_runs/phase2g2d_dampen_only_minimal_repair`
- `cat validation_runs/phase2g2d_dampen_only_minimal_repair/matrix_summary.json`

Matrix summary:

| field | value |
| --- | ---: |
| runs | 14 |
| overall_pass | true |
| boundary_violation_total | 0 |
| dry_run_write_violation_count | 0 |
| forbidden_write_count | 0 |
| gate_allow_total | 51 |
| gate_dampen_total | 22 |
| gate_defer_total | 0 |
| gate_block_total | 0 |
| safety_violation_total | 0 |
| write_violation_total | 0 |

The added diagnostic CSVs were present:

- `dampen_only_repair_summary.csv`
- `relaxed_legacy_vs_repaired_comparison.csv`
- `relation_unlock_repair_comparison.csv`
- `dampen_repair_safety_summary.csv`

## 7. Relation Unlock Repair Comparison

| mode | action_frame_rows | action_mass | relation_unlock_rows | relation_unlock_mass | gate_dampen | boundary/write | note |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `current` | 704 | 3.420649 | 242 | 1.054383 | observed | 0/0 | unchanged current baseline |
| `relaxed_legacy_dampen_075` | 836 | 6.259610 | 242 | 1.940366 | observed | 0/0 | old relaxed explicit rollback baseline |
| `relaxed` | 836 | 6.563894 | 242 | 2.040668 | observed | 0/0 | repaired relaxed minimal dampen repair |
| `flat` | 836 | 6.970200 | 242 | 2.242544 | observed | 0/0 | upper-bound comparator only |

## 8. Legacy Relaxed vs Repaired Relaxed

| metric | value |
| --- | ---: |
| legacy_relaxed_action_mass | 6.259610 |
| repaired_relaxed_action_mass | 6.563894 |
| repaired_delta_vs_legacy | +0.304284 |
| repaired_delta_vs_flat | -0.406306 |
| legacy_relation_unlock_mass | 1.940366 |
| repaired_relation_unlock_mass | 2.040668 |
| repaired_relation_unlock_delta_vs_legacy | +0.100302 |
| repaired_relation_unlock_delta_vs_flat | -0.201876 |

The repaired relaxed mode improves action mass and relation-unlock-family mass versus legacy relaxed while remaining below flat. This supports dampen-only adoption and keeps flat as validation-only evidence rather than a production candidate.

## 9. Safety and Boundary Findings

Safety checks passed for no-exploration, high-noise, and shock-recovery relaxed runs.

| finding | value |
| --- | ---: |
| boundary_violation_total | 0 |
| dry_run_write_violation_count | 0 |
| forbidden_write_count | 0 |
| direct ParameterBox input to ActionModule | 0 |
| G/K writeback detected | 0 |
| O_t writeback detected | 0 |
| canonical write detected | 0 |

No ActionModule, action primitive, hard safety, block/defer, acceptance, safety boundary, write path, or v2 integration behavior was changed.

## 10. Repair Implication

Classification:

- Dampen-only repair is acceptable as a minimal relaxed-mode repair.
- Additional post-repair stress is still recommended before using this as a v2 metric premise freeze.
- Guarded unlock should not be changed in this task.
- Candidate sparsity should not be changed in this task.
- Flat remains an upper-bound comparator and is not a production candidate.
- The repair is sufficient for the narrow Phase 2G-2d purpose because the repaired mode improves both action mass and relation-unlock-family mass versus explicit legacy relaxed with zero boundary/write violations.

The repair stays dampen-only because Phase 2G-2c showed dampen weakening explained the largest safe recovery signal, while neutral dampen was stronger than needed, guarded-unlock strength was secondary, and candidate sparsity did not move the sampled matrix.

## 11. Recommendation

Recommended next task: **Phase 2G-2e post-repair confirmation stress before v2 metric premise freeze**.

If reviewers want broader assurance first, the next task can be an additional stress probe. A guarded-unlock follow-up should remain separate and should not be combined with this dampen-only repair.

## 12. Conclusion

Phase 2G-2d implements the smallest production relaxed-mode repair supported by Phase 2G-2c: change only the relaxed dampen factor from `0.75` to `0.875`, preserve old relaxed as `relaxed_legacy_dampen_075`, keep current and flat unchanged, and add focused matrix evidence. Validation passed with zero boundary/write violations, repaired relaxed improved over legacy relaxed, and flat remains validation-only.
