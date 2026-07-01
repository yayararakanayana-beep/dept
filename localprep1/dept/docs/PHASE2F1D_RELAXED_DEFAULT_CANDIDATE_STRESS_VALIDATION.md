# Phase 2F-1d Relaxed Default Candidate Stress Validation

## 1. Scope

This PR adds an additional stress-validation matrix and report for `intermediate_conservatism_mode = relaxed`, the provisional default candidate from Phase 2F-1c. It is a validation PR only: it does **not** change the default from `current`, does **not** relax acceptance, and does **not** alter action policy, gate behavior, canonical-write behavior, or ActionModule boundaries.

`flat` is included only as an upper-bound / risk comparison. It is not treated as a default candidate.

## 2. Background

Phase 2F-1b showed that loosening intermediate conservatism improved relation-unlock pressure ActionFrame rows and action mass availability. Phase 2F-1c extended that comparison to a 12-step long-run matrix and found clean hard boundaries, improved rows/action mass under `relaxed`, and no available uncertainty / volatility / coupling regression versus `current`.

The remaining caveats were that a 24-step attempt exceeded local runtime limits, `m_overall` was not directly exported, `relaxed` remained provisional, and `flat` was only an upper-bound comparator.

## 3. Default Decision Question

**Is relaxed strong enough to proceed to a default-change PR?**

Japanese intent: relaxedをdefault変更PRへ進めてよいか？

## 4. Matrix Design

- Matrix: `configs/matrices/matrix_phase2f1d_relaxed_default_candidate_stress_validation.json`
- Runs: 30
- Steps: 12 committed steps per run.
- Seeds: `101` and `202` for `current` / `relaxed`; seed `101` for auxiliary `flat` upper-bound checks.
- Groups:
  - `relation_unlock_pressure_stress`
  - `relation_unlock_pressure_dominant_stress`
  - `relation_unlock_no_exploration_stress`
  - `high_noise_relation_unlock_stress`
  - `shock_recovery_relation_unlock_stress`
  - `relation_lock_default_control_stress`
- Mode handling:
  - `current`: baseline.
  - `relaxed`: default candidate under test.
  - `flat`: one-seed upper-bound comparator only.

A 24-step, 30-run matrix was attempted first but was interrupted after exceeding local runtime expectations. The committed design therefore uses the Phase 2F-1c-compatible fallback: 12-step runs across all required stress groups, with broader `current` / `relaxed` coverage and representative `flat` coverage.

## 5. Validation Commands

```bash
cd localprep1/dept
python -m json.tool configs/matrices/matrix_phase2f1d_relaxed_default_candidate_stress_validation.json > /tmp/matrix_phase2f1d_relaxed_default_candidate_stress_validation.validated.json
python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2f1d_relaxed_default_candidate_stress_validation.json --output-dir validation_runs/phase2f1d_relaxed_default_candidate_stress_validation
cat validation_runs/phase2f1d_relaxed_default_candidate_stress_validation/matrix_summary.json
```

## 6. Matrix Summary

| runs | overall_pass | boundary_violation_total | dry_run_write_violation_count | forbidden_write_count | projection_min | action_frame_min | action_source_audit_columns_present |
|---:|:---:|---:|---:|---:|---:|---:|:---:|
| 30 | true | 0 | 0 | 0 | 0 | 1287 | true |

`projection_min = 0` is expected for no-exploration stress runs and did not fail acceptance because the ActionFrame rows remained non-zero.

## 7. Current vs Relaxed vs Flat Stress Comparison

The table aggregates both `current` / `relaxed` seeds and the representative `flat` seed. Because `flat` has one seed, its rows/action_mass are an auxiliary upper-bound sample rather than a direct two-seed total.

