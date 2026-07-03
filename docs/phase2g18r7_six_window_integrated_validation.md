# Phase 2G-18R-7 Six-Window Integrated Validation

## Purpose

Phase 2G-18R-7 adds integrated validation for the six observation windows emitted in a single `observation_window_summary`. This is an integration-consistency check, not a performance evaluation and not a new control mechanism.

## Target windows

1. `v2_direct_benefit_window`
2. `v2_h11_action_effect_window`
3. `pressure_action_translation_audit_window`
4. `v2_direct_risk_band_window`
5. `v2_direct_growth_window`
6. `composite_balance_window`

## Validated perspectives

- Fixed six-window order and removal of legacy emitted window names.
- Required schema consistency, including `derived_fields` and `context_fields` for all six windows.
- Semantic independence of benefit, growth, H11 action effect, pressure-action translation audit, and direct risk-band windows.
- Core-missing cases becoming `unresolved` rather than being downgraded to watch-only states.
- Auxiliary-missing cases staying contextual when the main core remains available.
- `composite_balance_window` reading compressed window references only, without overwriting individual window judgments or masking tensions through aggregate averages.
- JSON/CSV flattening and export probe compatibility.
- Runtime boundary preservation: observation-window outputs remain validation/design-adjustment artifacts and are not runtime ActionModule inputs.

## Scenarios

The integrated test covers healthy input, benefit-only degradation, growth-only degradation, H11-effect-only degradation, translation-only degradation, risk-only escalation, benefit-good/risk-high tension, governance-good/benefit-bad tension, governance-good/growth-bad tension, translation-good/H11-bad tension, core-missing matrix, auxiliary-missing matrix, JSON/CSV export probing, and a light static runtime-boundary check.

## Result

The validation is implemented in `tests/test_phase2g18r7_six_window_integrated_validation.py`. No ActionModule runtime, v2 world dynamics, PressureTranslation runtime, ParameterBox, ParameterShadowBox, canonical write path, or observation-window-to-runtime feedback path was changed.

## Out of scope

This validation does not judge control performance, introduce new theory, redesign the six windows, or make `composite_balance_window` a primary success/failure controller.
