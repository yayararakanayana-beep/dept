# Phase 2G-16 v2 Indicator Observation Window Design

## 1. Scope

Phase 2G-16 fixes the observation-window design for the v2 indicator system.

Japanese fixed name:

`v2 指標観測窓口設計`

This is a **docs-only design pack**.

This pack converts the Phase 2G-15 / 15A / 15B indicators into structured observation windows.

It does not:

- implement observation windows in code;
- tune the ActionModule;
- change action primitives;
- change action-channel weights;
- change PressureTranslation;
- change ParameterWindow registry;
- change ParameterShadowBox;
- change safety boundaries;
- change write paths;
- change world dynamics;
- add new matrix validation;
- add production scoring;
- claim superiority, safety, deployment readiness, or real-world evidence.

## 2. Background

Phase 2G-15 fixed the main indicator groups:

- system benefit indicators;
- H11-aligned possibility-distribution indicators;
- pressure-action alignment indicators;
- representative v2 risk bands;
- expected results by risk band;
- success and failure patterns.

Phase 2G-15A added growth as a composite observation window:

- `realized_growth` / 実現成長;
- `sustainable_growth` / 持続可能な成長;
- `growth_capacity` / 成長余力.

Phase 2G-15B fixed the interpretation rule:

> Indicators are validation-oriented observation indicators. They are not direct optimization objectives, and they are not absolute criteria.

Phase 2G-16 now fixes how these indicators should be grouped into observation windows.

## 3. Central Thesis

An observation window is not an objective function.

An observation window is a structured reading surface that groups indicators so that validation can inspect system condition, benefit balance, possibility distribution, pressure-action alignment, risk state, growth quality, and total balance.

Japanese thesis:

> 観測窓口とは、指標を最大化するための目的関数ではない。観測窓口とは、系の状態・利益バランス・可能性分布・圧-作用整合・リスク帯・成長品質・総合バランスを読むために、複数の指標を束ねた構造化された読み口である。

This means:

- a window can show evidence;
- a window can raise warnings;
- a window can expose trade-offs;
- a window can support ActionModule tuning later;
- but a window must not become a standalone maximization target.

## 4. Window Set

Phase 2G-16 fixes six observation windows:

1. System Benefit Window / 系の利益観測窓口;
2. H11 Possibility-Distribution Window / H11可能性分布観測窓口;
3. Pressure-Action Alignment Window / 圧-作用整合観測窓口;
4. Risk-Band Window / リスク帯観測窓口;
5. Growth Window / 成長観測窓口;
6. Composite Balance Window / 総合バランス観測窓口.

These windows should be read together.

No single window is sufficient for success or failure judgment.

## 5. System Benefit Window

Japanese fixed name:

`系の利益観測窓口`

### 5.1 Purpose

This window reads whether the system is actually benefiting, without reducing benefit to a single indicator.

It asks:

> Is the system improving or being preserved across multiple benefit dimensions, without hidden damage or future viability loss?

### 5.2 Inputs

Primary indicators:

- `total_resource`;
- `private_resource`;
- `cooperation_intent`;
- `information_quality`;
- low `hidden_damage`;
- low `fatigue`;
- low `defensiveness`;
- low `latent_pressure`;
- `recovery_after_shock`;
- `long_term_stability`.

Optional derived links:

- short-term benefit trend;
- long-term benefit trend;
- benefit-axis balance;
- visible benefit versus hidden deterioration.

### 5.3 Good reading pattern

A good reading pattern is:

- multiple benefit indicators improve or remain acceptable;
- hidden damage does not rise excessively;
- fatigue does not rise excessively;
- defensiveness does not rise excessively;
- latent pressure does not accumulate excessively;
- long-term stability is not sacrificed for short-term gain.

### 5.4 Warning pattern

A warning pattern is:

- `total_resource` rises but `hidden_damage` rises;
- cooperation rises but fatigue rises too much;
- information quality rises but action cost becomes excessive;
- short-term benefit rises while long-term stability falls;
- the system looks improved but future viability is being consumed.

### 5.5 Prohibited interpretation

Do not interpret this window as:

> More `total_resource` means success.

Do interpret it as:

> Benefit must be read as a multi-indicator bundle with hidden-cost audit.

## 6. H11 Possibility-Distribution Window

Japanese fixed name:

