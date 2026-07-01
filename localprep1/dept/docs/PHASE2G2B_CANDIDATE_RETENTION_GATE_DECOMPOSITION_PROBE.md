# Phase 2G-2b Candidate Retention and Gate Decomposition Probe

## 1. Scope

This PR is a diagnostic probe, not an intermediate-conservatism repair. It adds a small Phase 2G-2b matrix and audit-only aggregation of candidate retention and gate decision decomposition from existing validation artifacts.

It does not change production behavior, gate judgment logic, ActionModule behavior, action policy, acceptance conditions, safety boundaries, write paths, defaults, relaxed/current/flat semantics, or v2 integration. The new retention and loss values are diagnostic-only and are not used as pass/fail criteria.

## 2. Background

Phase 2G-1b identified Group B intermediate conservatism as a high-risk candidate for follow-up review. Phase 2G-2a added readability exports such as `action_result`, `boundary_guard_audit`, `cycle_audit_row`, and `module_thinning_audit`. Phase 2G-2b uses that visibility to ask where candidates, projections, gate decisions, ActionFrame rows, and action mass narrow before any repair probe is attempted.

## 3. Matrix Design

The matrix `configs/matrices/matrix_phase2g2b_candidate_retention_gate_decomposition.json` contains 12 lightweight runs of 3-4 steps each. It includes required coverage for:

- `relation_unlock_pressure_current`
- `relation_unlock_pressure_relaxed`
- `relation_unlock_pressure_flat`
- `no_exploration_relaxed`
- `high_noise_relaxed`
- `shock_recovery_relaxed`
- `default_relaxed_smoke`
- `explicit_current_smoke`

Optional stress slices include relation unlock without exploration, relation unlock under higher noise, sparse projection, and high uncertainty. Relation unlock pressure is compared across current / relaxed / flat because prior Phase 2F work showed this family is especially sensitive to intermediate conservatism.

## 4. Added Diagnostic Exports

| export | source artifact | exact or approximate | behavior change? | purpose |
| --- | --- | --- | --- | --- |
| `candidate_retention_decomposition.csv` | exploration candidates/projection, planning audit, gate audit, ActionFrame, ActionResult | row counts are exact for available artifacts; cross-stage identity retention is approximate because stable candidate IDs are not available across every stage | no | summarize run-level candidate/projection/action-frame retention |
| `gate_decomposition_by_decision.csv` | coactivation gate + same-`loop_step` ActionFrame rows | exact for observed gate decision counts and same-step ActionFrame rows | no | show allow/dampen/defer/block/monitor_only distribution and action mass by decision |
| `action_loss_by_gate_decision.csv` | coactivation gate + same-`loop_step` ActionFrame rows | row loss is exact from aggregate gate rows vs same-step ActionFrame rows; mass loss is approximate from gate mean strength | no | estimate where gate decisions reduce rows or mass |
| `stage_retention_summary.csv` | staged artifacts named in each row | row counts are exact for available artifacts; mass is only available once ActionFrame exists | no | normalize stage-by-stage retained/lost counts |

## 5. Candidate Retention Findings

The validation run produced all four diagnostic CSVs. In the Phase 2G-2b matrix, planner-to-gate and gate-to-ActionFrame row retention were 1.0 wherever source rows were available. The largest visible row gap was not at the gate but between early exploration/projection evidence and planner candidates: projection can be zero while planner candidates and ActionFrame rows remain non-zero because planning can use pressure/action-surface sources independent of exploration projection.

Observed examples from the local matrix run:

- `relation_unlock_pressure_current`: 24 exploration candidates, 1 projection row, 462 planner/gate/ActionFrame rows.
- `relation_unlock_pressure_relaxed`: 24 exploration candidates, 0 projection rows, 550 planner/gate/ActionFrame rows.
- `no_exploration_relaxed`: 0 exploration candidates and 0 projection rows, but 407 planner/gate/ActionFrame rows.

This means candidate retention cannot be interpreted as a single linear identity-preserving pipeline in the current artifacts. The planner can create many pre-gate candidates from non-projection sources, so projection-to-planner ratios are diagnostic density ratios rather than true candidate identity retention.

## 6. Gate Decomposition Findings

Across the 12-run matrix, gate decisions were:

| decision | count |
| --- | ---: |
| allow | 26 |
| dampen | 17 |
| defer | 0 |
| block | 0 |
| monitor_only | 0 |

No defer, block, or monitor-only decisions occurred in this probe. Same-step row loss from gate to ActionFrame was zero in the observed matrix. The largest estimated action-mass loss came from dampen decisions, with `max_estimated_action_mass_loss` of about 14.18 in the matrix summary. This indicates the observed gate-side thinning is primarily action-mass dampening, not row blocking, for this matrix.

