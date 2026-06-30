"""ActionSurface affordance map, not upper-pressure compressor.

The surface tells the action planner where and how action is possible.
It must not reduce H-DEPT pressure components into coarse commands.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CHANNEL_FEATURE = {
    "exploration_injection": "exploration",
    "relation_unlock": "relation_lock",
    "volatility_damping": "volatility",
    "uncertainty_probe": "uncertainty",
    "coupling_relief": "coupling",
    "buffer_increase": "reversibility",
}

CHANNEL_DIRECTION = {
    "exploration_injection": 1.0,
    "relation_unlock": -1.0,
    "volatility_damping": -1.0,
    "uncertainty_probe": -1.0,
    "coupling_relief": -1.0,
    "buffer_increase": 1.0,
}


class ActionSurface:
    """Build possible action affordances from GraphObject state only.

    The pressure intent bundle is not consumed here; it stays available for the
    ActionPlanner. This prevents premature pressure compression.
    """

    def build_affordance(self, graph_objects: pd.DataFrame, params: dict) -> pd.DataFrame:
        if graph_objects.empty:
            return pd.DataFrame()
        rows = []
        # Low threshold: affordance should preserve possibilities; planner/gate can reject later.
        affordance_floor = float(params.get("action_affordance_floor", 0.025))
        for _, go in graph_objects.iterrows():
            need_map = {
                "exploration_injection": max(0.0, 0.62 - float(go.exploration)) + 0.28*float((go.relation_lock + go.coupling + (1-go.exploration)) / 3.0) + 0.18*float(go.risk),
                "relation_unlock": float(go.relation_lock) + 0.25*float(go.coupling) + 0.10*float((go.relation_lock + go.coupling + (1-go.exploration)) / 3.0),
                "volatility_damping": float(go.volatility) + 0.35*float(go.risk),
                "uncertainty_probe": float(go.uncertainty) + 0.30*float(go.residual),
                "coupling_relief": float(go.coupling) + 0.20*float(go.relation_lock),
                "buffer_increase": max(0.0, 1.0 - float(go.reversibility)) + 0.20*float(go.risk),
            }
            for channel, raw_need in need_map.items():
                target_need = float(np.clip(raw_need, 0.0, 1.0))
                if target_need < affordance_floor:
                    continue
                # Cost is an estimate; not a rejection decision.
                local_risk = float(np.clip((go.risk + go.volatility + go.uncertainty + go.residual) / 4.0, 0, 1))
                reversibility = float(np.clip(go.reversibility, 0, 1))
                action_cost = float(np.clip(0.25*local_risk + 0.35*(1-reversibility) + 0.20*go.coupling, 0, 1))
                rows.append({
                    "seed": int(go.seed),
                    "scenario": go.scenario,
                    "t": int(go.t),
                    "graph_object_id": go.graph_object_id,
                    "entity_id": go.entity_id,
                    "action_channel": channel,
                    "target_feature": CHANNEL_FEATURE[channel],
                    "direction": CHANNEL_DIRECTION[channel],
                    "target_need": target_need,
                    "estimated_action_cost": action_cost,
                    "estimated_reversibility": reversibility,
                    "local_risk_proxy": local_risk,
                    "affordance_contract": "action_surface_outputs_affordance_map__does_not_compress_upper_pressure__RC1",
                    "truth_used_for_affordance": False,
                })
        return pd.DataFrame(rows)

    # Backward-compatible name for old runner calls.
    def compress(self, graph_objects: pd.DataFrame, h11_field: pd.DataFrame, params: dict) -> pd.DataFrame:
        return self.build_affordance(graph_objects, params)