`H11可能性分布観測窓口`

### 6.1 Purpose

This window reads whether the system still has meaningful future routes.

It asks:

> Does the system preserve or widen future reachable good states without turning expansion into noise, divergence, or collapse?

### 6.2 Inputs

H11 indicators:

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

Core possibility indicators:

- 探索性;
- 構造的多様性;
- 回復可能性;
- 適応・再編性;
- 新規性の質;
- 整合性;
- 軌道動態.

Audit indicators:

- 安定性;
- 頑健性;
- 効率性;
- 予測可能性;
- 整合性.

### 6.3 Good reading pattern

A good reading pattern is:

- exploration remains meaningful;
- structural diversity remains available;
- recovery routes remain available;
- novelty is not merely noise;
- coherence is not broken;
- expansion does not destroy stability, robustness, efficiency, or predictability.

### 6.4 Warning pattern

A warning pattern is:

- exploration rises but becomes noise;
- stability rises because the system entered shrinking equilibrium;
- predictability rises because collapse became predictable;
- structural diversity falls while apparent benefit rises;
- novelty rises without quality;
- recovery routes close while short-term benefit improves.

### 6.5 Prohibited interpretation

Do not interpret this window as:

> One H11 axis improved, therefore possibility distribution improved.

Do interpret it as:

> Possibility distribution must be read as a pattern across H11 directions and audit indicators.

## 7. Pressure-Action Alignment Window

Japanese fixed name:

`圧-作用整合観測窓口`

### 7.1 Purpose

This window reads whether the ActionModule remains a pressure-based translator rather than an independent optimizer.

It asks:

> Did the selected action follow the upper-pressure direction, strength, and H11 intent without becoming metric maximization?

### 7.2 Inputs

Pressure-side indicators:

- upper-pressure direction;
- upper-pressure intensity;
- H11 direction carried by pressure;
- possibility-distribution intent;
- risk-band context.

Action-side indicators:

- selected action channel;
- action strength;
- `action_mass`;
- `action_mass_by_channel`;
- action cost;
- over-action risk;
- under-action risk;
- suppression when pressure is absent.

Alignment links:

- pressure direction to action-channel correspondence;
- pressure strength to action strength correspondence;
- pressure context to dynamic threshold behavior;
- pressure absence to no-action / weak-action behavior.

### 7.3 Good reading pattern

A good reading pattern is:

- action channel matches pressure direction;
- action strength is proportionate to pressure and risk band;
- action is reduced when pressure is absent;
- action does not chase local metric gain independently;
- action cost remains acceptable;
- action supports benefit and possibility distribution together.

### 7.4 Warning pattern

A warning pattern is:

- action increases without pressure;
- one channel dominates regardless of H11 direction;
- action mass rises but benefit and possibility distribution do not improve;
- action appears successful only because one metric improved;
- pressure is ignored in favor of local optimization.

### 7.5 Prohibited interpretation

Do not interpret this window as:

> More action means better action.

Do interpret it as:

> Action is good only if it remains pressure-aligned, bounded, and beneficial across windows.

## 8. Risk-Band Window

Japanese fixed name:

`リスク帯観測窓口`

### 8.1 Purpose

This window reads which representative v2 risk band the system currently resembles.

It asks:

> Is the current state stable, medium-risk, high-risk, or extreme-risk, and what kind of action posture does that imply later?

### 8.2 Inputs

Primary indicators:

- `information_asymmetry`;
- `action_cost`;
- relation lock / relation rigidity;
- `hidden_damage`;
- `fatigue`;
- `defensiveness`;
- `latent_pressure`;
- `cooperation_intent`;
- `information_quality`;
- recovery capacity;
- H11 possibility-distribution narrowing;
- shrinking-equilibrium risk.

### 8.3 Representative bands

Stable band / 安定帯:

- low information asymmetry;
- low hidden damage;
- low fatigue;
- low latent pressure;
- cooperation usable;
- possibility distribution not closed.

Medium-risk band / 中リスク帯:

- information asymmetry and action cost rising;
- early hidden damage;
- early fatigue;
- relation lock emerging;
- recovery routes still available.

High-risk band / 高リスク帯:

- high hidden damage;
- high fatigue;
- high latent pressure;
- high defensiveness;
- shrinking-equilibrium risk;
- possibility distribution narrowing.

