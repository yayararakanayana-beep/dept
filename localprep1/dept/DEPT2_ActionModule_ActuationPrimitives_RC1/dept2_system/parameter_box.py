"""Lower Parameter Governance Box.

Registry-limited weak/slow/reversible update of lower parameters from
H11-local pressure and G/K-derived system character.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REGISTRY_ROWS = [
    ("action_intensity_cap", "ActionSurface", 0.55, 0.25, 0.85, 0.025, 0.10, "pressure_cap|rollback_sensitivity|exploration_frequency", "Robustness|Stability|Exploration"),
    ("action_sparsity_threshold", "ActionSurface", 0.16, 0.06, 0.35, 0.015, 0.08, "deadzone_width|pressure_cap|update_frequency", "Efficiency|Stability|Adaptability"),
    ("v8_activation_threshold", "v8", 0.42, 0.20, 0.75, 0.020, 0.10, "diagnostic_depth|rollback_sensitivity", "Predictability|Robustness|Coherence"),
    ("conflict_penalty_weight", "v8", 0.60, 0.20, 1.00, 0.025, 0.10, "rollback_sensitivity|diagnostic_depth", "Robustness|Predictability"),
    ("unresolved_penalty_weight", "v8", 0.50, 0.15, 0.95, 0.025, 0.10, "diagnostic_depth|sandbox_entry_rate", "Predictability|StructuralDiversity"),
    ("shadow_threshold", "FinalGate", 0.48, 0.25, 0.80, 0.020, 0.10, "rollback_sensitivity|pressure_cap|deadzone_width", "Robustness|Stability"),
    ("rollback_sensitivity", "FinalGate", 0.55, 0.25, 0.95, 0.025, 0.10, "rollback_sensitivity|cooldown_length", "Recoverability|Robustness"),
    ("graph_update_rate", "GraphObject", 0.18, 0.05, 0.40, 0.015, 0.10, "update_frequency|commitment_strength", "Adaptability|Coherence"),
    ("exploration_gain", "ActionModule", 0.38, 0.05, 0.80, 0.025, 0.08, "exploration_frequency|sandbox_entry_rate", "Exploration|NoveltyQuality"),
    ("damping_gain", "ActionModule", 0.42, 0.08, 0.85, 0.025, 0.08, "pressure_cap|rollback_sensitivity", "Robustness|Stability"),
    ("unlock_gain", "ActionModule", 0.36, 0.05, 0.80, 0.025, 0.08, "hysteresis_strength|update_frequency", "Coherence|Adaptability"),
    ("buffer_gain", "ActionModule", 0.34, 0.05, 0.80, 0.025, 0.08, "cooldown_length|rollback_sensitivity", "Recoverability|Robustness"),
]


class LowerParameterGovernanceBox:
    def __init__(self):
        self.registry = pd.DataFrame(REGISTRY_ROWS, columns=[
            "parameter_name", "parameter_category", "theta0", "theta_min", "theta_max",
            "max_step_delta", "resistance_to_theta0", "primary_pressure_components",
            "primary_h11_dimensions",
        ])
        self.registry["parameter_governance_contract"] = "registry_limited__weak_slow_reversible__not_free_autotuning__codebase_RC1"
        self.registry["fixed_value_boundary_role"] = "theta0_reference__min_max_and_max_step_are_safety_boundaries"
        self.state = self.registry[["parameter_name", "theta0"]].rename(columns={"theta0":"theta"}).copy()

    def update(self, formal_packet: pd.DataFrame, h11_pressure_field: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        # System character from G/K only.
        gp = formal_packet.iloc[-1]
        caution = float(np.clip((gp["gt_volatility"] + gp["gt_uncertainty"] + gp["gt_conflict"] + (1-gp["gt_reversibility"])) / 4.0, 0, 1))
        exploration_need = float(np.clip((1-gp["gt_exploration"] + gp["gt_overconvergence"]) / 2.0, 0, 1))
        lock_need = float(np.clip((gp["gt_relation_lock"] + gp["gt_coupling"]) / 2.0, 0, 1))
        pressure_summary = h11_pressure_field.groupby("pressure_component")["h11_local_received_pressure"].mean().to_dict()
        h11_summary = h11_pressure_field.groupby("h11_dimension")["h11_local_received_pressure"].mean().to_dict()

        rows = []
        new_state = []
        cur = self.state.set_index("parameter_name")["theta"].to_dict()
        for _, reg in self.registry.iterrows():
            pname = reg.parameter_name
            pressure_signal = sum(abs(pressure_summary.get(c, 0.0)) for c in reg.primary_pressure_components.split("|"))
            h11_signal = sum(abs(h11_summary.get(d, 0.0)) for d in reg.primary_h11_dimensions.split("|"))
            # Direction heuristics are deliberately small and auditable.
            direction = 0.0
            if pname in ["action_intensity_cap", "action_sparsity_threshold"]:
                direction = -0.65*caution + 0.25*exploration_need
            elif pname in ["v8_activation_threshold"]:
                direction = -0.55*caution + 0.20*(1-caution)
            elif pname in ["conflict_penalty_weight", "unresolved_penalty_weight", "shadow_threshold", "rollback_sensitivity"]:
                direction = 0.55*caution - 0.20*(1-caution)
            elif pname == "graph_update_rate":
                direction = -0.45*caution + 0.30*(1-caution)
            elif pname == "exploration_gain":
                direction = 0.65*exploration_need - 0.25*caution
            elif pname == "unlock_gain":
                direction = 0.60*lock_need - 0.20*caution
            elif pname in ["damping_gain", "buffer_gain"]:
                direction = 0.55*caution + 0.25*(1-gp["gt_reversibility"])
            raw_delta = direction * (pressure_signal + h11_signal + 0.005)
            # resistance back to theta0
            theta_cur = float(cur[pname])
            raw_delta -= float(reg.resistance_to_theta0) * (theta_cur - float(reg.theta0))
            bounded_delta = float(np.clip(raw_delta, -float(reg.max_step_delta), float(reg.max_step_delta)))
            theta_next = float(np.clip(theta_cur + bounded_delta, float(reg.theta_min), float(reg.theta_max)))
            rows.append({
                "parameter_name": pname,
                "theta_before": theta_cur,
                "theta_after": theta_next,
                "theta_delta": theta_next - theta_cur,
                "system_caution": caution,
                "exploration_need": exploration_need,
                "relation_lock_need": lock_need,
                "pressure_signal": pressure_signal,
                "h11_signal": h11_signal,
                "update_contract": "G_K_system_character_plus_H11_pressure_only__no_graph_v8_final_gate_input",
                "truth_used_for_parameter_update": False,
            })
            new_state.append({"parameter_name": pname, "theta": theta_next})
        self.state = pd.DataFrame(new_state)
        return self.registry.copy(), pd.DataFrame(rows)

    def current_params(self) -> dict:
        return self.state.set_index("parameter_name")["theta"].to_dict()
