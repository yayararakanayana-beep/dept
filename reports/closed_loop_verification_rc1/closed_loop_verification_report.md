# Closed Loop Verification Package RC1

## 1. Execution Conditions

- Runner function used: `run_closed_loop_runner_integration_rc1(...)` imported from `tests.test_closed_loop_runner_integration_rc1`.
- Seeds used: `(0, 1, 2, 3, 4)`.
- Baselines: `NO_ACTION, V2_GREEDY_OPTIMIZER, ACTION_MODULE_RC1`.
- Scenario count: `7`.
- Step count per scenario: `12`.
- No production mutation was performed by this reporting script.
- No coefficient update was performed.
- No canonical writeback was performed.

## 2. Baselines

- **NO_ACTION**: no intervention baseline.
- **V2_GREEDY_OPTIMIZER**: visible-surface short-term optimizer.
- **ACTION_MODULE_RC1**: `action_module_step`-based conservative/action-audit baseline.

## 3. Scenarios

- **stable_closed_v2**: tests steady closed-loop opportunity where visible greedy gain should be strong.
- **shock_recovery**: tests post-shock recovery and risk control.
- **delayed_side_effect**: tests fatigue and relation-lock buildup after repeated action.
- **safety_boundary_shift**: tests behavior when safe action mass contracts.
- **reaction_surface_drift**: tests brittleness when the visible response surface shifts.
- **hidden_fragility**: tests conservative behavior under incomplete fragility exposure.
- **high_opportunity_high_risk**: tests balancing large opportunity against elevated risk.

## 4. Top-Level Comparison

| Winner category | Baseline |
| --- | --- |
| short_term_gain_winner | V2_GREEDY_OPTIMIZER |
| safety_winner | ACTION_MODULE_RC1 |
| over_action_winner | ACTION_MODULE_RC1 |
| recovery_winner | ACTION_MODULE_RC1 |
| relation_lock_winner | NO_ACTION |
| exploration_retention_winner | NO_ACTION |
| robustness_winner | ACTION_MODULE_RC1 |

Baseline comparison table:

| baseline_name | mean_cumulative_gain | mean_final_stability | mean_final_risk | mean_safety_violation_rate | mean_over_action_rate | mean_missed_opportunity_rate | mean_recovery_score | mean_time_to_recover | mean_final_relation_lock | mean_exploration_capacity_retention | mean_audit_pass_rate | closed_loop_robustness_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACTION_MODULE_RC1 | 0.0 | 0.575935 | 0.533844 | 0.0 | 0.0 | 0.478571 | 0.575343 | 28.285714 | 0.064214 | 0.969602 | 1.0 | 0.837179 |
| NO_ACTION | 0.0 | 0.570732 | 0.575 | 0.0 | 0.0 | 0.52381 | 0.564724 | 28.285714 | 0.06 | 0.974884 | 1.0 | 0.829844 |
| V2_GREEDY_OPTIMIZER | 5.962297 | 0.97001 | 0.743902 | 0.0 | 0.333333 | 0.0 | 0.435401 | 14.142857 | 0.299136 | 0.759116 | 1.0 | 0.676638 |

## 5. Scenario Breakdown

- **delayed_side_effect**: highest cumulative gain = V2_GREEDY_OPTIMIZER; safest = ACTION_MODULE_RC1. ACTION_MODULE_RC1 recovery=0.577, risk=0.490, over-action=0.000. GREEDY gain=7.420, risk=1.000, over-action=0.417. NO_ACTION missed-opportunity=0.667, recovery=0.577.
- **hidden_fragility**: highest cumulative gain = V2_GREEDY_OPTIMIZER; safest = ACTION_MODULE_RC1. ACTION_MODULE_RC1 recovery=0.577, risk=0.490, over-action=0.000. GREEDY gain=7.625, risk=1.000, over-action=0.917. NO_ACTION missed-opportunity=0.667, recovery=0.577.
- **high_opportunity_high_risk**: highest cumulative gain = V2_GREEDY_OPTIMIZER; safest = ACTION_MODULE_RC1. ACTION_MODULE_RC1 recovery=0.597, risk=0.720, over-action=0.000. GREEDY gain=4.888, risk=0.512, over-action=0.000. NO_ACTION missed-opportunity=0.167, recovery=0.526.
- **reaction_surface_drift**: highest cumulative gain = V2_GREEDY_OPTIMIZER; safest = ACTION_MODULE_RC1. ACTION_MODULE_RC1 recovery=0.577, risk=0.490, over-action=0.000. GREEDY gain=5.631, risk=0.842, over-action=0.333. NO_ACTION missed-opportunity=0.667, recovery=0.577.
- **safety_boundary_shift**: highest cumulative gain = V2_GREEDY_OPTIMIZER; safest = ACTION_MODULE_RC1. ACTION_MODULE_RC1 recovery=0.577, risk=0.490, over-action=0.000. GREEDY gain=3.369, risk=0.248, over-action=0.000. NO_ACTION missed-opportunity=0.500, recovery=0.577.
- **shock_recovery**: highest cumulative gain = V2_GREEDY_OPTIMIZER; safest = ACTION_MODULE_RC1. ACTION_MODULE_RC1 recovery=0.543, risk=0.735, over-action=0.000. GREEDY gain=5.731, risk=0.757, over-action=0.333. NO_ACTION missed-opportunity=0.000, recovery=0.543.
- **stable_closed_v2**: highest cumulative gain = V2_GREEDY_OPTIMIZER; safest = ACTION_MODULE_RC1. ACTION_MODULE_RC1 recovery=0.580, risk=0.322, over-action=0.000. GREEDY gain=7.072, risk=0.847, over-action=0.333. NO_ACTION missed-opportunity=1.000, recovery=0.577.

