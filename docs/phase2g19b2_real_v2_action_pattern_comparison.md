# Phase 2G-19B-2: Real v2 Action Impact + Action-Pattern Comparison

## Purpose and scope

Phase 2G-19B-2 is a validation-only comparison of real PseudoReality v2 action impact and fixed action patterns. It goes beyond the Phase 2G-19B-1R connection probe by reading how intended actions affect the real v2 runner, measuring side effects, and comparing `no_op`, `current_action_module`, `continuous_weak`, `threshold_insurance`, and `hybrid` in one B-2 task. This is not split into a separate result-audit task.

The validation does **not** adjust ActionPlanner runtime, ActionModule runtime, primitive definitions, gains, multipliers, v2 dynamics, PressureTranslation, ParameterBox, ShadowBox, or canonical write paths. It also does **not** feed v2 trace outputs or six observation-window outputs back into ActionPlanner or ActionModule runtime inputs.

## Difference from 19B-1R

Phase 2G-19B-1R proved that validation-only `ActionFrame` probes can be applied to `AsymmetricGamePseudoRealitySystem.step(action_frame)` and read from `v2_action_effect_trace`. Phase 2G-19B-2 keeps that real-v2 connection but adds:

- channel-level action impact aggregation,
- side-effect and cost aggregation,
- short-horizon evaluation rather than a single connection check,
- no-op baseline deltas,
- comparison of five fixed patterns across four state bands,
- adjustment hypotheses for the later Phase 2G-20 tuning specification.

## Real v2 runner and traces used

- Runner: `pseudo_reality.asymmetric_game_v2.AsymmetricGamePseudoRealitySystem`.
- Action application: `AsymmetricGamePseudoRealitySystem.step(action_frame)`.
- Primary trace: `v2_action_effect_trace`.
- Context traces read externally for benefit, growth, and risk proxies: `v2_resource_trace`, `v2_game_trace`, `v2_hidden_trace`, and `v2_information_trace`.

These traces are read after each step for external validation only.

## State bands, seeds, and horizon

State bands:

- `stable`: low fatigue, low hidden damage, low latent pressure, low inequality, sufficient resources.
- `medium`: moderate pressure, uncertainty, and local burden.
- `high`: high fatigue, hidden damage, resource pressure, blockage, and inequality.
- `limit`: near-limit fatigue, hidden damage, latent pressure, low resources, and low reversibility.

The test uses two deterministic seeds, `1922` and `1923`, and a minimum horizon of `3` steps for every pattern/state-band pair. Pattern rules are fixed before each horizon; no closed-loop policy changes are made from v2 trace observations.

## Action patterns

| Pattern | Definition used in B-2 |
|---|---|
| `no_op` | All bands receive `action_channel=no_op` with zero action strength. |
| `current_action_module` | A validation-local final-gate row is passed through the existing production `ActionModule.build_action_frame(...)`; if empty, the row is recorded as no-op/unresolved rather than silently skipped. |
| `continuous_weak` | Low-strength action (`0.06`) is applied across all bands, rotating buffer/probe/relief/damping and allowing light exploration in stable/medium. |
| `threshold_insurance` | Stable/medium are no-op or very light probe; high uses `0.12` and limit uses `0.16` buffer/damping/relief insurance actions. |
| `hybrid` | Stable uses very weak probe, medium uses continuous weak support, and high/limit use threshold-like insurance actions. |

## Action surface effect fields

For every horizon, B-2 aggregates the following from `v2_action_effect_trace`:

- `cumulative_exploration_delta`
- `cumulative_reversibility_delta`
- `cumulative_net_public_effect_score`
- `cumulative_net_hidden_effect_score`
- `cumulative_hidden_damage_delta`
- `cumulative_fatigue_delta`
- `cumulative_resource_inequality_delta`
- `cumulative_action_cost_effect`

It also records step-level trace summaries, final-state context, cumulative cost, cumulative hidden burden, no-op deltas, and DataFrame/CSV exportability.

