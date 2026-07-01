# PseudoReality v2 Impl-A Freeze

This document freezes the post-merge handoff state for PseudoReality v2 Impl-A after PR #28 was merged into `main`.

It is a documentation-only handoff. It does not define new runtime behavior, does not replace the existing v1 pseudo reality path, and does not authorize additional code migration.

---

## 1. v2-Impl-A positioning

PseudoReality v2 Impl-A is the first minimal connection of the asymmetric game pseudo reality world into the existing runner scaffold.

The scope is intentionally narrow:

- v2-Impl-A is a minimal connection.
- v2-Impl-A is not performance validation.
- v2-Impl-A does not replace existing v1 behavior.
- v2-Impl-A only reaches `v2_hidden_trace` as the v2-specific trace.
- `v2_game_trace`, `v2_resource_trace`, `v2_information_trace`, and `v2_action_effect_trace` are not implemented yet.
- Deep application of `profile_config` is deferred to v2-Impl-B or later.

The purpose of Impl-A is to prove that the v2 world engine can be selected and can emit repository-compatible traces without widening the closed-loop control boundaries.

---

## 2. What PR #28 added

PR #28 added the v2-Impl-A minimum surface needed for a smoke-level connection:

- A selectable PseudoReality v2 world engine path for the asymmetric game world.
- A `shrinking_equilibrium` profile path for the initial v2 smoke scenario.
- Compatibility with the existing `entity_trace.csv` and `relation_trace.csv` outputs.
- A new v2-specific `v2_hidden_trace.csv` output.
- A v2 smoke path that exercises the new world engine while preserving the existing smoke path.

This freeze records that PR #28 was an integration step, not a full implementation of the v2 RC1 design surface.

---

## 3. Post-merge validation on `main`

After PR #28 was merged into `main`, integration verification reported:

- Existing smoke validation: PASS.
- v2 smoke validation: PASS.
- `entity_trace.csv` generation under the v2 smoke path: confirmed.
- `relation_trace.csv` generation under the v2 smoke path: confirmed.
- `v2_hidden_trace.csv` generation under the v2 smoke path: confirmed.

No additional performance claim is made from these results. The validation confirms only that the existing smoke path and the new minimal v2 smoke path are runnable and produce the expected smoke-level artifacts.

---

## 4. What is currently possible

At the v2-Impl-A freeze point, the repository can:

- Select the v2 asymmetric game pseudo reality engine through the configured world-engine path.
- Run the initial `shrinking_equilibrium` v2 smoke scenario.
- Continue running the existing v1 smoke path without replacing it.
- Emit v2-compatible `entity_trace.csv` and `relation_trace.csv` files.
- Emit the v2-specific `v2_hidden_trace.csv` file.
- Use the v2 smoke artifacts as a minimal handoff point for later v2 design work.

These capabilities are limited to the smoke-level connection. They should not be interpreted as a completed game-world model, full trace taxonomy, or performance evaluation.

---

## 5. What is not possible yet

At this freeze point, the repository still cannot claim or provide:

- Performance validation for PseudoReality v2.
- Replacement of the existing v1 pseudo reality world.
- Full implementation of the PseudoReality v2 RC1 trace surface.
- `v2_game_trace.csv` output.
- `v2_resource_trace.csv` output.
- `v2_information_trace.csv` output.
- `v2_action_effect_trace.csv` output.
- Deep behavioral reflection of `profile_config` across the v2 model.
- Multiple mature v2 profiles beyond the initial smoke-level path.
- Any widened authority for world modules to write to canonical parameters, G/K, world state outside the world, or ActionModule internals.

---

## 6. Notes before moving to v2-Impl-B

Before starting v2-Impl-B, keep the following boundaries fixed:

- Preserve v1 compatibility and default behavior.
- Keep v2 additions additive unless a later task explicitly approves a replacement.
- Treat current v2 outputs as smoke evidence, not performance evidence.
- Do not infer a full closed-loop validation protocol from the Impl-A smoke pass.
- Keep ActionModule and world boundaries one-way: DEPT/H-DEPT may act through ActionFrame-style paths, but the pseudo reality world must not write back into DEPT internals.
- Document assumptions before encoding new behavior.
- Keep the next implementation slice small enough to review independently.

The most important planning point is that `profile_config` deep reflection belongs in v2-Impl-B or later, not in this freeze document.

---

## 7. v2-Impl-B candidates

Potential v2-Impl-B work may include, subject to a separate explicit task:

- Deeper `profile_config` reflection into the v2 asymmetric game dynamics.
- Additional bounded v2 profiles beyond the initial `shrinking_equilibrium` smoke path.
- Addition of `v2_game_trace` with a documented schema.
- Addition of `v2_resource_trace` with a documented schema.
- Addition of `v2_information_trace` with a documented schema.
- Addition of `v2_action_effect_trace` with a documented schema.
- Summary metric expansion that remains clearly separated from performance validation unless performance validation is explicitly requested.
- Additional smoke or pytest coverage for newly introduced documented behavior.

Each candidate should remain additive, bounded, and compatible with the closed-loop constraints already documented for this repository.

---

## 8. Prohibited items

The following are prohibited at the v2-Impl-A freeze point and must not be treated as already authorized by PR #28:

- Claiming that v2-Impl-A is performance validation.
- Claiming that v2-Impl-A replaces existing v1.
- Claiming that v2 game/resource/information/action-effect traces are implemented.
- Treating `v2_hidden_trace` as a direct write path into G/K or canonical parameters.
- Allowing exploration modules to update the Parameter Box directly.
- Allowing ActionModules to directly access DEPT internals.
- Turning watch/audit/proposal/readiness work into a controller, gate, actuator, rollback mechanism, or parameter update path.
- Expanding the RC1 freeze archive into the repository as part of this handoff.
- Introducing code changes under this docs-only freeze.