Scenario breakdown table:

| scenario_type | baseline_name | mean_cumulative_gain | mean_safety_violation_rate | mean_over_action_rate | mean_recovery_score | mean_time_to_recover | mean_final_relation_lock | mean_exploration_capacity_retention | scenario_result_class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| delayed_side_effect | ACTION_MODULE_RC1 | 0.0 | 0.0 | 0.0 | 0.576795 | 0.0 | 0.06 | 0.974884 | safety_winner |
| delayed_side_effect | NO_ACTION | 0.0 | 0.0 | 0.0 | 0.576795 | 0.0 | 0.06 | 0.974884 | stable_but_inactive |
| delayed_side_effect | V2_GREEDY_OPTIMIZER | 7.419979 | 0.0 | 0.416667 | 0.378726 | 0.0 | 0.324 | 0.712698 | over_action_loser |
| hidden_fragility | ACTION_MODULE_RC1 | 0.0 | 0.0 | 0.0 | 0.576795 | 0.0 | 0.06 | 0.974884 | safety_winner |
| hidden_fragility | NO_ACTION | 0.0 | 0.0 | 0.0 | 0.576795 | 0.0 | 0.06 | 0.974884 | stable_but_inactive |
| hidden_fragility | V2_GREEDY_OPTIMIZER | 7.624937 | 0.0 | 0.916667 | 0.280512 | 0.0 | 0.324 | 0.64293 | over_action_loser |
| high_opportunity_high_risk | ACTION_MODULE_RC1 | 0.0 | 0.0 | 0.0 | 0.597128 | 99.0 | 0.06 | 0.974884 | safety_winner |
| high_opportunity_high_risk | NO_ACTION | 0.0 | 0.0 | 0.0 | 0.525795 | 99.0 | 0.06 | 0.974884 | stable_but_inactive |
| high_opportunity_high_risk | V2_GREEDY_OPTIMIZER | 4.888033 | 0.0 | 0.0 | 0.544795 | 99.0 | 0.236975 | 0.787951 | short_term_gain_winner |
| reaction_surface_drift | ACTION_MODULE_RC1 | 0.0 | 0.0 | 0.0 | 0.576795 | 0.0 | 0.06 | 0.974884 | safety_winner |
| reaction_surface_drift | NO_ACTION | 0.0 | 0.0 | 0.0 | 0.576795 | 0.0 | 0.06 | 0.974884 | stable_but_inactive |
| reaction_surface_drift | V2_GREEDY_OPTIMIZER | 5.631461 | 0.0 | 0.333333 | 0.431714 | 0.0 | 0.324 | 0.782465 | over_action_loser |
| safety_boundary_shift | ACTION_MODULE_RC1 | 0.0 | 0.0 | 0.0 | 0.576795 | 0.0 | 0.06 | 0.974884 | safety_winner |
| safety_boundary_shift | NO_ACTION | 0.0 | 0.0 | 0.0 | 0.576795 | 0.0 | 0.06 | 0.974884 | stable_but_inactive |
| safety_boundary_shift | V2_GREEDY_OPTIMIZER | 3.368559 | 0.0 | 0.0 | 0.553528 | 0.0 | 0.236975 | 0.857718 | short_term_gain_winner |
| shock_recovery | ACTION_MODULE_RC1 | 0.0 | 0.0 | 0.0 | 0.543295 | 99.0 | 0.06 | 0.974884 | safety_winner |
| shock_recovery | NO_ACTION | 0.0 | 0.0 | 0.0 | 0.543295 | 99.0 | 0.06 | 0.974884 | stable_but_inactive |
| shock_recovery | V2_GREEDY_OPTIMIZER | 5.73088 | 0.0 | 0.333333 | 0.439852 | 0.0 | 0.324 | 0.712698 | over_action_loser |
| stable_closed_v2 | ACTION_MODULE_RC1 | 0.0 | 0.0 | 0.0 | 0.5798 | 0.0 | 0.089497 | 0.93791 | safety_winner |
| stable_closed_v2 | NO_ACTION | 0.0 | 0.0 | 0.0 | 0.576795 | 0.0 | 0.06 | 0.974884 | stable_but_inactive |
| stable_closed_v2 | V2_GREEDY_OPTIMIZER | 7.072231 | 0.0 | 0.333333 | 0.418678 | 0.0 | 0.324 | 0.817349 | over_action_loser |

