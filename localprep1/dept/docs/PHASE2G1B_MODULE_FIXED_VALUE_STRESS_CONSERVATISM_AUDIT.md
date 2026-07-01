# Phase 2G-1b Module Fixed-Value / Stress / Conservatism Audit

## 1. Scope

This PR is an audit/report PR. It does **not** implement repairs.

Non-goals and constraints:

- Production code behavior is unchanged.
- Runner behavior, gate logic, ActionModule behavior, action policy, acceptance criteria, safety boundaries, write paths, defaults, and v2 integration are unchanged.
- Validation conditions are not relaxed.
- No v2 runtime integration or full evaluation metric expansion is added.
- Holes found here are recorded as repair-planning inputs only.

## 2. Background

Phase 2F-1e made `relaxed` the default `intermediate_conservatism_mode` while keeping `current` as an explicit baseline and `flat` as a validation-only upper comparison. Phase 2G-1a then confirmed that the current environment is usable for the next validation stage and identified export/readability gaps as medium follow-up candidates.

This audit therefore asks whether module-level fixed values, stress behavior, and residual intermediate conservatism contain holes that should be repaired or probed before heavier v2 validation.

## 3. Module Groups

| group | scope | modules reviewed |
| --- | --- | --- |
| A | Pressure translation / parameter system | `PressureTranslationModule`, `ParameterBox`/registry, `ParameterShadowBox`, `ParameterWindowBinder`, commit/rollback-adjacent runner artifacts |
| B | Intermediate conservatism / gate / candidate generation | `CoactivationGateModule`, `ActionSurfacePlanningModule`, `ExplorationBridgeModule`, `ExplorationModule`, `LocalAuditModule`, action candidates / affordance |
| C | ActionFrame / ActionModule boundary | ActionFrame builder, `ActionExecutionModule`, ActionModule boundary, actuation primitives, action source audit |
| D | World / audit / validation export | `WorldAdapter`, `BoundaryGuard`, `AuditLedger`, `run_matrix_validation.py`, `profile_loader.py`, matrix summary, per-run CSV exports, v2 trace connection points |

## 4. Fixed-Value Extraction Summary

Approximate reviewed fixed-value/parameter count: **86**. Counts are grouped by audit-relevant values rather than every boolean/string contract marker.

| classification | count | notes |
| --- | ---: | --- |
| safety_boundary | 17 | no-write flags, ActionFrame-only boundary flags, canonical/dry-run defaults, gate hard block limits |
| numerical_stability | 13 | clipping ranges, `1e-12` denominators, empty/default numeric fallbacks, trace schema defaults |
| diagnostic_default | 17 | default steps/seeds/profiles, smoke settings, row/export defaults |
| tunable_parameter | 22 | registry mid/low/high values, threshold windows, candidate budgets, channel gains |
| arbitrariness_candidate | 12 | weighted blends and thresholds with weak in-repo calibration evidence |
| unnecessary_conservatism_candidate | 8 | dampen/defer/block, sparsity, guarded unlock delay/strength, projection adoption limits |
| v2_dependent | 5 | v2 world defaults, hidden trace assumptions, asymmetric-game dynamics defaults |
| observation_only | 9 | source-audit flags, matrix summary metrics, no-exploration projection zero behavior |

