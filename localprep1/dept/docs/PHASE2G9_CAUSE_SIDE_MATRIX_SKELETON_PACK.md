# Phase 2G-9 Cause-side Matrix Skeleton Pack

## 1. Scope

This pack freezes a **cause-side matrix skeleton** for the next validation design step. It is a static planning artifact, not a runnable v2.1 implementation matrix. It does not implement cause-side profiles, generated profiles, v2.1 world dynamics, ActionModule tuning, final validation, a superiority claim, a safety proof, or real-world deployment evidence.

The companion skeleton JSON is `configs/matrices/matrix_phase2g9_cause_side_matrix_skeleton.json`. Its status is `design_skeleton_not_executable_until_v2_1`; it must not be passed to matrix validation as an executable matrix until a later task explicitly implements cause-side v2.1 parameter handling.

## 2. Background

Phase 2G-5 showed that repaired relaxed remained comparable in preliminary v2 runs, preserved action mass, and kept boundary/write violations at zero, while state metrics were mixed. Phase 2G-6 extended that check and confirmed action mass and zero boundary/write violations across longer/multi-seed runs, but also recorded adverse longer-horizon directions: hidden damage and fatigue increased, information quality and cooperation declined, and defensiveness and latent pressure rose in some readings.

Phase 2G-7 therefore froze a cause-side parameterization design so future evidence does not rest on result-named profiles such as trust-collapse-like or shrinking-equilibrium-like labels. Phase 2G-8 repaired metric export readiness for cause-side validation while preserving exact/proxy/not_available distinctions. Phase 2G-9 uses those two packs to decide which cause-side parameters should be probed first, in what order, with which baselines, and under which metric-readiness or blocking rules.

## 3. Frozen Surfaces

This pack changes only documentation and a static matrix skeleton JSON. The following surfaces remain frozen and unchanged:

- v2 world dynamics unchanged.
- v2 state update unchanged.
- v2 action effect formula unchanged.
- v2 profile JSON unchanged.
- ActionModule unchanged.
- action primitives unchanged.
- PressureTranslation unchanged.
- ParameterWindow registry unchanged.
- ShadowBox unchanged.
- hard safety unchanged.
- block/defer unchanged.
- write path unchanged.
- acceptance unchanged.
- safety boundary unchanged.
- v2 integration unchanged.
- `flat` remains an upper-bound comparator only and is not a production candidate.
- repaired relaxed is maintained as the production candidate for continued investigation only.
- `relaxed_legacy_dampen_075` is maintained as the legacy comparator.

No canonical write, dry-run write, G/K/O_t writeback, ParameterBox direct-to-ActionModule path, ActionModule internal DEPT access, or profile-dynamics edit is enabled here.

## 4. Selected Cause-side Axes

Phase 2G-9 intentionally starts with six primary axes rather than all Phase 2G-7 candidates. This avoids an immediate full-combinatorial sweep and keeps the next implementation probe small.

| role | axis | reason selected |
| --- | --- | --- |
| primary | `information_asymmetry` | Separates visible information from hidden-state mismatch and supports observed/hidden gap checks. |
| primary | `hidden_state_visibility` | Directly targets surface stability versus hidden deterioration. |
| primary | `short_term_gain_pressure` | Tests whether near-term extraction pressure creates hidden damage, fatigue, private-resource stress, or cooperation loss. |
| primary | `relation_lock_strength` | Isolates relation-lock and relation-unlock conditions before tuning action behavior. |
| primary | `recovery_delay` | Tests whether deterioration persists after shocks or action pressure. |
| primary | `action_cost` | Tests whether action mass creates fatigue, defensiveness, or latent-pressure side effects without changing ActionModule internals. |

Secondary axes remain in the design table but are not first-class one-axis sweep drivers in this skeleton: `misread_probability`, `information_delay`, `information_distortion`, `resource_inequality`, `commons_dependency`, `private_information_rate`, `fatigue_accumulation_rate`, `intervention_fatigue`, `exploration_cost`, `repair_friction`, `trust_decay_rate`, `cooperation_decay_rate`, and `public_metric_bias`.

## 5. One-axis Sweep Skeleton

The one-axis stage varies exactly one primary cause-side axis while holding the other primary axes at a future v2.1 baseline or medium design value. These are design candidates only and are not active runtime values.

