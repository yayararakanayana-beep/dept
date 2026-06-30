# Task22 Controlled Canonical Parameter Update RC1

passed: `true`

## Cases
### update_off
- canonical_write_count: `0`
- rollback_count: `0`
- parameter_delta: `0.0`
- rollback_snapshot_id: `None`
- passed: `true`

### controlled_update_on
- canonical_write_count: `1`
- rollback_count: `0`
- parameter_delta: `-0.03`
- rollback_snapshot_id: `task22_snapshot_controlled_update_on_2202`
- passed: `true`

### forced_bad_update_rollback
- canonical_write_count: `1`
- rollback_count: `1`
- parameter_delta: `0.04`
- rollback_snapshot_id: `task22_snapshot_forced_bad_update_rollback_2203`
- passed: `true`

### real_watch_only_candidates
- canonical_write_count: `0`
- rollback_count: `0`
- parameter_delta: `0.0`
- rollback_snapshot_id: `None`
- passed: `true`

## Performance Delta
```json
{
  "forced_bad_update_before_rollback_vs_after_rollback": {
    "action_quality": 0.0,
    "boundary_margin": 0.0,
    "coactivation_risk": 0.0,
    "noise": 0.0,
    "parameter_drift": 0.0,
    "recovery_time": 0.0,
    "residual": 0.0,
    "stability_after_update": 0.0
  },
  "update_off_vs_controlled_update_on": {
    "action_quality": 0.0157,
    "boundary_margin": 0.0062,
    "coactivation_risk": -0.011,
    "noise": -0.011,
    "parameter_drift": 0.03,
    "recovery_time": -0.125,
    "residual": -0.022,
    "stability_after_update": 0.0
  }
}
```

## Boundary Audit
- gk_writeback_count: `0`
- world_direct_write_count: `0`
- action_module_internal_connection_count: `0`
- actionframe_direct_generation_count: `0`
- boundary_violation_count: `0`
