# PseudoReality v2 RC1 Preparation Design

This document prepares the repository for a future PseudoReality v2-RC1 freeze. It is a **docs-only preparation design**. It does not freeze v2-RC1, does not change code, does not change configuration, does not change matrices, and does not introduce new validation behavior.

PseudoReality v2-RC1 is not intended to mean that the full PseudoReality v2 world model is complete. It is intended to freeze the minimum closed-loop validation surface that is already present for an additional asymmetric dynamic-game pseudo reality system.

PseudoReality v2-RC1 is therefore:

- Not performance validation.
- Not a superiority claim for the v2 world.
- Not formal adoption of H-DEPT diagnostic indicators.
- Not a replacement for the v1 world.
- An additional pseudo reality system for DEPT2 / H-DEPT closed-loop validation.

---

## 1. Purpose of the v2-RC1 preparation design

The purpose of this preparation design is to define what must be true before a later task creates v2-RC1 freeze documentation.

This document organizes:

- The current v2 implementation and documentation state.
- The parts of v2 that may be frozen at v2-RC1.
- The parts of v2 that must remain unfrozen.
- Required conditions and evidence before moving to v2-RC1.
- Additional validation candidates that should remain separate tasks.
- Explicit prohibitions that prevent over-claiming or accidental closed-loop boundary expansion.
- A recommended next-task sequence.

This document is intentionally conservative. It prepares the v2-RC1 decision boundary without treating the current repository as a completed v2 world model.

---

## 2. Current arrival point

PseudoReality v2 has reached a scaffolded but useful validation surface across PR #28, PR #30, PR #31, PR #35, PR #36, and PR #37.

The current state includes:

- Minimal v2 world selection through `world_engine`.
- Minimal operation of `AsymmetricGamePseudoRealitySystem`.
- v2 profile support for `pseudo_reality_v2_shrinking_equilibrium`, `pseudo_reality_v2_trust_collapse`, and `pseudo_reality_v2_public_stability_hidden_decay`.
- Diagnostic trace output for hidden state, game behavior, resources, information, and action effects.
- Probe coverage through `matrix_v2_smoke` and `matrix_v2_probe`.
- A profile behavior report that checks directional tendencies for the three current v2 profiles.
- Main integration observations indicating that existing v1 smoke remains intact and v2 matrices pass with boundary and write counts at zero.

This state is sufficient to prepare a v2-RC1 freeze boundary. It is not sufficient to claim full v2 world completion, long-run validity, robustness, performance superiority, real-world applicability, or formal H-DEPT metric adoption.

---

## 3. What v2-Impl-A established

v2-Impl-A established the minimum connection layer required for PseudoReality v2 to run as an additional world option.

The Impl-A confirmed surface includes:

1. `world_engine` selection between v1 and v2 world behavior.
2. Minimal connection of `AsymmetricGamePseudoRealitySystem`.
3. The `pseudo_reality_v2_shrinking_equilibrium` profile.
4. The `matrix_v2_smoke` matrix.
5. The `v2_hidden_trace.csv` diagnostic trace.
6. Preservation of existing v1 smoke behavior.

Impl-A should be interpreted as the initial runnable v2 scaffold. It did not complete the v2 world, did not add broad profile coverage, and did not establish performance validation.

---

## 4. What v2-Impl-B established

v2-Impl-B expanded the readable diagnostic surface and probe coverage of the v2 scaffold.

The Impl-B confirmed surface includes:

1. `v2_game_trace.csv` for entity-level tendencies, payoff signals, and long-term health proxy observations.
2. `v2_resource_trace.csv` for shared-resource, commons-health, pressure, and inequality observations.
3. `v2_information_trace.csv` for information delay, distortion, hidden visibility, misread probability, information flow, and coordination lag observations.
4. `v2_action_effect_trace.csv` for ActionFrame direct effects and side-effect observations.
5. The `pseudo_reality_v2_trust_collapse` profile.
6. The `pseudo_reality_v2_public_stability_hidden_decay` profile.
7. Strengthened `profile_config` reflection in v2 diagnostic behavior.
8. The `matrix_v2_probe` matrix.

Impl-B made v2 more observable, but the added traces remain audit and diagnostic outputs only. They are not canonical H-DEPT metrics and must not be directly connected to `G_t`, `O_t`, or `K_t`.

---

## 5. What the profile behavior report confirmed