## 7. Relation Unlock Pressure Mode Comparison

| mode | action_frame_rows | relation_unlock_action_mass | gate_allow | gate_dampen | gate_defer | gate_block | retention_rate | notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| current | 462 | 0.699 | observed in matrix | observed in matrix | 0 | 0 | 1.0 gate-to-ActionFrame | lowest relation-unlock family action mass among compared modes |
| relaxed | 550 | 1.342 | observed in matrix | observed in matrix | 0 | 0 | 1.0 gate-to-ActionFrame | higher action rows and relation-unlock family mass than current |
| flat | 550 | 1.397 | observed in matrix | observed in matrix | 0 | 0 | 1.0 gate-to-ActionFrame | similar rows to relaxed with slightly higher relation-unlock family mass |

The local run therefore points to mode-dependent action mass differences rather than a gate row-blocking bottleneck in relation unlock pressure.

## 8. Stress Findings

- `no_exploration`: exploration candidates/projection are zero, but ActionFrame rows remain present through non-exploration planning sources.
- `high_noise`: projection rows remain available and planner/gate/ActionFrame rows remain retained; dampening is the main observed gate effect.
- `shock_recovery`: projection rows remain available and no row-blocking gate decision appears in this matrix.
- `relation_unlock_pressure`: current has lower relation-unlock family mass than relaxed/flat; relaxed and flat have zero projection rows in the sampled run but still create planner and ActionFrame rows.
- `sparse_projection` / `high_uncertainty`: included as optional diagnostic slices; they did not create block/defer row loss in the observed matrix.

## 9. Not Available / Evidence Gaps

| missing evidence | why unavailable | needed for | recommended next task |
| --- | --- | --- | --- |
| stable candidate identity from exploration candidate to planner candidate to ActionFrame | current artifacts expose aggregate rows but not a universal candidate ID that survives every stage | exact per-candidate retention rather than row-density comparison | add audit-only candidate lineage identifiers if behavior-safe |
| exact pre-gate action mass by candidate row and gate decision | gate audit exposes aggregate mean/max strength rather than the full pre-gate candidate table by decision | exact action mass loss instead of approximate gate-mean estimate | export an audit-only pre-gate candidate snapshot keyed by `loop_step` |
| projection identity before and after bridge | the active artifact is the post-bridge `exploration_projection`; no separate pre-bridge projection artifact is emitted | exact exploration-to-bridge thinning | add bridge audit row counts only, without changing bridge logic |
| defer/block/monitor_only examples | this lightweight matrix did not trigger those decisions | decomposition of hard row loss paths | add a future diagnostic-only stress matrix designed to trigger these decisions without changing thresholds |

## 10. Repair Implication

- **Gate-side to verify:** dampen appears to reduce action mass while preserving rows; a repair probe should inspect dampen magnitude before block/defer logic.
- **Candidate sparsity-side to verify:** planner rows can remain high even when projection is zero, so sparsity repair should not assume projection is the only upstream source.
- **ParameterWindowBinder-side to verify:** mode differences in relation-unlock action mass suggest ParameterWindow-mediated gains/sparsity remain a plausible repair surface.
- **ExplorationBridge-side to verify:** bridge/projection evidence gaps prevent exact projection loss attribution; bridge should be instrumented before changing it.
- **ActionExecution-side to verify:** ActionExecution row retention is stable in this matrix; no execution behavior repair is indicated by this probe alone.
- **v2-after decision:** no v2 integration change is justified by this diagnostic.

## 11. Recommendation

Recommended next step: **Phase 2G-2c Intermediate Conservatism Repair Probe**, focused first on dampen/action-mass behavior and ParameterWindow mode effects for relation unlock pressure.

Secondary candidates:

- Phase 2G-2c Candidate Sparsity Repair Probe
- Phase 2G-2c Gate Dampen/Defer/Block Repair Probe, after a diagnostic matrix can trigger defer/block/monitor_only without threshold changes
- Phase 2G-2c ParameterWindow Sweep Audit
- v2 premise freeze only after the above evidence gaps are accepted or closed

## 12. Conclusion

Phase 2G-2b adds a small diagnostic matrix and audit-only CSV summaries for candidate retention, gate decomposition, action loss by gate decision, and stage retention. The observed bottleneck is not row loss at the gate; it is primarily mode-dependent action mass dampening plus evidence gaps around exact lineage and pre-gate mass. Production behavior and all gate/action/default/acceptance/safety/write/v2 boundaries remain unchanged.
