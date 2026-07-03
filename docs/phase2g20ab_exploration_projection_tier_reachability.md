# Phase 2G-20AB: Exploration Projection Tier Reachability

## Purpose

Phase 2G-20AB updates the exploration bridge so that sandboxed exploration candidates are no longer treated as a strict all-or-nothing handoff.

The earlier bridge only projected candidates that satisfied a hard conjunction such as `sandbox_pass`, `sandbox_verified`, local audit pass, v8 pass, and projection threshold pass. That was safe, but it could make the exploration module practically silent if too few candidates reached the action side.

This phase keeps the hard safety boundary while allowing safe lower-confidence candidates to reach the action side as limited candidates.

## Design principle

The exploration bridge should not be the final execution decision maker.

It should:

- block clearly unsafe candidates,
- preserve full context in the sidecar,
- classify candidates into tiers,
- attach expected gain, side-effect budget, strength caps, and cooldown hints,
- pass a thin candidate projection to the action side.

The action module remains the final execution decision owner.

## Candidate tiers

| Tier | Meaning | Candidate use permission |
|---|---|---|
| `strong_candidate` | Verified sandbox-pass candidate above the projection adoption threshold. | `action_allowed` |
| `weak_candidate` | Verified sandbox-pass candidate below full adoption threshold but above watch threshold. | `probe_only` |
| `probe_only` | Verified watch candidate above watch threshold. | `probe_only` |
| `monitor_only` | Retained in sidecar but not action-readable. | `monitor_only` |
| `blocked` | Unsafe, failed, or explicitly blocked candidate. | `blocked` |

## Hard blocking rules

A candidate is not projected to the action-readable side when any of the following holds:

- `decision_status == block`
- `sandbox_status == block`
- `local_audit_passed == False`
- `v8_support_status != pass`
- `unverified_candidate_can_pass == True`
- candidate lacks sandbox verification for action/probe projection

This means Phase 2G-20AB increases reachability without allowing unverified or failed candidates to become action candidates.

## New projection fields

The thin `exploration_projection` now carries these action-readable hints:

- `projection_tier`
- `candidate_use_permission`
- `frontier_expectation_score`
- `side_effect_budget`
- `max_start_strength`
- `max_escalated_strength`
- `cooldown_steps`
- `execution_decision_owner`
- `action_module_final_decision_required`

These are not action commands. They are candidate metadata for the later insurance-hybrid action policy.

## Boundary confirmation

The bridge still does not:

- create an ActionFrame,
- call ActionModule,
- update ParameterBox or ShadowBox,
- write to world/G/K/O_t,
- pass the full sidecar directly into ActionModule.

The projection remains a thin, bounded candidate handoff. Full context remains in the sidecar.

## Why this matters for the next phases

This phase prepares the next insurance-hybrid action design by making exploration candidates available to the action module in a graded way:

- stable states can ignore them or keep them as monitor/probe information,
- medium states can test safe candidates at very low strength,
- high/limit states can still block exploration and prioritize insurance actions,
- the action module can decide whether the expected frontier gain is worth the side-effect budget.

This keeps the intended governance shape: insurance-based action as the default, with small-start exploration only when the expected frontier value justifies the cost.
