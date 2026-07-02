# Phase 2G-4 v2 Premise Freeze Pack

## 1. Scope

Phase 2G-4 is a v2 premise-freeze pack, not v2 full validation. It freezes what the next v2 preliminary validation will inspect: profile status, baseline roles, metric availability, success/failure reading rules, missing evidence handling, and boundary/write-safety premises.

This pack is intentionally non-behavior-changing:

- it does not change v2 world dynamics;
- it does not change the v2 world implementation;
- it does not change ActionModule behavior, action primitives, action strength design, PressureTranslation formulas, ParameterWindow registry values, ShadowBox update formulas, hard safety, block/defer logic, acceptance criteria, write paths, or v2 integration;
- it adds a lightweight matrix and report/CSV readiness summaries only.

## 2. Background

Phase 2G-2d introduced the B-group dampen-only minimal repair for intermediate conservatism. Phase 2G-3 then consolidated A/C/D/Cross validation and low-risk visibility work; A/C/D/Cross passed and v2 trace readiness passed. Before entering v2 full validation, Phase 2G-4 freezes the premises so the next task does not over-read result-named profiles, short-run metrics, or upper-bound comparators.

The immediate reason for this freeze is that current v2 profiles are useful stress/readiness scenarios but are named by expected outcome tendencies. The next validation may use them, but paper-facing claims need cause-side parameterization rather than treating these profile names as the final experimental axis.

## 3. v2 World Boundary Contract

The v2 premise freeze keeps the following boundary contract closed:

- the world receives ActionFrame rows as the action-side input;
- v2 world code must not read G/K/O_t or ParameterBox directly as an input path;
- no G/K/O_t writeback is allowed;
- dry-run canonical writes must remain disabled;
- ActionModule must remain a one-way actuator/translator and must not inspect DEPT internals directly;
- ParameterBox direct input to ActionModule remains forbidden;
- boundary/write violations must remain zero.

The matrix exports `v2_boundary_safety_summary.csv` to record these checks per run.

## 4. v2 Profiles and Their Status

| profile | type | result-named? | preliminary use | final claim use | caution |
|---|---|---:|---:|---:|---|
| `pseudo_reality_v2_trust_collapse` | trust-collapse-tendency stress/readiness profile | yes | yes | no | Not the sole main axis; future cause-side parameterization is required. |
| `pseudo_reality_v2_shrinking_equilibrium` | shrinking-equilibrium-tendency stress/readiness profile | yes | yes | no | Not the sole main axis; future cause-side parameterization is required. |
| `pseudo_reality_v2_public_stability_hidden_decay` | surface-stability/hidden-decay stress/readiness profile | yes | yes | no | Use for preliminary readiness only; final claims need cause-side parameters. |

These profiles may be used in Phase 2G-5 preliminary validation. They must not be described as proving external superiority or as fully representing real social systems.

## 5. Baseline Comparison Plan

| baseline | mode | action profile | purpose | production candidate? |
|---|---|---|---|---:|
| no_action / no_intervention | relaxed with no exploration and near-zero action settings where available | `action_conservative` with run overrides | natural drift/readiness reference | no |
| current | `current` | `action_conservative` | old conservative baseline | no |
| relaxed_legacy_dampen_075 | `relaxed_legacy_dampen_075` | `action_conservative` | rollback/comparison baseline | no |
| repaired relaxed | `relaxed` | `action_conservative` | Phase 2G-2d current main candidate | yes |
| flat | `flat` | `action_conservative` | upper-bound comparator only | no |
| action_conservative | `relaxed` | `action_conservative` | optional action profile comparison | no |
| action_buffered | `relaxed` | `action_buffered` | optional buffered action comparison | no |
| no_exploration_relaxed | `relaxed`, `exploration_enabled=false` | `action_conservative` | optional no-exploration comparison | no |

`flat` remains an upper-bound comparator and is not a production candidate.

## 6. Metric Availability

The preliminary v2 metric plan is fixed as availability-first. If an exact metric is not already exported by the current traces, Phase 2G-4 records `not_available`/missing evidence instead of inventing a new formula.

| metric | source trace | available? | exact/proxy | primary/secondary |
|---|---|---:|---|---|
| hidden_damage mean/final | `v2_hidden_trace` | matrix-checked | exact if column exists | primary |
| fatigue mean/final | `v2_hidden_trace` | matrix-checked | exact if column exists | primary |
| information_quality mean/final | `v2_information_trace` | matrix-checked | exact if column exists | primary |
| cooperation_intent mean/final | `v2_game_trace` | matrix-checked | exact if column exists | primary |
| defensiveness mean/final | `v2_game_trace` | matrix-checked | exact if column exists | primary |
| private_resource mean | `v2_resource_trace` | matrix-checked | exact if column exists | primary |
| latent_pressure mean | `v2_hidden_trace` | matrix-checked | exact if column exists | primary |
| relation_lock_proxy | `v2_game_trace` or existing summary | matrix-checked | proxy | primary |
| recovery_after_shock_proxy | v2/game trace if exported | matrix-checked | proxy | primary |
| action_mass_total / by_channel | `action_frame` | matrix-checked | exact from ActionFrame | primary |
| boundary/write violation counts | boundary/write audits | matrix-checked | exact audit counts | primary |
| volatility_proxy, collapse_delay_proxy, hidden_decay_gap, public_stability_hidden_decay_gap | v2 traces or existing summaries | matrix-checked | proxy where available | secondary |
| projection/action/result/v2 trace row counts | exported CSVs | matrix-checked | exact row counts | secondary |

