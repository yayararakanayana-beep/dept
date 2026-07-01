"""Final gate combining planned action candidates, v8 support, and parameter box state."""
from __future__ import annotations

import numpy as np
import pandas as pd


class FinalGate:
    def decide(self, v8_surface: pd.DataFrame, params: dict) -> pd.DataFrame:
        if v8_surface.empty:
            return pd.DataFrame()
        conflict_w = float(params.get("conflict_penalty_weight", 0.60))
        unresolved_w = float(params.get("unresolved_penalty_weight", 0.50))
        shadow_threshold = float(params.get("shadow_threshold", 0.48))
        rollback = float(params.get("rollback_sensitivity", 0.55))
        rows = []
        for _, r in v8_surface.iterrows():
            action_strength = float(r.get("action_strength", r.get("planned_action_strength", 0.0)))
            if r.action_channel == "no_op":
                decision = "gate_no_op"
                eff = 0.0
                score = 1.0
            else:
                penalty = conflict_w * r.v8_conflict + unresolved_w * r.v8_unresolved
                planner_conf = float(r.get("planner_confidence", 0.50))
                score = float(np.clip(0.50*r.v8_confidence + 0.35*planner_conf - penalty + 0.30*action_strength, 0, 1))
                if r.v8_unresolved > shadow_threshold or r.v8_conflict > shadow_threshold + 0.10:
                    decision = "hold_shadow"
                    eff = 0.0
                elif score < rollback * 0.40:
                    decision = "weaken"
                    eff = float(action_strength * 0.35)
                elif score < rollback * 0.75:
                    decision = "weaken"
                    eff = float(action_strength * 0.65)
                else:
                    decision = "allow"
                    eff = float(action_strength)
            out = r.to_dict()
            out.update({
                "action_strength": action_strength,
                "final_gate_decision": decision,
                "effective_action_strength": eff,
                "gate_score": score,
                "final_gate_contract": "final_gate_after_action_planner__not_upper_formal_input__noncompressed_RC1",
                "truth_used_for_final_gate": False,
            })
            rows.append(out)
        return pd.DataFrame(rows)
