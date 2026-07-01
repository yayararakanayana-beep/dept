# Phase 2E-1 Exploration Zero NO_OP Probe

## 1. Scope

- This probe cuts the Phase 2D `projection_rows = 0` candidates into a focused 10-run small loop.
- This is a hole-finding task, not a performance validation and not a fix task.
- No existing runner code, profiles, existing matrices, or acceptance criteria were changed.
- Added only a new Phase 2E-1 matrix and this verification report.

## 2. Main HEAD

- Checkout branch name at work start: `work`; implementation branch: `task30-phase2e1-exploration-zero-no-op-probe`.
- PR #29 merge commit confirmed: `True` (`281006b Merge PR #29: Add Phase 2D full integrated summary audit`).

```text
281006b Merge PR #29: Add Phase 2D full integrated summary audit
a048468 Merge PR #28: Add PseudoReality v2 shrinking smoke world
f8b370a Add Phase 2D full integrated summary audit
2fbb24a Add PseudoReality v2 shrinking smoke world
ad17516 Merge PR #27: Add Phase 2C stress ablation validation matrix
```

## 3. Matrix Design

- Matrix name: `phase2e1_exploration_zero_no_op_probe`.
- Run count: 10.
- The matrix reproduces Phase 2D zero-projection candidates from slow drift, exploration loss, and shock conditions.
- It includes `exploration_enabled: false` / `true` pair comparisons for exploration loss default, exploration loss buffered, slow drift low-coupling, and shock buffered.
- Steps are bounded to 24 or 36, using only existing `world_profile` and `action_profile` values.

## 4. Test Commands

- `pwd`
- `git status --short --branch`
- `git branch --show-current`
- `git log --oneline -5`
- `cd localprep1/dept`
- `python -m json.tool configs/matrices/matrix_phase2e1_exploration_zero_no_op_probe.json > /tmp/phase2e1_matrix_check.json`
- `python -m compileall .`
- `python scripts/run_smoke_validation.py`
- `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2e1_exploration_zero_no_op_probe.json --output-dir validation_runs/phase2e1_exploration_zero_no_op_probe`
- `cat validation_runs/phase2e1_exploration_zero_no_op_probe/matrix_summary.json`

## 5. Matrix Summary

| runs | overall_pass | boundary_violation_total | dry_run_write_violation_count | forbidden_write_count | projection_min | action_frame_min |
|---:|---|---:|---:|---:|---:|---:|
| 10 | True | 0 | 0 | 0 | 0 | 3410 |

## 6. Run-Level Probe Table

| label | exploration_enabled | projection_rows | exploration_candidates_rows | exploration_decision_rows | action_frame_rows | strength_sum_fmt | no_op_rows | no_op_ratio_fmt | exploration_injection_rows | gate_risk_mean_fmt | rollback_steps | commit_steps | acceptance_pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| repro_slow_drift_default_phase2b_zero_projection | default/not overridden | 0 | 153 | 153 | 3410 | 15.204 | 0 | 0.000 | 1056 | 0.443 | 24/24 | 24/24 | True |
| repro_exploration_loss_no_exploration_default | false | 0 | 0 | 24 | 3410 | 15.898 | 0 | 0.000 | 1056 | 0.446 | 24/24 | 24/24 | True |
| control_exploration_loss_exploration_enabled_default | true | 140 | 153 | 153 | 3410 | 15.418 | 0 | 0.000 | 1056 | 0.536 | 24/24 | 24/24 | True |
| repro_exploration_loss_no_exploration_buffered | false | 0 | 0 | 36 | 5126 | 24.065 | 0 | 0.000 | 1584 | 0.451 | 36/36 | 36/36 | True |
| control_exploration_loss_exploration_enabled_buffered | true | 245 | 245 | 245 | 5126 | 23.601 | 0 | 0.000 | 1584 | 0.541 | 36/36 | 36/36 | True |
| repro_slow_drift_low_coupling_no_exploration | false | 0 | 0 | 36 | 5126 | 23.599 | 0 | 0.000 | 1584 | 0.461 | 36/36 | 36/36 | True |
| control_slow_drift_low_coupling_exploration_enabled | true | 31 | 255 | 255 | 5126 | 23.599 | 0 | 0.000 | 1584 | 0.504 | 36/36 | 36/36 | True |
| repro_shock_no_exploration_buffered | false | 0 | 0 | 36 | 5522 | 20.677 | 0 | 0.000 | 1188 | 0.437 | 36/36 | 36/36 | True |
| control_shock_exploration_enabled_buffered | true | 139 | 216 | 216 | 5522 | 20.270 | 0 | 0.000 | 1188 | 0.527 | 36/36 | 36/36 | True |
| probe_exploration_loss_no_exploration_low_coupling | false | 0 | 0 | 24 | 3410 | 16.040 | 0 | 0.000 | 1056 | 0.441 | 24/24 | 24/24 | True |

