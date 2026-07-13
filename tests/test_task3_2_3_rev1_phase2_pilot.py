from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import task3_2_3_rev1_phase2_pilot as module  # noqa: E402


def _config() -> dict:
    return json.loads(
        (ROOT / "configs" / "task3_2_3_rev1_phase2_pilot.json").read_text(
            encoding="utf-8"
        )
    )


def _metric_rows(
    risk: list[float],
    *,
    concentration_tail: float = 1.0,
    mobility_tail: float = 1.0,
    rigidity_tail: float = 0.0,
) -> list[dict[str, float]]:
    tail_start = len(risk) - 6
    return [
        {
            "risk_score": value,
            "concentration": concentration_tail if index >= tail_start else 1.0,
            "moved_mass": mobility_tail if index >= tail_start else 1.0,
            "weighted_rigidity": rigidity_tail if index >= tail_start else 0.0,
        }
        for index, value in enumerate(risk)
    ]


def _reference(length: int, risk: float = 0.0) -> list[dict[str, float]]:
    return _metric_rows([risk] * length)


@pytest.mark.parametrize(
    ("risk", "kwargs", "expected"),
    [
        ([0.0] * 30, {}, "safe_continuation"),
        ([0.0] * 6 + [0.05] * 5 + [0.0] * 19, {}, "full_recovery"),
        ([0.0] * 6 + [0.05] * 10 + [0.02] * 5 + [0.0] * 9, {}, "delayed_recovery"),
        ([0.0] * 6 + [0.05] * 10 + [0.02] * 14, {}, "partial_recovery"),
        (
            [0.0] * 6 + [0.05] * 5 + [0.0] * 7 + [0.05] * 5 + [0.0] * 7,
            {},
            "relapse",
        ),
        ([0.0] * 6 + [0.05] * 24, {}, "persistent_deterioration"),
        (
            [0.0] * 6 + [0.05] * 24,
            {"concentration_tail": 1.2, "mobility_tail": 0.5, "rigidity_tail": 0.3},
            "fixation_candidate",
        ),
        ([0.1] * 6 + [0.6] * 24, {}, "collapse_candidate"),
    ],
)
def test_raw_metric_classifier_recovers_each_outcome_family(
    risk: list[float], kwargs: dict[str, float], expected: str
) -> None:
    rules = _config()["raw_truth_contract"]["classification_rules"]
    reference_risk = 0.1 if expected == "collapse_candidate" else 0.0
    result = module.classify_relative_metrics(
        _metric_rows(risk, **kwargs), _reference(len(risk), reference_risk), rules
    )
    assert result["observed_outcome_family"] == expected
    assert result["classification_source"] == "raw_state_arrays_only"


def test_relapse_is_found_when_second_peak_is_higher_than_first() -> None:
    rules = _config()["raw_truth_contract"]["classification_rules"]
    risk = [0.0] * 6 + [0.04] * 5 + [0.0] * 8 + [0.08] * 5 + [0.0] * 6
    result = module.classify_relative_metrics(
        _metric_rows(risk), _reference(len(risk)), rules
    )
    assert result["observed_outcome_family"] == "relapse"
    assert result["recovery_step"] is not None
    assert result["relapse_step"] is not None
    assert result["first_episode_peak_step"] < result["peak_step"]


def test_phase2_contract_is_valid_and_remains_pre_model() -> None:
    config, phase1_config = module.load_config()
    result = module.validate_config(config, phase1_config)
    assert result["status"] == "valid"
    assert result["required_outcome_count"] == 8
    assert "model_training" in config["phase_boundaries"]["prohibited_work"]
    assert "formal_corpus_generation" in config["phase_boundaries"]["prohibited_work"]


def test_pilot_reuse_for_formal_modeling_is_rejected() -> None:
    config, phase1_config = module.load_config()
    config = copy.deepcopy(config)
    config["pilot_reuse_policy"][
        "pilot_trajectories_may_be_reused_for_formal_fit_validation_or_holdout"
    ] = True
    with pytest.raises(module.Phase2Error, match="must not be reused"):
        module.validate_config(config, phase1_config)


def test_same_current_pair_must_share_prefix_schedule() -> None:
    config, phase1_config = module.load_config()
    config = copy.deepcopy(config)
    config["pilot_design"]["schedule_families"]["persistent_deterioration"][
        "duration"
    ] += 1
    with pytest.raises(module.Phase2Error, match="entire prefix schedule"):
        module.validate_config(config, phase1_config)


