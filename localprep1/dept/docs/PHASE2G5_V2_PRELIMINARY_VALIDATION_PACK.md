# Phase 2G-5 v2 Preliminary Validation Pack

## 1. Scope

This pack is a **v2 preliminary validation** pack. It is not v2 full validation, does not make a superiority claim, and does not present a safety proof. No behavior-changing repair is introduced here.

The goal is to check whether repaired relaxed can be compared in the v2 pseudo-reality profiles using existing trace and metric exports, whether action mass remains observable, and whether boundary/write counts remain clean.

## 2. Background

Phase 2G-4 froze the v2 premise, including the result-named v2 profiles, baseline comparison plan, metric availability approach, and boundary contract. Phase 2G-2d left repaired relaxed as the current dampen-only minimal repair with dampen factor 0.875, while retaining `relaxed_legacy_dampen_075` as the old relaxed comparison baseline.

This validation exists because v2 behavior cannot be read only through short-term stability. Hidden damage, fatigue, information quality, cooperation intent, defensiveness, private resource, latent pressure, action mass, and write/boundary traces must be examined together.

## 3. Matrix Design

Added matrix: `configs/matrices/matrix_phase2g5_v2_preliminary_validation.json`.

The matrix contains 26 lightweight runs:

- v2 profile families:
  - `pseudo_reality_v2_trust_collapse`
  - `pseudo_reality_v2_shrinking_equilibrium`
  - `pseudo_reality_v2_public_stability_hidden_decay`
- Required baselines:
  - near-zero-action approximation
  - current
  - `relaxed_legacy_dampen_075`
  - repaired relaxed (`relaxed`)
  - flat upper-bound comparator
- Additional comparisons:
  - `action_buffered_relaxed`
  - `no_exploration_relaxed`
- Non-v2 sanity runs:
  - `default_relaxed_smoke`
  - `relation_unlock_pressure_relaxed`
  - `high_noise_relaxed`

The no-action baseline is represented as a **near-zero-action approximation**, not a claim of perfect no action. It disables exploration and uses very small configured action strength/coupling values, but existing action-frame exports still expose planned action mass; this is therefore reported explicitly as near-zero-action evidence only.

These v2 profiles are result-named stress/readiness profiles. They are acceptable for this preliminary check but must not be used as final claim basis.

## 4. Metrics and Availability

The preliminary pack exports:

- `v2_preliminary_validation_summary.csv`
- `v2_profile_mode_comparison.csv`
- `v2_metric_by_run_summary.csv`
- `v2_metric_delta_vs_baseline.csv`
- `v2_action_channel_comparison.csv`
- `v2_safety_boundary_summary.csv`
- `v2_preliminary_reading_summary.csv`
- `v2_missing_metric_evidence.csv`
- `v2_next_task_recommendation.csv`

Primary state metrics are aggregated as mean/final/delta where available. Action metrics are reported as total/by-channel/row counts. Safety metrics are reported as violation counts. Proxy metrics remain labelled as proxy, and unavailable exact metrics are reported as missing evidence.

## 5. Validation Results

Validation commands completed successfully:

- `python -m json.tool configs/matrices/matrix_phase2g5_v2_preliminary_validation.json > /tmp/matrix_phase2g5_v2_preliminary_validation.validated.json`
- `python -m compileall .`
- `python scripts/run_smoke_validation.py`
- `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2g5_v2_preliminary_validation.json --output-dir validation_runs/phase2g5_v2_preliminary_validation`

Matrix summary:

- runs: 26
- overall_pass: true
- v2_preliminary_pass: true
- v2 profile families: 3
- v2 trace available run count: 23 v2 runs
- boundary_violation_total: 0
- dry_run_write_violation_count: 0
- forbidden_write_count: 0
- recommended_next_task: Phase 2G-6 v2 Multi-seed / Longer-horizon Validation Pack, with v2 Metric Export Repair if exact secondary metrics are required.

## 6. Profile-wise Results

### trust_collapse

The trust-collapse profile produced readable v2 hidden, game, resource, information, and action-effect traces. Repaired relaxed was comparable to current, legacy relaxed, near-zero-action, flat, no-exploration relaxed, and action-buffered relaxed.

Observed profile averages:

| baseline | hidden_damage | fatigue | information_quality | cooperation_intent | defensiveness | action_mass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| near-zero-action | 0.375279 | 0.430887 | 0.251550 | 0.389192 | 0.568674 | 6.241021 |
| current | 0.352065 | 0.401196 | 0.246585 | 0.390143 | 0.601840 | 2.918482 |
| legacy relaxed | 0.349359 | 0.380430 | 0.243994 | 0.395399 | 0.560569 | 7.010395 |
| repaired relaxed | 0.357822 | 0.416581 | 0.249411 | 0.407861 | 0.570217 | 7.023890 |
| flat | 0.344394 | 0.455810 | 0.256628 | 0.400401 | 0.581829 | 7.176753 |

Preliminary reading: repaired relaxed remains comparable and preserves action mass, but it is not uniformly lower on hidden damage/fatigue than all references. This is not a superiority result.

### shrinking_equilibrium

