# Phase 2G-18 Observation Window Export / Probe Report

Japanese fixed name: `観測窓口 export / probe 確認`

## 1. Scope

This report validates Phase 2G-17 observation-window export behavior against real runner output.

Observation-window outputs remain external validation/design-adjustment artifacts. They are not runtime ActionModule inputs.

観測窓口の出力は、外部検証と後続の設計調整のためのものであり、作用モジュールの実行時入力ではない。

This Phase 2G-18 work does not change ActionModule behavior, world dynamics, safety boundaries, write paths, PressureTranslation, ParameterWindow registry, or ParameterShadowBox.

## 2. Commands executed

Preparation and existing checks:

```bash
python -m compileall localprep1/dept/scripts tests/test_phase2g17_observation_window_summary.py
pytest tests/test_phase2g17_observation_window_summary.py -q
python localprep1/dept/scripts/run_smoke_validation.py
```

Full-loop observation-window export probes:

```bash
python localprep1/dept/scripts/run_full_loop_validation.py \
  --validation-profile smoke \
  --world-profile pseudo_reality_default \
  --action-profile action_default \
  --label phase2g18_default \
  --output-dir /tmp/phase2g18_default

python localprep1/dept/scripts/run_full_loop_validation.py \
  --validation-profile smoke \
  --world-profile pseudo_reality_v2_trust_collapse \
  --action-profile action_default \
  --label phase2g18_v2_trust_collapse \
  --output-dir /tmp/phase2g18_v2_trust_collapse

python localprep1/dept/scripts/run_full_loop_validation.py \
  --validation-profile smoke \
  --world-profile pseudo_reality_v2_shrinking_equilibrium \
  --action-profile action_default \
  --label phase2g18_v2_shrinking_equilibrium \
  --output-dir /tmp/phase2g18_v2_shrinking_equilibrium

python localprep1/dept/scripts/run_full_loop_validation.py \
  --validation-profile smoke \
  --world-profile pseudo_reality_v2_public_stability_hidden_decay \
  --action-profile action_default \
  --label phase2g18_v2_public_stability_hidden_decay \
  --output-dir /tmp/phase2g18_v2_public_stability_hidden_decay
```

Export-shape probe:

```bash
python localprep1/dept/scripts/probe_observation_window_exports.py \
  /tmp/phase2g18_default \
  /tmp/phase2g18_v2_trust_collapse \
  /tmp/phase2g18_v2_shrinking_equilibrium \
  /tmp/phase2g18_v2_public_stability_hidden_decay
```

## 3. Profiles used

Existing profile files were checked under `localprep1/dept/configs` before use.

| Role | Profile |
| --- | --- |
| validation | `smoke` |
| action | `action_default` |
| stable-ish world | `pseudo_reality_default` |
| high-risk-ish world | `pseudo_reality_v2_trust_collapse` |
| high-risk-ish world | `pseudo_reality_v2_shrinking_equilibrium` |
| high-risk-ish world | `pseudo_reality_v2_public_stability_hidden_decay` |

## 4. Export generation result

Each run generated both expected observation-window files:

| Output directory | JSON generated | CSV generated | JSON windows | CSV data rows |
| --- | --- | --- | ---: | ---: |
| `/tmp/phase2g18_default` | yes | yes | 6 | 6 |
| `/tmp/phase2g18_v2_trust_collapse` | yes | yes | 6 | 6 |
| `/tmp/phase2g18_v2_shrinking_equilibrium` | yes | yes | 6 | 6 |
| `/tmp/phase2g18_v2_public_stability_hidden_decay` | yes | yes | 6 | 6 |

The probe confirmed the required six-window order in both JSON and CSV:

1. `system_benefit_window`
2. `h11_possibility_distribution_window`
3. `pressure_action_alignment_window`
4. `risk_band_window`
5. `growth_window`
6. `composite_balance_window`

The probe also confirmed that every JSON window has:

- `window_name`
- `status_label`
- `evidence_fields`
- `warning_flags`
- `unresolved_flags`
- `short_reason`

The allowed status labels remain:

- `healthy`
- `watch`
- `warning`
- `critical`
- `unresolved`

The JSON top-level `boundary_note` and CSV row-level `boundary_note` were present and preserved the statement that observation-window outputs are not runtime ActionModule inputs.

## 5. Profile-by-profile status summary

| World profile | system benefit | H11 possibility | pressure/action | risk band | growth | composite |
| --- | --- | --- | --- | --- | --- | --- |
| `pseudo_reality_default` | watch | watch | watch | watch | watch | watch |
| `pseudo_reality_v2_trust_collapse` | watch | watch | watch | watch | watch | watch |
| `pseudo_reality_v2_shrinking_equilibrium` | watch | watch | watch | watch | watch | watch |
| `pseudo_reality_v2_public_stability_hidden_decay` | watch | watch | watch | watch | watch | watch |

### Stable-ish reading

`pseudo_reality_default` did not collapse into all-`critical` or all-`warning`. It produced `watch` statuses across all windows, with available evidence still emitted and unresolved fields preserved. This is acceptable for a minimal export probe, but the default profile also raised low cooperation/information warnings because the available smoke metrics currently report zero means for those fallback fields.

### High-risk-ish reading

The high-risk-ish profiles did not return all-`healthy`, so the export is not falsely declaring clean success. However, the profiles also did not produce differentiated warning flags in this probe. That suggests the current minimal export is readable but still too coarse to separate risk profiles when the runner artifacts do not expose hidden-damage/fatigue/latent-pressure traces in the fields consumed by the window builder.

## 6. Warning flag summary

