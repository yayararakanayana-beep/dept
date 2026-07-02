# Phase 2G-6 v2 Extended Validation + Metric Adequacy Pack

## 1. Scope

This pack is a v2 extended validation and metric adequacy check. It is not v2 final validation, does not prove superiority, does not prove safety, and is not deployment evidence. The work keeps behavior-changing surfaces frozen: no v2 world dynamics changes, no ActionModule tuning, no action primitive changes, no PressureTranslation changes, no ParameterWindow registry changes, no ParameterShadowBox update changes, no hard-safety changes, no block/defer changes, and no write-path enablement.

The pack adds a bounded validation matrix and export summarizers for existing traces only. New metric definitions that would change semantics are deliberately deferred.

## 2. Background

Phase 2G-5 provided short-horizon preliminary evidence that repaired relaxed remained comparable, preserved action mass, and kept boundary/write violations at zero, while state metrics were mixed and some metric evidence was missing. Phase 2G-6 expands that check with additional seeds, slightly longer horizons, v2 profile-wise comparison, and explicit metric adequacy classification.

The v2 profiles used here are result-named stress/readiness profiles. They are acceptable for extended preliminary validation, but they must not be used as final claim basis.

## 3. Matrix Design

Matrix file: `configs/matrices/matrix_phase2g6_v2_extended_validation_metric_adequacy.json`.

The matrix contains 48 runs:

- Three v2 profile families: `trust_collapse`, `shrinking_equilibrium`, and `public_stability_hidden_decay`.
- Required baselines: near-zero-action, current, `relaxed_legacy_dampen_075`, repaired relaxed, and flat.
- Optional comparators: `action_buffered_relaxed` and `no_exploration_relaxed`.
- Seed expansion: 3 seeds for trust collapse and 2 seeds for the other two v2 profiles.
- Longer-horizon emphasis: repaired relaxed long runs at 12-14 steps.
- Non-v2 sanity runs: default relaxed smoke, relation-lock relaxed, and high-noise relaxed.

Near-zero-action is an approximation, not exact `no_action`: exploration is disabled and action strength/coupling are set to tiny values.

## 4. Metrics and Adequacy Classification

The extended exports classify metrics as:

- `exact_available`: directly readable from existing traces.
- `proxy_available`: readable as an explicit proxy, not an exact claim.
- `row_count_only`: only trace presence or row counts are available.
- `not_available`: not readable from current exports.
- `needs_metric_export_repair`: future metric export repair is needed for exact secondary claims.

Core exact/proxy coverage was sufficient for cautious extended validation of action mass, hidden damage, fatigue, information quality, cooperation/defensiveness proxies, trace availability, and write/boundary counts. Missing or insufficient evidence remains for exact recovery/collapse timing and hidden-decay gap claims.

## 5. Validation Results

Commands run:

```bash
python -m json.tool configs/matrices/matrix_phase2g6_v2_extended_validation_metric_adequacy.json > /tmp/matrix_phase2g6_v2_extended_validation_metric_adequacy.validated.json
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2g6_v2_extended_validation_metric_adequacy.json --output-dir validation_runs/phase2g6_v2_extended_validation_metric_adequacy
```

Observed matrix result:

- Runs: 48.
- Overall pass: true.
- Extended validation pass: true.
- Boundary violations: 0.
- Dry-run write violations: 0.
- Forbidden writes: 0.
- v2 trace-available run count: 45 v2 runs.
- Extended summary CSVs present: yes.
- Metric export repair recommended: yes, for exact secondary claims.

## 6. Profile-wise Extended Results

### trust_collapse

Multi-seed preliminary evidence suggests repaired relaxed preserved materially more action mass than current and stayed in the same broad range as legacy relaxed and flat. Repaired relaxed action mass averaged about 12.58 across available repaired trust-collapse runs; current averaged about 5.05, legacy relaxed about 11.84, flat about 12.06, and near-zero-action about 10.97.