Extreme-risk band / 極端リスク帯:

- extreme hidden damage or fatigue;
- severe relation lock;
- severe recovery delay;
- high collapse risk;
- only residual viable routes may remain.

### 8.4 Good reading pattern

A good reading pattern is:

- the risk band is identified without relying on one metric;
- hidden risk is not missed by public stability;
- fatigue affects later action posture;
- information quality affects confidence;
- possibility distribution affects threshold sensitivity.

### 8.5 Warning pattern

A warning pattern is:

- stable-looking public metrics hide high latent pressure;
- risk band remains stable while hidden damage rises;
- information quality is too low for confident classification;
- extreme-risk state is mistaken for high-risk recoverability.

### 8.6 Prohibited interpretation

Do not interpret this window as:

> Risk band is a fixed label.

Do interpret it as:

> Risk band is a dynamic reading that should influence later threshold and action-mode design.

## 9. Growth Window

Japanese fixed name:

`成長観測窓口`

### 9.1 Purpose

This window reads growth as a composite observation surface, not as resource increase.

It asks:

> Is the system visibly improving, doing so sustainably, and preserving future growth routes?

### 9.2 Inputs

Growth components fixed in Phase 2G-15A:

- `realized_growth` / 実現成長;
- `sustainable_growth` / 持続可能な成長;
- `growth_capacity` / 成長余力.

Visible realized improvement:

- `total_resource` trend;
- `private_resource` trend;
- `cooperation_intent` trend;
- `information_quality` trend;
- short-term benefit trend.

Sustainability audit:

- `hidden_damage` trend;
- `fatigue` trend;
- `defensiveness` trend;
- `latent_pressure` trend;
- resource concentration risk;
- action cost burden;
- long-term stability trend.

Future route capacity:

- H11 exploration;
- H11 structural diversity;
- H11 recoverability;
- H11 adaptability/reorganization;
- H11 novelty quality;
- H11 coherence;
- H11 trajectory dynamics;
- stability, robustness, efficiency, and predictability audits.

### 9.3 Good reading pattern

A good reading pattern is:

- visible improvement exists or growth capacity is preserved;
- hidden damage does not rise excessively;
- fatigue does not rise excessively;
- latent pressure does not accumulate excessively;
- possibility distribution remains open;
- growth does not consume future routes.

### 9.4 Warning pattern

A warning pattern is:

- visible resources rise while future routes close;
- growth looks positive but hidden damage rises;
- short-term growth is bought with fatigue;
- growth proxy improves but pressure-action alignment is ignored;
- the system shows false growth, extractive growth, or fragile growth.

### 9.5 Prohibited interpretation

Do not interpret this window as:

> Growth proxy improved, therefore the system succeeded.

Do interpret it as:

> Growth must be read as realized improvement plus sustainability audit plus future-route capacity.

## 10. Composite Balance Window

Japanese fixed name:

`総合バランス観測窓口`

### 10.1 Purpose

This window reads the balance among all other windows.

It asks:

> Did the system preserve or improve benefit, possibility distribution, pressure-action alignment, risk condition, growth quality, and future routes without hidden cost explosion?

### 10.2 Inputs

Inputs are aggregated from the other windows:

- System Benefit Window;
- H11 Possibility-Distribution Window;
- Pressure-Action Alignment Window;
- Risk-Band Window;
- Growth Window.

Key cross-window checks:

- benefit versus possibility distribution;
- visible benefit versus hidden damage;
- growth versus fatigue;
- stability versus shrinking equilibrium;
- predictability versus predictable collapse;
- action mass versus action usefulness;
- pressure alignment versus metric optimization;
- risk band versus action cost;
- short-term benefit versus long-term route preservation.

### 10.3 Good reading pattern

A good reading pattern is:

- benefit improves or remains acceptable;
- possibility distribution remains open;
- action remains pressure-aligned;
- risk band does not worsen unexpectedly;
- growth is sustainable or growth capacity is preserved;
- hidden damage, fatigue, defensiveness, and latent pressure remain controlled.

### 10.4 Warning pattern

A warning pattern is:

- one window improves while another collapses;
- benefit improves but possibility distribution closes;
- growth improves but hidden damage rises;
- action aligns with a metric but not with pressure;
- risk band worsens while short-term benefit improves;
- the system moves toward shrinking equilibrium while appearing stable.