The v2 profile behavior report confirmed that the current v2 diagnostic traces are useful for observing profile-level tendencies.

The report observed:

- `pseudo_reality_v2_shrinking_equilibrium` showed the expected short-term / long-term split, with hidden damage, latent pressure, fatigue, and pressure rising while cooperation, exploration, reversibility, information quality, and long-term health declined.
- `pseudo_reality_v2_trust_collapse` showed the expected information and coordination degradation, including falling information quality and flow with rising distortion, misread probability, coordination lag, defense tendency, hidden damage, and latent pressure.
- `pseudo_reality_v2_public_stability_hidden_decay` showed strong hidden decay while public-facing stability was only partially supported because activity was near-maintained but volatility and uncertainty rose.

The report should be read as an observational profile tendency check. It is not performance validation, not acceptance gating, and not formal adoption of any v2 trace as an H-DEPT diagnostic indicator.

---

## 6. Range that may be frozen at v2-RC1

A later v2-RC1 freeze may freeze the currently demonstrated minimum closed-loop validation surface, provided the required conditions remain satisfied.

The freeze-eligible range is:

1. `world_engine` v1 / v2 switching.
2. Minimal operation of `AsymmetricGamePseudoRealitySystem`.
3. `pseudo_reality_v2_shrinking_equilibrium` profile.
4. `pseudo_reality_v2_trust_collapse` profile.
5. `pseudo_reality_v2_public_stability_hidden_decay` profile.
6. `matrix_v2_smoke`.
7. `matrix_v2_probe`.
8. `v2_hidden_trace.csv`.
9. `v2_game_trace.csv`.
10. `v2_resource_trace.csv`.
11. `v2_information_trace.csv`.
12. `v2_action_effect_trace.csv`.
13. Evidence that existing v1 smoke is not broken.
14. Evidence that boundary, dry-run write, and forbidden-write counts remain zero.

Freezing this range would mean freezing a minimum additional pseudo reality system for closed-loop validation. It would not mean freezing every possible v2 behavior, metric, stress case, or long-horizon claim.

---

## 7. Range that must not be frozen at v2-RC1

The following areas must remain outside v2-RC1 freeze scope:

1. Any design that connects v2 added traces to `G_t`, `O_t`, or `K_t`.
2. Adoption of v2 traces as formal H-DEPT diagnostic indicators.
3. Long-term validity of each v2 profile.
4. v2 stress validation and ablation validation.
5. v2 long-run validation.
6. Formal adoption of v2 metrics.
7. Completeness of the v2 world model.
8. Applicability to real-world systems.
9. Any performance superiority claim.

These items require later explicit design, implementation, and validation tasks. They must not be implied by a v2-RC1 freeze.

---

## 8. Required conditions before moving to v2-RC1

| Condition | Status | Evidence | Notes |
| --- | --- | --- | --- |
| `compileall` PASS | completed | Main integration confirmation reported `compileall` PASS. | Re-run during v2-RC1 main integration verification. |
| Existing smoke PASS | completed | Main integration confirmation reported existing smoke `overall_pass: true`. | Confirms v1 smoke was not broken. |
| `matrix_v2_smoke` PASS | completed | Main integration confirmation reported `matrix_v2_smoke` `overall_pass: true`. | Minimal v2 matrix remains required for RC1. |
| `matrix_v2_probe` PASS | completed | Main integration confirmation reported `matrix_v2_probe` `overall_pass: true`. | Probe matrix is diagnostic, not performance validation. |
| v2 profile behavior report completed | completed | PR #37 added the v2 profile behavior report. | Observational profile tendency check only. |
| `boundary_violation_total` 0 | completed | Main integration confirmation reported `boundary_violation_total: 0`. | Must remain zero at RC1 verification. |
| `dry_run_write_violation_count` 0 | completed | Main integration confirmation reported `dry_run_write_violation_count: 0`. | Must remain zero at RC1 verification. |
| `forbidden_write_count` 0 | completed | Main integration confirmation reported `forbidden_write_count: 0`. | Must remain zero at RC1 verification. |
| v2 added CSV files emitted for every run | completed | Main integration confirmation reported additional CSV output was present for checked runs. | Includes hidden, game, resource, information, and action-effect traces. |
| No `NaN` values | completed | Main integration confirmation reported no `NaN` values. | Re-check during RC1 verification. |
| No `inf` values | completed | Main integration confirmation reported no `inf` values. | Re-check during RC1 verification. |
| Major numeric columns within `0.0` to `1.0` | completed | Main integration confirmation reported major numeric columns were within range. | Applies to the checked numeric trace columns. |
| Impl-A docs freeze completed | completed | PR #30 added v2-Impl-A freeze documentation. | Required historical documentation is present. |
| Impl-B docs freeze completed | completed | PR #36 added v2-Impl-B freeze documentation. | Required historical documentation is present. |

