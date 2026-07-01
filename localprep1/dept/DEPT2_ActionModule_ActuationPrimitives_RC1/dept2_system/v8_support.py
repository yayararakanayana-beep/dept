"""v8 local support proxy for affordances/planned candidates.

v8 is local observation support, not main controller.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class V8LocalSupport:
    def evaluate(self, candidates: pd.DataFrame, graph_objects: pd.DataFrame, params: dict) -> pd.DataFrame:
        if candidates.empty:
            return pd.DataFrame()
        go = graph_objects.set_index("graph_object_id")
        rows = []
        activation = float(params.get("v8_activation_threshold", 0.42))
        conflict_weight = float(params.get("conflict_weight", params.get("conflict_penalty_weight", 0.60) / 0.60))
        unresolved_weight = float(params.get("unresolved_weight", params.get("unresolved_penalty_weight", 0.50) / 0.50))
        for _, c in candidates.iterrows():
            if c.action_channel == "no_op":
                rows.append({**c.to_dict(), "v8_requested": False, "v8_confidence": 1.0, "v8_conflict": 0.0, "v8_unresolved": 0.0, "v8_conflict_weight": conflict_weight, "v8_unresolved_weight": unresolved_weight, "v8_support_contract": "no_op_no_detail_needed"})
                continue
            g = go.loc[c.graph_object_id]
            target_need = float(c.get("target_need", c.get("planned_need", 0.0)))
            local_need = float(np.clip((g.risk + g.residual + target_need) / 3.0, 0, 1))
            requested = local_need >= activation
            confidence = float(np.clip(g.readiness * (1 - 0.35*g.residual), 0.0, 1.0))
            conflict_raw = float(np.clip((g.risk + g.volatility + g.relation_lock - g.reversibility) / 3.0, 0, 1))
            unresolved_raw = float(np.clip((g.residual + g.uncertainty + (1 - confidence)) / 3.0, 0, 1))
            conflict = float(np.clip(conflict_raw * conflict_weight, 0, 1))
            unresolved = float(np.clip(unresolved_raw * unresolved_weight, 0, 1))
            rows.append({
                **c.to_dict(),
                "v8_requested": bool(requested),
                "v8_confidence": confidence,
                "v8_conflict": conflict,
                "v8_unresolved": unresolved,
                "v8_conflict_weight": conflict_weight,
                "v8_unresolved_weight": unresolved_weight,
                "v8_support_contract": "local_support_only__not_upper_formal_input__noncompressed_RC1",
            })
        return pd.DataFrame(rows)