### 10.5 Prohibited interpretation

Do not interpret this window as:

> Add all window scores into one flat scalar and maximize it.

Do interpret it as:

> Composite balance is a structured trade-off reading, not a flat objective.

## 11. Window Status Labels

Phase 2G-16 does not implement numeric window scores.

However, later validation may use qualitative or derived labels.

Allowed status labels:

- `healthy` / 健全;
- `watch` / 注意;
- `warning` / 警戒;
- `critical` / 危険;
- `unresolved` / 未解決.

Rules:

- `healthy` does not mean perfect;
- `watch` means monitor trade-offs;
- `warning` means risk is visible;
- `critical` means a serious failure mode may be active;
- `unresolved` means evidence is insufficient or conflicting.

These labels are optional design aids and must not be treated as final implementation requirements.

## 12. Window Interaction Rules

### 12.1 No single-window success

No single window can prove success.

For example:

- benefit success without possibility preservation is insufficient;
- possibility widening without benefit balance is insufficient;
- growth without sustainability audit is insufficient;
- action without pressure alignment is insufficient;
- risk reduction through over-fixation is insufficient.

### 12.2 No flat aggregation by default

The windows should not be collapsed into a flat weighted sum by default.

Flat aggregation may hide failures.

For example:

- high growth can hide high fatigue;
- high stability can hide shrinking equilibrium;
- high predictability can hide predictable collapse;
- high action diversity can hide noisy action.

### 12.3 Preserve contradiction

If windows disagree, the disagreement should be preserved.

Example:

- System Benefit Window improves;
- H11 Possibility-Distribution Window worsens;
- Composite Balance Window should flag the conflict, not erase it.

### 12.4 Window readings are evidence, not command

Observation windows should support later ActionModule tuning, but should not command action directly.

The later ActionModule must still operate from upper pressure and pressure-action alignment.

## 13. ActionModule Visibility Rule

For future implementation, the ActionModule may use observation windows only as bounded contextual information.

It must not:

- read windows as direct objectives;
- maximize window scores independently;
- act without pressure because a window is low;
- ignore pressure because a window suggests local gain;
- use growth proxy as a target;
- use risk band as an unconditional action trigger without pressure context.

Allowed future use:

- adjust action strength within pressure direction;
- adjust dynamic threshold within pressure direction;
- suppress action when fatigue or action cost is excessive;
- choose safer translation when hidden damage or latent pressure is high;
- preserve unresolved/conflicting readings rather than forcing one decision.

## 14. Phase 2G-17 Entry Conditions

Phase 2G-17 should not start implementation until the following are explicitly decided:

1. Which windows are exported first;
2. Whether window outputs are qualitative labels, numeric derived proxies, or both;
3. Which existing trace fields support each window;
4. Whether new derived metrics are needed;
5. Whether CSV/export changes are required;
6. Whether runner summary changes are required;
7. Whether ActionModule may consume window outputs;
8. Whether dynamic thresholds are in scope;
9. Which risk bands are included in the first validation;
10. Whether Codex is required.

Recommended next step:

`Phase 2G-17: Observation Window Export / Probe Design`

Japanese fixed name:

`観測窓口 export / probe 設計`

## 15. Boundaries

This document is a design freeze for observation-window grouping.

It is not:

- a scoring implementation;
- a validation result;
- an ActionModule tuning result;
- a new objective function;
- a proof of superiority;
- a safety proof;
- a deployment claim.

## 16. Conclusion

Phase 2G-16 fixes how the v2 indicators should be grouped into observation windows.

The fixed view is:

- indicators are read through windows;
- windows are structured observation surfaces;
- windows are not objectives;
- no single window proves success;
- disagreements between windows must be preserved;
- the ActionModule must remain pressure-based;
- future implementation should start from export/probe design, not direct tuning.

This document should be read together with:

- `PHASE2G15_V2_RISK_BAND_BENEFIT_POSSIBILITY_METRIC_FIXATION.md`;
- `PHASE2G15A_V2_GROWTH_COMPOSITE_OBSERVATION_WINDOW.md`;
- `PHASE2G15B_INDICATOR_STATUS_AND_INTERPRETATION_RULE.md`;
- `PHASE2G14_RC_FREEZE_HANDOFF_PACK.md`.
