# Phase 2G-7 Cause-side Parameterization Design Pack

## 1. Scope

This is a **design pack** for cause-side parameterization of PseudoReality v2. It is not an implementation task, not a v2 world change, not ActionModule tuning, not a profile migration, not a superiority claim, not a safety proof, and not deployment evidence.

Frozen surfaces for this pack:

- no v2 world body or world dynamics changes;
- no v2 profile JSON changes;
- no ActionModule behavior, action primitive, action strength, or PressureTranslation changes;
- no ParameterWindow registry, ParameterShadowBox update, hard-safety, block/defer, acceptance, safety-boundary, write-path, or v2 integration changes;
- no canonical writes, dry-run writes, G/K/O_t writeback, or ParameterBox direct-to-ActionModule path enablement;
- repaired `relaxed` remains the active repaired relaxed mode, `relaxed_legacy_dampen_075` remains a legacy comparator, and `flat` remains an upper-bound comparator only.

The purpose is to stop treating result-named v2 profiles as final claim axes and instead define cause-side parameters, mappings, metrics, and sweep structure for a future v2.1/v3 validation design.

## 2. Background

Phase 2G-5 performed v2 preliminary validation. The result-named v2 profiles were usable as stress/readiness profiles, repaired relaxed preserved action mass, and boundary/write violations stayed at zero. State metrics were mixed, and exact secondary evidence for recovery/collapse/hidden-decay claims was incomplete.

Phase 2G-6 extended that validation across more seeds and longer horizons. Action mass remained observable and stronger than the old current baseline, while boundary/write violations stayed at zero. However, longer repaired relaxed runs showed adverse directions: hidden damage and fatigue increased, information quality and cooperation decreased, and defensiveness/latent pressure increased. Phase 2G-6 therefore treated the evidence as preliminary and recommended both metric export repair and cause-side parameterization.

Current interpretation:

- repaired relaxed appears to work as a minimal intermediate-conservatism relaxation that restores action mass;
- action mass recovery is not equivalent to hidden-state improvement;
- current v2 profiles are result-named and do not isolate cause-side drivers;
- v2 hidden dynamics may require ActionModule specialization, but tuning should not begin until cause-side mismatch conditions are separated;
- metric export is still too coarse for exact recovery timing, collapse delay, hidden-decay gap, and channel-cost claims.

## 3. Problem with Result-named Profiles

The existing v2 profiles are acceptable preliminary stress/readiness profiles but must not be used as final claim basis.

| existing profile | preliminary use | limitation as final claim axis | better cause-side reading |
| --- | --- | --- | --- |
| `pseudo_reality_v2_trust_collapse` | stress profile for trust-loss-like behavior | the name describes an outcome, making it hard to tell whether trust loss came from information asymmetry, misreads, distortion, natural trust decay, defensive reactivity, or action side effects | compose from high information asymmetry, high misread probability, high information distortion, high trust decay, high defensive reactivity, and medium/high relation lock |
| `pseudo_reality_v2_shrinking_equilibrium` | stress profile for contraction/low-cooperation behavior | the name describes the expected macro-result, not the causal pressure; repaired relaxed could look worse because the profile naturally shrinks or because actions add cost | compose from high short-term gain pressure, high commons dependency, medium/high resource inequality, high recovery delay, high relation lock, and high exploration cost |
| `pseudo_reality_v2_public_stability_hidden_decay` | readiness profile for visible stability with hidden deterioration | the profile blends observability, delay, distortion, fatigue accumulation, public bias, and latent pressure; hidden deterioration cannot be attributed cleanly | compose from low hidden-state visibility, high information delay, high information distortion, high fatigue accumulation, public metric bias, and latent pressure |

Bad final-validation design would ask whether a “trust collapse profile” collapses trust, whether a “shrinking equilibrium profile” shrinks, or whether a “hidden decay profile” hides decay. Good final-validation design varies cause-side conditions and then observes whether trust collapse, shrinking equilibrium, public stability/hidden decay, or mitigation/delay occurs.

## 4. Cause-side Parameter Candidates

The table below is a design candidate list only. It does not define active runtime configuration, acceptance criteria, or production values.

