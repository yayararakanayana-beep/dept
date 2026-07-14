from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import relation_field_prediction_p3_flow_translation as p3_2


def _rf5_fixture(edge_count: int = 3) -> dict[str, object]:
    representative = np.zeros((2, edge_count), dtype=np.float64)
    representative[0] = [0.10, 0.05, 0.00]
    representative[1] = [0.15, -0.02, 0.04]
    candidates = np.asarray(
        [
            [0.10, 0.05, 0.00],
            [0.12, 0.04, 0.00],
            [0.14, -0.03, 0.03],
            [0.16, 0.02, 0.05],
        ],
        dtype=np.float64,
    )
    residual = np.zeros((4, p3_2.CELL_COUNT), dtype=np.float64)
    residual[2, 10] = 0.01
    residual[2, 11] = -0.01
    common = {
        "common_net_flow": np.asarray(
            [[0.10, 0.04, 0.00], [0.14, 0.00, 0.03]], dtype=np.float64
        ),
        "axis_flow_min": np.asarray(
            [[0.10, 0.05, 0.00, 0.00, 0.00], [0.11, -0.03, 0.03, 0.00, 0.00]],
            dtype=np.float64,
        ),
        "axis_flow_max": np.asarray(
            [[0.12, 0.05, 0.00, 0.00, 0.00], [0.17, 0.02, 0.05, 0.00, 0.00]],
            dtype=np.float64,
        ),
        "axis_flow_mean": np.asarray(
            [[0.11, 0.05, 0.00, 0.00, 0.00], [0.14, -0.005, 0.04, 0.00, 0.00]],
            dtype=np.float64,
        ),
    }
    return {
        "transition_times": np.asarray([1, 2], dtype=np.int32),
        "representative_flow": representative,
        "offsets": np.asarray([0, 2, 4], dtype=np.int32),
        "candidate_flow": candidates,
        "candidate_residual": residual,
        "common": common,
        "diagnostics": {
            "axis_flow_acceleration": [
                [0.0, 0.0, 0.0, 0.0, 0.0],
                [0.03, -0.055, 0.04, 0.0, 0.0],
            ],
            "axis_direction_reversal": [
                [0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0],
            ],
            "edge_common_fraction": [1.0, 0.75],
            "field_change_candidate": [False, True],
        },
    }


def _rf8_fixture() -> dict[str, object]:
    coupling_mean = np.zeros((1, 5, 5), dtype=np.float64)
    coupling_mean[0, 0, 1] = 0.25
    minimum = coupling_mean - 0.05
    maximum = coupling_mean + 0.05
    innovation = np.zeros((2, 5), dtype=np.float64)
    innovation[-1, 0] = 0.08
    score = np.zeros((2, 5), dtype=np.float64)
    score[-1, 0] = 2.5
    labels = np.zeros((2, 5), dtype=np.uint8)
    labels[-1, 0] = 1
    return {
        "lag_feedback": {
            "local_coupling_mean": coupling_mean,
            "local_coupling_minimum": minimum,
            "local_coupling_maximum": maximum,
            "positive_consensus": (coupling_mean > 0).astype(np.uint8),
            "negative_consensus": (coupling_mean < 0).astype(np.uint8),
        },
        "same_axis": {
            "lags": [
                {
                    "lag_index": 0,
                    "same_direction_amplification_candidate": [True, False, False, False, False],
                    "same_direction_amplification_candidate_pair_fraction": [1.0, 0.0, 0.0, 0.0, 0.0],
                    "same_direction_attenuation_candidate": [False] * 5,
                    "same_direction_attenuation_candidate_pair_fraction": [0.0] * 5,
                    "direction_reversal_candidate": [False, True, False, False, False],
                    "direction_reversal_candidate_pair_fraction": [0.0, 1.0, 0.0, 0.0, 0.0],
                }
            ]
        },
        "innovation": {
            "baseline_available": np.asarray([0, 1], dtype=np.uint8),
            "innovation_axis_flow": innovation,
            "innovation_scale": np.ones((2, 5), dtype=np.float64) * 0.02,
            "normalized_innovation_score": score,
            "history_conditioned_new_drive_candidate": labels,
        },
        "residual": {
            "transition_times": np.asarray([1, 2], dtype=np.int32),
            "residual_l1_minimum": np.asarray([0.0, 0.01]),
            "residual_l1_maximum": np.asarray([0.0, 0.03]),
            "residual_l1_mean": np.asarray([0.0, 0.02]),
        },
    }