| group | module | fixed value / parameter | location | classification | rationale | risk |
| --- | --- | --- | --- | --- | --- | --- |
| A | `FullSpecRunnerConfig` | `steps=2`, `seed=42`, `n_entities=18` | `contracts/cycle_state.py` | diagnostic_default | smoke/scaffold defaults | low; not stress-representative |
| A | `FullSpecRunnerConfig` | `action_coupling=0.045`, `noise_scale=0.018`, `drift_scale=0.006`, `shock_strength=0.18` | `contracts/cycle_state.py` | tunable_parameter / v2_dependent | world/stress parameters | medium; fixed environment assumptions may under-cover v2 |
| A | `FullSpecRunnerConfig` | `min_action_strength=0.006`, `max_action_strength=0.030`, `strength_scale=0.12`, `alignment_threshold=0.50` | `contracts/cycle_state.py` | tunable_parameter | action strength envelope | medium; calibration basis unclear |
| A | `FullSpecRunnerConfig` | `canonical_commit_enabled=False`, `canonical_commit_dry_run=True` | `contracts/cycle_state.py` | safety_boundary | preserves no canonical writes | low; correct boundary but must remain explicit |
| A | `FullSpecRunnerConfig` | `intermediate_conservatism_mode="relaxed"` | `contracts/cycle_state.py` | diagnostic_default | Phase 2F-1e default | observation_only |
| A | `ParameterWindowBinder.REGISTRY` | 12 `(theta0, lo, hi)` triples | `parameter_window_binder.py` | tunable_parameter | central module windows | high; many values are not sweep-backed in current docs |
| A | `ParameterWindowBinder` | `_clip`, `_clip_int`, `d(...)/max(...,1e-12)` | `parameter_window_binder.py` | numerical_stability | prevents bad values/division blowup | low |
| A | `ParameterWindowBinder` | current mode: dampening `0.50`, guarded unlock strength `0.70` | `parameter_window_binder.py` | unnecessary_conservatism_candidate | current baseline retains strong thinning | medium if accidentally used as default |
| A | `ParameterWindowBinder` | relaxed mode: sparsity x `0.50`, dampen threshold + `0.12`, dampening `0.75`, guarded unlock strength `0.90` | `parameter_window_binder.py` | arbitrariness_candidate / unnecessary_conservatism_candidate | relaxed choices improve earlier probes but remain fixed | medium |
| A | `ParameterWindowBinder` | flat mode: sparsity `0.0`, threshold `1.01`, gains `1.0` | `parameter_window_binder.py` | diagnostic_default | upper-comparison mode | low if validation-only |
| A | `ParameterShadowBox` | pressure/shadow deltas, sensitivity, boundary damping, rollback sensitivity values | `parameter_shadow_box.py` | tunable_parameter / safety_boundary | bounded shadow update scaffolding | medium; commit boundary is safe but calibration sparse |
| B | `ExplorationThresholds` | budget `6`, sandbox `0.34`, pass `0.50`, watch `0.34`, max risk `0.72` | `exploration_module.py` | arbitrariness_candidate | candidate and sandbox gates | high under sparse/high-noise stress |
| B | `ExplorationModule` | score weights `0.22/0.20/0.18/0.15/0.10/0.08/0.04/0.03` | `exploration_module.py` | arbitrariness_candidate | hand-weighted candidate signal | medium/high; may bias candidate axes |
| B | `ExplorationModule` | noise/topology weights and clamp `0.0..1.0` | `exploration_module.py` | tunable_parameter / numerical_stability | controls sandbox eligibility | medium |
| B | `ExplorationModule` | disabled returns zero candidates/projection | `exploration_module.py` | diagnostic_default / observation_only | no-exploration probe behavior | low if ActionFrame survives |
| B | `ExplorationBridgeModule` | projection adoption threshold `0.5`, topology confidence fallbacks `0.5`, small weights `0.2/0.1` | `exploration_bridge_module.py` | arbitrariness_candidate / unnecessary_conservatism_candidate | projection can thin candidates | medium |
| B | `CoactivationGateModule` | component weights, active threshold `0.20`, pair bonus cap `0.18`, increment `0.045` | `coactivation_gate_module.py` | arbitrariness_candidate | risk score blend | high; gate may act as discretionary conservatism |
| B | `CoactivationGateModule` | hard block `conflict>=0.92`, `unresolved>=0.95`, `candidate_risk>=0.95` | `coactivation_gate_module.py` | safety_boundary / arbitrariness_candidate | severe risk cutoff | medium; safety-like but needs calibration evidence |
| B | `CoactivationGateModule` | decisions `monitor_only`, `block`, `defer`, `dampen`, `allow` | `coactivation_gate_module.py` | unnecessary_conservatism_candidate | can zero/dampen ActionFrames | high under relation_unlock/no_exploration |
| B | `ActionSurfacePlanningModule` | max strength fallback `0.030`, sparsity fallback `0.0`, top-candidate rescue | `action_surface_planning_module.py` | tunable_parameter / safety_boundary | strength cap and sparsity filtering | medium |
| B | `ActionSurfacePlanningModule` | local observation need threshold `0.30` | `action_surface_planning_module.py` | arbitrariness_candidate | local audit trigger | low/medium |
| C | `ActionExecutionModule` | fallback gate factor `0.50` | `action_execution_module.py` | unnecessary_conservatism_candidate | fallback if gate field missing | medium; hidden damping path if audit schema drifts |
| C | `ActionExecutionModule` | block/defer returns empty ActionFrame; dampen multiplies action strength | `action_execution_module.py` | safety_boundary / unnecessary_conservatism_candidate | gate applied before ActionModule | high; verify it is safety not middle-layer preference |
| C | `ActionExecutionModule` | direct-read/write flags always false | `action_execution_module.py` | safety_boundary | ActionFrame-only boundary | low; preserve |
| C | action primitives | fixed primitive/channel map and reversibility classes | `action_module/actions.py` | tunable_parameter / v2_dependent | translates action intent to primitive family | medium; v2 calibration needed |
| C | integrated diagnostic loop | action/stress defaults and epsilon `1e-12` | `integrated_diagnostic_closed_loop.py` | diagnostic_default / numerical_stability | standalone ActionModule diagnostics | medium; separate defaults can drift from runner |
| D | `WorldAdapter` | `world_engine="pseudo_reality_v1"`, trace columns, v2 engine selector | `world_adapter.py` | diagnostic_default / v2_dependent | v1 default with v2 connection | medium; v2 trace coverage should be audited before heavy run |
| D | `BoundaryGuard` | zero violation defaults and forbidden write checks | `boundary_guard.py` | safety_boundary | detects write boundary violation | low; export readability still relevant |
| D | `AuditLedger` | ordered module ledger | `audit_ledger_module.py` | observation_only | supports review | low |
| D | `run_matrix_validation.py` | fixed `PER_RUN_EXPORTS`, summary minima | `scripts/run_matrix_validation.py` | observation_only / unnecessary_conservatism_candidate | not behavior, but evidence can be hidden | medium; Phase 2G-1a export gap |
| D | `profile_loader.py` | summary metric set | `scripts/profile_loader.py` | observation_only | matrix-level visibility | medium; missing columns can mask module holes |
| D | v2 asymmetric game | seed/profile/default dynamics, hidden trace schemas | `asymmetric_game_v2.py` | v2_dependent | v2 premises | medium/high until v2-specific probes run |

