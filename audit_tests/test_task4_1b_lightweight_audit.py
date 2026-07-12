from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import task4_1b_lightweight_audit as module


def test_budget_contract_is_bounded() -> None:
    config = module.load_config()
    budget = config["budget"]
    assert budget["phase_b"] == 144
    assert sum(budget[name] for name in ("phase_b", "phase_c", "phase_d", "phase_e")) <= budget["absolute_maximum"]
    assert config["boundaries"]["holdout_state_read"] is False
    assert config["boundaries"]["predictor_retraining"] is False


def test_branch_budget_rejects_overrun() -> None:
    budget = module.BranchBudget(5)
    budget.reserve(5)
    with pytest.raises(module.AuditError, match="budget exceeded"):
        budget.reserve(1)


def _synthetic_rows() -> pd.DataFrame:
    rows = []
    for group, level, escape, window, recovery in (
        ("stable", 0, 0, 8, 1.0),
        ("boundary", 2, 0, 4, 1.0),
        ("failed", 4, 1, -1, 0.0),
    ):
        for index in range(8):
            rows.append(
                {
                    "trajectory_id": f"{group}_{index}",
                    "scenario_id": "not_used_for_selection",
                    "seed": index,
                    "split": "fit" if index < 6 else "validation",
                    "snapshot_step": 28,
                    "current_risk": 0.1 + index * 0.01,
                    "current_value": 0.5 - index * 0.01,
                    "maintenance_cost": 0.1 + index * 0.01,
                    "minimum_escape_cost": 0.2 + index * 0.02,
                    "reachable_value": 0.6 - index * 0.01,
                    "reachable_range": 1.0 - index * 0.02,
                    "last_action_window": window,
                    "provisional_irreversibility_level": level,
                    "escape_not_observed": escape,
                    "best_recovery_probability": recovery,
                }
            )
    return pd.DataFrame(rows)


def test_representative_selection_is_18_and_excludes_holdout() -> None:
    selected = module.select_representatives(_synthetic_rows(), module.load_config())
    assert len(selected) == 18
    assert set(selected["split"]) <= {"fit", "validation"}
    assert selected.groupby("audit_group").size().to_dict() == {
        "stable_structure": 6,
        "boundary_transition": 6,
        "escape_not_observed": 6,
    }


def test_selection_lock_rejects_holdout(tmp_path: Path) -> None:
    body = {
        "task_id": "Task 3.2-4.1b",
        "holdout_state_read": False,
        "representative_states": [
            {"trajectory_id": f"t{index}", "snapshot_step": 12, "split": "fit"}
            for index in range(17)
        ]
        + [{"trajectory_id": "holdout", "snapshot_step": 12, "split": "holdout"}],
    }
    body["lock_hash"] = module._canonical_hash(body)
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(module.AuditError, match="18 fit/validation"):
        module._validate_selection_lock(path)
