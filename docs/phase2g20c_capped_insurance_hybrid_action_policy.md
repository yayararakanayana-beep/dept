# Phase 2G-20C: Capped Insurance-Hybrid Action Policy

## Purpose and scope

Phase 2G-20C freezes the action-policy specification that follows from the real-v2 observations in Phase 2G-19B-1R, Phase 2G-19B-2, and the tiered exploration handoff in Phase 2G-20A/B.

This is a specification phase, not a production runtime rewrite. It defines how later action policy work should decide:

- which state bands should trigger action,
- which channels are allowed in each band,
- how much action mass is permitted,
- when exploration candidates may be tried,
- when action must stop or cool down,
- which module owns the final execution decision,
- which runtime boundaries must not be crossed.

Phase 2G-20C does not change production ActionModule, ActionPlanner, pseudo-reality v2 dynamics, PressureTranslation, ParameterBox, ShadowBox, G/K/O_t construction, canonical write paths, or the exploration bridge implementation. It creates a research contract for Phase 2G-20D, where this capped insurance-hybrid policy can be compared on real v2.

## Research interpretation

The policy is not a force-control policy. It is an insurance-style governance policy.

The default assumption is:

- action has nonzero side-effect cost,
- stable states should not pay unnecessary action cost,
- riskier states may justify action when the expected cost of no action is larger than the expected side-effect burden,
- exploration is an investment, not a default control signal,
- exploration starts very small and stops quickly when side effects appear.

This keeps the DEPT/H-DEPT interpretation centered on viability maintenance rather than direct optimization.

## Evidence base from prior phases

Phase 2G-19B-2 found the following pattern-level implications:

- `no_op` is strong in stable states because it has zero action mass and zero action-effect side burden.
- `buffer_increase` is the clearest insurance channel for reversibility/public-effect support, but it carries cost and fatigue burden.
- `volatility_damping` has comparatively light fatigue burden, but weak direct opening effect.
- `coupling_relief` is useful only conditionally; it should not be assumed to produce strong direct improvement.
- `uncertainty_probe` is a light probe, not a strong improvement channel.
- `exploration_injection` increases exploration/public effect but carries the heaviest hidden/fatigue burden among observed channels.
- `relation_unlock` remains theoretically interesting, but real-v2 direct signal was weak and it carries nonzero burden.
- `hybrid` has a good structural shape, but uncapped hybrid action accumulates high action mass and side-effect burden.

Therefore Phase 2G-20C freezes a capped insurance-hybrid policy rather than a continuous-control policy.

## State-band policy

### stable

Stable state means low fatigue, low hidden damage, low latent pressure, low inequality, and sufficient recovery resource.

Default action:

- `no_op`

Allowed only as an optional very weak secondary check:

- `uncertainty_probe`

Default-forbidden:

- `buffer_increase`
- `volatility_damping`
- `coupling_relief`
- `exploration_injection`
- `relation_unlock`

Stable-state purpose:

- avoid paying unnecessary side-effect cost,
- avoid damaging a working equilibrium,
- keep observation open without treating stability as a reason to act.

Action-mass cap:

- `total_action_mass <= 0.03`

### medium

Medium state means risk, unresolved pressure, residual burden, reversibility decline, or local coupling pressure has become visible but the system is not yet in high/limit defense mode.

Default allowed actions:

- weak `buffer_increase`
- weak `uncertainty_probe`
- conditional weak `coupling_relief`

Allowed exploration:

- only from Phase 2G-20A/B `exploration_projection`,
- only when the candidate is `strong_candidate`, `weak_candidate`, or `probe_only`,
- only when `candidate_use_permission` is `action_allowed` or `probe_only`,
- only when `execution_decision_owner == action_module`,
- only when not in cooldown,
- only within `side_effect_budget`,
- only at or below `max_start_strength`,
- only as a very weak start.

Medium-state purpose:

- reduce delayed response from pure threshold insurance,
- provide weak support without accumulating continuous-control burden,
- test safe exploration candidates only at small strength.

Action-mass cap:

- `total_action_mass <= 0.08`

### high

High state means fatigue, hidden burden, resource pressure, relation lock, coupling, or risk has become severe enough that collapse-prevention takes priority over opening/exploration.

Default allowed actions:

- `buffer_increase`
- `volatility_damping`
- conditional `coupling_relief`

Default-forbidden:

- `exploration_injection`
- `relation_unlock`
- continuous weak exploration
- stacked multi-channel hybrid bursts

High-state purpose:

- protect reversibility,
- damp volatility/fatigue pressure,
- relieve coupled pressure only when the coupling signal is clear,
- avoid paying exploration burden when the system is already vulnerable.

Action-mass cap:

- `total_action_mass <= 0.14`

### limit

Limit state means the system is near collapse, near irreversible burden, or too constrained to safely explore.

Default allowed actions:

- `volatility_damping`
- `buffer_increase`

Default-forbidden:

- `exploration_injection`
- `relation_unlock`
- `uncertainty_probe` as a routine action
- `coupling_relief` as a default action
- continuous or high-mass mixed action

Limit-state purpose:

- avoid collapse,
- preserve or rebuild recovery margin,
- avoid adding exploratory or unlocking burden.

Action-mass cap:

- `total_action_mass <= 0.16`

## Channel roles