def test_flow_state_preserves_activation_reversal_and_strength() -> None:
    assert p3_2._flow_state(0.0, 0.1) == "activated"
    assert p3_2._flow_state(0.1, -0.1) == "reversed"
    assert p3_2._flow_state(0.1, 0.2) == "strengthened"
    assert p3_2._flow_state(0.2, 0.1) == "weakened"


def test_translate_micro_flows_without_rf8_keeps_missing_information_explicit() -> None:
    grid = {
        "edge_source": np.asarray([0, 1, 2], dtype=np.int32),
        "edge_target": np.asarray([1, 2, 3], dtype=np.int32),
        "edge_axis": np.asarray([0, 1, 2], dtype=np.int8),
    }
    current_gt = np.zeros(p3_2.CELL_COUNT, dtype=np.float64)
    current_gt[:4] = [0.40, 0.30, 0.20, 0.10]
    rf3_flow = np.asarray([0.15, -0.01, 0.04], dtype=np.float64)

    rows, residual = p3_2.translate_micro_flows(
        current_gt=current_gt,
        grid=grid,
        rf3_net_flow=rf3_flow,
        rf5=_rf5_fixture(),
        rf8=None,
    )

    by_edge = {row["canonical_edge_id"]: row for row in rows}
    assert by_edge[0]["persistence_state"] == "strengthened"
    assert by_edge[0]["available_source_mass"] == 0.40
    assert by_edge[1]["persistence_state"] == "reversed"
    assert by_edge[1]["source_cell_id"] == 2
    assert by_edge[1]["candidate_sign_ambiguous"] is True
    assert by_edge[1]["confidence"] is None
    assert by_edge[1]["axis_context"]["coupling_from_axis"] is None
    assert "RF-8 coupling and innovation context unavailable" in by_edge[1]["unavailable_fields"]
    assert residual["candidate_residual_l1_maximum"] == 0.02


def test_translate_micro_flows_adds_rf8_axis_context_without_calling_it_causal() -> None:
    grid = {
        "edge_source": np.asarray([0, 1, 2], dtype=np.int32),
        "edge_target": np.asarray([1, 2, 3], dtype=np.int32),
        "edge_axis": np.asarray([0, 1, 2], dtype=np.int8),
    }
    current_gt = np.zeros(p3_2.CELL_COUNT, dtype=np.float64)
    current_gt[:4] = [0.40, 0.30, 0.20, 0.10]

    rows, residual = p3_2.translate_micro_flows(
        current_gt=current_gt,
        grid=grid,
        rf3_net_flow=np.asarray([0.15, -0.01, 0.04], dtype=np.float64),
        rf5=_rf5_fixture(),
        rf8=_rf8_fixture(),
    )

    edge_zero = next(row for row in rows if row["canonical_edge_id"] == 0)
    axis_context = edge_zero["axis_context"]
    assert axis_context["rf8_available"] is True
    assert axis_context["coupling_from_axis"]["mean"][1] == 0.25
    assert axis_context["history_conditioned_innovation"]["new_drive_candidate"] is True
    assert edge_zero["source_kind"] == "G/K-derived observed relation field"
    assert edge_zero["prediction_performed"] is False
    assert residual["rf8_residual_l1_mean"] == 0.02


def test_translation_uses_only_active_edges() -> None:
    grid = {
        "edge_source": np.asarray([0, 1, 2, 3], dtype=np.int32),
        "edge_target": np.asarray([1, 2, 3, 4], dtype=np.int32),
        "edge_axis": np.asarray([0, 1, 2, 3], dtype=np.int8),
    }
    rf5 = _rf5_fixture(edge_count=3)
    rf5["representative_flow"] = np.pad(rf5["representative_flow"], ((0, 0), (0, 1)))
    rf5["candidate_flow"] = np.pad(rf5["candidate_flow"], ((0, 0), (0, 1)))
    rf5["common"]["common_net_flow"] = np.pad(rf5["common"]["common_net_flow"], ((0, 0), (0, 1)))
    current_gt = np.zeros(p3_2.CELL_COUNT, dtype=np.float64)
    current_gt[:5] = 0.2

    rows, _ = p3_2.translate_micro_flows(
        current_gt=current_gt,
        grid=grid,
        rf3_net_flow=np.zeros(4, dtype=np.float64),
        rf5=rf5,
        rf8=None,
    )

    assert {row["canonical_edge_id"] for row in rows} == {0, 1, 2}