| group | seed count | steps | current rows | relaxed rows | flat rows | current action_mass | relaxed action_mass | flat action_mass | relaxed rows gain | relaxed action_mass increase | flat marginal rows gain | flat marginal action_mass increase | boundary status | interpretation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| relation_unlock_pressure_stress | c/r=2, f=1 | 12 | 3212 | 3388 | 1694 | 14.5704 | 24.2047 | 15.1944 | +176 | +9.6343 | n/a one-seed | n/a one-seed | clean | relaxed improves rows with bounded safety; flat remains comparator only. |
| relation_unlock_pressure_dominant_stress | c/r=2, f=1 | 12 | 3212 | 3388 | 1694 | 14.5704 | 24.2047 | 15.1944 | +176 | +9.6343 | n/a one-seed | n/a one-seed | clean | relaxed repeats pressure thinning improvement under stronger action limits. |
| relation_unlock_no_exploration_stress | c/r=2, f=1 | 12 | 3212 | 3388 | 1694 | 14.5704 | 29.0372 | 15.1944 | +176 | +14.4668 | n/a one-seed | n/a one-seed | clean | relaxed remains active without exploration projection; projection zero is expected. |
| high_noise_relation_unlock_stress | c/r=2, f=1 | 12 | 3322 | 3652 | 1826 | 14.1646 | 26.6053 | 15.4712 | +330 | +12.4407 | n/a one-seed | n/a one-seed | clean | relaxed gives the largest row gain under high noise. |
| shock_recovery_relation_unlock_stress | c/r=2, f=1 | 12 | 2585 | 3652 | 1826 | 11.3461 | 21.3278 | 14.2573 | +1067 | +9.9817 | n/a one-seed | n/a one-seed | clean | relaxed materially improves rows during shock recovery. |
| relation_lock_default_control_stress | c/r=2, f=1 | 12 | 3212 | 3388 | 1694 | 14.5709 | 24.5135 | 15.1922 | +176 | +9.9426 | n/a one-seed | n/a one-seed | clean | relaxed improves rows without boundary regression in the control condition. |

## 8. Cost-Performance Findings

- `relaxed` improved total ActionFrame rows over `current` in every stress group.
- The strongest row gain was shock recovery: `+1067` rows over the two-seed baseline.
- `relaxed` consumed more action mass than `current`, as expected for a relaxed conservatism setting.
- The auxiliary `flat` one-seed samples are not sufficient for a two-seed total comparison, but the per-seed upper-bound samples did not justify treating `flat` as a candidate. `flat` remains risk / upper-bound evidence only.
- Rows-gain-per-action-mass is favorable for `relaxed` where row gains are large, especially shock recovery. In pressure/control groups, `relaxed` is better characterized as a minimum effective relaxation rather than a maximal-efficiency setting.

## 9. Relation Unlock Outcome Findings

- Relation-unlock-family rows remained stable at `1012` for each two-seed `current` and `relaxed` group, while total ActionFrame rows improved under `relaxed`.
- Relation-unlock-family action mass increased under `relaxed`, showing that pressure thinning was not caused by row disappearance or zeroing.
- High-noise and shock-recovery groups showed sustained non-zero ActionFrame rows with no long-run collapse across the committed 12-step fallback.
- `guarded_relation_unlock` and `coupling_relief` remained present via the relation-unlock-family aggregation; no evidence showed delayed unlock disappearance.

## 10. World Outcome Safety Findings

`m_overall_proxy_delta_mean` is summary-only and defined as:

```text
mean_delta(exploration + reversibility + entropy)
- mean_delta(volatility + uncertainty + relation_lock + coupling) / 4
```

This follows the requested proxy shape and uses exported `world_transition_audit` mean deltas. It does not change runner behavior.

