# Phase 2D Full Integrated Closed-Loop Validation Summary Audit
## 1. Scope
- Re-ran Phase 2A / Phase 2B / Phase 2C validation matrices from the checked-out main-positive HEAD content.
- This is a hole-finding cross-matrix audit, not a performance optimization or pass-rate tuning exercise.
- No runner code, profiles, matrices, acceptance conditions, or parameters were changed; this PR adds only this audit report and one machine-readable audit snapshot.
## 2. Main HEAD
- Checkout branch name: `task28-phase2d-summary-audit`.
- PR #27 merge commit confirmed: `True`.

```text
ad17516 Merge PR #27: Add Phase 2C stress ablation validation matrix
05b617f Add Phase 2C stress ablation validation matrix
3756859 Remove accidental temporary docs file
863bc7c TMP
b0282a9 Merge PR #26: Add PseudoReality v2 RC1 docs
```
## 3. Test Commands
- `pwd`
- `git status --short --branch`
- `git branch --show-current`
- `git log --oneline -5`
- `cd localprep1/dept`
- `python -m compileall .`
- `python scripts/run_smoke_validation.py`
- `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_full_closed_loop_phase2a.json --output-dir validation_runs/phase2d_phase2a`
- `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_full_closed_loop_phase2b_longrun.json --output-dir validation_runs/phase2d_phase2b`
- `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_full_closed_loop_phase2c_stress_ablation.json --output-dir validation_runs/phase2d_phase2c`
- `cat validation_runs/phase2d_phase2a/matrix_summary.json`
- `cat validation_runs/phase2d_phase2b/matrix_summary.json`
- `cat validation_runs/phase2d_phase2c/matrix_summary.json`

## 4. Matrix Summary

| matrix | runs | overall_pass | boundary_violation_total | dry_run_write_violation_count | forbidden_write_count | projection_min | action_frame_min |
|---|---:|---|---:|---:|---:|---:|---:|
| Phase 2A / `full_closed_loop_phase2a` | 18 | True | 0 | 0 | 0 | 3 | 2365 |
| Phase 2B / `full_closed_loop_phase2b_longrun` | 15 | True | 0 | 0 | 0 | 0 | 3410 |
| Phase 2C / `full_closed_loop_phase2c_stress_ablation` | 18 | True | 0 | 0 | 0 | 0 | 3322 |

Expected run counts were met: Phase 2A = 18, Phase 2B = 15, Phase 2C = 18. All three matrices passed, while Phase 2B and Phase 2C both exposed `projection_min = 0` candidates.

## 5. Cross-Matrix Observations
- Boundary/write integrity was stable across all 51 runs: boundary, dry-run write, and forbidden-write counts stayed at zero.
- Projection behavior is the primary hole-finding signal: Phase 2A had a low but nonzero minimum of 3, while Phase 2B and Phase 2C each included zero-projection runs.
- ActionFrame generation was present in every run. The lowest row count was in Phase 2A shock/conservative conditions, while long and stress runs naturally produced more rows.
- Highest gate risk clustered around relation-lock conservative and shock/exploration-loss long-run combinations, suggesting gate-risk small-loop probes should focus on locked relation and stress-memory interactions.
- Rollback snapshots and commit gate rows matched step counts in every audited run, leaving no observed slack deficit in this pass.

## 6. Suspect Runs / Hole Candidates

