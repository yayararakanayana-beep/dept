from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import relation_field_prediction_p3_micro_predictor as p3_3


def _config() -> dict[str, object]:
    return {
        "prediction": {
            "acceleration_weight": 0.5,
            "acceleration_cap_ratio": 2.0,
            "local_coupling_weight": 0.25,
            "local_coupling_cap_ratio": 0.5,
            "minimum_flow_scale": 1e-12,
        },
        "constraints": {
            "flow_threshold": 1e-12,
            "mass_tolerance": 1e-10,
            "nonnegative_tolerance": 1e-12,
        },
    }


def _row(
    edge: int,
    source: int,
    target: int,
    current: float,
    change: float,
    width: float,
    adjacent: list[int],
) -> dict[str, object]:
    direction = 1 if current > 0 else (-1 if current < 0 else 0)
    actual_source = source if direction >= 0 else target
    actual_target = target if direction >= 0 else source
    return {
        "flow_id": f"fixed-edge:{edge}",
        "canonical_edge_id": edge,
        "axis_index": edge % 5,
        "axis_name": f"axis-{edge % 5}",
        "current_flow": current,
        "flow_change": change,
        "candidate_width": width,
        "candidate_flow_mean": current,
        "current_direction": direction,
        "source_cell_id": actual_source if direction != 0 else None,
        "target_cell_id": actual_target if direction != 0 else None,
        "adjacent_active_edge_ids": adjacent,
        "candidate_sign_ambiguous": False,
        "evidence": ["test evidence"],
        "counterevidence": [],
    }


def test_raw_models_apply_acceleration_and_local_support_competition() -> None:
    rows = [
        _row(0, 0, 1, 0.20, 0.10, 0.05, [1, 2]),
        _row(1, 1, 2, 0.10, 0.00, 0.02, [0]),
        _row(2, 0, 3, 0.05, 0.00, 0.02, [0]),
    ]

    result = p3_3.predict_raw_edge_flows(rows, edge_count=4, config=_config())

    assert np.isclose(result["raw_flow_continuation"][0], 0.20)
    assert np.isclose(result["acceleration_contribution"][0], 0.05)
    assert np.isclose(result["raw_flow_acceleration"][0], 0.25)
    assert np.isclose(result["local_support"][0], 0.10)
    assert np.isclose(result["local_competition"][0], 0.05)
    assert np.isclose(result["local_coupling_contribution"][0], 0.0125)
    assert np.isclose(result["raw_flow_local_coupling"][0], 0.2625)
    assert result["raw_flow_continuation"][3] == 0.0
    assert result["raw_flow_acceleration"][3] == 0.0
    assert result["raw_flow_local_coupling"][3] == 0.0


def test_acceleration_is_capped_before_weighting() -> None:
    rows = [_row(0, 0, 1, 0.10, 1.00, 0.05, [])]

    result = p3_3.predict_raw_edge_flows(rows, edge_count=1, config=_config())

    assert np.isclose(result["acceleration_change_clipped"][0], 0.20)
    assert np.isclose(result["acceleration_contribution"][0], 0.10)
    assert np.isclose(result["raw_flow_acceleration"][0], 0.20)


def test_transport_constraints_scale_competing_outflow_and_preserve_mass() -> None:
    current = np.zeros(p3_3.CELL_COUNT, dtype=np.float64)
    current[0] = 0.10
    current[1] = 0.30
    current[2] = 0.20
    current[3] = 0.40
    grid = {
        "edge_source": np.asarray([0, 0], dtype=np.int32),
        "edge_target": np.asarray([1, 2], dtype=np.int32),
        "edge_axis": np.asarray([0, 1], dtype=np.int8),
    }
    raw_flow = np.asarray([0.08, 0.08], dtype=np.float64)

    result = p3_3.apply_transport_constraints(
        current,
        grid,
        raw_flow,
        flow_threshold=1e-12,
        mass_tolerance=1e-10,
        nonnegative_tolerance=1e-12,
    )

    assert np.allclose(result["constrained_flow"], [0.05, 0.05])
    assert np.allclose(result["edge_scale"], [0.625, 0.625])
    predicted = result["predicted_gt"]
    assert np.isclose(predicted[0], 0.0)
    assert np.isclose(predicted[1], 0.35)
    assert np.isclose(predicted[2], 0.25)
    assert result["constrained_source_count"] == 1
    assert result["constrained_edge_count"] == 2
    assert np.isclose(np.sum(predicted), np.sum(current))
    assert np.min(predicted) >= 0.0


def test_transport_constraints_handle_reverse_flow() -> None:
    current = np.zeros(p3_3.CELL_COUNT, dtype=np.float64)
    current[0] = 0.25
    current[1] = 0.75
    grid = {
        "edge_source": np.asarray([0], dtype=np.int32),
        "edge_target": np.asarray([1], dtype=np.int32),
        "edge_axis": np.asarray([0], dtype=np.int8),
    }

    result = p3_3.apply_transport_constraints(
        current,
        grid,
        np.asarray([-0.20]),
        flow_threshold=1e-12,
        mass_tolerance=1e-10,
        nonnegative_tolerance=1e-12,
    )

    predicted = result["predicted_gt"]
    assert np.isclose(predicted[0], 0.45)
    assert np.isclose(predicted[1], 0.55)
    assert np.isclose(result["constrained_flow"][0], -0.20)
    assert np.isclose(np.sum(predicted), 1.0)


def test_prediction_rows_keep_model_contributions_separate() -> None:
    rows = [_row(0, 0, 1, 0.10, 0.02, 0.03, [])]
    raw = p3_3.predict_raw_edge_flows(rows, edge_count=1, config=_config())
    current = np.zeros(p3_3.CELL_COUNT, dtype=np.float64)
    current[0] = 1.0
    grid = {
        "edge_source": np.asarray([0], dtype=np.int32),
        "edge_target": np.asarray([1], dtype=np.int32),
        "edge_axis": np.asarray([0], dtype=np.int8),
    }
    constrained = {
        model: p3_3.apply_transport_constraints(
            current,
            grid,
            raw[key],
            flow_threshold=1e-12,
            mass_tolerance=1e-10,
            nonnegative_tolerance=1e-12,
        )
        for model, key in {
            "continuation": "raw_flow_continuation",
            "acceleration": "raw_flow_acceleration",
            "local_coupling": "raw_flow_local_coupling",
        }.items()
    }

    output = p3_3._prediction_rows(rows, raw, constrained)

    assert len(output) == 1
    assert output[0]["continuation"]["raw_flow"] == 0.10
    assert output[0]["acceleration_contribution"] == 0.01
    assert output[0]["prediction_horizon_steps"] == 1
