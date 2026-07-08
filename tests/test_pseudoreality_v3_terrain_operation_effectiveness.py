from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pytest

from pseudo_reality.distribution_terrain_v3 import DistributionTerrainV3World
from scripts.pseudoreality_v3_terrain_operation_effectiveness import (
    TerrainOperationSpec,
    apply_terrain_operation,
    export_terrain_operation_effectiveness,
    run_terrain_operation_effectiveness_suite,
    terrain_operation_specs,
)


def test_terrain_operation_specs_include_expected_candidates():
    names = {spec.name for spec in terrain_operation_specs(steps=10)}

    assert {
        "terrain_op_no_operation",
        "terrain_op_damage_reduction_early",
        "terrain_op_rigidity_reduction_early",
        "terrain_op_friction_reduction_early",
        "terrain_op_recovery_speed_boost_early",
        "terrain_op_medium_path_boost_early",
        "terrain_op_wrong_direction_early",
        "terrain_op_damage_reduction_late",
        "terrain_op_recovery_speed_boost_late",
    } <= names


def test_apply_terrain_operation_changes_targeted_terrain_field():
    world = DistributionTerrainV3World()
    world.damage = np.full(world.shape, 0.5)
    spec = TerrainOperationSpec(
        name="test_damage_reduction",
        target="damage_reduction",
        scope="distribution_hotspot",
        start=0,
        duration=1,
        strength=0.2,
    )

    effect = apply_terrain_operation(world, spec)

    assert effect > 0.0
    assert float(world.damage.max()) < 0.5


def test_apply_terrain_operation_rejects_unknown_target():
    world = DistributionTerrainV3World()
    spec = TerrainOperationSpec(
        name="bad",
        target="unknown",
        scope="distribution_hotspot",
        start=0,
        duration=1,
        strength=0.1,
    )

    with pytest.raises(ValueError):
        apply_terrain_operation(world, spec)


def test_run_terrain_operation_effectiveness_suite_returns_summary_columns():
    summary, traces = run_terrain_operation_effectiveness_suite(seed=0, steps=4)

    assert "terrain_op_no_operation" in set(summary["scenario"])
    assert "terrain_op_damage_reduction_early" in set(summary["scenario"])
    assert "final_total_gain_distribution_weighted_mean" in summary.columns
    assert "delta_total_gain_distribution_weighted_mean" in summary.columns
    assert "damage_residual_distribution_weighted_mean" in summary.columns
    assert "rigidity_residual_distribution_weighted_mean" in summary.columns
    assert "operation_effect_strength_sum" in summary.columns
    assert "v3_internal_terrain_operation_trace" in traces["terrain_op_damage_reduction_early"]


def test_export_terrain_operation_effectiveness_writes_summary(tmp_path):
    summary = export_terrain_operation_effectiveness(tmp_path, seed=0, steps=4)

    assert not summary.empty
    assert (tmp_path / "terrain_operation_effectiveness_summary.csv").exists()
    assert (tmp_path / "terrain_operation_effectiveness_summary.json").exists()