## 7. Success / Failure Reading Rules

Good signs in Phase 2G-5 preliminary validation include:

- hidden damage and fatigue do not worsen versus relevant baselines, or are lower;
- information quality and cooperation intent are maintained;
- defensiveness does not rise excessively;
- action mass does not disappear completely and does not explode into instability;
- relation unlock, coupling relief, buffer increase, or recovery-after-shock proxies can be read without boundary/write violations;
- boundary/write counts remain zero;
- repaired relaxed shows useful improvement without requiring the `flat` upper-bound comparator.

Bad signs include:

- hidden damage or fatigue increases;
- information quality or cooperation intent drops;
- defensiveness rises excessively;
- action mass disappears, or grows enough to destabilize the run;
- any boundary/write violation appears;
- repaired relaxed worsens versus legacy relaxed;
- only `flat` wins;
- no-action is better than the candidate mode on the intended safety/stability dimensions.

Repaired relaxed does not need to win every metric. The reading must include hidden degradation, recovery, information quality, and boundary safety, not just short-run apparent gain.

This pack does not claim that DEPT/H-DEPT always wins, proves external benchmark superiority, proves safety, is deployable in the real world, fully models real societies, or completes paper-level v2 claims.

## 8. Matrix Design

The added matrix is `configs/matrices/matrix_phase2g4_v2_premise_freeze.json`. It is intentionally lightweight: 16 bounded runs with 4-step v2 runs and short non-v2 sanity/continuity checks. It covers:

- `pseudo_reality_v2_trust_collapse` no-action/minimal-action readiness, repaired relaxed, legacy relaxed, flat, current, high-noise, no-exploration, and buffered-action runs;
- `pseudo_reality_v2_shrinking_equilibrium` repaired relaxed, legacy relaxed, and flat;
- `pseudo_reality_v2_public_stability_hidden_decay` repaired relaxed, legacy relaxed, and flat;
- non-v2 `default_relaxed_smoke` and `relation_unlock_pressure_relaxed` sanity/continuity runs.

The matrix is not a full validation matrix and must not be presented as if it produced v2 superiority evidence.

## 9. Validation Results

Validation commands for this PR are:

```bash
python -m json.tool configs/matrices/matrix_phase2g4_v2_premise_freeze.json > /tmp/matrix_phase2g4_v2_premise_freeze.validated.json
python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2g4_v2_premise_freeze.json --output-dir validation_runs/phase2g4_v2_premise_freeze
cat validation_runs/phase2g4_v2_premise_freeze/matrix_summary.json
```

The expected pass interpretation is premise/readiness pass with zero boundary/write violations and with missing evidence explicitly recorded where exact metric columns are not currently exported.

## 10. Missing Evidence

Phase 2G-4 intentionally does not force exact formulas for every candidate metric. Missing exact columns are reported in `v2_metric_availability_summary.csv` and summarized in `v2_missing_evidence_summary.csv`. Missing evidence does not get hidden or converted into a passing scientific claim.

Known premise-level missing/deferred evidence:

- some v2 primary/secondary metrics may not exist as exact exported columns yet;
- cause-side parameterized profiles are not implemented yet.

## 11. Deferred Design Candidates

Future cause-side parameterization candidates, deferred from this pack, are:

- `information_asymmetry`
- `hidden_state_visibility`
- `private_information_rate`
- `misread_probability`
- `information_delay`
- `information_distortion`
- `resource_inequality`
- `commons_dependency`
- `short_term_gain_pressure`
- `relation_lock_strength`
- `recovery_delay`
- `action_cost`

These are candidates for v2.1/v3 or a dedicated Phase 2G-5 design task, not implementation changes in this PR.

## 12. Recommendation

If the matrix passes with zero boundary/write violations and the v2 premise-freeze summaries are present, proceed to **Phase 2G-5 v2 Preliminary Validation Pack**.

If trace or metric availability is insufficient for the desired preliminary validation, split out **Phase 2G-5 v2 Metric Export Repair**. If the result-named profile concern needs immediate resolution before preliminary validation, split out **Phase 2G-5 v2 Cause-side Parameterization Design**. If boundary/readiness violations appear, split out additional boundary/readiness repair before v2 preliminary validation.

## 13. Conclusion

Phase 2G-4 freezes the v2 validation premises without changing v2 behavior. It keeps repaired relaxed, legacy relaxed, and flat comparator roles intact; records profile cautions; fixes baseline and metric-availability plans; preserves the no-write/action-boundary contract; and recommends moving to Phase 2G-5 preliminary validation only after the lightweight premise matrix passes.