| group | current m_proxy | relaxed m_proxy | relaxed uncertainty | relaxed volatility | relaxed coupling | relaxed relation_lock | safety read |
|---|---:|---:|---:|---:|---:|---:|---|
| relation_unlock_pressure_stress | -0.021481 | -0.020953 | 0.000339 | 0.000966 | 0.005869 | 0.010034 | relaxed slightly better proxy; no explosion. |
| relation_unlock_pressure_dominant_stress | -0.021481 | -0.020953 | 0.000339 | 0.000966 | 0.005869 | 0.010034 | same stress signature as pressure stress. |
| relation_unlock_no_exploration_stress | -0.021481 | -0.020685 | 0.000296 | 0.000953 | 0.005811 | 0.009999 | relaxed slightly better proxy with no exploration. |
| high_noise_relation_unlock_stress | 0.003594 | 0.003878 | -0.000218 | 0.000788 | -0.001152 | 0.000470 | relaxed improves proxy and does not worsen uncertainty/coupling. |
| shock_recovery_relation_unlock_stress | -0.019202 | -0.018831 | 0.017083 | 0.023293 | -0.000189 | -0.000669 | shock drives uncertainty/volatility, but relaxed is not worse than current. |
| relation_lock_default_control_stress | -0.021371 | -0.020824 | 0.000295 | 0.000889 | 0.006097 | 0.010297 | no over-unlock symptom; relation_lock delta remains near current. |

No group showed relaxed uncertainty, volatility, coupling, or m_overall_proxy materially worse than current. Relation-lock deltas under `relaxed` stayed close to current and did not indicate excessive unlock.

## 11. Boundary Safety Findings

- `boundary_violation_total = 0`
- `dry_run_write_violation_count = 0`
- `forbidden_write_count = 0`
- `direct_parameter_box_input_to_actionmodule = false` in all collected per-run metrics.
- Canonical writes remained disabled/dry-run only; no canonical write, G/K writeback, O_t writeback, or world builder writeback was reported.
- ActionModule input remained ActionFrame-only according to the action execution audit columns.

## 12. Default Candidate Assessment

Assessment: **strong default candidate**.

Reasoning:

- `relaxed` improved ActionFrame rows over `current` in all six stress groups.
- Hard safety boundaries remained clean.
- `m_overall_proxy_delta_mean` did not worsen versus current in the aggregate stress groups.
- Uncertainty / volatility / coupling did not show relaxed-specific explosion.
- Relation-lock changes stayed near current, with no evidence of excessive unlock.
- `flat` remains an upper-bound comparator, not a candidate.

This most closely matches Pattern A / Pattern D: `relaxed` improves rows and relation-unlock pressure behavior while retaining boundary safety; `flat` is retained only for upper-bound comparison.

## 13. Hole Candidate List

| severity | condition | symptom | likely source | recommended next task |
|---|---|---|---|---|
| medium | 24-step full matrix runtime | 24-step, 30-run attempt exceeded local runtime expectations | matrix size and runner cost | Run a selected 24-step subset or optimize summary-only matrix execution. |
| low | `projection_min = 0` in no-exploration stress | expected zero projection rows | `exploration_enabled = false` stress design | Keep documented; do not treat as failure when ActionFrame rows are non-zero. |
| observation_only | `flat` has one seed | upper-bound comparison is representative, not statistically broad | runtime-aware matrix design | Keep flat as auxiliary comparator or add selected flat seeds only if needed. |
| observation_only | m_overall is proxy only | direct `m_overall` is not exported | current runner summary surface | Formalize summary-only `m_overall_proxy` export if useful. |

## 14. Recommendation

Recommended:

- Proceed to a default-change PR from `current` to `relaxed`, if reviewers accept the 12-step fallback evidence.
- Keep `flat` as validation-only upper-bound evidence; do not make it a default candidate.
- Preserve current acceptance and hard boundary checks.
- Consider a selected 24-step subset before or during the default-change PR if reviewers require longer-run confirmation.
- Formalize `m_overall_proxy` as summary-only export in future validation tooling.

Not recommended:

- Do not change the default in this PR.
- Do not relax safety boundaries or ActionModule input constraints.

## 15. Conclusion

Phase 2F-1d supports `relaxed` as a strong default candidate under the committed runtime-safe stress design. The next task can be a narrowly scoped default-change PR, with `flat` retained only as an upper-bound / risk comparator and with all canonical-write, dry-run-write, G/K/O_t writeback, and ActionModule boundary constraints unchanged.
