# Phase 2G-15 v2 Risk-Band Benefit / Possibility Metric Fixation Pack

## 1. Scope

Phase 2G-15 fixes the evaluation premises for the next ActionModule v2 system-fit work.

Japanese fixed name:

`v2 リスク帯別 利益・可能性分布 指標固定パック`

This is a **docs-only metric fixation pack**.

This pack fixes:

1. system benefit indicators;
2. H11-aligned possibility-distribution indicators;
3. pressure-action alignment indicators;
4. representative v2 risk bands;
5. expected results by risk band;
6. success patterns;
7. failure patterns;
8. indicators allowed during ActionModule adjustment;
9. single-objective indicators that must not be used alone;
10. premises for the next ActionModule v2 tuning probe.

This pack does not:

- tune the ActionModule;
- change action primitives;
- change PressureTranslation;
- change ParameterWindow registry;
- change ParameterShadowBox;
- change safety boundaries;
- change write paths;
- change world dynamics;
- add new cause-side axes;
- add new matrix files;
- run extended validation;
- claim superiority, safety, deployment readiness, or real-world evidence.

## 2. Central Thesis

The ActionModule must not become an independent optimizer.

The purpose of the ActionModule is:

> To translate upper pressure into concrete actions suitable for the target pseudo-reality system while preserving the pressure direction, maintaining multiple system-benefit indicators, and keeping or widening the system's possibility distribution without causing excessive hidden damage, fatigue, defensiveness, or latent pressure.

In Japanese:

> 作用モジュールの目的は、上位圧を無視して勝手に最適化することではない。上位圧が持つ「可能性分布を広げる方向性」を、対象系の複数利益指標と回復可能性を壊さない範囲で、具体的な作用へ翻訳することである。

This central thesis must remain active during Phase 2G-16 and later ActionModule work.

## 3. System Benefit Indicators

System benefit must not be reduced to one number.

The following indicators should be treated as a bundle:

- `total_resource`
- `private_resource`
- `cooperation_intent`
- `information_quality`
- low `hidden_damage`
- low `fatigue`
- low `defensiveness`
- low `latent_pressure`
- `recovery_after_shock`
- `long_term_stability`

### 3.1 `total_resource` — total system resource

Japanese fixed meaning:

`系全体の総資源量`

This indicates how much resource remains in the system as a whole.

It is useful for reading total wealth or total remaining capacity, but it must not be used alone.

A high `total_resource` may hide:

- resource concentration;
- internal depletion;
- worsening hidden damage;
- worsening cooperation;
- future collapse risk.

Interpretation:

> `total_resource` is a total-amount benefit indicator, not a complete welfare indicator.

### 3.2 `private_resource` — individual/private resource

Japanese fixed meaning:

`各主体が持つ個別資源`

This indicates whether individual entities retain enough resources.

It helps detect cases where total system resources look acceptable but the internal distribution is damaged.

Watch for:

- one-sided resource concentration;
- partial depletion;
- hidden exhaustion behind good aggregate numbers;
- individual agents becoming too weak to participate in recovery.

Interpretation:

> `private_resource` is a distribution-sensitive benefit indicator.

### 3.3 `cooperation_intent` — cooperative orientation

Japanese fixed meaning:

`協調意向`

This indicates whether entities still tend toward cooperation rather than defensive closure, exploitation, or mutual loss avoidance.

High `cooperation_intent` means:

- cooperative routes remain;
- relation repair remains possible;
- shrinking equilibrium is less likely;
- pressure may be translated into constructive action.

Low `cooperation_intent` means:

- defensive behavior increases;
- relation lock becomes more likely;
- entities may choose self-protection over joint recovery;
- pressure may be absorbed as resistance.

Interpretation:

> `cooperation_intent` is a relational benefit indicator.

### 3.4 `information_quality` — information quality

Japanese fixed meaning:

`情報品質`

This indicates how well visible information reflects the actual state of the system.

High `information_quality` means:

- state reading is easier;
- mistaken actions are less likely;
- pressure can be translated more accurately;
- hidden deterioration is less likely to be missed.

Low `information_quality` means:

- hidden damage can be overlooked;
- short-term gain can be misleading;
- ActionModule translation can target the wrong surface;
- pressure may be misapplied.