## Channel impact summary

Average three-step channel effects across state bands with seed `2922`:

| action_channel | exploration | reversibility | public effect | hidden effect | hidden damage | fatigue | inequality | cost | Observation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `no_op` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | Baseline natural drift without action mass. |
| `buffer_increase` | 0.0000 | 0.0162 | 0.0162 | 0.0076 | 0.0000 | 0.0040 | 0.0000 | 0.0040 | It raised reversibility and public effect, while adding measurable fatigue/hidden-effect burden and action cost. |
| `coupling_relief` | 0.0000 | 0.0000 | 0.0000 | 0.0076 | 0.0000 | 0.0040 | 0.0000 | 0.0040 | It did not worsen measured inequality in this setup, but its public/reversibility contribution was weak and hidden/cost burden remained visible. |
| `volatility_damping` | 0.0000 | 0.0000 | 0.0000 | 0.0052 | 0.0000 | 0.0016 | 0.0000 | 0.0040 | It produced the lightest fatigue-side burden among non-no-op channels, but also had weak direct public opening and can dull growth/exploration if overused. |
| `uncertainty_probe` | 0.0000 | 0.0000 | 0.0000 | 0.0076 | 0.0000 | 0.0040 | 0.0000 | 0.0040 | It behaved as a low-intensity probe with small but nonzero burden; the direct effect was thin. |
| `exploration_injection` | 0.0162 | 0.0000 | 0.0162 | 0.0128 | 0.0000 | 0.0089 | 0.0000 | 0.0040 | It increased exploration and public effect, but had the heaviest fatigue/hidden-effect side burden, making high/limit use risky. |
| `relation_unlock` | 0.0000 | 0.0000 | 0.0000 | 0.0076 | 0.0000 | 0.0040 | 0.0000 | 0.0040 | It points toward lock loosening but produced weak direct reversibility/public trace signal and nonzero defensiveness/fatigue cost. |

## Pattern comparison table

Average results across two seeds and four state bands:

| pattern | balance | h11 proxy | side-effect burden | risk burden | cost burden | benefit proxy | growth proxy | no-op rate | action mass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `no_op` | 0.2921 | 0.0000 | 0.0000 | 0.3702 | 0.0000 | 0.5152 | 0.1471 | 1.0000 | 0.0000 |
| `current_action_module` | 0.2859 | -0.0005 | 0.0045 | 0.3702 | 0.0018 | 0.5152 | 0.1477 | 0.0000 | 0.1606 |
| `continuous_weak` | 0.2845 | -0.0002 | 0.0067 | 0.3702 | 0.0020 | 0.5152 | 0.1484 | 0.0000 | 0.1800 |
| `threshold_insurance` | 0.2833 | -0.0006 | 0.0066 | 0.3702 | 0.0026 | 0.5152 | 0.1481 | 0.0000 | 0.2325 |
| `hybrid` | 0.2819 | -0.0006 | 0.0077 | 0.3702 | 0.0030 | 0.5152 | 0.1483 | 0.0000 | 0.2662 |

The composite `pattern_balance_score` is retained only as a helper. The table keeps risk burden, side-effect burden, and action-cost burden as separate columns so benefit/growth cannot hide hidden burden.

## Pattern-by-pattern observations

### no_op

`no_op` was sufficient as a stable comparison baseline because it had zero action cost and zero action-effect side burden. However, high/limit states still carried high final risk burden from the initialized v2 state and natural dynamics, so no-op is not a credible high/limit intervention hypothesis.

### current_action_module

The validation attempted the existing production `ActionModule.build_action_frame(...)` through a validation-local final-gate helper. It produced non-no-op rows in this comparison and leaned by band toward probe/buffer/damping/relief rather than exploration injection. Its average action mass was lower than the explicit insurance/hybrid patterns, and side-effect burden was lower than continuous/hybrid. The main weakness is not excessive cost here, but that the observed public/H11 lift is thin relative to no-op.