Additional run-level notes:

- All required exploration/action/gate CSV files were emitted for every run: `exploration_candidates.csv`, `exploration_sandbox.csv`, `exploration_decision.csv`, `exploration_sidecar.csv`, `exploration_projection.csv`, `coactivation_gate.csv`, `action_surface_planning_audit.csv`, `action_frame.csv`, and `action_execution_audit.csv`.
- `exploration_projection.csv` is an empty CSV for projection-zero runs, so the file exists but has zero readable rows.
- `no_op` did not appear as an explicit `action_frame.csv` row value in these runs; `no_op rows` is therefore `0` for all runs. The available audit signal is instead `exploration_projection_used=False` on action frames where projection rows are zero.
- `gate_risk max` was not available because `coactivation_gate.csv` does not expose a `gate_risk` column; matrix-level `gate_risk_mean` is available.

## 7. Reproduction Check

| candidate | reproduction classification | evidence |
|---|---|---|
| `slow_drift_default_action_phase2b_24` | reproduced | `repro_slow_drift_default_phase2b_zero_projection` had `projection_rows = 0`. |
| `exploration_loss_no_exploration_default_phase2c` | reproduced | `repro_exploration_loss_no_exploration_default` had `projection_rows = 0`. |
| `exploration_loss_no_exploration_buffered_phase2c` | reproduced | `repro_exploration_loss_no_exploration_buffered` had `projection_rows = 0`. |
| `slow_drift_low_coupling_no_exploration_phase2c` | reproduced | `repro_slow_drift_low_coupling_no_exploration` had `projection_rows = 0`. |
| `shock_no_exploration_buffered_phase2c` | reproduced | `repro_shock_no_exploration_buffered` had `projection_rows = 0`. |
| added low-coupling exploration-loss no-exploration probe | reproduced as zero projection | `probe_exploration_loss_no_exploration_low_coupling` had `projection_rows = 0`. |

## 8. Exploration Disabled vs Enabled Comparison

| pair | disabled projection/candidates/decision | enabled projection/candidates/decision | action frame rows | no_op ratio | strength sum disabled -> enabled | gate risk mean disabled -> enabled | acceptance |
|---|---|---|---:|---:|---|---|---|
| exploration_loss default seed 507 | 0 / 0 / 24 | 140 / 153 / 153 | 3410 / 3410 | 0.000 / 0.000 | 15.898 -> 15.418 | 0.446 -> 0.536 | both pass |
| exploration_loss buffered seed 508 | 0 / 0 / 36 | 245 / 245 / 245 | 5126 / 5126 | 0.000 / 0.000 | 24.065 -> 23.601 | 0.451 -> 0.541 | both pass |
| slow_drift low-coupling seed 512 | 0 / 0 / 36 | 31 / 255 / 255 | 5126 / 5126 | 0.000 / 0.000 | 23.599 -> 23.599 | 0.461 -> 0.504 | both pass |
| shock buffered seed 516 | 0 / 0 / 36 | 139 / 139 / 139 | 5522 / 5522 | 0.000 / 0.000 | 20.677 -> 20.270 | 0.437 -> 0.527 | both pass |

Interpretation: disabling exploration suppresses candidates and sandbox rows and leaves per-step `skipped_disabled` decision/sidecar audit rows. Enabling exploration restores candidates, sandbox, decisions, and projection rows in all paired controls.

## 9. NO_OP / ActionFrame Safety

- Projection-zero did not remove ActionFrame generation: action frame rows stayed positive with minimum `3410`.
- Explicit `no_op` rows were not available in `action_frame.csv`; observed `no_op rows = 0` for all runs.
- For exploration-disabled zero-projection runs, `exploration_projection_used` was consistently `False` on all action-frame rows, while non-exploration action channels continued.
- The safest classification is: **exploration is stopped or not projected, while other action-frame generation continues normally**.
- This is not a clear safe NO_OP-only condition because action frames remain numerous, including `exploration_injection`, `uncertainty_probe`, `buffer_increase`, `coupling_relief`, and `guarded_relation_unlock` channels.
- It is also not an observed boundary breach or over-strength failure: action strength maxima remained bounded at or below `0.009`, acceptance passed, and gate dampening was applied.

## 10. Boundary / Write / ActionModule Integrity

- Boundary violations: `0` total.
- Dry-run write violations: `0` total.
- Forbidden writes: `0` total.
- Direct ParameterBox input to ActionModule: `False` for all run summaries and all action execution audit rows checked.
- Canonical write audit rows exist because these stress profiles use canonical commit mode; no forbidden write was detected.
- G/K/O_t writeback violations were not observed in summary or action-frame boundary columns.
- Rollback snapshots and commit gate rows matched `steps` for every run: 24/24 or 36/36.