| matrix | run label | reason | metric evidence | recommended next small-loop validation |
|---|---|---|---|---|
| Phase 2B | `slow_drift_default_action_phase2b_24` | projection_rows = 0 | projection=0; action_frame_rows=3410; strength_sum=15.204; gate_risk_mean=0.443; rollback/steps=24/24; commit/steps=24/24 | exploration_zero_no_op_probe or no-exploration projection probe |
| Phase 2C | `exploration_loss_no_exploration_default_phase2c` | projection_rows = 0 | projection=0; action_frame_rows=3410; strength_sum=15.898; gate_risk_mean=0.446; rollback/steps=24/24; commit/steps=24/24 | exploration_zero_no_op_probe or no-exploration projection probe |
| Phase 2C | `exploration_loss_no_exploration_buffered_phase2c` | projection_rows = 0 | projection=0; action_frame_rows=5126; strength_sum=24.065; gate_risk_mean=0.451; rollback/steps=36/36; commit/steps=36/36 | exploration_zero_no_op_probe or no-exploration projection probe |
| Phase 2C | `slow_drift_low_coupling_no_exploration_phase2c` | projection_rows = 0 | projection=0; action_frame_rows=5126; strength_sum=23.599; gate_risk_mean=0.461; rollback/steps=36/36; commit/steps=36/36 | exploration_zero_no_op_probe or no-exploration projection probe |
| Phase 2C | `shock_no_exploration_buffered_phase2c` | projection_rows = 0 | projection=0; action_frame_rows=5522; strength_sum=20.677; gate_risk_mean=0.437; rollback/steps=36/36; commit/steps=36/36 | exploration_zero_no_op_probe or no-exploration projection probe |
| Phase 2A | `relation_lock_buffered_action_phase2a` | projection_rows very low (1-5) | projection=4; action_frame_rows=2552; strength_sum=11.237; gate_risk_mean=0.473; rollback/steps=18/18; commit/steps=18/18 | projection sparsity small-loop probe |
| Phase 2A | `slow_drift_buffered_action_phase2a` | projection_rows very low (1-5) | projection=3; action_frame_rows=2552; strength_sum=11.618; gate_risk_mean=0.458; rollback/steps=18/18; commit/steps=18/18 | projection sparsity small-loop probe |
| Phase 2A | `shock_world_conservative_action_phase2a` | lowest action_frame_rows | projection=31; action_frame_rows=2365; strength_sum=9.946; gate_risk_mean=0.520; rollback/steps=18/18; commit/steps=18/18 | action frame coverage probe |
| Phase 2A | `relation_lock_conservative_action_phase2a` | lowest action_frame_rows | projection=19; action_frame_rows=2409; strength_sum=11.029; gate_risk_mean=0.485; rollback/steps=18/18; commit/steps=18/18 | action frame coverage probe |
| Phase 2A | `exploration_loss_conservative_action_phase2a` | lowest action_frame_rows | projection=106; action_frame_rows=2486; strength_sum=11.343; gate_risk_mean=0.522; rollback/steps=18/18; commit/steps=18/18 | action frame coverage probe |
| Phase 2A | `shock_world_conservative_action_phase2a` | lowest action_frame_strength_sum | projection=31; action_frame_rows=2365; strength_sum=9.946; gate_risk_mean=0.520; rollback/steps=18/18; commit/steps=18/18 | weak response / shock recovery probe |
| Phase 2A | `shock_world_buffered_action_phase2a` | lowest action_frame_strength_sum | projection=32; action_frame_rows=2618; strength_sum=10.101; gate_risk_mean=0.504; rollback/steps=18/18; commit/steps=18/18 | weak response / shock recovery probe |
| Phase 2A | `shock_world_default_action_phase2a` | lowest action_frame_strength_sum | projection=72; action_frame_rows=2750; strength_sum=11.027; gate_risk_mean=0.523; rollback/steps=18/18; commit/steps=18/18 | weak response / shock recovery probe |
| Phase 2C | `exploration_loss_no_exploration_buffered_phase2c` | highest action_frame_strength_sum | projection=0; action_frame_rows=5126; strength_sum=24.065; gate_risk_mean=0.451; rollback/steps=36/36; commit/steps=36/36 | strong/buffered action amplitude probe |
| Phase 2B | `high_noise_buffered_action_phase2b_36` | highest action_frame_strength_sum | projection=189; action_frame_rows=5522; strength_sum=23.934; gate_risk_mean=0.470; rollback/steps=36/36; commit/steps=36/36 | strong/buffered action amplitude probe |
| Phase 2C | `slow_drift_low_coupling_no_exploration_phase2c` | highest action_frame_strength_sum | projection=0; action_frame_rows=5126; strength_sum=23.599; gate_risk_mean=0.461; rollback/steps=36/36; commit/steps=36/36 | strong/buffered action amplitude probe |
| Phase 2C | `relation_lock_hard_conservative_phase2c` | highest gate_risk_mean | projection=68; action_frame_rows=5049; strength_sum=23.575; gate_risk_mean=0.559; rollback/steps=36/36; commit/steps=36/36 | gate risk isolation probe |
| Phase 2B | `relation_lock_conservative_action_phase2b_36` | highest gate_risk_mean | projection=98; action_frame_rows=5038; strength_sum=23.524; gate_risk_mean=0.554; rollback/steps=36/36; commit/steps=36/36 | gate risk isolation probe |
| Phase 2B | `shock_world_conservative_action_phase2b_36` | highest gate_risk_mean | projection=136; action_frame_rows=3861; strength_sum=16.703; gate_risk_mean=0.546; rollback/steps=36/36; commit/steps=36/36 | gate risk isolation probe |
| Phase 2B | `exploration_loss_buffered_action_phase2b_36` | highest gate_risk_mean | projection=232; action_frame_rows=5126; strength_sum=23.572; gate_risk_mean=0.545; rollback/steps=36/36; commit/steps=36/36 | gate risk isolation probe |
| Phase 2B | `shock_world_default_action_phase2b_24` | highest gate_risk_mean | projection=71; action_frame_rows=3674; strength_sum=14.506; gate_risk_mean=0.545; rollback/steps=24/24; commit/steps=24/24 | gate risk isolation probe |

