# Phase 2G-21C-D Shadow Coefficient Validation

## Purpose

Phase 2G-21C-D is a test-local shadow coefficient validation layer. It consumes Phase 2G-21C-C coefficient drift diagnosis outputs and Phase 2G-21C-B functional policy / v2 response alignment outputs, creates bounded shadow adjustment candidates, evaluates whether those copied-output candidates improve alignment against measured v2 evidence, and classifies each candidate for Phase 2G-21C-E review.

## Position After 21C-C

21C-C diagnoses suspected coefficient-family drift from 21C-B misalignment reasons. 21C-D does not convert those diagnoses into real updates. It only tests the candidate direction in shadow form and emits evidence for the next phase.

## Inputs

- `diagnose_coefficient_drift_from_alignment(...)` from Phase 2G-21C-C.
- `align_functional_policy_with_v2_response_curve(...)` from Phase 2G-21C-B.
- Measured v2 response evidence embedded in the 21C-B alignment rows.

Scenario labels are retained only as audit fields. They must not control candidate generation, scoring, or decisions.

## Outputs

21C-D emits three tables:

1. `functional_policy_shadow_validation_long`: candidate × case × channel evidence with baseline and shadow values side by side.
2. `functional_policy_shadow_validation_summary`: candidate-level counts, score deltas, regression counts, and final decision.
3. `functional_policy_shadow_candidate_decisions`: the 21C-E handoff table with expected benefit, known risk, and recommended action.

Every output row carries the no-write markers:

- `coefficient_changed = False`
- `production_runtime_changed = False`
- `canonical_writeback_performed = False`

## Shadow Candidate Generation

Candidates are generated from 21C-C diagnosis rows:

- `decrease_or_tighten`: small tightening candidates at strengths `0.05`, `0.10`, and `0.15`.
- `increase_or_relax`: small relaxation candidates at strengths `0.05` and `0.10`.
- `rebalance_channel_weights`: small channel rebalancing candidates at strengths `0.05`, `0.10`, and `0.15`.
- unresolved or missing-input rows: hold-only candidates; no strong update candidate is created.

Cap-related diagnoses adjust copied `action_mass_cap`; permission-related diagnoses adjust copied `fire_permission_score`; cooldown-related diagnoses adjust copied `cooldown_score`; channel-weight diagnoses reduce the policy-preferred copied channel weight and increase the observed-best copied channel weight only when that observed-best channel is not harmful.

## Shadow Adjustment Rules

All changes are applied only to copied policy output values inside the test-local validation table. Scalar values are clamped to valid ranges. Baseline values and shadow values are preserved side by side. The real 21B-B policy function, its coefficients, v2 dynamics, ActionPlanner, ActionModule, ParameterBox, ShadowBox, runtime files, and canonical state are never modified.

## Validation Metrics

The validation compares baseline and shadow alignment using:

- `alignment_score_delta`
- primary misalignment resolution
- harmful threshold / cap-above-harmful regression detection
- over-firing and over-permission regression detection
- missed-opportunity and under-firing regression detection
- non-target regression detection

## Candidate Decision Logic

Allowed decisions are:

- `accepted_shadow_candidate`: primary and overall alignment improve without detected safety regression or meaningful non-target damage.
- `rejected_safety_regression`: harmful threshold, over-firing, over-permission, or safety-critical risk increases.
- `rejected_no_improvement`: primary and overall alignment do not improve.
- `rejected_over_correction`: tightening or relaxation over-corrects into under-firing, missed opportunity, broken routing, or unsafe behavior.
- `hold_mixed_evidence`: target evidence improves while another component worsens or evidence remains entangled.
- `hold_missing_inputs`: 21C-C confidence is low or key safe-range / harmful-threshold / v2 evidence is missing.

## Strict No-Write Boundaries

21C-D must not:

- modify 21B-B coefficients;
- modify `functional_insurance_policy` formulas;
- modify v2 dynamics;
- modify ActionPlanner, ActionModule, ParameterBox, or ShadowBox;
- modify production runtime files;
- perform canonical writeback;
- apply coefficient changes;
- treat shadow candidates as real coefficient updates.

## Success Conditions

21C-D succeeds when it creates shadow candidates from 21C-C diagnosis, validates them against 21C-B / 21C-A evidence, compares baseline and shadow outcomes, classifies candidates into accepted / rejected / hold groups, emits a clear 21C-E handoff table, and leaves coefficients, runtime files, v2 dynamics, and canonical state unchanged.

## Failure Conditions

21C-D fails if any real coefficient or production runtime file is changed, `functional_insurance_policy` or v2 dynamics are modified, shadow changes are treated as real updates, harmful threshold or over-firing regressions are accepted, scenario labels control validation decisions, missing input is ignored, or no 21C-E handoff table is produced.

## 21C-E Handoff

Accepted candidates require 21C-E review and recommend `propose_limited_coefficient_update`. Rejected candidates do not become update proposals and recommend `reject_candidate`. Hold candidates remain shadow-only evidence requests and recommend `request_more_evidence` or `keep_shadow_only`.