| parameter | Japanese description | layer | expected affected metrics | expected failure mode | implementation risk | priority |
| --- | --- | --- | --- | --- | --- | --- |
| `information_asymmetry` | 情報非対称性。見えている情報と隠れ状態のズレを大きくする。 | information | information_quality, misread proxy, defensiveness, cooperation_intent, hidden_damage | visible actions are based on incomplete/misaligned information; cooperative intent decays despite action mass | medium: must avoid duplicating existing distortion/delay semantics | high |
| `hidden_state_visibility` | 隠れ状態の見えやすさ。低いほど hidden damage / fatigue / latent pressure が観測されにくい。 | information | public_stability_hidden_decay_gap, hidden_damage visibility, fatigue visibility, latent_pressure visibility | public stability masks internal deterioration | medium: requires explicit export distinction between true hidden state and observed proxy | high |
| `private_information_rate` | 各主体が持つ私的情報の比率。高いほど全体判断が歪みやすい。 | information | information_quality, cooperation_intent, defensiveness, private_resource | local incentives override shared interpretation | medium | high |
| `misread_probability` | 他者状態や環境状態の読み間違い確率。 | information | misread proxy, defensiveness, cooperation_intent, information_quality | defensive or mistimed responses grow from incorrect readings | medium | high |
| `information_delay` | 情報遅延。 | information | action timing proxy, recovery_after_shock_proxy, collapse_delay_proxy, information_quality | actions arrive late or at the wrong phase | medium | high |
| `information_distortion` | 情報歪み。 | information | hidden_decay_gap, information_quality, defensiveness, latent_pressure | visible stability diverges from internal state | medium | high |
| `resource_inequality` | 資源偏り。 | resource / incentive | private_resource, cooperation_intent, defensiveness, hidden_damage | hoarding, unequal depletion, cooperation loss | medium | high |
| `commons_dependency` | 共有資源依存度。 | resource / incentive | commons health proxy, cooperation_intent, private_resource, hidden_damage | shared-resource depletion creates shrinking equilibrium | medium | high |
| `short_term_gain_pressure` | 短期利得圧。 | resource / incentive | hidden_damage, fatigue, private_resource, cooperation_intent, latent_pressure | near-term extraction improves surface payoff while damaging long-run state | medium | high |
| `relation_lock_strength` | 関係固定強度。 | relation / topology | relation_lock_proxy, defensiveness, cooperation_intent, relation_unlock action mass, recovery_after_shock_proxy | relation unlock is needed but may fragment or increase hidden damage | low/medium: current traces already include relation-lock-like features | high |
| `recovery_delay` | 回復遅延。 | recovery / fatigue | recovery_after_shock_proxy, fatigue_final, hidden_damage_final, cooperation_intent_final | deterioration persists after shocks/actions | medium | high |
| `action_cost` | 作用コスト。 | action interaction | fatigue, defensiveness, latent_pressure, information_quality, action_effect_trace | actions restore mass but add friction, fatigue, or defensive response | medium/high: must stay world-local and not alter ActionModule semantics | high |
| `trust_decay_rate` | 信頼低下率。 | recovery / fatigue | cooperation_intent, defensiveness, relation metrics | trust collapses without isolating information vs relation drivers | low/medium | medium |
| `cooperation_decay_rate` | 協調低下率。 | recovery / fatigue | cooperation_intent, private_resource, commons health proxy | cooperation deteriorates independently of action mass | low/medium | medium |
| `fatigue_accumulation_rate` | 疲弊蓄積率。 | recovery / fatigue | fatigue, hidden_damage, latent_pressure | repeated pressure/actions accumulate hidden fatigue | medium | medium |
| `defensive_reactivity` | 防衛反応性。 | information / relation | defensiveness, cooperation_intent, hidden_damage | misreads or pressure convert quickly into defensive behavior | medium | medium |
| `noise_visibility_gap` | ノイズと可視性のギャップ。 | information | information_quality, hidden_decay_gap | noisy public signals hide true internal state | medium | optional |
| `coupling_rigidity` | 結合硬直性。 | relation / topology | relation_lock_proxy, recovery proxy, action effect by channel | topology resists corrective actions | medium | optional |
| `volatility_transmission_rate` | 変動伝播率。 | relation / topology | latent_pressure, fatigue, hidden_damage | local volatility spreads through relations | medium | optional |
| `repair_friction` | 修復摩擦。 | action interaction | action_cost_effect, fatigue, recovery proxy | repair actions have slower or costly effects | medium/high | optional |
| `exploration_cost` | 探索コスト。 | action interaction | fatigue, information_quality, private_resource | exploration worsens fatigue/resource loss before benefits appear | medium/high | optional |
| `intervention_fatigue` | 介入疲れ。 | action interaction | fatigue, defensiveness, latent_pressure | repeated intervention raises resistance | medium/high | optional |
| `public_metric_bias` | 公開指標バイアス。 | information | public_stability_hidden_decay_gap | public indicators remain stable while hidden state worsens | medium | medium |
| `latent_pressure` | 潜在圧の初期/蓄積条件。 | recovery / fatigue | latent_pressure, defensiveness, hidden_damage | hidden pressure accumulates before visible deterioration | medium | medium |