## 7. Boundary / Write / ActionModule Integrity
- `boundary_violation_total` was 0 for Phase 2A, Phase 2B, and Phase 2C.
- `dry_run_write_violation_count` was 0 for all matrices.
- `forbidden_write_count` was 0 for all matrices.
- `direct_parameter_box_input_to_actionmodule` was false for all run-level metrics.
- `action_frame_rows` was nonzero for all runs, so no ActionFrame generation absence was observed.
- `canonical_write_rows` stayed 0 in all run metrics, consistent with no canonical write. No G/K/O_t writeback issue was observed in the exported acceptance metrics.

## 8. Exploration / Projection Observations
- Required exploration/action diagnostic CSV presence check: PASS; missing file count = 0.
- Zero-projection runs:
  - `slow_drift_default_action_phase2b_24` (Phase 2B): scenario=relation_lock, world=pseudo_reality_slow_drift, action=action_default, steps=24.
  - `exploration_loss_no_exploration_default_phase2c` (Phase 2C): scenario=exploration_loss, world=pseudo_reality_exploration_loss, action=action_default, steps=24.
  - `exploration_loss_no_exploration_buffered_phase2c` (Phase 2C): scenario=exploration_loss, world=pseudo_reality_exploration_loss, action=action_buffered, steps=36.
  - `slow_drift_low_coupling_no_exploration_phase2c` (Phase 2C): scenario=relation_lock, world=pseudo_reality_slow_drift, action=action_low_coupling, steps=36.
  - `shock_no_exploration_buffered_phase2c` (Phase 2C): scenario=shock, world=pseudo_reality_shock, action=action_buffered, steps=36.
- Exploration-disabled/no-exploration labels all preserved acceptance pass, but they are still high-priority holes because projection can legitimately disappear while action frames, rollback, and gates continue to operate.

## 9. K_t / Window / Gate Observations
- kt_window-short candidate `relation_lock_short_kt_window_phase2c`: projection=24, gate_risk_mean=0.534, binding_pass=True, planning=True, gate=True.
- kt_window-short candidate `high_noise_short_kt_window_phase2c`: projection=125, gate_risk_mean=0.480, binding_pass=True, planning=True, gate=True.
- Binding stayed active in planning and gate metrics across the collected runs, but short-window relation/high-noise runs remain useful because their gate risk sits in the upper band without producing boundary violations.

## 10. Recommended Phase 2E Small-Loop Targets
- `exploration_zero_no_op_probe`
- `kt_window_short_memory_probe`
- `shock_recovery_action_frame_probe`
- `relation_lock_unlock_probe`
- `high_noise_gate_risk_probe`
- `strong_action_boundary_probe`
- `slow_drift_low_coupling_probe`

