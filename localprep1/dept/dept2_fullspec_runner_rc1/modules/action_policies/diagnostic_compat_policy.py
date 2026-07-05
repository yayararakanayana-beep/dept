"""diagnostic_compat_policy: legacy diagnostic action-policy compatibility layer.

Task: ActionModule UpperPressure Reception Split RC1 / Task 1.

This module deliberately preserves the existing RepairedDiagnosticActionPolicy
for old diagnostic runners, pseudo-pressure smoke tests, and historical
reproducibility.  It must not be treated as the FullSpec primary upper-pressure
reception policy.

Boundary:
    - wraps the existing validation-only repaired diagnostic policy
    - emits explicit compatibility/provenance audit columns
    - does not create ActionFrame by itself in the FullSpec runner context
    - does not call ActionModule
    - does not write to world, G/K, O_t, or canonical parameters
"""
from __future__ import annotations

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.integrated_diagnostic_closed_loop import (
    IntegratedDiagnosticConfig,
    RepairedDiagnosticActionPolicy,
)


DIAGNOSTIC_COMPAT_POLICY_PROFILE = "diagnostic_compat"
DIAGNOSTIC_COMPAT_POLICY_CONTRACT = (
    "diagnostic_compat_policy__wraps_RepairedDiagnosticActionPolicy__"
    "legacy_diagnostic_only__not_fullspec_primary_upper_pressure_reception__Task1_RC1"
)


class DiagnosticCompatPolicy(RepairedDiagnosticActionPolicy):
    """Compatibility wrapper around the legacy repaired diagnostic policy.

    The parent class is intentionally retained for diagnostic reproducibility.
    This wrapper only makes the provenance explicit so later FullSpec tasks can
    separate diagnostic compatibility from the primary upper-pressure reception
    path.
    """

    policy_profile = DIAGNOSTIC_COMPAT_POLICY_PROFILE
    policy_contract = DIAGNOSTIC_COMPAT_POLICY_CONTRACT

    def __init__(self, cfg: IntegratedDiagnosticConfig):
        super().__init__(cfg)

    def build_action_candidates(
        self,
        intents: pd.DataFrame,
        graph_objects: pd.DataFrame,
        step: int,
        seed: int,
        scenario: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Build legacy diagnostic pre-gate candidates with explicit tags."""
        action_candidates, sequence_events = super().build_action_frame(
            intents=intents,
            graph_objects=graph_objects,
            step=step,
            seed=seed,
            scenario=scenario,
        )
        return self._tag_candidates(action_candidates), self._tag_sequence_events(sequence_events)

    def build_action_frame(
        self,
        intents: pd.DataFrame,
        graph_objects: pd.DataFrame,
        step: int,
        seed: int,
        scenario: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Backward-compatible name used by the current planning module.

        The legacy method name is kept until the policy selector is introduced.
        In the FullSpec runner these rows are still pre-gate candidates, not the
        final ActionFrame.
        """
        return self.build_action_candidates(intents, graph_objects, step, seed, scenario)

    def _tag_candidates(self, action_candidates: pd.DataFrame | None) -> pd.DataFrame:
        if action_candidates is None or action_candidates.empty:
            return pd.DataFrame() if action_candidates is None else action_candidates
        out = action_candidates.copy()
        out["action_policy_profile"] = DIAGNOSTIC_COMPAT_POLICY_PROFILE
        out["diagnostic_compat_policy_used"] = True
        out["upper_pressure_reception_policy_used"] = False
        out["diagnostic_compat_policy_contract"] = DIAGNOSTIC_COMPAT_POLICY_CONTRACT
        out["legacy_repaired_policy_preserved"] = True
        out["fullspec_primary_upper_pressure_reception_policy"] = False
        # Preserve the legacy diagnostic-only meaning.  This column existed in
        # the parent policy outputs; keep it explicit in case older rows lacked it.
        out["diagnostic_only"] = True
        return out

    def _tag_sequence_events(self, sequence_events: pd.DataFrame | None) -> pd.DataFrame:
        if sequence_events is None or sequence_events.empty:
            return pd.DataFrame() if sequence_events is None else sequence_events
        out = sequence_events.copy()
        out["action_policy_profile"] = DIAGNOSTIC_COMPAT_POLICY_PROFILE
        out["diagnostic_compat_policy_used"] = True
        out["upper_pressure_reception_policy_used"] = False
        out["diagnostic_compat_policy_contract"] = DIAGNOSTIC_COMPAT_POLICY_CONTRACT
        out["legacy_repaired_policy_preserved"] = True
        out["fullspec_primary_upper_pressure_reception_policy"] = False
        out["diagnostic_only"] = True
        return out