def _write_state(path: Path, damage: float) -> None:
    shape = (5, 5, 5, 5, 5)
    distribution = np.full(shape, 1.0 / np.prod(shape), dtype=np.float64)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        distribution=distribution,
        damage=np.full(shape, damage),
        rigidity=np.full(shape, 0.05),
        friction=np.full(shape, 0.1),
        viscosity=np.full(shape, 0.3),
        recovery_speed=np.full(shape, 0.05),
        route_support=np.full(shape, 0.7),
        viability_reserve=np.full(shape, 0.65),
        negative_viability_pressure=np.zeros(shape),
        last_flow=np.full(shape, 1.0 / np.prod(shape)),
    )


def _raw_fixture(tmp_path: Path) -> tuple[Path, dict, dict]:
    root = tmp_path / "corpus"
    reference_id = "reference"
    target_id = "target"
    for step in range(16):
        _write_state(root / "trajectories" / reference_id / "states" / f"step_{step:06d}.npz", 0.0)
        damage = 0.0 if step < 6 else 0.3
        _write_state(root / "trajectories" / target_id / "states" / f"step_{step:06d}.npz", damage)
    for trajectory_id, label in ((reference_id, "collapse_or_divergence_candidate"), (target_id, "stable")):
        directory = root / "trajectories" / trajectory_id
        (directory / "summary.json").write_text(
            json.dumps({"outcome": {"coarse_outcome": label}}), encoding="utf-8"
        )
        (directory / "truth.jsonl").write_text("{}\n", encoding="utf-8")
        (directory / "metrics.jsonl").write_text("{}\n", encoding="utf-8")
    reference_hash, reference_count = module._state_chain_hash(
        root / "trajectories" / reference_id
    )
    target_hash, target_count = module._state_chain_hash(root / "trajectories" / target_id)
    base = {
        "split": "fit",
        "seed": 1,
        "background_regime_id": "fit-background",
        "background_content_hash": "fit-background-hash",
        "world_parameter_profile_id": "fit-world",
        "world_parameter_content_hash": "fit-world-hash",
        "applied_external_series_hash": "applied",
        "hard_case_tags": [],
        "repetition": 0,
        "environment_group": 0,
        "pair_instance_id": None,
        "pair_role": None,
        "pair_cutoff_step": None,
    }
    reference_row = {
        **base,
        "trajectory_id": reference_id,
        "relative_path": f"trajectories/{reference_id}",
        "schedule_template_id": "fit-reference",
        "schedule_content_hash": "reference-schedule",
        "disturbance_family_id": "stable_reference",
        "intended_outcome_family": "safe_continuation",
        "reference_trajectory_id": reference_id,
        "is_stable_reference": True,
        "include_in_outcome_coverage": False,
        "raw_state_chain_hash": reference_hash,
        "state_count": reference_count,
    }
    target_row = {
        **base,
        "trajectory_id": target_id,
        "relative_path": f"trajectories/{target_id}",
        "schedule_template_id": "fit-target",
        "schedule_content_hash": "target-schedule",
        "disturbance_family_id": "persistent_deterioration",
        "intended_outcome_family": "persistent_deterioration",
        "reference_trajectory_id": reference_id,
        "is_stable_reference": False,
        "include_in_outcome_coverage": True,
        "raw_state_chain_hash": target_hash,
        "state_count": target_count,
    }
    config = _config()
    manifest = {
        "manifest_version": "task3_2_3_rev1_phase2_pilot_v1",
        "phase1_contract_hash": config["source_of_truth"]["phase1_contract_hash"],
        "phase2_contract_hash": module.canonical_hash(config),
        "raw_outcome_fields_present": False,
        "source_labels_are_not_truth": True,
        "trajectories": [reference_row, target_row],
    }
    return root, config, manifest


def test_recomputation_ignores_tampered_source_labels(tmp_path: Path) -> None:
    root, config, manifest = _raw_fixture(tmp_path)
    module.validate_pilot_manifest(manifest, root, config, check_state_hashes=True)
    first = module.recompute_pilot_outcomes(root, manifest, config)
    summary = root / "trajectories" / "target" / "summary.json"
    summary.write_text(
        json.dumps({"outcome": {"coarse_outcome": "natural_recovery"}}),
        encoding="utf-8",
    )
    (root / "trajectories" / "target" / "truth.jsonl").write_text(
        '{"future_risk_event":"none"}\n', encoding="utf-8"
    )
    second = module.recompute_pilot_outcomes(root, manifest, config)
    assert first == second
    assert second["source_label_files_used"] == []
    target = next(row for row in second["rows"] if row["trajectory_id"] == "target")
    assert target["observed_outcome_family"] == "persistent_deterioration"


def test_self_certified_outcome_family_is_rejected(tmp_path: Path) -> None:
    root, config, manifest = _raw_fixture(tmp_path)
    manifest["trajectories"][1]["outcome_family"] = "safe_continuation"
    with pytest.raises(module.Phase2Error, match="self-certified"):
        module.validate_pilot_manifest(manifest, root, config, check_state_hashes=False)