## 5. Parameter Layers

| layer | parameters | design role |
| --- | --- | --- |
| information layer | `information_asymmetry`, `hidden_state_visibility`, `private_information_rate`, `misread_probability`, `information_delay`, `information_distortion`, optional `noise_visibility_gap`, `public_metric_bias` | separates observability, delay, distortion, and private knowledge drivers that are currently blended in result-named profiles |
| resource / incentive layer | `resource_inequality`, `commons_dependency`, `short_term_gain_pressure` | distinguishes extraction/inequality/commons pressures from information failure |
| relation / topology layer | `relation_lock_strength`, optional `coupling_rigidity`, `volatility_transmission_rate` | isolates whether relation topology makes action channels helpful, ineffective, or harmful |
| recovery / fatigue layer | `recovery_delay`, `fatigue_accumulation_rate`, `trust_decay_rate`, `cooperation_decay_rate`, `latent_pressure` | separates persistence and accumulation from immediate shock magnitude |
| action interaction layer | `action_cost`, `intervention_fatigue`, `exploration_cost`, `repair_friction` | tests whether action mass creates side effects under v2 conditions without changing ActionModule internals |

## 6. Existing Profile Mapping

| existing profile | likely cause-side drivers | design implication |
| --- | --- | --- |
| `pseudo_reality_v2_trust_collapse` | `information_asymmetry` high; `misread_probability` high; `information_distortion` high; `trust_decay_rate` high; `defensive_reactivity` high; `relation_lock_strength` medium/high | should be decomposed into information and relation/trust axes before claiming trust-collapse mitigation |
| `pseudo_reality_v2_shrinking_equilibrium` | `short_term_gain_pressure` high; `commons_dependency` high; `resource_inequality` medium/high; `recovery_delay` high; `relation_lock_strength` high; `exploration_cost` high | should be decomposed into incentive/resource pressure and recovery-friction axes before claiming shrinkage mitigation |
| `pseudo_reality_v2_public_stability_hidden_decay` | `hidden_state_visibility` low; `information_delay` high; `information_distortion` high; `fatigue_accumulation_rate` high; `public_metric_bias` high; `latent_pressure` high | should be decomposed into visibility, delay/distortion, fatigue, and latent-pressure axes before claiming hidden-decay mitigation |

## 7. Metric Mapping

| cause-side parameter | expected affected v2 hidden/state metrics | metric status needed for validation |
| --- | --- | --- |
| `information_asymmetry` | information_quality, misread probability proxy, defensiveness, cooperation_intent, hidden_damage | information_quality exact/proxy exists; misread proxy likely needs export repair |
| `hidden_state_visibility` | public_stability_hidden_decay_gap, hidden_damage visibility, fatigue visibility, latent_pressure visibility | true-vs-observed gap needs export repair |
| `private_information_rate` | information_quality, cooperation_intent, defensiveness, private_resource | private_resource availability should be repaired/export-confirmed |
| `misread_probability` | defensiveness, cooperation_intent, information_quality, misread proxy | misread proxy needs explicit export |
| `information_delay` | recovery_after_shock_proxy, collapse_delay_proxy, action timing/effect lag | recovery/collapse timing needs export repair |
| `information_distortion` | hidden_decay_gap, public_stability_hidden_decay_gap, information_quality, latent_pressure | gap metrics need export repair |
| `resource_inequality` | private_resource, cooperation_intent, defensiveness | private_resource and inequality summaries need export repair |
| `commons_dependency` | commons health proxy, cooperation_intent, private_resource, hidden_damage | commons metric needs explicit availability classification |
| `short_term_gain_pressure` | hidden_damage, fatigue, private_resource, cooperation_intent, latent_pressure | latent_pressure/private_resource availability should be repaired/export-confirmed |
| `relation_lock_strength` | relation_lock_proxy, defensiveness, cooperation_intent, relation_unlock action mass, recovery_after_shock_proxy | relation lock is currently proxy-only and should be repaired if exact claims are desired |
| `recovery_delay` | recovery_after_shock_proxy, fatigue_final, hidden_damage_final, cooperation_intent_final | recovery timing needs export repair; final state metrics are usable |
| `action_cost` | fatigue, defensiveness, latent_pressure, information_quality, action_effect_trace | action_effect_by_channel, action_cost_effect, and intervention_fatigue need export repair |