Interpretation:

> `information_quality` is a benefit indicator for judgment possibility.

### 3.5 Low `hidden_damage` — low hidden damage

Japanese fixed meaning:

`隠れ損傷の少なさ`

This indicates whether internal damage is accumulating behind apparently good public signals.

High `hidden_damage` means:

- the system may look stable while internally deteriorating;
- short-term benefit may be false benefit;
- delayed collapse becomes more likely;
- the ActionModule may be overfitting public indicators.

Interpretation:

> Low `hidden_damage` is a core benefit indicator for avoiding invisible deterioration.

### 3.6 Low `fatigue` — low fatigue

Japanese fixed meaning:

`疲弊の少なさ`

This indicates whether the system can still tolerate exploration, intervention, or recovery work.

Low `fatigue` means:

- recovery capacity remains;
- additional action is less likely to harm the system;
- long-term operation remains feasible.

High `fatigue` means:

- exploration becomes costly;
- intervention may become harmful;
- recovery routes may close;
- pressure may increase burden rather than possibility.

Interpretation:

> Low `fatigue` is a persistence and endurance benefit indicator.

### 3.7 Low `defensiveness` — low defensiveness

Japanese fixed meaning:

`防衛反応の少なさ`

This indicates whether entities are overly closed, resistant, or defensive.

Low `defensiveness` means:

- the system can receive action;
- relation repair is easier;
- exploration pressure can pass through more constructively.

High `defensiveness` means:

- entities close down;
- relation lock strengthens;
- pressure may be converted into resistance;
- shrinking equilibrium becomes more likely.

Interpretation:

> Low `defensiveness` is a softness/receptivity benefit indicator.

### 3.8 Low `latent_pressure` — low latent pressure

Japanese fixed meaning:

`潜在圧の少なさ`

This indicates hidden tension or accumulated pressure that may later erupt.

Low `latent_pressure` means:

- current stability is more likely to be genuine;
- future reaction risk is lower;
- the system is not merely suppressing instability.

High `latent_pressure` means:

- apparent stability may be forced;
- rebound risk increases;
- small shocks can trigger collapse;
- pressure may be accumulating rather than being resolved.

Interpretation:

> Low `latent_pressure` is a future-fracture-risk benefit indicator.

### 3.9 `recovery_after_shock` — recovery after shock

Japanese fixed meaning:

`外乱後の回復力`

This indicates whether the system can return or reorganize after disturbance.

It is different from ordinary stability:

- stability means the system does not shake much;
- recovery means the system can return after it shakes.

In high-risk systems, recovery may be more important than stillness.

Interpretation:

> `recovery_after_shock` is a benefit indicator for post-disturbance survivability.

### 3.10 `long_term_stability` — long-term stability

Japanese fixed meaning:

`長期安定性`

This indicates whether the system remains viable over time, not only in the short term.

It is needed to distinguish:

- short-term gain followed by long-term collapse;
- short-term cost followed by long-term viability.

Interpretation:

> `long_term_stability` is a long-horizon viability benefit indicator.

## 4. Benefit Evaluation Rule

System benefit must be evaluated as a multi-indicator balance.

The following are prohibited as single success criteria:

- maximizing only `total_resource`;
- maximizing only `private_resource`;
- maximizing only `cooperation_intent`;
- maximizing only `information_quality`;
- minimizing only `hidden_damage`;
- maximizing only short-term gain.

Reason:

A single benefit indicator can be improved while damaging the wider system.

Examples:

- `total_resource` rises while `hidden_damage` rises;
- `cooperation_intent` rises while `fatigue` rises too much;
- `information_quality` rises but action cost becomes too high;
- short-term gain rises while `latent_pressure` and long-term collapse risk increase.

Fixed rule:

> A good ActionModule adjustment must avoid improving one benefit indicator by destroying other essential benefit indicators.

## 5. H11-Aligned Possibility-Distribution Indicators

Possibility distribution should be aligned with the upper-layer H11 semantic basis.

Reason:

1. Upper pressure is produced from H11-like semantic/geometry readings.
2. Possibility distribution is not mere action variety; it is the meaningful spread of viable future routes.
3. H11 alignment prevents the ActionModule from inventing an independent optimization axis.

H11 fixed Japanese names:

| H11 name | Japanese fixed name | Role in possibility distribution |
| --- | --- | --- |
| Stability | 安定性 | Prevents possibility expansion from becoming destructive instability. |
| AdaptabilityStar | 適応・再編性 | Measures whether the system can change and reorganize when needed. |
| Exploration | 探索性 | Measures whether unknown or underexplored routes remain open. |
| Efficiency | 効率性 | Checks whether exploration/action cost is not exploding. |
| Robustness | 頑健性 | Checks whether the system can tolerate disturbance. |
| StructuralDiversity | 構造的多様性 | Measures whether the system has meaningful mode/path diversity. |
| TrajectoryDynamics | 軌道動態 | Reads movement, turning, oscillation, path switching, and momentum. |
| Predictability | 予測可能性 | Checks whether the future is readable enough for safe action. |
| Coherence | 整合性 | Checks whether the possibility spread remains internally coherent. |
| Recoverability | 回復可能性 | Measures whether recovery routes remain available. |
| NoveltyQuality | 新規性の質 | Distinguishes meaningful novelty from noise. |

### 5.1 Core possibility indicators

The core possibility-distribution indicators are:

- 探索性;
- 構造的多様性;
- 回復可能性;
- 適応・再編性;
- 新規性の質;
- 整合性;
- 軌道動態.

These read whether the system has meaningful future options, not merely many actions.

### 5.2 Audit indicators for bad expansion

The following indicators should audit whether expansion is becoming harmful:

- 安定性;
- 頑健性;
- 効率性;
- 予測可能性;
- 整合性.

They prevent confusing the following with good possibility expansion:

- noise;
- uncontrolled divergence;
- fatigue-driven scattering;
- relation breakage;
- predictable collapse;
- incoherent novelty.

Fixed rule:

> Possibility distribution is H11-aligned. Exploration, structural diversity, recoverability, adaptability/reorganization, and novelty quality are central, while stability, robustness, efficiency, predictability, and coherence audit whether the expansion is healthy.

## 6. Pressure-Action Alignment Indicators

Pressure-action alignment means:

> The ActionModule must translate the H11 direction of the upper pressure into suitable action channels without ignoring the pressure or replacing it with independent local optimization.

The ActionModule should not decide:

> This action wins locally, so use it regardless of pressure.

Instead, it should decide:

> This pressure is trying to open a certain H11 direction, so choose a channel, strength, and timing that translate that pressure into this v2 system without damaging benefit balance or possibility distribution.

### 6.1 Provisional H11-to-action channel mapping

| H11 direction | Candidate action channels | Main caution |
| --- | --- | --- |
| 探索性 | `exploration_injection`, `uncertainty_probe` | Avoid noise-like exploration and fatigue. |
| 構造的多様性 | `exploration_injection`, `relation_unlock`, `coupling_relief` | Avoid fragmentation or incoherent spreading. |
| 回復可能性 | `buffer_increase`, `volatility_damping`, `coupling_relief` | Avoid over-stabilizing into fixed equilibrium. |
| 適応・再編性 | `relation_unlock`, `uncertainty_probe`, `exploration_injection` | Avoid random reconfiguration without benefit. |
| 新規性の質 | `uncertainty_probe`, `exploration_injection` | Novelty must not be confused with noise. |
| 整合性 | `volatility_damping`, `coupling_relief` | Avoid suppressing useful exploration. |
| 頑健性 | `buffer_increase`, `volatility_damping` | Avoid excessive conservatism. |
| 安定性 | `volatility_damping`, `buffer_increase` | Avoid shrinking equilibrium and over-fixation. |
| 効率性 | action-cost suppression, unnecessary action-mass suppression | Avoid killing pressure by over-minimizing cost. |
| 軌道動態 | `relation_unlock`, `uncertainty_probe` | Avoid oscillation noise and uncontrolled switching. |
| 予測可能性 | `volatility_damping`, information-quality preservation | Avoid mistaking predictable collapse for safety. |

This mapping is fixed as a **provisional alignment table** for Phase 2G-16. It is not a final tuning formula.

### 6.2 Alignment checks

During ActionModule adjustment, check:

- whether action channels match the H11 direction of pressure;
- whether action strength is proportionate to pressure strength;
- whether action is suppressed when pressure is absent;
- whether action cost is reasonable for the risk band;
- whether action diversity reflects pressure diversity rather than random variety;
- whether `action_mass_by_channel` follows the intended pressure shape;
- whether over-action risk is controlled;
- whether under-action risk is controlled.

## 7. Representative v2 Risk Bands

Risk bands are validation categories, not universal classifications.

For now, representative patterns are enough. Later work may vary v2 parameters to study which risks emerge from which parameter settings.

### 7.1 Stable band

Japanese fixed name:

`安定帯`

Expected profile:

- low `information_asymmetry`;
- low to medium `action_cost`;
- low relation lock;
- low fatigue;
- low hidden damage;
- low latent pressure;
- cooperation remains usable;
- information quality is sufficient.

Expected result:

- short-term cost may be slightly worse;
- long-term result should be equal or slightly positive;
- possibility distribution should not narrow;
- small insurance cost is acceptable.

### 7.2 Medium-risk band

Japanese fixed name:

`中リスク帯`

Expected profile:

- medium `information_asymmetry`;
- medium `action_cost`;
- relation lock begins to rise;
- fatigue begins to rise;
- hidden damage begins to appear;
- latent pressure begins to appear;
- cooperation starts to weaken;
- future routes are still recoverable.

Expected result:

- short-term result may be slightly worse;
- long-term result should be positive;
- possibility distribution should remain relatively wide;
- short-term cost is acceptable if it protects long-term benefit and recovery routes.

### 7.3 High-risk band

Japanese fixed name:

`高リスク帯`

Expected profile:

- high `information_asymmetry`;
- high `action_cost`;
- high relation lock;
- high fatigue;
- high hidden damage;
- high latent pressure;
- decreasing cooperation;
- increasing defensiveness;
- risk of shrinking equilibrium.

Expected result:

- shrinking equilibrium should be avoided;
- short-term result should improve or deterioration should be reduced;
- long-term result should improve clearly;
- possibility distribution should remain comparatively large;
- hidden damage, fatigue, defensiveness, and latent pressure should not explode.

### 7.4 Extreme-risk band

Japanese fixed name:

`極端リスク帯`

Expected profile:

- extreme `information_asymmetry`;
- extreme `action_cost`;
- extreme relation lock;
- extreme recovery delay;
- very high hidden damage;
- very high fatigue;
- very high defensiveness;
- very high latent pressure.

Expected result:

- full recovery is not expected;
- collapse delay may count as partial success;
- loss reduction may count as partial success;
- remaining recovery routes should be measured;
- possibility distribution may shrink, but residual viable paths matter.

## 8. Expected Results by Risk Band

| Risk band | Short-term benefit | Long-term benefit | Possibility distribution | Success interpretation |
| --- | --- | --- | --- | --- |
| 安定帯 | Slight disadvantage is acceptable. | Equal to slightly positive. | Maintained or slightly widened. | Small insurance cost is acceptable if the system is not damaged. |
| 中リスク帯 | Slight disadvantage is acceptable. | Positive. | Relatively wide. | Short-term cost is acceptable if long-term benefit and recovery routes improve. |
| 高リスク帯 | Positive or deterioration reduced. | Clearly positive. | Comparatively large. | Avoids shrinking equilibrium, hidden deterioration, and relation lock. |
| 極端リスク帯 | Large improvement not required. | Loss reduction or collapse delay. | Residual viable paths matter. | Tests limit behavior; full success is not expected. |

## 9. Success Patterns

A successful ActionModule adjustment should show:

- action follows the pressure direction;
- action does not ignore upper pressure;
- multiple benefit indicators are not damaged together;
- no single benefit indicator is maximized at the expense of the system;
- possibility distribution is maintained or widened;
- exploration does not become noise;
- `hidden_damage` does not increase excessively;
- `fatigue` does not increase excessively;
- `defensiveness` does not increase excessively;
- `latent_pressure` does not increase excessively;
- high-risk bands avoid shrinking equilibrium;
- medium-risk bands trade small short-term cost for long-term benefit;
- stable bands stay within acceptable insurance cost.

## 10. Failure Patterns

A failed ActionModule adjustment includes:

- action ignores pressure;
- action increases without pressure;
- one benefit indicator is maximized while others break;
- `total_resource` rises while `hidden_damage` rises;
- short-term gain rises while long-term stability falls;
- `cooperation_intent` rises while `fatigue` rises too much;
- exploration rises but becomes noise;
- possibility distribution closes;
- relation lock strengthens;
- defensiveness increases;
- latent pressure accumulates;
- high-risk bands fall into shrinking equilibrium;
- `action_mass` exists but benefit and possibility distribution do not improve.

## 11. Indicators Allowed During ActionModule Adjustment

### 11.1 Benefit indicators

Allowed benefit indicators:

- `total_resource`;
- `private_resource`;
- `cooperation_intent`;
- `information_quality`;
- `hidden_damage`;
- `fatigue`;
- `defensiveness`;
- `latent_pressure`;
- `recovery_after_shock`;
- `long_term_stability`.

They must be read together.

### 11.2 H11 possibility-distribution indicators

Allowed H11 possibility indicators:

- 安定性;
- 適応・再編性;
- 探索性;
- 効率性;
- 頑健性;
- 構造的多様性;
- 軌道動態;
- 予測可能性;
- 整合性;
- 回復可能性;
- 新規性の質.

They must be read as a distribution, not as a flat sum.

### 11.3 Pressure-action alignment indicators

Allowed pressure-action alignment indicators:

- pressure direction to action-channel correspondence;
- pressure strength to action strength correspondence;
- suppression of unnecessary action when pressure is absent;
- action cost relative to risk band;
- action diversity;
- `action_mass_by_channel`;
- over-action risk;
- under-action risk.

## 12. Single-Objective Indicators Not Allowed as Standalone Success Criteria

The following must not be used alone as success criteria:

- only `total_resource`;
- only short-term gain;
- only `cooperation_intent`;
- only `information_quality`;
- only `action_mass`;
- only action diversity;
- only low `hidden_damage`;
- only stability;
- only predictability;
- only flat-comparator win/loss.

Reason:

- `total_resource` alone can miss distribution damage and hidden damage;
- short-term gain alone can miss long-term collapse;
- `cooperation_intent` alone can miss fatigue or resource depletion;
- `information_quality` alone can miss excessive information cost;
- `action_mass` alone can mean only that the system moved, not that it improved;
- action diversity alone can reward noise;
- stability alone can reward shrinking equilibrium;
- predictability alone can reward predictable collapse;
- flat-comparator win/loss alone can confuse an upper-bound comparator with a deployable policy.

## 13. Premises for Phase 2G-16 ActionModule v2 System-Fit Tuning Probe

Before ActionModule adjustment, the following premises are fixed:

1. The ActionModule must not optimize independently of pressure.
2. Action must be selected from H11-aligned pressure direction.
3. System benefit must be read through multiple indicators.
4. Single-benefit maximization is prohibited.
5. Short-term gain alone is not success.
6. Actions that close possibility distribution are failures.
7. High-risk bands prioritize shrinking-equilibrium avoidance.
8. Medium-risk bands allow short-term cost for long-term benefit.
9. Stable bands allow small insurance cost.
10. Independent action without pressure is prohibited.
11. Safety boundary, write path, and world dynamics remain frozen.
12. Phase 2G-16 should begin as a bounded probe, not production tuning.

## 14. Task-Nature Change Warning

Moving from Phase 2G-15 to Phase 2G-16 changes the task nature.

Phase 2G-15 is docs-only metric fixation.

Phase 2G-16 may touch behavior if ActionModule tuning is performed.

Therefore, before Phase 2G-16 starts, explicitly confirm:

- whether ActionModule behavior may be changed;
- whether action-channel weights may be changed;
- whether action strength rules may be changed;
- whether any runner summary/export changes are needed;
- whether matrix validation should be run;
- which risk bands are used first;
- whether Codex is required.

## 15. Conclusion

Phase 2G-15 fixes the evaluation premises for ActionModule v2 system-fit work.

The fixed view is:

- benefit is multi-indicator, not single-objective;
- possibility distribution is H11-aligned;
- pressure-action alignment is mandatory;
- risk bands define expected behavior;
- success and failure patterns are fixed before tuning;
- the next ActionModule work must remain pressure-based, bounded, and explicit.

This document should be used as the entry condition for Phase 2G-16.