## 5. Arbitrariness Candidate List

| severity | group | module | value | why arbitrary candidate | recommended validation |
| --- | --- | --- | --- | --- | --- |
| high | A | `ParameterWindowBinder.REGISTRY` | 12 `(theta0, lo, hi)` triples | central parameter windows lack in-repo sweep evidence tying ranges to stress outcomes | small sweep/readability probe before changing values |
| medium | A | `ParameterWindowBinder` | relaxed: sparsity x `0.50`, dampen threshold + `0.12`, dampen factor `0.75`, guarded unlock `0.90` | justified by prior relaxed probes but still fixed magic deltas/factors | compare `current/relaxed/flat` on relation_unlock_pressure, no_exploration, high_noise |
| high | B | `CoactivationGateModule` | risk score weights `0.22/0.16/0.20/0.20/0.14/0.08` | gate risk blend can decide dampen/defer/block without clear calibration target | gate-risk decomposition matrix with per-decision outcome deltas |
| high | B | `CoactivationGateModule` | active component threshold `0.20`, pair bonus cap `0.18`, increment `0.045` | coactivation penalty may be a middle-layer conservative heuristic | stress probe for action loss vs boundary violation |
| medium | B | `CoactivationGateModule` | hard block `0.92/0.95/0.95` | may be safety boundary, but documentation does not prove thresholds | targeted forced-risk probe; do not relax without evidence |
| high | B | `ExplorationThresholds` | budget `6`, sandbox/watch `0.34`, pass `0.50`, max risks `0.72` | candidate survival in sparse/high-noise worlds depends on these values | candidate-retention sweep with no acceptance relaxation |
| medium | B | `ExplorationModule` | candidate signal/noise/topology weights | hand-weighted composite can bias which axes survive | per-axis sensitivity audit |
| medium | B | `ExplorationBridgeModule` | projection adoption `0.5` and fallback confidences | can suppress exploration projection before ActionFrame planning | projection retention probe under sparse_projection/projection_zero |
| medium | B | `ActionSurfacePlanningModule` | local observation need threshold `0.30` | local audit trigger threshold lacks stress calibration | local audit trigger coverage check |
| medium | C | `ActionExecutionModule` | fallback `gate_dampening_factor=0.50` | hidden conservative fallback if gate audit column is absent | schema-drift test/audit, not behavior change |
| medium | C | action primitives | fixed primitive/channel/reversibility map | v2 suitability cannot be inferred from v1 traces alone | v2 action primitive calibration premise task |
| medium | D | v2 engine defaults | v2 seeds/dynamics/default profile constants | v2 stress semantics require environment-specific evidence | v2 smoke plus trace completeness audit |