| axis | candidate levels | required baselines | primary metrics | proxy metrics | blocking metric rule |
| --- | --- | --- | --- | --- | --- |
| `information_asymmetry` | low 0.1; medium 0.3; high 0.6; extreme 0.9 | near-zero-action; current; `relaxed_legacy_dampen_075`; repaired relaxed; flat | information_quality; hidden_damage; cooperation_intent; defensiveness | observed_vs_hidden_gap; misread_proxy | If observed_vs_hidden_gap cannot be read at all, this axis is proxy-only. |
| `hidden_state_visibility` | high_visibility 0.9; medium_visibility 0.6; low_visibility 0.3; extreme_hidden 0.1 | same required baselines | hidden_damage; fatigue; latent_pressure | hidden_decay_gap; public_stability_hidden_decay_gap; observed_vs_hidden_gap | If hidden_decay_gap and public_stability_hidden_decay_gap are both unreadable, route to additional metric export repair. |
| `short_term_gain_pressure` | low 0.1; medium 0.3; high 0.6; extreme 0.8 | same required baselines | hidden_damage; fatigue; private_resource; cooperation_intent; latent_pressure | commons_health_proxy | If private_resource is unreadable, stop resource-related sweeps. |
| `relation_lock_strength` | low 0.1; medium 0.3; high 0.6; extreme 0.8 | same required baselines | relation_lock_proxy; defensiveness; cooperation_intent; action_effect_by_channel | relation_unlock_action_mass; recovery_after_shock_proxy | If relation_lock_proxy is unreadable, relation sweeps become proxy-only. |
| `recovery_delay` | low 0.1; medium 0.3; high 0.6; extreme 0.8 | same required baselines | hidden_damage_final; fatigue_final; cooperation_intent_final | recovery_after_shock_proxy; collapse_delay_proxy | If recovery_after_shock_proxy is unreadable, exact recovery_delay claims are prohibited. |
| `action_cost` | none_or_low 0.0; medium 0.05; high 0.10; extreme 0.20 | same required baselines | fatigue; defensiveness; latent_pressure; action_effect_by_channel | action_cost_effect; intervention_fatigue; repeated_intervention_proxy | If action_effect_by_channel is unreadable, ActionModule tuning decisions are prohibited. |

## 6. Pair Sweep Skeleton

Pair sweeps are priority interaction probes, not a full grid over every cause-side axis.

| priority pair | purpose | expected interaction | required metric readiness |
| --- | --- | --- | --- |
| `information_asymmetry` x `hidden_state_visibility` | Separate misaligned information from hidden-state opacity. | Visible metrics may remain stable while hidden damage, fatigue, or latent pressure rises. | information_quality, hidden_damage, hidden_decay/public-stability gap proxies. |
| `information_asymmetry` x `misread_probability` | Test whether incomplete information becomes harmful through mistaken interpretation. | Cooperation may fall and defensiveness may rise even when action mass exists. | information_quality, cooperation_intent, defensiveness, observed_vs_hidden/misread proxies. |
| `short_term_gain_pressure` x `recovery_delay` | Test extraction pressure under slow recovery. | Hidden damage/fatigue may persist longer and cooperation may fail to rebound. | hidden_damage_final, fatigue_final, cooperation_intent_final, recovery_after_shock_proxy. |
| `relation_lock_strength` x `action_cost` | Test costly intervention under locked relations. | Relation-unlock/coupling actions may increase fatigue, defensiveness, or latent pressure. | relation_lock_proxy, action_effect_by_channel, fatigue, defensiveness, latent_pressure. |
| `commons_dependency` x `resource_inequality` | Test shared-resource depletion under unequal resource conditions. | Private resource imbalance may amplify cooperation decline and hidden damage. | private_resource, cooperation_intent, hidden_damage, commons_health_proxy. |
| `information_delay` x `action_cost` | Test late or mistimed intervention when actions are costly. | Action mass may arrive after deterioration and add fatigue/defensiveness. | information_quality, action_effect_by_channel, action_cost_effect, intervention_fatigue. |

## 7. Scenario Composition Skeleton

Scenario compositions reinterpret existing result-named profiles as cause-side driver combinations. They are not final claims and do not replace one-axis or pair evidence.

| composition | cause-side drivers |
| --- | --- |
| trust-collapse-like | high `information_asymmetry`; high `misread_probability`; high `information_distortion`; high `trust_decay_rate`; medium/high `relation_lock_strength`. |
| shrinking-equilibrium-like | high `short_term_gain_pressure`; high `commons_dependency`; medium/high `resource_inequality`; high `recovery_delay`; high `relation_lock_strength`. |
| hidden-decay-like | low or extreme-hidden `hidden_state_visibility`; high `information_delay`; high `information_distortion`; high `fatigue_accumulation_rate`; high `public_metric_bias`. |
| high-action-cost-like | high/extreme `action_cost`; high `intervention_fatigue`; high `exploration_cost`; high `repair_friction`; medium/high `recovery_delay`. |

## 8. Baseline Comparison Plan

Every cause-side skeleton row should compare at least these required baselines:

- near-zero-action: a minimal-action approximation, not a perfect no-action claim.
- current: old conservative baseline.
- `relaxed_legacy_dampen_075`: legacy relaxed comparator.
- repaired relaxed: production candidate for continued investigation only.
- flat: upper-bound comparator only; not a production candidate.

Optional baselines are `action_buffered_relaxed` and `no_exploration_relaxed` when the next implementation probe needs action-profile or exploration isolation.

## 9. Metric Assignment and Readiness

