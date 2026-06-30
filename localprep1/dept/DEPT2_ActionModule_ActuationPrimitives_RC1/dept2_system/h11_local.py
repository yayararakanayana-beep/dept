"""H11-local pressure reception: high-fidelity receiver, not action compressor."""
from __future__ import annotations

import numpy as np
import pandas as pd
from .hdept_observer import H11_DIMS, PRESSURE_COMPONENTS

# Which H11 dimensions are most receptive to each upper pressure component.
COMPONENT_H11_RECEPTIVITY = {
    "diagnostic_depth": ["Predictability", "Coherence", "TrajectoryDynamics"],
    "exploration_frequency": ["Exploration", "NoveltyQuality", "Adaptability"],
    "sandbox_entry_rate": ["Exploration", "StructuralDiversity", "Recoverability"],
    "adoption_threshold": ["Robustness", "Predictability", "Efficiency"],
    "rollback_sensitivity": ["Robustness", "Recoverability", "Stability"],
    "deadzone_width": ["Efficiency", "Stability", "Coherence"],
    "cooldown_length": ["Stability", "Robustness", "Predictability"],
    "hysteresis_strength": ["Coherence", "Predictability", "TrajectoryDynamics"],
    "update_frequency": ["Adaptability", "TrajectoryDynamics", "Exploration"],
    "pressure_cap": ["Robustness", "Stability", "Coherence"],
    "commitment_strength": ["Coherence", "Predictability", "Efficiency"],
}


class H11LocalPressureReceiver:
    """Receive upper pressure as H11-dimension pressure field.

    It deliberately avoids compressing pressure into action channels.
    """

    def receive(self, m: pd.DataFrame, pressure: pd.DataFrame) -> pd.DataFrame:
        joined = m.merge(
            pressure,
            on=[c for c in ["seed", "scenario", "t", "generator", "phase_bin"] if c in m.columns and c in pressure.columns],
            how="inner",
            suffixes=("", "_pressure"),
        )
        rows = []
        for _, r in joined.iterrows():
            base = {k: r[k] for k in ["seed", "scenario", "t", "generator", "phase_bin"] if k in r.index}
            for dim in H11_DIMS:
                dim_val = float(r[dim])
                # More deficient dimensions are more receptive to pressure, but bounded.
                dim_receptivity = float(np.clip(0.25 + 0.85*(1 - dim_val), 0.05, 1.0))
                for comp in PRESSURE_COMPONENTS:
                    comp_val = float(r[f"approved_{comp}"])
                    match = 1.0 if dim in COMPONENT_H11_RECEPTIVITY[comp] else 0.35
                    received = comp_val * dim_receptivity * match
                    rows.append({
                        **base,
                        "h11_dimension": dim,
                        "pressure_component": comp,
                        "hdept_approved_component_value": comp_val,
                        "h11_dimension_observed_value": dim_val,
                        "h11_local_receptivity": dim_receptivity * match,
                        "h11_local_received_pressure": received,
                        "pressure_reception_contract": "high_fidelity_H11_local_reception__not_action_compressed__codebase_RC1",
                        "truth_used_for_pressure_reception": False,
                    })
        return pd.DataFrame(rows)
