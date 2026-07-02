# Phase 2G-15A v2 Growth Composite Observation Window

## 1. Scope

Phase 2G-15A supplements Phase 2G-15 by adding growth as a composite system-benefit observation window.

Japanese fixed name:

`v2 成長の複合観測窓口`

This is a **docs-only addendum** to Phase 2G-15.

This addendum does not:

- tune the ActionModule;
- change runtime code;
- change runner behavior;
- change matrix files;
- change world dynamics;
- change action effect formulas;
- add new cause-side axes;
- add production scoring;
- claim real-world growth measurement;
- treat growth as a single objective.

## 2. Motivation

Phase 2G-15 fixed system benefit as a multi-indicator bundle, but the explicit macro-benefit concept of growth was not yet separated.

In real systems, growth is often a major macro-level benefit.

However, growth is dangerous if it is treated as a single indicator, because apparent growth can hide:

- hidden damage;
- fatigue;
- defensiveness;
- latent pressure;
- resource concentration;
- shrinking possibility distribution;
- long-term collapse risk.

Therefore, growth should not be treated as:

> `total_resource` increased, therefore the system grew well.

Instead, growth should be treated as a composite observation window that reads several indicators together.

## 3. Fixed Thesis

Growth is not a single metric.

Growth is a composite observation window over benefit indicators and H11-aligned possibility-distribution indicators.

Japanese thesis:

> 成長とは、単なる資源増加ではない。成長とは、資源・協調・情報品質・回復余力・可能性分布が、隠れ損傷・疲弊・防衛反応・潜在圧を増やしすぎずに、時間方向に改善している状態である。

This addendum fixes three growth-related observation windows:

1. `realized_growth` — 実現成長;
2. `sustainable_growth` — 持続可能な成長;
3. `growth_capacity` — 成長余力.

These are v2 proxy windows, not real-world growth proof.

## 4. `realized_growth` — 実現成長

Japanese fixed meaning:

`実現成長`

Meaning:

> The system is actually improving over time in visible and measurable benefit indicators.

Observed through:

- increase in `total_resource`;
- improvement in `private_resource`;
- improvement in `cooperation_intent`;
- improvement in `information_quality`;
- improved or maintained long-term stability;
- non-deteriorating recovery condition.

Interpretation:

`realized_growth` indicates whether the system has already moved in a beneficial direction.

However, it is not enough by itself.

Failure risk:

- `total_resource` rises while `hidden_damage` rises;
- cooperation improves briefly while fatigue rises;
- information improves while action cost becomes excessive;
- short-term visible growth masks future collapse.

Fixed rule:

> `realized_growth` may indicate visible improvement, but it must be audited by sustainable-growth and growth-capacity windows.

## 5. `sustainable_growth` — 持続可能な成長

Japanese fixed meaning:

`持続可能な成長`

Meaning:

> The system improves without consuming its own future viability.

Observed through:

- positive or stable `realized_growth`;
- low or controlled `hidden_damage`;
- low or controlled `fatigue`;
- low or controlled `defensiveness`;
- low or controlled `latent_pressure`;
- no excessive resource concentration;
- possibility distribution not closing;
- long-term stability not worsening.

Interpretation:

`sustainable_growth` is the main growth-quality indicator.

It distinguishes:

- healthy growth;
- forced growth;
- extractive growth;
- short-term growth that borrows from future stability.

Fixed rule:

> Growth that increases hidden damage, fatigue, defensiveness, or latent pressure too much is not healthy growth, even if visible resources rise.

## 6. `growth_capacity` — 成長余力

Japanese fixed meaning:

`成長余力`

Meaning:

> The system still has routes through which future growth can occur, even if immediate visible growth is small.

Observed through:

- preserved or improved `recovery_after_shock`;
- preserved `long_term_stability`;
- preserved or improved `information_quality`;
- preserved `cooperation_intent`;
- H11-aligned possibility distribution remains open;
- exploration routes remain meaningful;
- structural diversity remains available;
- recovery routes remain available;
- novelty quality remains non-noisy;
- fatigue and latent pressure do not close future paths.

Interpretation:

`growth_capacity` is especially important for DEPT/H-DEPT because the system may accept short-term cost in order to preserve future viable routes.

Fixed rule:

> Growth capacity matters even when immediate growth is small, because DEPT/H-DEPT aims to preserve future reachable good states rather than only current visible gain.

## 7. Growth and H11 Possibility Distribution

Growth is not independent from H11.

Growth depends on the following H11 directions:

| H11 direction | Growth role |
| --- | --- |
| 適応・再編性 | Allows the system to reorganize toward better states. |
| 探索性 | Keeps unknown or underused growth routes open. |
| 構造的多様性 | Keeps multiple growth paths available. |
| 回復可能性 | Allows growth after shock or damage. |
| 新規性の質 | Distinguishes meaningful new routes from noise. |
| 整合性 | Prevents growth from becoming internally contradictory. |
| 効率性 | Prevents growth from requiring unsustainable action cost. |
| 頑健性 | Prevents growth from collapsing under disturbance. |
| 安定性 | Prevents growth from becoming destructive instability. |
| 軌道動態 | Reads whether growth is improving, stalling, reversing, or oscillating. |
| 予測可能性 | Checks whether growth trajectory is readable enough for safe action. |

Fixed rule:

> Growth should be read as a composite of realized benefit improvement and H11-aligned future-route preservation.

## 8. Growth Composite Observation Window

The growth observation window combines three layers.

### Layer 1: visible realized improvement

Reads:

- `total_resource` trend;
- `private_resource` trend;
- `cooperation_intent` trend;
- `information_quality` trend;
- short-term benefit trend.

This layer asks:

> Is the system visibly improving?

### Layer 2: sustainability audit

Reads:

- `hidden_damage` trend;
- `fatigue` trend;
- `defensiveness` trend;
- `latent_pressure` trend;
- resource concentration risk;
- action cost burden;
- long-term stability trend.

This layer asks:

> Is the visible improvement damaging the future system?

### Layer 3: future route capacity

Reads H11-aligned possibility distribution:

- 探索性;
- 構造的多様性;
- 回復可能性;
- 適応・再編性;
- 新規性の質;
- 整合性;
- 軌道動態;
- plus stability, robustness, efficiency, and predictability audits.

This layer asks:

> Does the system still have meaningful future growth routes?

## 9. Growth Pattern Classification

### 9.1 Healthy growth

Japanese fixed name:

`健全な成長`

Pattern:

- realized growth is positive;
- hidden damage does not rise excessively;
- fatigue does not rise excessively;
- defensiveness does not rise excessively;
- latent pressure does not accumulate excessively;
- possibility distribution remains open;
- growth capacity remains positive.

Interpretation:

> The system is improving without closing its future.

### 9.2 Extractive growth

Japanese fixed name:

`収奪的成長`

Pattern:

- visible resources rise;
- short-term benefit rises;
- hidden damage rises;
- fatigue rises;
- latent pressure rises;
- possibility distribution narrows;
- future routes are consumed.

Interpretation:

> The system appears to grow by borrowing from future viability.

### 9.3 Fragile growth

Japanese fixed name:

`脆い成長`

Pattern:

- realized growth exists;
- stability or predictability is weak;
- recovery routes are insufficient;
- small shock can reverse gains;
- possibility distribution is not resilient.

Interpretation:

> Growth exists but cannot survive disturbance.

### 9.4 Latent-growth capacity

Japanese fixed name:

`潜在成長余力`

Pattern:

- immediate visible growth is small;
- recovery routes remain;
- exploration routes remain;
- structural diversity remains;
- cooperation and information quality remain usable;
- hidden damage and fatigue remain controlled.

Interpretation:

> The system is not yet visibly growing, but future growth paths remain alive.

### 9.5 False growth

Japanese fixed name:

`見かけの成長`

Pattern:

- one visible metric improves;
- other benefit indicators deteriorate;
- H11 possibility distribution closes;
- long-term stability worsens;
- pressure-action alignment may be ignored.

Interpretation:

> A single metric improved, but the system did not genuinely improve.

## 10. Risk-Band Growth Expectations

| Risk band | Growth expectation | Interpretation |
| --- | --- | --- |
| 安定帯 | Large growth is not required. Growth capacity should be preserved with low insurance cost. | Do not over-act to force growth in a stable system. |
| 中リスク帯 | Short-term realized growth may be weak, but sustainable growth and growth capacity should improve. | Accept short-term cost if future growth routes are protected. |
| 高リスク帯 | Avoid shrinking equilibrium and recover growth capacity. Realized growth should improve if possible. | DEPT/H-DEPT value should appear most clearly here. |
| 極端リスク帯 | Full growth is not expected. Residual growth capacity, collapse delay, and loss reduction matter. | Tests limit behavior rather than normal success. |

## 11. Growth and Pressure-Action Alignment

The ActionModule must not optimize for growth independently of pressure.

Forbidden:

> This channel increases growth metrics locally, so use it regardless of upper pressure.

Allowed:

> This upper pressure tries to open an H11 direction related to growth capacity, so choose a suitable action channel that preserves benefit balance and future routes.

Pressure-action growth alignment should check:

- whether pressure direction corresponds to the growth window being affected;
- whether action channel selection follows the H11 direction;
- whether growth improvement comes from pressure-aligned action rather than independent optimization;
- whether action cost is acceptable for the risk band;
- whether visible growth does not close possibility distribution;
- whether growth capacity improves without hidden damage accumulation.

## 12. Indicators Not Allowed as Standalone Growth Criteria

The following must not be used alone as growth criteria:

- only `total_resource` increase;
- only short-term gain;
- only `private_resource` increase;
- only `cooperation_intent` increase;
- only `information_quality` increase;
- only low `hidden_damage`;
- only action mass;
- only action diversity;
- only stability;
- only flat-comparator win/loss.

Reason:

Each can be improved while real system growth is false, fragile, extractive, or future-damaging.

## 13. Phase 2G-16 Implication

Phase 2G-16 should treat growth as a composite observation window.

Before tuning, Phase 2G-16 should decide whether to include growth windows in the evaluation table:

- `realized_growth_proxy`;
- `sustainable_growth_proxy`;
- `growth_capacity_proxy`.

These should be clearly labelled as proxy or derived-proxy unless exact implementation is added later.

Phase 2G-16 must not:

- tune directly for `total_resource` growth only;
- tune directly for short-term growth only;
- tune the ActionModule independently of pressure;
- claim real-world growth evidence;
- treat v2 growth proxies as full economic/social growth measures.

## 14. Conclusion

Growth should be added to Phase 2G-15 as a composite system-benefit observation window.

The fixed view is:

- growth is not a single metric;
- growth is not equal to `total_resource` increase;
- growth has realized, sustainable, and capacity components;
- growth must be audited by hidden damage, fatigue, defensiveness, latent pressure, and possibility distribution;
- growth must remain pressure-aligned;
- v2 can represent growth only as proxy or derived-proxy unless later implementation adds exact semantics.

This addendum should be read together with:

- `PHASE2G15_V2_RISK_BAND_BENEFIT_POSSIBILITY_METRIC_FIXATION.md`;
- `PHASE2G14_RC_FREEZE_HANDOFF_PACK.md`.