def test_ood_axis_overlap_across_splits_is_rejected(tmp_path: Path) -> None:
    root, config, manifest = _raw_fixture(tmp_path)
    copied = copy.deepcopy(manifest["trajectories"][1])
    copied["trajectory_id"] = "validation-target"
    copied["relative_path"] = "trajectories/target"
    copied["split"] = "validation"
    copied["reference_trajectory_id"] = "validation-reference"
    reference = copy.deepcopy(manifest["trajectories"][0])
    reference["trajectory_id"] = "validation-reference"
    reference["relative_path"] = "trajectories/reference"
    reference["split"] = "validation"
    reference["reference_trajectory_id"] = "validation-reference"
    # schedule_template_id deliberately remains fit-target / fit-reference.
    manifest["trajectories"].extend([reference, copied])
    with pytest.raises(module.Phase2Error, match="OOD axis overlap"):
        module.validate_pilot_manifest(manifest, root, config, check_state_hashes=False)


def test_target_schedule_content_overlap_across_splits_is_rejected(
    tmp_path: Path,
) -> None:
    root, config, manifest = _raw_fixture(tmp_path)
    copied = copy.deepcopy(manifest["trajectories"][1])
    copied.update(
        {
            "trajectory_id": "validation-target",
            "relative_path": "trajectories/target",
            "split": "validation",
            "seed": 2,
            "schedule_template_id": "validation-target",
            "background_regime_id": "validation-background",
            "background_content_hash": "validation-background-hash",
            "world_parameter_profile_id": "validation-world",
            "world_parameter_content_hash": "validation-world-hash",
            "reference_trajectory_id": "validation-reference",
        }
    )
    reference = copy.deepcopy(manifest["trajectories"][0])
    reference.update(
        {
            "trajectory_id": "validation-reference",
            "relative_path": "trajectories/reference",
            "split": "validation",
            "seed": 2,
            "schedule_template_id": "validation-reference",
            "background_regime_id": "validation-background",
            "background_content_hash": "validation-background-hash",
            "world_parameter_profile_id": "validation-world",
            "world_parameter_content_hash": "validation-world-hash",
            "reference_trajectory_id": "validation-reference",
        }
    )
    # Only the concrete target schedule hash still overlaps fit.
    manifest["trajectories"].extend([reference, copied])
    with pytest.raises(module.Phase2Error, match="schedule_content_hash"):
        module.validate_pilot_manifest(manifest, root, config, check_state_hashes=False)


def test_manifest_contract_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    root, config, manifest = _raw_fixture(tmp_path)
    manifest["phase2_contract_hash"] = "tampered"
    with pytest.raises(module.Phase2Error, match="Phase 2 contract hash mismatch"):
        module.validate_pilot_manifest(manifest, root, config, check_state_hashes=False)


def test_raw_state_tampering_breaks_manifest_hash(tmp_path: Path) -> None:
    root, config, manifest = _raw_fixture(tmp_path)
    module.validate_pilot_manifest(manifest, root, config, check_state_hashes=True)
    _write_state(
        root / "trajectories" / "target" / "states" / "step_000010.npz", 0.8
    )
    with pytest.raises(module.Phase2Error, match="raw state hash mismatch"):
        module.validate_pilot_manifest(manifest, root, config, check_state_hashes=True)


def test_same_current_pair_audit_detects_prefix_mismatch(tmp_path: Path) -> None:
    root, config, manifest = _raw_fixture(tmp_path)
    target = manifest["trajectories"][1]
    second_id = "target-b"
    second_dir = root / "trajectories" / second_id
    for step in range(16):
        _write_state(second_dir / "states" / f"step_{step:06d}.npz", 0.0 if step < 7 else 0.4)
    second = copy.deepcopy(target)
    second["trajectory_id"] = second_id
    second["relative_path"] = f"trajectories/{second_id}"
    target["pair_instance_id"] = "pair"
    second["pair_instance_id"] = "pair"
    target["pair_role"] = "recovering_future"
    second["pair_role"] = "deteriorating_future"
    target["pair_cutoff_step"] = 6
    second["pair_cutoff_step"] = 6
    manifest["trajectories"].append(second)
    recomputed = {
        "rows": [
            {"trajectory_id": "target", "observed_outcome_family": "persistent_deterioration"},
            {"trajectory_id": second_id, "observed_outcome_family": "full_recovery"},
        ]
    }
    result = module._same_current_pair_audit(root, manifest, recomputed)
    assert result["same_current_identity_gate"] is False
    assert result["opposite_future_observation_gate"] is True


def test_wilson_interval_and_sample_count_use_trajectory_support() -> None:
    lower, upper = module._wilson(5, 10, 0.95)
    assert lower is not None and upper is not None
    assert 0.0 < lower < 0.5 < upper < 1.0
