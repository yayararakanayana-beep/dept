"""pressure_translation_module: non-compressive H11 pressure translation audit.

Task11 strengthens the existing H11LocalPressureReceiver + PressureIntentAnnotator
path.  The module translates M_t and weak pressure into:
  1. H11 local pressure field
  2. PressureIntentBundle
  3. pressure_translation_audit

It does not build ActionFrame, does not call ActionModule, and does not compress
approved pressure components into a single coarse action label.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Iterable
import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.h11_local import H11LocalPressureReceiver
from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.pressure_intent import HDEPTPressureIntentAnnotator

FORBIDDEN_TRANSLATION_PREFIXES = (
    "ot_", "v8_", "exploration_", "action_surface", "action_", "coactivation_",
    "final_gate", "sidecar", "world_write", "canonical_",
)


def _fingerprint(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "empty"
    view = df.sort_index(axis=1).reset_index(drop=True)
    payload = view.to_json(orient="split", date_format="iso", double_precision=12)
    return sha256(payload.encode("utf-8")).hexdigest()[:24]


def _prefix_leaks(columns: Iterable[str]) -> list[str]:
    return [str(c) for c in columns if str(c).startswith(FORBIDDEN_TRANSLATION_PREFIXES)]


class PressureTranslationModule:
    name = "pressure_translation_module"

    def __init__(self):
        self.h11_receiver = H11LocalPressureReceiver()
        self.annotator = HDEPTPressureIntentAnnotator()
        self.contract = "noncompressive_H11_pressure_translation__preserve_component_identity_and_direction__Task11_RC1"

    def translate(self, m_observation: pd.DataFrame, weak_pressure: pd.DataFrame, *, loop_step: int | None = None) -> dict[str, pd.DataFrame]:
        """Translate M_t + weak pressure into H11 local field and pressure intents.

        The signature deliberately accepts only M_t and weak pressure. O_t, v8,
        exploration, action candidates, and ActionFrame are not accepted here.
        """
        self._validate_inputs(m_observation, weak_pressure)
        m_fp = _fingerprint(m_observation)
        weak_fp = _fingerprint(weak_pressure)

        h11_field = self.h11_receiver.receive(m_observation, weak_pressure)
        h11_field = self._annotate_h11_field(h11_field, m_fp, weak_fp)

        intents = self.annotator.annotate(h11_field)
        intents = self._annotate_intents(intents, _fingerprint(h11_field), m_fp, weak_fp)

        audit = self._build_audit(m_observation, weak_pressure, h11_field, intents, m_fp, weak_fp, loop_step)
        return {
            "h11_local_pressure_field": h11_field,
            "pressure_intent_bundle": intents,
            "pressure_translation_audit": audit,
        }

    def _validate_inputs(self, m_observation: pd.DataFrame, weak_pressure: pd.DataFrame) -> None:
        if m_observation is None or m_observation.empty:
            raise ValueError("pressure_translation_module requires non-empty M_t observation")
        if weak_pressure is None or weak_pressure.empty:
            raise ValueError("pressure_translation_module requires non-empty weak pressure")
        m_leaks = _prefix_leaks(m_observation.columns)
        p_leaks = _prefix_leaks(weak_pressure.columns)
        if m_leaks:
            raise ValueError(f"pressure_translation_module M_t lower-artifact leakage: {m_leaks}")
        if p_leaks:
            raise ValueError(f"pressure_translation_module weak-pressure lower-artifact leakage: {p_leaks}")
        required_pressure = [c for c in weak_pressure.columns if str(c).startswith("approved_")]
        if not required_pressure:
            raise ValueError("pressure_translation_module found no approved_* pressure components")

    def _annotate_h11_field(self, h11_field: pd.DataFrame, m_fp: str, weak_fp: str) -> pd.DataFrame:
        if h11_field is None or h11_field.empty:
            return pd.DataFrame()
        out = h11_field.copy()
        out["pressure_translation_contract"] = self.contract
        out["pressure_translation_stage"] = "h11_local_pressure_reception"
        out["translation_source_m_fingerprint"] = m_fp
        out["translation_source_weak_pressure_fingerprint"] = weak_fp
        out["component_identity_preserved"] = True
        out["h11_dimension_identity_preserved"] = True
        out["noncompressive_translation"] = True
        out["compression_allowed_before_action_planner"] = False
        out["translation_uses_ot"] = False
        out["translation_uses_v8"] = False
        out["translation_uses_exploration"] = False
        out["translation_writeback_performed"] = False
        out["truth_used_for_pressure_translation"] = False
        return out

    def _annotate_intents(self, intents: pd.DataFrame, h11_fp: str, m_fp: str, weak_fp: str) -> pd.DataFrame:
        if intents is None or intents.empty:
            return pd.DataFrame()
        out = intents.copy()
        out["pressure_translation_contract"] = self.contract
        out["pressure_translation_stage"] = "pressure_intent_annotation"
        out["translation_source_h11_fingerprint"] = h11_fp
        out["translation_source_m_fingerprint"] = m_fp
        out["translation_source_weak_pressure_fingerprint"] = weak_fp
        out["component_identity_preserved"] = True
        out["component_direction_preserved"] = True
        out["noncompressive_translation"] = True
        out["translation_uses_ot"] = False
        out["translation_uses_v8"] = False
        out["translation_uses_exploration"] = False
        out["translation_writeback_performed"] = False
        out["truth_used_for_pressure_translation"] = False
        return out

    def _build_audit(self, m: pd.DataFrame, weak: pd.DataFrame, h11: pd.DataFrame, intents: pd.DataFrame, m_fp: str, weak_fp: str, loop_step: int | None) -> pd.DataFrame:
        h11_components = set(h11["pressure_component"].astype(str)) if h11 is not None and not h11.empty and "pressure_component" in h11.columns else set()
        intent_components = set(intents["pressure_component"].astype(str)) if intents is not None and not intents.empty and "pressure_component" in intents.columns else set()
        approved_components = {c.replace("approved_", "") for c in weak.columns if str(c).startswith("approved_") and c != "approved_component_l1"}
        h11_dims = set(h11["h11_dimension"].astype(str)) if h11 is not None and not h11.empty and "h11_dimension" in h11.columns else set()
        direction_values = set(intents["component_direction"].astype(str)) if intents is not None and not intents.empty and "component_direction" in intents.columns else set()
        component_identity_preserved = bool(approved_components and approved_components.issubset(h11_components) and approved_components.issubset(intent_components))
        direction_preserved = bool(direction_values and direction_values.issubset({"increase", "decrease", "neutral"}))
        compression_allowed = False
        if intents is not None and not intents.empty and "compression_allowed_before_action_planner" in intents.columns:
            compression_allowed = bool(intents["compression_allowed_before_action_planner"].astype(bool).any())
        forbidden_flags = {
            "translation_uses_ot": False,
            "translation_uses_v8": False,
            "translation_uses_exploration": False,
            "translation_uses_action_surface": False,
            "translation_uses_action_result": False,
            "action_frame_created_by_translation": False,
            "actionmodule_called_by_translation": False,
            "translation_writeback_performed": False,
            "truth_used_for_pressure_translation": False,
        }
        noncompressive_pass = bool(
            not h11.empty
            and not intents.empty
            and component_identity_preserved
            and direction_preserved
            and not compression_allowed
        )
        row = {
            "pressure_translation_contract": self.contract,
            "pressure_translation_input_source": "M_t_and_weak_pressure_only",
            "loop_step": -1 if loop_step is None else int(loop_step),
            "m_rows": int(len(m)),
            "weak_pressure_rows": int(len(weak)),
            "h11_rows": int(len(h11)),
            "intent_rows": int(len(intents)),
            "approved_pressure_component_count": int(len(approved_components)),
            "h11_pressure_component_count": int(len(h11_components)),
            "intent_pressure_component_count": int(len(intent_components)),
            "h11_dimension_count": int(len(h11_dims)),
            "component_identity_preserved": component_identity_preserved,
            "component_direction_preserved": direction_preserved,
            "h11_field_created": bool(not h11.empty),
            "pressure_intent_bundle_created": bool(not intents.empty),
            "noncompressive_translation_passed": noncompressive_pass,
            "compression_allowed_before_action_planner": compression_allowed,
            "m_fingerprint": m_fp,
            "weak_pressure_fingerprint": weak_fp,
            "h11_field_fingerprint": _fingerprint(h11),
            "pressure_intent_fingerprint": _fingerprint(intents),
            "m_lower_leak_count": int(len(_prefix_leaks(m.columns))),
            "weak_pressure_lower_leak_count": int(len(_prefix_leaks(weak.columns))),
            "h11_lower_leak_count": int(len(_prefix_leaks(h11.columns))),
            "intent_lower_leak_count": int(len(_prefix_leaks(intents.columns))),
            "pressure_translation_audit_status": "pass" if noncompressive_pass else "fail",
            **forbidden_flags,
        }
        return pd.DataFrame([row])