### continuous_weak

`continuous_weak` did not strongly damage stable behavior in this run, and it provided the highest average growth proxy among the non-no-op patterns. Its drawback is accumulated side-effect burden: because it acts every step, the cost and hidden-effect burden remain visible even when stable/medium states might not need support. High/limit use should avoid continuous exploration unless explicitly justified.

### threshold_insurance

`threshold_insurance` kept stable/medium cost low relative to high/limit and fired stronger buffer/damping/relief actions in high/limit. The medium band showed a `delayed_response` status in the tests because light probe/no-op behavior produced little reversibility delta versus no-op. This pattern is useful for high/limit defense but may need earlier medium support in Phase 2G-20.

### hybrid

`hybrid` combined weak continuous support with threshold-like high/limit insurance. It preserved the intended structure, but it also had the highest average action mass, side-effect burden, and cost among the compared patterns. It is a promising rule family only if Phase 2G-20 caps stable actions and avoids stacking continuous weak burden with threshold burden.

## Side-effect summary

- `exploration_injection` was the clearest growth/opening channel but also the heaviest fatigue/hidden-burden channel.
- `buffer_increase` gave the clearest reversibility lift with moderate action-cost/fatigue burden.
- `volatility_damping` had comparatively low fatigue burden, but weak direct opening; it can become over-suppressive if treated as a blanket action.
- `uncertainty_probe`, `coupling_relief`, and `relation_unlock` had low visible public deltas in this runner configuration, so they should not be assumed effective merely because they are connected.
- `hybrid` and `threshold_insurance` have higher action mass than `current_action_module`; this must remain visible rather than hidden by the composite balance score.

## Which patterns are promising, risky, or weak

- Most promising for Phase 2G-20: a constrained hybrid/insurance rule that uses very weak stable probe, low medium buffer/probe support, and high/limit buffer/damping/relief.
- Riskiest channel: `exploration_injection` in high/limit because it raises exploration but also fatigue/hidden-effect burden.
- Weakest direct-effect channels in the observed action trace: `coupling_relief`, `uncertainty_probe`, and `relation_unlock`, which need clearer trigger rules or lower expectations.
- Weakest pattern aspect: threshold insurance in `medium`, where response can be delayed.

## No-op baseline deltas

The comparison table includes `delta_vs_no_op_*` columns for every core `v2_action_effect_trace` cumulative field. This keeps the natural/no-action baseline available for all patterns and prevents B-2 from becoming a raw connection-only check.

## Adjustment hypotheses for Phase 2G-20

- Current module weakness: current output can remain too low-impact in real v2 action-effect terms; it should not be judged only by successful action-frame construction.
- Channels to weaken: high/limit `exploration_injection`; stable blanket action; stacked hybrid action mass when no risk threshold is crossed.
- Channels to strengthen conditionally: `buffer_increase` for reversibility, `volatility_damping` for high/limit fatigue damping, and `coupling_relief` only when coupled pressure is clearly high.
- Stable suppression rule: prefer no-op or very weak `uncertainty_probe`; avoid routine buffer/damping/exploration unless a separate signal warrants it.
- High/limit prohibition or weakening: prohibit or sharply weaken `exploration_injection` and relation unlock when hidden burden/fatigue is already near limit.
- Hybrid candidate rule: stable = no-op/very weak probe; medium = weak buffer/probe/relief; high/limit = threshold buffer/damping/relief; cap total action mass to prevent over-action.
- Phase 2G-20 target: specify ActionModule/ActionPlanner adjustment candidates from these real-v2 observations, without using B-2 validation traces as runtime inputs.

## Runtime boundary confirmation

B-2 changes are limited to the validation test and this documentation. Production ActionPlanner, ActionModule, primitive library, gains/multipliers, v2 dynamics, PressureTranslation, ParameterBox/ShadowBox, and canonical write paths are not changed. The v2 traces and six observation-window outputs remain external validation observations and are not returned to action runtime inputs.