The shrinking-equilibrium profile produced readable v2 traces and allowed comparison across required baselines.

| baseline | hidden_damage | fatigue | information_quality | cooperation_intent | defensiveness | action_mass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| near-zero-action | 0.286051 | 0.376639 | 0.485996 | 0.454619 | 0.570807 | 5.099256 |
| current | 0.324329 | 0.392423 | 0.446814 | 0.458894 | 0.533820 | 2.400705 |
| legacy relaxed | 0.340106 | 0.404252 | 0.457342 | 0.428367 | 0.578987 | 5.827712 |
| repaired relaxed | 0.334384 | 0.350746 | 0.464489 | 0.404881 | 0.586333 | 5.806850 |
| flat | 0.310174 | 0.389657 | 0.472137 | 0.453363 | 0.556869 | 5.900780 |

Preliminary reading: repaired relaxed reduces fatigue relative to legacy relaxed in this short run and keeps action mass near legacy/flat levels, while cooperation intent is lower than current and near-zero-action. Longer-horizon and multi-seed validation is required.

### public_stability_hidden_decay

The public-stability/hidden-decay profile produced readable v2 traces and baseline comparisons.

| baseline | hidden_damage | fatigue | information_quality | cooperation_intent | defensiveness | action_mass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| near-zero-action | 0.384936 | 0.411652 | 0.428750 | 0.404479 | 0.595879 | 5.304666 |
| current | 0.408987 | 0.423135 | 0.413884 | 0.425961 | 0.570290 | 2.371629 |
| legacy relaxed | 0.387202 | 0.441659 | 0.398578 | 0.452535 | 0.573795 | 5.828584 |
| repaired relaxed | 0.364832 | 0.424118 | 0.405202 | 0.413883 | 0.556913 | 5.803200 |
| flat | 0.380460 | 0.407790 | 0.415182 | 0.444150 | 0.539899 | 5.885942 |

Preliminary reading: repaired relaxed appears promising on hidden damage and defensiveness relative to several references, while information quality and cooperation remain mixed. This remains preliminary evidence only.

## 7. Repaired Relaxed Comparison

- vs near-zero-action: repaired relaxed is comparable but not uniformly better across all v2 profile metrics. The near-zero baseline is only an approximation.
- vs current: repaired relaxed generally restores action mass relative to current; state metric comparisons are mixed by profile.
- vs legacy relaxed: repaired relaxed preserves comparable action mass and shows some improved readings in selected profile/metric pairs, but not all.
- vs flat: flat remains an upper-bound comparator only and is not a production candidate. Repaired relaxed is evaluated as the only current production candidate in this pack.

## 8. Safety and Boundary

The validation did not modify v2 world dynamics, ActionModule behavior, action primitives, PressureTranslation, ParameterWindow registry values, ParameterShadowBox update logic, hard safety, block/defer rules, acceptance conditions, write paths, or v2 integration.

Observed boundary/write results:

- boundary_violation_total: 0
- dry_run_write_violation_count: 0
- forbidden_write_count: 0
- direct ParameterBox input to ActionModule: not detected
- G/K writeback: not detected
- O_t writeback: not detected
- canonical write: not detected
- world input remains ActionFrame-only in the exported safety summaries

## 9. Missing Metric Evidence

Missing evidence is exported in `v2_missing_metric_evidence.csv`. Exact columns for several secondary proxies are not currently exported, including recovery-after-shock, collapse-delay, hidden-decay-gap, and public-stability-hidden-decay-gap. These are not hidden or converted into exact claims.

This affects exact secondary conclusions and points to a future v2 Metric Export Repair if those metrics must be claimed precisely.

## 10. Preliminary Interpretation

Preliminary evidence suggests that repaired relaxed is comparable in this lightweight v2 preliminary setting and that the existing v2 traces can be read for core metrics. It appears to preserve action mass relative to current and remains close to legacy/flat action mass levels in the short matrix.

The state-metric evidence is mixed and profile-dependent. Additional multi-seed and longer-horizon validation is required before stronger conclusions. Metric export repair may be needed for exact secondary/proxy claims.

## 11. Recommended Next Task

Recommended next task:

1. **Phase 2G-6 v2 Multi-seed / Longer-horizon Validation Pack**
   - Priority: high
   - Condition: proceed because boundary/write counts are zero and core v2 metrics are readable.
2. **Phase 2G-6 v2 Metric Export Repair**
   - Priority: medium
   - Condition: needed before exact claims on proxy-only or unavailable secondary metrics.

Other possible follow-ups remain cause-side parameter sweep design, boundary/readiness repair if future violations appear, or ActionModule v2 tuning probe if action mass becomes too small or unstable in longer runs.

## 12. Conclusion

Phase 2G-5 adds a bounded preliminary validation matrix and summary exports for comparing no/near-zero action, current, legacy relaxed, repaired relaxed, and flat across v2 stress/readiness profiles. The run completed with overall pass true, v2 preliminary pass true, readable v2 traces for v2 runs, and zero boundary/write violations.

This is preliminary readiness evidence only. It is not v2 full validation, not a superiority claim, not a safety proof, and not real-world deployment evidence.
