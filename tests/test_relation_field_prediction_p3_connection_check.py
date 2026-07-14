from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import relation_field_prediction_p3_connection_check as p3_1


def _row(t: int, *, status: str, previous: str, current: str) -> dict[str, str]:
    return {
        "trajectory_id": "trajectory-a",
        "t": str(t),
        "gt_row_index": str(t),
        "gt_hash": current,
        "previous_gt_hash": previous,
        "history_chain_hash": f"chain-{t}",
        "continuity_status": status,
        "admissible_for_research": "true",
    }


def test_select_causal_cutoff_and_fixed_edge_key() -> None:
    rows = [
        _row(0, status="initial", previous="", current="gt-0"),
        _row(1, status="continuous", previous="gt-0", current="gt-1"),
        _row(2, status="continuous", previous="gt-1", current="gt-2"),
        _row(3, status="continuous", previous="gt-2", current="gt-3"),
    ]

    previous, current = p3_1.select_causal_cutoff_rows(rows, 2)

    assert previous["gt_hash"] == "gt-1"
    assert current["gt_hash"] == "gt-2"
    assert p3_1.stable_fixed_edge_key(
        {"canonical_edge_id": "17", "direction": "-1"}
    ) == "edge:17:direction:-1"


def test_select_causal_cutoff_rejects_gap() -> None:
    rows = [
        _row(0, status="initial", previous="", current="gt-0"),
        _row(1, status="continuous", previous="gt-0", current="gt-1"),
        _row(2, status="gap", previous="gt-1", current="gt-2"),
    ]

    with pytest.raises(p3_1.P3ConnectionError, match="not continuous"):
        p3_1.select_causal_cutoff_rows(rows, 2)


def test_rf3_identity_rejects_future_read() -> None:
    identity = {
        "trajectory_id": "trajectory-a",
        "from_t": 1,
        "to_t": 2,
        "source_gt_hash_from": "gt-1",
        "source_gt_hash_to": "gt-2",
        "max_source_t_read": 3,
        "observed_transition_reconstruction_not_forecast": True,
    }

    with pytest.raises(p3_1.P3ConnectionError, match="max_source_t_read"):
        p3_1._validate_rf3_identity(
            identity,
            trajectory_id="trajectory-a",
            cutoff_t=2,
            previous_gt_hash="gt-1",
            current_gt_hash="gt-2",
        )


def test_build_connection_record_keeps_p3_1_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    gk = {
        "trajectory_id": "trajectory-a",
        "cutoff_t": 2,
        "previous_gt_hash": "gt-1",
        "current_gt_hash": "gt-2",
    }
    rf3 = {
        "relation_field_id": "rf3-a",
        "maximum_source_t_read": 2,
        "observed_reconstruction_only": True,
    }
    monkeypatch.setattr(p3_1, "inspect_gk_connection", lambda *_args, **_kwargs: gk)
    monkeypatch.setattr(p3_1, "inspect_rf3_connection", lambda *_args, **_kwargs: rf3)

    record = p3_1.build_connection_record(
        gk_trajectory_dir="gk",
        rf3_artifact_dir="rf3",
        cutoff_t=2,
    )

    assert record["status"] == "connection_confirmed"
    assert record["prediction_performed"] is False
    assert record["source_writeback_performed"] is False
    assert record["input_boundary"]["future_information_visible_to_predictor"] is False
    assert record["flow_identity_decision"]["directed_flow_id_is_cross_time_identity"] is False
    assert record["p3_2_handoff"]["translation_not_implemented_in_p3_1"] is True