## 6. Unnecessary Conservatism Candidate List

| severity | group | module | mechanism | symptom risk | why possibly excessive | recommended next task |
| --- | --- | --- | --- | --- | --- | --- |
| high | B/C | Gate + ActionFrame builder | `defer`/`block` returns empty ActionFrame | relation_unlock/no_exploration loses needed actions | middle gate can erase actions before actuator layer | Phase 2G-2 intermediate conservatism repair probe |
| high | B/C | Gate + ActionFrame builder | `dampen` multiplies `action_strength` | action mass too weak under shock/recovery | not all dampening is safety; some may be discretionary | gate decision vs outcome delta probe |
| medium | A/B | ParameterWindowBinder + planner | candidate sparsity threshold filtering | sparse candidates disappear | relaxed halves sparsity, but fixed threshold may still be too high | candidate retention audit matrix |
| medium | A/B | ParameterWindowBinder | guarded unlock delay preserved and strength `0.90` in relaxed | relation_unlock family remains thin | relaxed neutralizes gains but still preserves delay and sub-1 strength | relation_unlock_pressure focused probe |
| medium | B | ExplorationBridge | projection adoption threshold | verified candidates may not project | projection thinning before planning can mimic no_exploration | projection survival audit |
| medium | B | ExplorationModule | max noise/topology risk `0.72` | high_noise/shock candidates are watched/blocked | risk caps may be over-conservative in stress where exploration is needed | high_noise candidate pass-rate probe |
| low | B | ActionSurfacePlanningModule | top-candidate rescue | keeps one candidate but may hide excessive filtering | rescue prevents zero rows but not loss of diversity | export candidate pre/post counts |
| medium | D | validation exports | omitted runner artifacts from per-run CSV | holes harder to review | evidence absence can delay repair decisions | Phase 2G-2 audit/export readability repair |

## 7. Stress Function Readiness

| stress condition | relevant modules | expected role | possible failure | recommended probe |
| --- | --- | --- | --- | --- |
| high_noise | Exploration, Gate, BoundaryGuard | retain useful candidates while blocking unsafe writes | exploration risk caps and gate noise component over-dampen | high_noise small matrix with candidate/gate decomposition |
| shock_recovery | ParameterShadowBox, Binder, Gate, ActionExecution | allow recovery action without runaway update | shadow deltas plus gate coactivation produce defer/block cascade | shock recovery recovery-time probe |
| relation_lock | Binder, Planner, Gate, Action primitives | preserve relation unlock/coupling relief action mass | guarded unlock delay/strength and gate dampen thin action | relation_lock/relaxed/flat comparison |
| relation_unlock_pressure | Pressure translation, Binder, Planner, Gate | translate pressure to unlock candidates | middle conservatism narrows candidates before ActionFrame | focused relation_unlock_pressure probe |
| no_exploration | Exploration, Bridge, Planner, ActionExecution | keep non-exploration ActionFrames alive | projection zero misread or planning loses necessary frame | no_exploration projection-zero + ActionFrame-min check |
| high_uncertainty | Exploration, LocalAudit, Gate | generate probes and local needs | local audit/gate becomes watch/defer rather than candidate support | high_uncertainty local audit coverage probe |
| high_relation_lock | Planner, Gate, Action primitives | unlock without direct unsafe writes | topology risk and gate risk block unlock family | topology-risk decomposition probe |
| sparse_projection | ExplorationBridge, Planner | avoid over-reliance on projection rows | projection adoption threshold creates candidate starvation | sparse_projection projection retention probe |
| projection_zero | Bridge, Planner, ActionExecution | ActionFrames remain from pressure/planning | matrix aggregate `projection_min=0` can obscure issue | keep as observation-only with source audit columns |
| flat upper-bound | Binder, Gate, Planner | validation-only comparison ceiling | flat can mask safety-risk if misused as default | keep validation-only; compare not adopt |
| relaxed default | Binder, Gate, Planner | production-like reduced middle conservatism | residual current-derived delay/dampen remains | relaxed-vs-flat delta review |

## 8. Group A Findings: Pressure / Parameter