## 8. Cause-side Schema Proposal

The following sketch is a design proposal only. The values are candidate ranges for future reduction into a feasible v2.1/v3 probe; they are not implemented in this PR.

```yaml
cause_side_profile:
  name: v2_cause_side_information_asymmetry_sweep
  base_world: asymmetric_game_v2
  parameters:
    information_asymmetry: [0.1, 0.3, 0.5, 0.7, 0.9]
    hidden_state_visibility: [0.9, 0.7, 0.5, 0.3, 0.1]
    misread_probability: [0.05, 0.10, 0.20, 0.35]
    information_delay: [0, 1, 2, 4]
    short_term_gain_pressure: [0.1, 0.3, 0.5, 0.7]
    relation_lock_strength: [0.1, 0.3, 0.5, 0.7]
    recovery_delay: [0.1, 0.3, 0.5, 0.7]
    action_cost: [0.0, 0.05, 0.10, 0.20]
```

Generator design proposal:

1. load an immutable base v2 world template;
2. overlay one cause-side parameter set into a separate generated profile namespace;
3. record generator provenance: base template, parameter axes, values, seed plan, and expected metrics;
4. keep generated profiles out of production defaults until explicitly reviewed;
5. emit a matrix skeleton that names cause axes directly rather than outcomes.

The generator must not mutate existing result-named profile JSON, world dynamics code, ActionModule code, PressureTranslation, registry values, ShadowBox formulas, safety conditions, or write paths.

## 9. Sweep Design

Do not run the full Cartesian product at first. The candidate ranges above would explode quickly and would obscure causal reading. The first cause-side validation should use staged sweeps.

| step | sweep type | axes | purpose |
| --- | --- | --- | --- |
| Step 1 | one-axis sweep | `information_asymmetry`, `hidden_state_visibility`, `short_term_gain_pressure`, `relation_lock_strength`, `recovery_delay`, `action_cost` | estimate monotonicity, metric sensitivity, and safe range size |
| Step 2 | pair sweep | `information_asymmetry × hidden_state_visibility`; `information_asymmetry × misread_probability`; `short_term_gain_pressure × recovery_delay`; `relation_lock_strength × action_cost`; `commons_dependency × resource_inequality` | isolate interactions that likely explain current result-named profiles |
| Step 3 | scenario composition | trust-collapse-like; shrinking-equilibrium-like; hidden-decay-like | reconstruct existing stress families from explicit causal axes |
| Step 4 | baseline comparison | near-zero/current/repaired relaxed/legacy relaxed/flat | compare whether repaired relaxed reduces loss under cause-defined pressure, while flat remains an upper-bound comparator only |

Cause-pressure reading rules:

- low cause pressure: near-zero/current/repaired relaxed differences may be small; DEPT/H-DEPT-style actions can be cost without much benefit;
- medium cause pressure: check whether repaired relaxed is favorable on hidden damage, fatigue, information quality, and cooperation;
- high cause pressure: no-action/current/legacy may degrade more; repaired relaxed should be evaluated for loss reduction, not universal prevention;
- extreme cause pressure: repaired relaxed may not rescue the state; collapse delay or loss reduction may still be informative if exact metrics are available.

## 10. ActionModule Mismatch Hypotheses

Action modules are system-dependent specialized designs. Phase 2G-6 indicates that the current ActionModule can produce action mass, but it is not yet shown to be optimized for v2 hidden-state improvement.

Do not tune the ActionModule immediately. First use cause-side parameterization to identify which cause conditions create channel/state mismatches.