## 11. Conclusion
The current full integrated closed-loop validation state is structurally clean in this rerun: compileall, smoke, and all Phase 2A/2B/2C matrices passed; boundary/write/forbidden-write counters remained zero; ActionFrame generation and rollback/commit-gate rows were present. The audit still identifies meaningful holes before an RC1 Freeze decision: zero-projection/no-exploration cases, short K_t window gate-risk cases, relation-lock high-risk cases, shock recovery strength lows, and action-strength extremes should be cut into Phase 2E small-loop validations before treating the integrated matrix pass as sufficient evidence.

## Appendix A. Run-Level Cross-Matrix Table

| matrix | run label | scenario | world_profile | action_profile | steps | projection_rows | action_frame_rows | action_frame_strength_sum | gate_risk_mean | rollback/steps | commit/steps |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| Phase 2A | `default_world_default_action_phase2a` | normal | pseudo_reality_default | action_default | 18 | 89 | 2750 | 11.854 | 0.462 | 18/18 | 18/18 |
| Phase 2A | `default_world_conservative_action_phase2a` | normal | pseudo_reality_default | action_conservative | 18 | 85 | 2629 | 11.568 | 0.454 | 18/18 | 18/18 |
| Phase 2A | `default_world_buffered_action_phase2a` | normal | pseudo_reality_default | action_buffered | 18 | 80 | 2750 | 11.477 | 0.452 | 18/18 | 18/18 |
| Phase 2A | `shock_world_default_action_phase2a` | shock | pseudo_reality_shock | action_default | 18 | 72 | 2750 | 11.027 | 0.523 | 18/18 | 18/18 |
| Phase 2A | `shock_world_conservative_action_phase2a` | shock | pseudo_reality_shock | action_conservative | 18 | 31 | 2365 | 9.946 | 0.520 | 18/18 | 18/18 |
| Phase 2A | `shock_world_buffered_action_phase2a` | shock | pseudo_reality_shock | action_buffered | 18 | 32 | 2618 | 10.101 | 0.504 | 18/18 | 18/18 |
| Phase 2A | `relation_lock_default_action_phase2a` | relation_lock | pseudo_reality_relation_lock | action_default | 18 | 26 | 2552 | 11.425 | 0.532 | 18/18 | 18/18 |
| Phase 2A | `relation_lock_conservative_action_phase2a` | relation_lock | pseudo_reality_relation_lock | action_conservative | 18 | 19 | 2409 | 11.029 | 0.485 | 18/18 | 18/18 |
| Phase 2A | `relation_lock_buffered_action_phase2a` | relation_lock | pseudo_reality_relation_lock | action_buffered | 18 | 4 | 2552 | 11.237 | 0.473 | 18/18 | 18/18 |
| Phase 2A | `exploration_loss_default_action_phase2a` | exploration_loss | pseudo_reality_exploration_loss | action_default | 18 | 111 | 2552 | 11.513 | 0.520 | 18/18 | 18/18 |
| Phase 2A | `exploration_loss_conservative_action_phase2a` | exploration_loss | pseudo_reality_exploration_loss | action_conservative | 18 | 106 | 2486 | 11.343 | 0.522 | 18/18 | 18/18 |
| Phase 2A | `exploration_loss_buffered_action_phase2a` | exploration_loss | pseudo_reality_exploration_loss | action_buffered | 18 | 110 | 2552 | 11.533 | 0.541 | 18/18 | 18/18 |
| Phase 2A | `high_noise_default_action_phase2a` | normal | pseudo_reality_high_noise | action_default | 18 | 98 | 2750 | 11.843 | 0.465 | 18/18 | 18/18 |
| Phase 2A | `high_noise_conservative_action_phase2a` | normal | pseudo_reality_high_noise | action_conservative | 18 | 71 | 2585 | 11.232 | 0.482 | 18/18 | 18/18 |
| Phase 2A | `high_noise_buffered_action_phase2a` | normal | pseudo_reality_high_noise | action_buffered | 18 | 88 | 2750 | 11.850 | 0.476 | 18/18 | 18/18 |
| Phase 2A | `slow_drift_default_action_phase2a` | relation_lock | pseudo_reality_slow_drift | action_default | 18 | 13 | 2552 | 11.186 | 0.508 | 18/18 | 18/18 |
| Phase 2A | `slow_drift_buffered_action_phase2a` | relation_lock | pseudo_reality_slow_drift | action_buffered | 18 | 3 | 2552 | 11.618 | 0.458 | 18/18 | 18/18 |
| Phase 2A | `slow_drift_low_coupling_action_phase2a` | relation_lock | pseudo_reality_slow_drift | action_low_coupling | 18 | 15 | 2552 | 11.252 | 0.490 | 18/18 | 18/18 |
| Phase 2B | `default_world_default_action_phase2b_24` | normal | pseudo_reality_default | action_default | 24 | 87 | 3674 | 15.691 | 0.467 | 24/24 | 24/24 |
| Phase 2B | `default_world_buffered_action_phase2b_36` | normal | pseudo_reality_default | action_buffered | 36 | 160 | 5522 | 22.920 | 0.468 | 36/36 | 36/36 |
| Phase 2B | `shock_world_default_action_phase2b_24` | shock | pseudo_reality_shock | action_default | 24 | 71 | 3674 | 14.506 | 0.545 | 24/24 | 24/24 |
| Phase 2B | `shock_world_conservative_action_phase2b_36` | shock | pseudo_reality_shock | action_conservative | 36 | 136 | 3861 | 16.703 | 0.546 | 36/36 | 36/36 |
| Phase 2B | `shock_world_buffered_action_phase2b_36` | shock | pseudo_reality_shock | action_buffered | 36 | 73 | 4895 | 19.097 | 0.520 | 36/36 | 36/36 |
| Phase 2B | `relation_lock_default_action_phase2b_24` | relation_lock | pseudo_reality_relation_lock | action_default | 24 | 34 | 3410 | 15.237 | 0.527 | 24/24 | 24/24 |
| Phase 2B | `relation_lock_conservative_action_phase2b_36` | relation_lock | pseudo_reality_relation_lock | action_conservative | 36 | 98 | 5038 | 23.524 | 0.554 | 36/36 | 36/36 |
| Phase 2B | `relation_lock_buffered_action_phase2b_36` | relation_lock | pseudo_reality_relation_lock | action_buffered | 36 | 55 | 5126 | 23.340 | 0.528 | 36/36 | 36/36 |
| Phase 2B | `exploration_loss_default_action_phase2b_24` | exploration_loss | pseudo_reality_exploration_loss | action_default | 24 | 149 | 3410 | 15.414 | 0.525 | 24/24 | 24/24 |
| Phase 2B | `exploration_loss_buffered_action_phase2b_36` | exploration_loss | pseudo_reality_exploration_loss | action_buffered | 36 | 232 | 5126 | 23.572 | 0.545 | 36/36 | 36/36 |
| Phase 2B | `high_noise_conservative_action_phase2b_24` | normal | pseudo_reality_high_noise | action_conservative | 24 | 134 | 3498 | 14.731 | 0.466 | 24/24 | 24/24 |
| Phase 2B | `high_noise_buffered_action_phase2b_36` | normal | pseudo_reality_high_noise | action_buffered | 36 | 189 | 5522 | 23.934 | 0.470 | 36/36 | 36/36 |
| Phase 2B | `slow_drift_default_action_phase2b_24` | relation_lock | pseudo_reality_slow_drift | action_default | 24 | 0 | 3410 | 15.204 | 0.443 | 24/24 | 24/24 |
| Phase 2B | `slow_drift_buffered_action_phase2b_36` | relation_lock | pseudo_reality_slow_drift | action_buffered | 36 | 30 | 5126 | 23.490 | 0.505 | 36/36 | 36/36 |
| Phase 2B | `slow_drift_low_coupling_action_phase2b_36` | relation_lock | pseudo_reality_slow_drift | action_low_coupling | 36 | 46 | 5126 | 23.184 | 0.501 | 36/36 | 36/36 |
| Phase 2C | `shock_early_high_default_phase2c` | shock | pseudo_reality_shock | action_default | 24 | 50 | 3674 | 14.231 | 0.520 | 24/24 | 24/24 |
| Phase 2C | `shock_early_high_conservative_phase2c` | shock | pseudo_reality_shock | action_conservative | 36 | 65 | 4488 | 16.948 | 0.537 | 36/36 | 36/36 |
| Phase 2C | `shock_early_high_buffered_phase2c` | shock | pseudo_reality_shock | action_buffered | 36 | 61 | 5368 | 19.262 | 0.524 | 36/36 | 36/36 |
| Phase 2C | `relation_lock_hard_default_phase2c` | relation_lock | pseudo_reality_relation_lock | action_default | 24 | 25 | 3410 | 15.622 | 0.501 | 24/24 | 24/24 |
| Phase 2C | `relation_lock_hard_conservative_phase2c` | relation_lock | pseudo_reality_relation_lock | action_conservative | 36 | 68 | 5049 | 23.575 | 0.559 | 36/36 | 36/36 |
| Phase 2C | `relation_lock_hard_buffered_phase2c` | relation_lock | pseudo_reality_relation_lock | action_buffered | 36 | 51 | 5126 | 22.868 | 0.534 | 36/36 | 36/36 |
| Phase 2C | `exploration_loss_no_exploration_default_phase2c` | exploration_loss | pseudo_reality_exploration_loss | action_default | 24 | 0 | 3410 | 15.898 | 0.446 | 24/24 | 24/24 |
| Phase 2C | `exploration_loss_no_exploration_buffered_phase2c` | exploration_loss | pseudo_reality_exploration_loss | action_buffered | 36 | 0 | 5126 | 24.065 | 0.451 | 36/36 | 36/36 |
| Phase 2C | `high_noise_default_phase2c` | normal | pseudo_reality_high_noise | action_default | 24 | 124 | 3674 | 15.402 | 0.469 | 24/24 | 24/24 |
| Phase 2C | `high_noise_conservative_phase2c` | normal | pseudo_reality_high_noise | action_conservative | 36 | 143 | 5379 | 22.787 | 0.513 | 36/36 | 36/36 |
| Phase 2C | `high_noise_buffered_phase2c` | normal | pseudo_reality_high_noise | action_buffered | 36 | 196 | 5522 | 23.179 | 0.515 | 36/36 | 36/36 |
| Phase 2C | `slow_drift_low_coupling_no_exploration_phase2c` | relation_lock | pseudo_reality_slow_drift | action_low_coupling | 36 | 0 | 5126 | 23.599 | 0.461 | 36/36 | 36/36 |
| Phase 2C | `slow_drift_buffered_weak_action_phase2c` | relation_lock | pseudo_reality_slow_drift | action_buffered | 36 | 33 | 5126 | 23.556 | 0.507 | 36/36 | 36/36 |
| Phase 2C | `default_weak_action_phase2c` | normal | pseudo_reality_default | action_default | 24 | 92 | 3498 | 14.969 | 0.457 | 24/24 | 24/24 |
| Phase 2C | `default_strong_action_boundary_probe_phase2c` | normal | pseudo_reality_default | action_default | 24 | 127 | 3674 | 15.050 | 0.453 | 24/24 | 24/24 |
| Phase 2C | `shock_no_exploration_buffered_phase2c` | shock | pseudo_reality_shock | action_buffered | 36 | 0 | 5522 | 20.677 | 0.437 | 36/36 | 36/36 |
| Phase 2C | `relation_lock_short_kt_window_phase2c` | relation_lock | pseudo_reality_relation_lock | action_conservative | 24 | 24 | 3322 | 15.365 | 0.534 | 24/24 | 24/24 |
| Phase 2C | `high_noise_short_kt_window_phase2c` | normal | pseudo_reality_high_noise | action_buffered | 24 | 125 | 3674 | 15.593 | 0.480 | 24/24 | 24/24 |