## 6. Drift Diagnosis

Major drift counts:

| drift_type | severity | count |
| --- | --- | --- |
| exploration_loss_drift | high | 3 |
| exploration_loss_drift | low | 1 |
| exploration_loss_drift | medium | 4 |
| missed_opportunity_drift | high | 10 |
| missed_opportunity_drift | medium | 2 |
| over_action_drift | high | 5 |
| recovery_drift | high | 3 |
| recovery_drift | low | 2 |
| recovery_drift | medium | 4 |
| relation_lock_drift | high | 5 |
| relation_lock_drift | medium | 2 |
| short_term_gain_drift | high | 14 |

Important diagnosis rows are recorded in `drift_diagnosis.csv`; high and medium rows identify the main mismatch patterns by scenario, baseline, reference baseline, and metric.

## 7. Adjustment Candidates

Candidate priority counts:

| priority | count |
| --- | --- |
| high | 2 |
| low | 1 |

| candidate_id | target_component | trigger_condition | observed_issue | suggested_adjustment | expected_effect | risk_of_adjustment | priority | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACR-RC1-001 | fire_permission_threshold | ACTION_MODULE_RC1 missed_opportunity_drift severity high in delayed_side_effect, hidden_fragility, high_opportunity_high_risk, reaction_surface_drift, safety_boundary_shift, stable_closed_v2 | missed_opportunity_drift observed for ACTION_MODULE_RC1 in 6 scenario row(s). | review whether safe opportunities are being filtered too aggressively | reduce missed safe opportunities | may increase over-action or safety exposure | high | candidate_only |
| ACR-RC1-002 | recovery_priority_weight | ACTION_MODULE_RC1 recovery_drift severity high in shock_recovery | recovery_drift observed for ACTION_MODULE_RC1 in 1 scenario row(s). | review recovery weighting, cooldown trigger, or rollback trigger under stress | improve post-shock recovery | may make the module too conservative | high | candidate_only |
| ACR-RC1-003 | over_action_penalty | GREEDY brittleness evidence in delayed_side_effect, hidden_fragility, high_opportunity_high_risk, reaction_surface_drift, safety_boundary_shift | Pure visible-surface optimization shows stress drift; this is evidence only, not a request to change GREEDY. | retain as comparative evidence for why ACTION_MODULE_RC1 needs audit-aware constraints | keeps GREEDY as a brittle-reference baseline | none because no runtime adjustment is applied | low | candidate_only |

No adjustments are applied by this package; every row remains `candidate_only`.

## 8. What We Learned

- V2_GREEDY_OPTIMIZER wins aggregate short-term/cumulative gain.
- ACTION_MODULE_RC1 wins aggregate closed-loop robustness.
- ACTION_MODULE_RC1 shows gain=0.000, risk=0.534, over-action=0.000, recovery=0.575.
- V2_GREEDY_OPTIMIZER shows gain=5.962, risk=0.744, over-action=0.333, recovery=0.435.
- NO_ACTION shows gain=0.000 and missed-opportunity=0.524.

## 9. What We Cannot Claim Yet

- This is not full v3 validation.
- This is not real-world validation.
- This does not prove universal superiority.
- This does not justify runtime coefficient updates yet.
- This does not update ParameterBox or ShadowBox.

## 10. Next Recommended Step

targeted adjustment proposal
