# Phase 2G-18R-1 v2 Direct Benefit Window Report

Phase 2G-18R-1 modifies only the v2 direct benefit observation window.

`v2_direct_benefit_window` is an external observation and verification surface for direct v2 benefit state. It reads shared resource, commons health, private resource mean, local payoff mean, short-term payoff mean, resource pressure, resource inequality, and cooperation / information context directly from v2 traces.

This window does not handle risk-band evaluation, H11 action effects, pressure-action translation audits, aggregate balance, or tension windows.

The following fields are excluded from this window's status decision: `hidden_damage`, `fatigue`, `defensiveness`, and `latent_pressure`. They may be present in traces for other windows, but they do not make `v2_direct_benefit_window` warning or critical.

When a core field is missing, the window reports `status_label: unresolved`, records an `unresolved_core_<field>` flag, and does not fall back to `watch`. Derived benefit proxies are emitted only when all core fields are available.

The comprehensive balance / tension windows are not part of this task.