State metrics remain mixed. Longer repaired runs showed hidden damage and fatigue increasing, information quality and cooperation decreasing, and defensiveness increasing. This is not a superiority signal; it is evidence that cause-side parameterization and exact metric exports remain necessary before stronger claims.

### shrinking_equilibrium

Repaired relaxed action mass averaged about 10.13, above current at about 3.90 and slightly above legacy/flat/near-zero-action in this lightweight matrix. State metrics again remained mixed, with longer-horizon repaired relaxed showing increased hidden damage/fatigue and decreased information quality/cooperation.

### public_stability_hidden_decay

Repaired relaxed action mass averaged about 10.11, above current at about 3.90 and broadly comparable to legacy/flat/near-zero-action. The longer-horizon repaired run showed increased hidden damage/fatigue and lower information quality/cooperation, so this profile also remains preliminary and not final claim evidence.

## 7. Seed Stability

Seed stability was adequate for a preliminary pass on action-mass preservation and safety/boundary invariants. State metrics showed mixed profile-specific movement, and long-run repaired relaxed samples increased the spread for repaired relaxed action mass. This does not invalidate the extended preliminary matrix, but it prevents stronger claims.

## 8. Longer-horizon Reading

Longer-horizon repaired relaxed runs did not lose action mass. However, all longer repaired runs showed adverse state-direction deltas: hidden damage and fatigue increased, information quality and cooperation decreased, and defensiveness/latent pressure increased. This indicates that longer-horizon evidence is mixed rather than cleanly positive.

## 9. Metric Adequacy

Sufficient for cautious extended validation:

- hidden damage, fatigue, and information quality as existing trace metrics.
- cooperation intent and defensiveness as available proxies.
- action mass total/mean/by-channel from `action_frame`.
- trace row counts and boundary/write counts.

Insufficient for exact claims:

- private resource and latent pressure were classified as primary but missing from the current row-level availability scan.
- relation-lock is proxy-only in this pack.
- recovery after shock, collapse delay, hidden decay gap, and public-stability hidden-decay gap need metric export repair before exact secondary claims.

## 10. Safety and Boundary

The matrix kept safety/write boundaries closed:

- `boundary_violation_total = 0`.
- `dry_run_write_violation_count = 0`.
- `forbidden_write_count = 0`.
- No direct ParameterBox input to ActionModule was detected.
- No G/K writeback was detected.
- No O_t writeback was detected.
- No canonical write was detected.
- World input remains ActionFrame-only for this validation reading.

These are validation observations, not a safety proof.

## 11. Interpretation

Extended preliminary evidence suggests repaired relaxed remains comparable under the selected v2 result-named profiles and preserves action mass better than the old current baseline. It does not establish superiority over legacy relaxed, flat, or near-zero-action on state outcomes. Longer-horizon state signals are mixed and sometimes adverse.

Metric export repair is required before exact secondary claims. Cause-side parameterization design remains necessary because result-named profiles are not suitable final claim axes.

## 12. Recommended Next Task

1. **Phase 2G-7 Cause-side Parameterization Design Pack** — high priority; needed because current v2 profiles are result-named and cannot support final claims.
2. **Phase 2G-7 v2 Metric Export Repair** — high priority before exact secondary claims on recovery/collapse/hidden-decay gaps.
3. **Phase 2G-7 ActionModule v2 Tuning Probe** — optional after metrics and cause-side axes clarify whether state degradation is caused by action coupling or world dynamics.
4. **Phase 2G-7 Freeze Decision Pack** — only after cause-side and metric-export work; not yet appropriate.

## 13. Conclusion

Phase 2G-6 strengthens Phase 2G-5 from a short preliminary check into a multi-seed, longer-horizon, metric-adequacy-oriented validation pack. Repaired relaxed remains a viable production candidate for continued investigation, with action mass preserved and boundary/write counts at zero. The evidence remains mixed for state metrics, especially in longer horizons, and missing metric evidence is explicit rather than hidden.

The recommended path is to proceed to cause-side parameterization design and v2 metric export repair before attempting final v2 validation.
