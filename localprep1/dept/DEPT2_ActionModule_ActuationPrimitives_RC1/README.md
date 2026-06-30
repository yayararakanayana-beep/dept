# DEPT2 ActionModule ActuationPrimitives RC1

This package introduces an environment-specific actuation primitive layer for the current pseudo reality closed-loop environment.

The key correction is:

```text
Lower layer translates upper pressure without compression.
Action module decides how to compress and act depending on system state.
```

## Main files

- `action_module/actions.py` — modified ActionPlanner / ActionModule with actuation primitives
- `runner/run_action_module_actuation_primitives_rc1.py` — runner
- `docs/ACTION_MODULE_ACTUATION_PRIMITIVES_CONTRACT_RC1.md` — contract
- `docs/VALIDATION_DESIGN_AND_RESULTS_ACTUATION_PRIMITIVES_RC1.md` — validation report
- `results/primitive_library_RC1.csv` — primitive library
- `results/planned_action_candidates_RC1.csv` — planned primitive candidates
- `results/action_module_frames_RC1.csv` — actuated primitive-derived actions
- `results/primitive_vs_noncompressed_baseline_RC1.csv` — comparison with prior non-compressed baseline
- `results/primitive_route_summary_RC1.csv` — planned primitive route summary
- `results/primitive_actuated_action_summary_RC1.csv` — actuated primitive summary
- `results/validation_summary.json` — machine-readable summary

## Status

Sanity checks passed.

This is not a performance proof. It is a structural improvement and diagnostic baseline for action-module refinement.