- Pressure translation appears mostly contract/audit oriented and preserves noncompressive/no-write semantics. No pressure-to-ActionFrame or pressure-to-ActionModule direct path was identified.
- The largest A-group fixed-value concentration is in `ParameterWindowBinder.REGISTRY`, where each parameter has a fixed default/lower/upper triple. These are appropriate as a central registry but should be treated as tunable, not proven constants.
- `relaxed` mode reduces some middle conservatism but does not remove it: candidate sparsity is halved, dampen thresholds move, dampening becomes `0.75`, and guarded unlock strength remains below 1.0.
- `flat` is useful as an upper comparison but should not become a default or repair substitute.
- Commit/write boundaries remain safety boundaries. The audit did not identify a reason to loosen canonical write, dry-run, or rollback constraints.

Required validation before repair:

1. Registry/window sweep over relation_unlock_pressure, no_exploration, and one noise/shock condition.
2. Per-module export of pre/post parameter-window candidate counts before changing thresholds.
3. Separate safety-boundary check if any dampen/defer/block thresholds are considered for change.

## 9. Group B Findings: Gate / Planning / Exploration

- Group B contains the highest concentration of possible discretionary conservatism.
- `CoactivationGateModule` blends pressure, exploration, action, local risk, noise, and shadow components with fixed weights, then applies `allow/dampen/defer/block/monitor_only` decisions. This is the main hole candidate because it can behave like a middle-layer conservative controller rather than a pure safety boundary.
- `ExplorationModule` has fixed candidate budget, sandbox thresholds, risk caps, and hand-weighted signal/noise/topology scores. Under sparse/high-noise/high-lock stress, these can reduce candidate diversity before the ActionFrame layer sees it.
- `ExplorationBridgeModule` projection thresholds can further thin exploration outputs. This is especially relevant for sparse_projection and relation_unlock_pressure.
- `ActionSurfacePlanningModule` has a rescue-top-candidate path, which prevents total disappearance but may hide excessive candidate sparsity by preserving only the strongest row.

Required validation before repair:

1. Gate decision decomposition exported by run/stress condition.
2. Candidate counts before/after exploration, bridge projection, parameter-window filtering, gate, and ActionFrame builder.
3. Relation unlock family action mass comparison across `current`, `relaxed`, and `flat`.

## 10. Group C Findings: ActionFrame / ActionModule Boundary

- ActionFrame source-audit columns are present and useful: planning source, pressure source, binding source, gate source, and exploration projection source make no-exploration/projection-zero cases reviewable.
- Boundary flags are explicitly false for direct G/K, O_t, v8, exploration sidecar, ParameterBox, canonical write, world write, G/K writeback, and direct ActionModule call during frame building.
- The major C-group concern is not boundary leakage; it is information/action loss before ActionModule invocation. `block` and `defer` produce empty ActionFrames, and `dampen` reduces strength.
- The ActionModule primitive map is fixed and should be treated as v2-dependent. Primitive calibration should not be changed before v2 trace behavior is visible.

Required validation before repair:

1. ActionFrame information-retention audit under relation_unlock_pressure and no_exploration.
2. Action source audit remains true across stress runs.
3. v2 primitive premise/calibration review before changing primitive maps or strengths.

## 11. Group D Findings: World / Audit / Export

- The world/audit boundary is generally clean: writeback and canonical write flags are audited, and Phase 2G-1a found no blocker/high boundary holes.
- The known medium gap remains audit/export readability. Some runner artifacts such as `action_result`, `boundary_guard_audit`, and `cycle_audit_row` are present internally but not first-class per-run CSV exports in the current matrix runner.
- `profile_loader.py` already exposes useful aggregate metrics, including action mass and gate counts, but module-level pre/post thinning is still not sufficiently readable for repair decisions.
- v2 trace connection points exist, but the adequacy of hidden/resource/information/action-effect traces is v2-dependent and should not be inferred from v1/default smoke alone.

Required validation before repair:

1. Audit/export readability repair before larger v2 evidence review.
2. Add export-only module thinning columns or CSVs; do not change acceptance.
3. v2 trace completeness check before v2-specific calibration.

## 12. Hole List

