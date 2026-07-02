# Phase 2G-17 v2 Observation Window Minimal Implementation

This implementation exports six validation-only observation windows from existing runner traces:

1. `system_benefit_window`
2. `h11_possibility_distribution_window`
3. `pressure_action_alignment_window`
4. `risk_band_window`
5. `growth_window`
6. `composite_balance_window`

Each window emits `window_name`, `status_label`, `evidence_fields`, `warning_flags`, `unresolved_flags`, and `short_reason` in `observation_window_summary.json`, with a flat CSV companion at `observation_window_summary.csv`.

The output is derived from existing validation artifacts such as `v2_hidden_trace`, `v2_resource_trace`, `v2_information_trace`, `world_transition_audit`, `parameter_shadow_audit`, `coactivation_gate`, and `action_frame`. Missing fields are reported as `missing_*` unresolved flags rather than being inferred.

## Boundary

Observation-window outputs are for validation and design adjustment only. They are not runtime ActionModule inputs.

観測窓口の出力は、外部検証と後続の設計調整のためのものであり、作用モジュールの実行時入力ではない。

This change does not alter ActionModule behavior, world dynamics, safety boundaries, write paths, PressureTranslation, ParameterWindow registry, or ParameterShadowBox.

## Phase 2G-18 follow-up points

- Decide which unresolved fields should become first-class trace exports.
- Review whether threshold constants should remain documentation-only or become configurable validation-only settings.
- Compare stable-ish and high-risk-ish profiles with these windows before any ActionModule tuning proposal.
- Keep verifying that observation summaries are never passed into runtime action generation.