At preparation time, no listed condition is intentionally pending. The later v2-RC1 freeze task should still re-check the executable and matrix conditions against the then-current `main` state before freezing RC1.

---

## 9. Additional validation needed before or around v2-RC1

The following validation candidates should be kept as separate tasks. This preparation design does not implement them.

### Priority 1

- v2-RC1 Freeze docs.
- v2-RC1 main integration verification.

Priority 1 is the minimum bridge from preparation design to an actual v2-RC1 freeze. The main integration verification should re-check compile, smoke, matrix, trace-output, numeric-cleanliness, and boundary/write conditions.

### Priority 2

- v2 long-run smoke.
- `matrix_v2_probe_long`.
- Profile behavior repeatability check.

Priority 2 extends confidence beyond the current short probe surface. These checks should not be silently folded into RC1 unless explicitly requested.

### Priority 3

- v2 stress / ablation validation.
- Profile-specific ablation.
- Deeper action side-effect audit.

Priority 3 is robustness and interpretability work. It is outside the minimum v2-RC1 freeze boundary and should remain a later design and validation track.

---

## 10. Issues to leave after v2-RC1

Even after a future v2-RC1 freeze, the following issues should remain open:

- Whether and how v2 diagnostic traces can safely inform later H-DEPT diagnostic indicators.
- Whether any v2 trace should ever connect to `G_t`, `O_t`, or `K_t`, and under what explicit constraints.
- Long-run profile validity.
- Stress and ablation behavior.
- Profile-specific calibration and repeatability.
- Interpretation of public stability when volatility and uncertainty rise.
- Deeper audit of action side effects.
- Real-world mapping limits and non-claims.
- Any performance comparison between v1 and v2 worlds.

These issues must not be treated as resolved by RC1.

---

## 11. Prohibitions

For v2-RC1 preparation and freeze work, the following are prohibited:

- Do not directly mix v2 added traces into `G_t`, `O_t`, or `K_t`.
- Do not treat v2 added traces as formal H-DEPT indicators.
- Do not replace the v1 world.
- Do not loosen existing acceptance conditions.
- Do not treat the profile behavior report as performance validation.
- Do not describe v2-RC1 as real-world-ready.
- Do not describe v2-RC1 as safety-proven.
- Do not claim that v2-RC1 proves v2 world superiority.
- Do not convert probe matrices into hidden commit gates.
- Do not introduce controllers, actuators, rollback mechanisms, or parameter update paths through the v2 trace surface.

These prohibitions preserve the closed-loop validation boundary and prevent documentation from over-claiming the current scaffold.

---

## 12. Recommended next tasks

The recommended task sequence is:

### Task A: PseudoReality v2-RC1 Freeze docs

Create the actual v2-RC1 freeze documentation after confirming that the preparation conditions still hold. This current document is not Task A; it is the preparation design before Task A.

### Task B: v2-RC1 main integration verification

Re-run and record the main integration checks for compile, existing smoke, v2 smoke, v2 probe, trace output, numeric cleanliness, and boundary/write counts.

### Task C: `matrix_v2_probe_long` design

Design a longer v2 probe matrix without treating it as already implemented or required for minimum RC1 freeze.

### Task D: v2 long-run validation

Run and report long-horizon behavior after the long-run matrix design is agreed.

### Task E: v2 stress / ablation design

Design stress and ablation validation for v2 profiles, trace surfaces, and action side-effect behavior.

---

## 13. Summary

PseudoReality v2-RC1 should freeze a minimum additional asymmetric dynamic-game pseudo reality system for DEPT2 / H-DEPT closed-loop validation. It should cover minimal execution, trace output, profile differences, probe matrix coverage, and audit-boundary preservation.

It must not claim full v2 world completion, performance superiority, real-world applicability, safety proof, H-DEPT metric adoption, or replacement of the v1 world.