Phase 2G-8 readiness is carried forward without promoting proxy fields to exact evidence. The next implementation probe may proceed only where the relevant axis has readable primary metrics or explicitly proxy-only wording.

| axis | primary metrics | proxy metrics | readiness interpretation |
| --- | --- | --- | --- |
| `information_asymmetry` | information_quality; hidden_damage; cooperation_intent; defensiveness | observed_vs_hidden_gap; misread_proxy | Can proceed as a cautious one-axis probe if core fields are readable; exact observed/hidden claims require gap evidence. |
| `hidden_state_visibility` | hidden_damage; fatigue; latent_pressure | hidden_decay_gap; public_stability_hidden_decay_gap; observed_vs_hidden_gap | Needs at least one hidden-decay/public-stability gap proxy for visibility-specific claims. |
| `short_term_gain_pressure` | hidden_damage; fatigue; private_resource; cooperation_intent; latent_pressure | commons_health_proxy | Resource-related sweeps depend on private_resource readability. |
| `relation_lock_strength` | relation_lock_proxy; defensiveness; cooperation_intent; action_effect_by_channel | relation_unlock_action_mass; recovery_after_shock_proxy | Relation sweeps are proxy-only unless relation_lock_proxy is available. |
| `recovery_delay` | hidden_damage_final; fatigue_final; cooperation_intent_final | recovery_after_shock_proxy; collapse_delay_proxy | Recovery-delay exact claims are prohibited without recovery_after_shock_proxy or later exact repair. |
| `action_cost` | fatigue; defensiveness; latent_pressure; action_effect_by_channel | action_cost_effect; intervention_fatigue; repeated_intervention_proxy | ActionModule tuning decisions are prohibited unless channel-level action effects are readable. |

Metric labels must remain exact, proxy, row_count_only, not_available, or deferred_requires_semantic_design as appropriate. A proxy summary can guide next-task selection but cannot be reported as exact proof.

## 10. Blocking Conditions

- If `private_resource` is unreadable, resource-related sweeps such as `short_term_gain_pressure`, `commons_dependency`, or `resource_inequality` stop or return to Additional Metric Export Repair.
- If `relation_lock_proxy` is unreadable, relation-related sweeps are downgraded to proxy-only and cannot make exact relation-lock claims.
- If `action_effect_by_channel` is unreadable, ActionModule v2 tuning judgment is prohibited.
- If `recovery_after_shock_proxy` is unreadable, exact `recovery_delay` claims are prohibited.
- If both `hidden_decay_gap` and `public_stability_hidden_decay_gap` are unreadable, `hidden_state_visibility` needs Additional Metric Export Repair before exact visibility-gap claims.
- If any boundary/write violation appears in a future executable probe, Phase 2G-10 must stop and repair boundary/readiness before continuing.

## 11. Transition Criteria to Phase 2G-10

Phase 2G-10 may proceed only if all of the following are true:

1. The skeleton JSON is valid JSON.
2. The skeleton is explicitly marked non-executable until v2.1 cause-side implementation exists.
3. Primary cause-side axes are limited to six.
4. One-axis sweeps are defined.
5. Pair sweeps are bounded and not a full combinatorial grid.
6. Scenario compositions are defined as cause-side driver combinations, not final result-name claims.
7. Required baseline comparisons are fixed.
8. Metric assignments identify primary, proxy, and blocking metrics per axis.
9. Exact/proxy/not_available distinctions from Phase 2G-8 remain intact.
10. Frozen surfaces remain unchanged.
11. v2.1 implementation scope is minimized to the smallest implementation probe needed for one-axis validation.

## 12. Recommended Next Task

Recommended Phase 2G-10 task selection:

1. **Cause-side Parameterized v2.1 Minimal Implementation Probe** if primary metrics are readable and the next step is to implement only the minimum cause-side parameter hooks needed for one-axis sweeps.
2. **Additional Metric Export Repair** if private_resource, relation_lock_proxy, action_effect_by_channel, recovery_after_shock_proxy, hidden_decay_gap, or public_stability_hidden_decay_gap blocks the intended axis.
3. **Cause-side Skeleton Readiness Existing-v2 Validation** if the team wants a no-implementation readiness run over existing v2 profiles before implementing v2.1.
4. **ActionModule v2 Tuning Probe** only after cause-side evidence shows readable channel-level mismatch and `action_effect_by_channel` is available.
5. **Freeze Decision Pack** only after bounded cause-side evidence exists and no boundary/write regression appears.

## 13. Conclusion

Phase 2G-9 fixes the next validation plan as a cause-side matrix skeleton. It narrows the first probe to six primary axes, defines one-axis and priority pair sweeps, maps result-named scenarios back to cause-side drivers, fixes baseline roles, assigns metrics and blocking conditions, and records Phase 2G-10 transition criteria. It does not implement v2.1, change world dynamics, tune ActionModule behavior, alter safety/write paths, claim superiority, prove safety, or claim deployment readiness.