| World profile | Warning flags |
| --- | --- |
| `pseudo_reality_default` | `system_benefit_window`: `cooperation_intent_low`, `information_quality_low`; `risk_band_window`: `cooperation_intent_low` |
| `pseudo_reality_v2_trust_collapse` | none |
| `pseudo_reality_v2_shrinking_equilibrium` | none |
| `pseudo_reality_v2_public_stability_hidden_decay` | none |

Interpretation:

- The stable-ish smoke run is not over-escalated to `warning` or `critical`.
- The high-risk-ish profiles are not sufficiently distinguished by warning flags in this export layer.
- This looks like a trace/readability limitation rather than an ActionModule or world-dynamics issue.

## 7. Unresolved flag summary

The unresolved flags were consistent across the four probed runs.

| Window | Unresolved flags |
| --- | --- |
| `system_benefit_window` | `missing_total_resource`, `missing_recovery_after_shock` |
| `h11_possibility_distribution_window` | `missing_novelty_quality` |
| `pressure_action_alignment_window` | `missing_action_cost`, `missing_upper_pressure_direction`, `missing_h11_pressure_direction`, `missing_action_mass_by_channel`, `missing_over_action_risk`, `missing_under_action_risk` |
| `risk_band_window` | `missing_information_asymmetry`, `missing_action_cost`, `missing_recovery_capacity`, `missing_possibility_distribution_narrowing`, `missing_shrinking_equilibrium_risk`, `missing_relation_rigidity` |
| `growth_window` | `missing_realized_growth_proxy`, `missing_sustainable_growth_proxy`, `missing_growth_capacity_proxy`, `missing_h11_possibility_route_preservation` |
| `composite_balance_window` | `missing_benefit_vs_possibility`, `missing_visible_benefit_vs_hidden_damage`, `missing_growth_vs_fatigue`, `missing_stability_vs_shrinking_equilibrium`, `missing_predictability_vs_predictable_collapse`, `missing_pressure_alignment_vs_metric_optimization`, `missing_short_term_benefit_vs_long_term_route_preservation` |

Windows with many unresolved fields:

1. `composite_balance_window` has the largest unresolved set because most cross-window contradiction fields are not first-class trace exports yet.
2. `pressure_action_alignment_window` and `risk_band_window` each lack important directional/action-cost/recovery fields.
3. `growth_window` lacks first-class realized/sustainable/capacity growth exports.

Fields that should be considered before Phase 2G-19 design:

- `action_cost`
- `upper_pressure_direction`
- `h11_pressure_direction`
- `action_mass_by_channel`
- `over_action_risk`
- `under_action_risk`
- hidden-cost fields in a runner artifact directly consumed by the window builder
- `recovery_capacity`
- `possibility_distribution_narrowing`
- `shrinking_equilibrium_risk`

Fields that can remain Phase 2G-20+ candidates:

- `novelty_quality`
- `recovery_after_shock`
- full composite contradiction fields such as `visible_benefit_vs_hidden_damage` and `short_term_benefit_vs_long_term_route_preservation`
- richer growth decomposition fields such as `realized_growth_proxy` and `sustainable_growth_proxy`

## 8. Proxy adequacy review

This task did not perform large threshold tuning.

- `mean_delta_reversibility` as `growth_capacity_proxy_from_reversibility_delta`: acceptable as a temporary readability proxy, but too narrow to represent growth capacity by itself. It should remain a proxy and be paired with hidden-cost and route-preservation evidence.
- `mean_delta_relation_lock` as coherence/robustness proxy: the sign convention used by Phase 2G-17 appears consistent with relation-lock risk when the delta is positive. No sign reversal bug was found during this probe.
- `mean_delta_uncertainty` as predictability/efficiency proxy: acceptable only as derived/proxy evidence. It can be misread if lower uncertainty means predictable collapse rather than healthy predictability, so composite contradiction fields should eventually be added.
- `action_mass` versus `pressure_norm`: the current condition did not over-trigger in smoke/default. The ratio remains coarse because pressure direction and action channel distribution are unresolved.
- `hidden_damage` / `fatigue` / `latent_pressure` thresholds at `0.55` and `0.75`: acceptable as provisional validation thresholds. The larger issue is not the constants but field availability/readability for high-risk-ish profiles.

## 9. Bug fixes

No Phase 2G-17 observation-window logic bug was repaired in this task.

A validation-only probe script was added to make export shape/readability checks repeatable. The script inspects existing output directories only; it does not run the ActionModule and does not feed observation-window outputs into runtime execution.

## 10. Boundary reconfirmation

This task preserved the fixed two-path boundary:

```text
system information -> ActionModule -> action
validation traces -> observation windows -> external analysis / design adjustment
```

The second path was not connected back to the ActionModule at runtime.

No changes were made to:

- ActionModule behavior
- world dynamics
- safety boundaries
- write paths
- PressureTranslation
- ParameterWindow registry
- ParameterShadowBox

## 11. Phase 2G-19 progression decision

Phase 2G-18の観測窓口exportは、外部診断情報として利用可能であるため、Phase 2G-19の作用モジュール検証設計へ進める。

Phase 2G-19 can proceed to ActionModule validation design, using the Phase 2G-18 observation-window export as external diagnostic evidence.

However, Phase 2G-19 should treat the current export as coarse diagnostic evidence, not as a complete profile discriminator. In particular, Phase 2G-19 design should inspect:

1. pressure/action alignment fields;
2. risk-band hidden-cost evidence;
3. growth hidden-cost tension;
4. composite contradictions between visible benefit, possibility distribution, fatigue, hidden damage, and pressure alignment;
5. whether additional runner trace exports are needed before any later ActionModule tuning probe.