| severity | group | module | issue | evidence | recommended next task |
| --- | --- | --- | --- | --- | --- |
| blocker | - | - | none found | no production behavior change needed for this audit | proceed with planned follow-ups |
| high | B | `CoactivationGateModule` | middle gate may perform discretionary dampen/defer/block | fixed weighted risk blend and decisions can zero or shrink ActionFrames | Phase 2G-2 intermediate conservatism repair probe |
| high | B | `ExplorationModule` | fixed candidate/sandbox/risk thresholds may drop needed candidates under stress | budget `6`, pass `0.50`, risk caps `0.72`, weighted signals | candidate-retention stress probe |
| high | A/B | `ParameterWindowBinder` + planner | registry/window values are central and fixed without sweep evidence | 12 parameter triples plus relaxed/current/flat transforms | parameter-window sweep audit |
| medium | C | `ActionExecutionModule` | block/defer/dampen may erase needed ActionFrame information | block/defer return empty frame; dampen multiplies strength | ActionFrame information-retention audit |
| medium | D | matrix export | module thinning not sufficiently visible | Phase 2G-1a export gap; current exports omit some internal artifacts | Phase 2G-2 audit/export readability repair |
| medium | C | action primitives | primitive map/action strength calibration is v2-dependent | fixed primitive family and reversibility map | action module calibration premise after v2 traces |
| medium | B | `ExplorationBridgeModule` | projection adoption can thin candidates | fixed adoption threshold/fallbacks | projection survival probe |
| low | D | projection-zero summary | `projection_min=0` can be misread | no-exploration expected behavior from Phase 2G-1a | document as observation-only when ActionFrame rows remain |
| low | B | planner rescue | top-candidate rescue masks diversity loss | at least one candidate survives even if sparsity too high | export diversity/pre-post counts |
| observation_only | A | default relaxed mode | default is relaxed | Phase 2F-1e decision | preserve; compare explicitly |
| observation_only | A/B | flat mode | upper-bound validation mode | flat disables some thinning | never use as production default |
| observation_only | D | v2 traces | connection exists but not yet validated heavily | v2 trace columns/export hooks exist | v2 trace completeness audit |

Counts: blocker **0**, high **3**, medium **4**, low **2**, observation_only **3**.

## 13. Repair Planning

### Audit/export系の軽微修正

- Add first-class per-run exports/readability for internal artifacts already produced by the runner.
- Add module-level pre/post thinning visibility for candidates, projection, gate, and ActionFrame rows.
- Keep acceptance and behavior unchanged.

### 中間保守系の慎重修正

- Do not directly relax gate or threshold values yet.
- First run a focused probe measuring candidate/action loss by module boundary.
- Treat gate changes as high-risk because they sit between planning and ActionFrame construction.

### 作用モジュール系のv2前提調整

- Do not change action strength, primitive mapping, or ActionModule behavior in this phase.
- Use v2 trace behavior to decide whether primitive/channel calibration is necessary.

### v2後に判断すべきもの

- v2 asymmetric-game dynamics constants.
- Action primitive calibration and reversibility assumptions.
- Whether v2 hidden/resource/information traces require additional audit columns.

### 修正不要で記録のみのもの

- Canonical write default disabled and dry-run enabled.
- ActionFrame-only boundary flags.
- Flat mode as validation-only upper comparison.
- Projection-zero as expected in explicit no-exploration runs when ActionFrame evidence remains present.

## 14. Recommendation

Recommended next task: **Phase 2G-2 audit/export readability repair**, followed by **Phase 2G-2 intermediate conservatism repair probe**.

Rationale:

1. No blocker was found.
2. The most actionable immediate gap is evidence readability: before changing gate/sparsity/dampen behavior, reviewers need module-by-module pre/post candidate and ActionFrame thinning evidence.
3. Intermediate conservatism is the highest-risk repair area, but changing it without a focused probe risks weakening safety boundaries or changing acceptance by accident.
4. Action module calibration should wait for v2 trace evidence.

The audit does **not** recommend changing production values, gate behavior, ActionModule behavior, defaults, acceptance, or safety boundaries in this PR.

## 15. Conclusion

Phase 2G-1b found no blocker requiring immediate production repair, but it found several high/medium holes that should be addressed through audit-first probes before v2-heavy validation:

- The highest-risk area is Group B middle-layer conservatism: gate risk scoring, dampen/defer/block behavior, exploration thresholds, and candidate sparsity.
- Group A fixed parameter windows are central and should be swept or better evidenced before any value changes.
- Group C boundary safety is readable and should remain unchanged; the concern is ActionFrame/action-mass loss before the ActionModule.
- Group D should be improved first through export/readability work so later repair decisions are evidence-based.

Success criteria for this audit are met: production code is unchanged, fixed values are listed and classified, arbitrariness candidates are identified, unnecessary conservatism candidates are identified, stress concerns are organized, repair priorities are separated, and the recommended next tasks are explicit.