## 11. Interpretation

Classification: **B. Missing exploration opportunity**, with a secondary audit-improvement note.

Rationale:

- Exploration-disabled zero-projection runs are explainable: candidates/sandbox are empty and decision/sidecar rows say `skipped_disabled` for each step.
- The slow-drift default zero-projection reproduction is more subtle: candidates, sandbox, decisions, and sidecar rows exist, but projection remains zero because decisions are `watch` or `block` rather than projected/accepted. This is a safe non-adoption pattern in the currently exposed audit, not a boundary failure.
- However, action frames continue at high row counts with no explicit `no_op` rows. This means Phase 2E-1 cannot prove a pure NO_OP pathway; it can only show that exploration projection is absent while other action mechanisms continue under gate dampening and boundary guards.
- Therefore the primary hole is not acceptance failure, write leakage, or ActionModule boundary violation. The hole is whether zero projection in exploratory contexts is always intended, especially where action frames still include exploration-adjacent channels.

## 12. Recommended Next Step

- Add a future small-loop audit enhancement for `no_op / projection reason` columns or a clearer projection-disabled reason summary; do not change code in this task.
- Proceed next to **Phase 2E-2 high_noise_gate_risk_probe** after recording this Phase 2E-1 finding, because boundary/write integrity is clean and projection-zero is now reproduced and classified.

## Appendix A. Action Channel / Decision Notes

| run label | decision counts | action channel counts |
|---|---|---|
| `repro_slow_drift_default_phase2b_zero_projection` | `{'watch': 130, 'block': 23}` | `{'exploration_injection': 1056, 'uncertainty_probe': 792, 'buffer_increase': 528, 'coupling_relief': 528, 'guarded_relation_unlock': 506}` |
| `repro_exploration_loss_no_exploration_default` | `{'skipped_disabled': 24}` | `{'exploration_injection': 1056, 'uncertainty_probe': 792, 'buffer_increase': 528, 'coupling_relief': 528, 'guarded_relation_unlock': 506}` |
| `control_exploration_loss_exploration_enabled_default` | `{'sandbox_pass': 140, 'watch': 10, 'block': 3}` | `{'exploration_injection': 1056, 'uncertainty_probe': 792, 'buffer_increase': 528, 'coupling_relief': 528, 'guarded_relation_unlock': 506}` |
| `repro_exploration_loss_no_exploration_buffered` | `{'skipped_disabled': 36}` | `{'exploration_injection': 1584, 'uncertainty_probe': 1188, 'buffer_increase': 792, 'coupling_relief': 792, 'guarded_relation_unlock': 770}` |
| `control_exploration_loss_exploration_enabled_buffered` | `{'sandbox_pass': 245}` | `{'exploration_injection': 1584, 'uncertainty_probe': 1188, 'buffer_increase': 792, 'coupling_relief': 792, 'guarded_relation_unlock': 770}` |
| `repro_slow_drift_low_coupling_no_exploration` | `{'skipped_disabled': 36}` | `{'exploration_injection': 1584, 'uncertainty_probe': 1188, 'buffer_increase': 792, 'coupling_relief': 792, 'guarded_relation_unlock': 770}` |
| `control_slow_drift_low_coupling_exploration_enabled` | `{'watch': 162, 'block': 62, 'sandbox_pass': 31}` | `{'exploration_injection': 1584, 'uncertainty_probe': 1188, 'buffer_increase': 792, 'coupling_relief': 792, 'guarded_relation_unlock': 770}` |
| `repro_shock_no_exploration_buffered` | `{'skipped_disabled': 36}` | `{'exploration_injection': 1188, 'buffer_increase': 1188, 'uncertainty_probe': 836, 'coupling_relief': 792, 'guarded_relation_unlock': 770, 'diagnostic_probe_restraint_direct': 396, 'diagnostic_update_restraint': 352}` |
| `control_shock_exploration_enabled_buffered` | `{'sandbox_pass': 139, 'watch': 77}` | `{'exploration_injection': 1188, 'buffer_increase': 1188, 'uncertainty_probe': 836, 'coupling_relief': 792, 'guarded_relation_unlock': 770, 'diagnostic_probe_restraint_direct': 396, 'diagnostic_update_restraint': 352}` |
| `probe_exploration_loss_no_exploration_low_coupling` | `{'skipped_disabled': 24}` | `{'exploration_injection': 1056, 'uncertainty_probe': 792, 'buffer_increase': 528, 'coupling_relief': 528, 'guarded_relation_unlock': 506}` |
