# Phase 2F-1e Relaxed Default Mode

## Scope

This change sets `intermediate_conservatism_mode` default from `current` to `relaxed` in `FullSpecRunnerConfig`.

This is a narrow default-selection change only. It does not change gate logic, action policy, ActionModule boundaries, acceptance criteria, canonical-write behavior, dry-run behavior, or forbidden-write handling.

## Rationale

Phase 2F-1b introduced the explicit `current` / `relaxed` / `flat` ablation switch and showed that relation-unlock pressure thinning improved when distributed intermediate conservatism was relaxed.

Phase 2F-1c extended the comparison with longer runtime-safe runs and assessed `relaxed` as a provisional default candidate while keeping `flat` as an upper-bound risk comparator.

Phase 2F-1d added stress validation and assessed `relaxed` as a strong default candidate under the committed runtime-safe stress design. It also preserved hard boundary safety and documented that `flat` should remain validation-only.

## Default mode decision

- New default: `relaxed`
- Explicit baseline mode retained: `current`
- Validation upper-bound mode retained: `flat`

## Non-goals

This PR does not:

- make `flat` a default candidate
- relax acceptance conditions
- relax safety boundaries
- change ActionModule input constraints
- enable canonical writes
- enable dry-run writes
- allow direct ParameterBox input to ActionModule
- allow G/K/O_t writeback

## Follow-up

After merge, future validation matrices should treat `relaxed` as the runtime default and explicitly set `current` when a baseline comparison is needed.