| mismatch hypothesis | cause condition | likely observed symptom | channel/metric evidence needed |
| --- | --- | --- | --- |
| costly action friction | high `action_cost` or high `intervention_fatigue` | action mass remains high while fatigue/defensiveness/latent_pressure rise | action_effect_by_channel, action_cost_effect, intervention_fatigue |
| relation unlock fragmentation | high `relation_lock_strength` with high fragmentation/reactivity | relation-unlock action mass increases but hidden_damage or defensiveness also increases | relation_unlock channel traces, relation_lock_proxy, hidden_damage deltas |
| mistimed intervention | high `information_delay` | actions arrive after state has shifted, weakening recovery or increasing side effects | action timing/effect lag, recovery_after_shock_proxy, collapse_delay_proxy |
| information-misaligned action | high `information_asymmetry`, high `misread_probability`, high `information_distortion` | actions target visible symptoms but information_quality/cooperation degrade | misread proxy, observed-vs-hidden gap, cooperation/defensiveness |
| extraction/recovery mismatch | high `short_term_gain_pressure` with high `recovery_delay` | action mass is insufficient to offset hidden damage/fatigue accumulation | hidden_damage/fatigue final and delta, recovery_after_shock_proxy |

ActionModule v2 tuning should become a candidate only if one or more of these conditions appears:

- high `action_cost` conditions increase fatigue or defensiveness;
- high `relation_lock_strength` conditions make relation-unlock increase hidden damage;
- high `information_delay` conditions show consistently bad action timing;
- repaired relaxed is worse than legacy across multiple cause-side conditions;
- action mass is adequate but state metrics consistently degrade.

## 11. Metric Export Repair Requirements

Metric export repair is needed because several cause-side claims require exact or better-labelled proxy evidence.

| metric/export | current design status | needed for | priority |
| --- | --- | --- | --- |
| hidden_damage, fatigue, information_quality | exact/proxy usable in current summaries | core state reading | high, already partly available |
| cooperation_intent, defensiveness | available as state/proxy in current summaries | social response reading | high, already partly available |
| private_resource | missing or inconsistently available in prior row-level scans | resource/incentive sweeps | high |
| latent_pressure | missing or inconsistently available in prior row-level scans | hidden pressure and extreme cause-pressure reading | high |
| `recovery_after_shock_proxy` | proxy/missing | `recovery_delay`, action timing, scenario composition | high |
| `collapse_delay_proxy` | proxy/missing | high/extreme pressure loss-delay claims | high |
| `hidden_decay_gap` | missing/exact not available | hidden decay and visibility claims | high |
| `public_stability_hidden_decay_gap` | missing/exact not available | public stability with hidden deterioration | high |
| `relation_lock_proxy` | proxy-only | relation/topology sweeps and relation-unlock mismatch | medium/high |
| `action_effect_by_channel` | coarse | channel-level mismatch hypotheses | high |
| `action_cost_effect` | missing | action interaction layer | high |
| `intervention_fatigue` | missing | repeated-action side-effect claims | medium/high |

Recommended order: freeze this cause-side design first, then implement Metric Export Repair against the selected cause axes. Designing the axes first prevents metric repair from overfitting to result-named profiles or exporting metrics that do not support the next validation matrix.

## 12. Recommended Next Task

Recommended next task is **Phase 2G-8 v2 Metric Export Repair for Cause-side Validation**.

Rationale:

- cause-side axes are now defined at design level;
- exact/proxy/missing metric needs can be targeted to those axes;
- implementing profiles or matrices before export repair risks another preliminary-only validation with insufficient causal evidence.

Other candidate tasks, in suggested order after metric repair:

1. **Phase 2G-8 Cause-side Matrix Skeleton Pack** — no world changes; generate a reviewable matrix skeleton around one-axis and pair sweeps.
2. **Phase 2G-8 Cause-side Parameterized v2.1 Implementation Probe** — implement a minimal generated-profile mechanism only after metric requirements are clear.
3. **Phase 2G-8 ActionModule v2 Tuning Probe** — only if cause-side evidence shows action/state mismatch rather than natural world degradation.
4. **Phase 2G-8 Freeze Decision Pack** — only after cause-side metrics and at least one bounded cause-side probe exist.

## 13. Conclusion

Phase 2G-7 converts the next v2 validation direction from result-named profiles to cause-side parameterization design. The existing v2 profiles remain useful as preliminary stress/readiness references, but not final claim axes. The proposed cause-side candidates, layers, profile mapping, metric mapping, schema sketch, staged sweep plan, ActionModule mismatch hypotheses, and metric export requirements define the path toward v2.1/v3 cause-side validation without changing runtime behavior.

No superiority claim, safety proof, or real-world deployment claim is made.