| Channel | Role | Default placement |
|---|---|---|
| `no_op` | Zero-cost baseline and stable default. | stable default; allowed in all bands as fallback. |
| `uncertainty_probe` | Light information check. Not a strong improvement channel. | stable/medium only, very weak. |
| `buffer_increase` | Core insurance channel for reversibility margin. | medium/high/limit, capped. |
| `volatility_damping` | Defensive brake for high/limit risk and fatigue pressure. | high/limit, capped. |
| `coupling_relief` | Conditional relief when coupled pressure is clear. | medium/high only when coupling is high. |
| `exploration_injection` | Exploration investment with high hidden/fatigue burden. | only medium or lower, only through approved exploration projection, very weak start. |
| `relation_unlock` | Theoretical fixed-structure loosening channel with weak observed v2 direct effect. | default-forbidden; only a future separately justified exception. |

## Action-mass caps

The capped insurance-hybrid family must expose explicit action-mass caps.

| State band | Total action mass cap |
|---|---:|
| `stable` | `0.03` |
| `medium` | `0.08` |
| `high` | `0.14` |
| `limit` | `0.16` |

These values are not claimed as final optimal constants. They are the first frozen research contract for Phase 2G-20D comparison. If 20D shows that the caps are too weak or too heavy, a later phase may tune them with real-v2 evidence.

## Trigger rule

The policy is condition-triggered rather than continuous.

A non-no-op action is justified only when:

`expected_no_action_risk > expected_action_side_effect_cost`

Operationally, this means:

- stable defaults to no-op,
- medium may fire weak support when risk, residual, unresolved, or reversibility decline is visible,
- high fires insurance actions when hidden burden, fatigue, risk, relation lock, or coupling pressure is high,
- limit fires only collapse-prevention actions.

## One-step action shape

To keep causal attribution readable:

- one step may contain at most one primary action,
- one step may additionally contain at most one very weak probe,
- exploration counts as the probe/secondary action unless a later phase explicitly separates it,
- action mass across all rows must remain below the state-band cap.

This prevents stacked hybrid action from hiding which channel caused benefit or burden.

## Exploration rule

Exploration is not routine control.

Exploration from Phase 2G-20A/B may be considered only when all of the following hold:

- state band is `stable` or `medium`,
- the candidate comes from `exploration_projection`,
- `projection_tier` is one of `strong_candidate`, `weak_candidate`, or `probe_only`,
- `candidate_use_permission` is `action_allowed` or `probe_only`,
- `execution_decision_owner == action_module`,
- the candidate is verified/audited/v8-supported by projection metadata,
- requested strength is not above `max_start_strength`,
- requested side-effect exposure is not above `side_effect_budget`,
- the candidate is not in cooldown.

Even when allowed, exploration starts very weak. Escalation requires later evidence of positive response and low side effects. Phase 2G-20C does not yet implement escalation; it only freezes the starting contract.

High and limit states default to exploration prohibition.

## Side-effect stop conditions

Action must stop, cool down, or roll back when any of these appear:

- fatigue delta rises beyond budget,
- hidden burden rises,
- hidden damage delta rises,
- resource inequality delta worsens,
- reversibility delta fails to improve when reversibility support was the purpose,
- exploration delta is below expectation for an exploration action,
- action cost effect exceeds the band/candidate budget,
- risk band worsens to high or limit after exploratory action,
- cooldown would be violated,
- projection/source verification is missing,
- v8/local audit support is missing,
- benefit/growth appears only by hiding hidden burden or action cost.

Benefit and growth never automatically cancel hidden burden. The policy must keep burden, cost, risk, benefit, and growth visible as separate columns in 20D.

## Runtime boundary rules

The following remain prohibited:

- ActionModule directly reads G/K/O_t,
- ActionModule directly reads ParameterBox or ShadowBox internals,
- ActionModule directly writes ParameterBox or ShadowBox,
- ActionModule writes world/G/K/O_t,
- ActionPlanner or ActionModule uses `v2_action_effect_trace` as runtime input,
- ActionPlanner or ActionModule uses six observation-window outputs as runtime input,
- exploration bridge creates ActionFrame,
- exploration bridge calls ActionModule,
- full sidecar is passed directly into ActionModule.

Allowed:

- DEPT-side prepared candidate hints may be passed as thin action-side input,
- ActionModule may make the final action decision from prepared hints and current allowed policy state,
- real-v2 traces may be read after action for external validation and later research tuning,
- observation-window outputs may be used for external evaluation, audit, and later specification work.

## Phase 2G-20D handoff

Phase 2G-20D should compare:

- `no_op`,
- `current_action_module`,
- Phase 2G-19B-2 `hybrid`,
- `capped_insurance_hybrid`,
- `capped_insurance_hybrid_with_sandbox_approved_exploration`.

20D should keep separate columns for:

- benefit,
- growth,
- risk burden,
- hidden burden,
- fatigue,
- resource inequality,
- action cost,
- reversibility,
- exploration,
- collapse or near-collapse rate,
- total action mass,
- no-op rate,
- band-level trigger reason,
- stop/cooldown reason.

A composite score may be used only as a helper. It must not hide burden, cost, or risk.

## Acceptance contract

Phase 2G-20C is complete when this specification and its test contract establish that:

- the policy is insurance-based, not force-control based,
- each state band has allowed/prohibited channels,
- each state band has an action-mass cap,
- stable defaults to no-op,
- medium permits weak support and very weak approved exploration,
- high/limit prioritize defensive insurance,
- exploration has a small-start rule,
- exploration has cooldown and side-effect budget conditions,
- side-effect stop conditions are explicit,
- ActionModule remains the final execution decision owner,
- runtime boundary violations remain prohibited,
- the handoff to Phase 2G-20D is concrete enough for real-v2 comparison.
