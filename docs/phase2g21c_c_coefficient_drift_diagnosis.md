# Phase 2G-21C-C Functional Policy Coefficient Drift Diagnosis

## Purpose

Phase 2G-21C-C adds a **test-local coefficient drift diagnosis layer**. It consumes the Phase 2G-21C-B functional policy × v2 response curve alignment outputs and converts observed misalignment reasons into bounded coefficient-family hypotheses for later Phase 2G-21C-D validation.

This phase is diagnostic only. It does not tune, replace, or apply coefficients.

## Inputs

The diagnosis imports and calls:

- `align_functional_policy_with_v2_response_curve()` from `tests/test_phase2g21c_b_functional_policy_v2_alignment.py`.

It reads the 21C-B long alignment rows and summary rows, including:

- alignment judgement
- misalignment reason
- functional policy evidence trace
- v2 response evidence trace
- missing input flags
- cap, channel, permission, and cooldown alignment scores

Scenario labels remain audit-only and are preserved for traceability, but they do not control diagnosis logic.

## Outputs

`diagnose_coefficient_drift_from_alignment()` returns `CoefficientDriftDiagnosisResult` with three dataframes:

1. `functional_policy_coefficient_drift_diagnosis_long`
   - one row per 21C-B alignment row/channel
   - suspected coefficient family, drift direction, suggested adjustment direction, confidence, priority, evidence, and counter-evidence
2. `functional_policy_coefficient_drift_diagnosis_summary`
   - one row per 21C-B case/run
   - aggregate families, dominant drift direction, aggregate confidence, and handoff priority
3. `functional_policy_coefficient_family_summary`
   - one row per suspected coefficient family
   - row counts, reason coverage, directions, confidence, priority, and validation markers

Every output row is marked:

- `coefficient_changed = False`
- `production_runtime_changed = False`
- `canonical_writeback_performed = False`
- `requires_21c_d_validation = True`

## Coefficient Family Map

21C-B misalignment reasons are mapped as follows:

| 21C-B misalignment reason | Suspected coefficient family |
| --- | --- |
| `policy_cap_too_high` | `action_mass_cap_family` |
| `policy_cap_too_low` | `action_mass_cap_family` |
| `policy_channel_weight_mismatch` | `channel_weight_family` |
| `policy_permission_too_high` | `fire_permission_family` |
| `policy_permission_too_low` | `fire_permission_family` |
| `cooldown_too_strong` | `cooldown_suppression_family` |
| `cooldown_too_weak` | `cooldown_suppression_family` |
| `safe_range_absent` | `safety_boundary_family` |
| `harmful_threshold_low` | `safety_boundary_family` |
| `v2_curve_mostly_harmful` | `safety_boundary_family` |
| `v2_curve_mostly_no_effect` | `opportunity_detection_family` |

Unknown reasons are classified as `unresolved_family`.

## Drift Direction Logic

The layer emits directions only; it does not apply changes.

- Over-aggressive reasons such as high cap, high permission, weak cooldown, low harmful threshold, absent safe range, or mostly harmful v2 curve produce `too_aggressive` with `decrease_or_tighten`.
- Over-conservative reasons such as low cap, low permission, strong cooldown, or mostly no-effect v2 curve produce `too_conservative` with `increase_or_relax`.
- Channel mismatches produce `misrouted` with `rebalance_channel_weights`.
- Missing or unmapped evidence produces `unresolved` with `requires_more_evidence`.

## Confidence Logic

Diagnosis confidence is intentionally conservative:

- `low` when 21C-B reported missing input flags or no explicit misalignment reason exists.
- `high` when strong alignment judgements are paired with multiple explicit reasons.
- `medium` for explicit but less complete evidence.

## Safety Priority Logic

Safety priority is derived from observed alignment evidence, not scenario labels:

- `safety_critical` for harmful threshold, over-firing, over-permission, weak cooldown, absent safe ranges, or mostly harmful v2 curves.
- `opportunity_recovery` for missed opportunities, under-firing, under-permission, strong cooldown, low caps, or no-effect curves.
- `routing_accuracy` for channel-weight mismatch or wrong-channel judgements.
- `mixed` is reserved for future rows that carry simultaneous safety and opportunity evidence.
- `unresolved` is used when the evidence is insufficient.

## Strict Boundaries

Phase 2G-21C-C must not:

- modify 21B-B coefficients
- modify functional insurance policy formulas
- modify v2 dynamics
- modify ActionPlanner, ActionModule, ParameterBox, ShadowBox, or production runtime files
- perform canonical writeback
- apply coefficient changes
- allow scenario labels to control diagnosis

The layer is implemented only in tests and documentation.

## Success Conditions

The phase succeeds when:

- expected columns exist in long, summary, and family-summary outputs
- 21C-B alignment outputs are read directly
- scenario-label overrides do not change diagnostic conclusions
- every known 21C-B reason maps to the expected coefficient family
- missing inputs reduce confidence
- harmful/over-firing evidence receives safety-critical priority
- opportunity-loss evidence receives opportunity-recovery priority
- channel mismatch receives routing-accuracy priority
- all rows require 21C-D validation
- no coefficient, runtime, or canonical writeback flags are set

## Failure Conditions

The phase fails if it:

- applies or writes coefficient changes
- changes production runtime behavior
- changes 21B-B formulas or v2 dynamics
- uses scenario labels as diagnostic controls
- suppresses missing-input uncertainty
- omits evidence or counter-evidence summaries
- treats this diagnosis as a commit gate or canonical parameter update path

## Phase 2G-21C-D Handoff

21C-C output rows are handoff candidates for Phase 2G-21C-D validation. The handoff consists of suspected coefficient family, drift direction, suggested adjustment direction, confidence, safety priority, preserved evidence, and counter-evidence. 21C-D must independently validate candidates before any later task considers coefficient changes.
