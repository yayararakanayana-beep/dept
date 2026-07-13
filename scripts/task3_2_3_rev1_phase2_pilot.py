"""Task 3.2-3 Rev1 Phase 2 pilot-corpus feasibility audit.

The pilot generator creates deliberately varied raw trajectories.  The audit
does not trust generator scenario names, ``summary.json``, ``truth.jsonl``, or
``metrics.jsonl``.  Outcomes are frozen from persisted raw state arrays first;
source-label disagreement is inspected only afterwards.

This module does not build predictor features, train or select a model, create
a formal corpus, use Task 4 / Task 4.1 information, construct formal G_t or a
relation field, classify game structures, or select actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import task3_2_3_rev1_contract as phase1  # noqa: E402


DEFAULT_CONFIG = ROOT / "configs" / "task3_2_3_rev1_phase2_pilot.json"
EXTERNAL_FIELDS = (
    "external_resource_supply",
    "external_demand",
    "external_competition_pressure",
    "external_information_noise",
    "external_shock",
    "external_constraint_pressure",
)
SPLITS = ("fit", "validation", "holdout")
WORLD_OVERRIDE_FIELDS = {
    "base_move_fraction",
    "diffusion_rate",
    "natural_recovery_rate",
    "base_recovery_speed",
    "viability_reserve_initial",
    "route_support_initial",
    "route_support_loss_rate",
}


class Phase2Error(ValueError):
    """Raised when the Phase 2 pilot or its independent audit is invalid."""


def _json_load(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_dump(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Phase2Error(f"{name} must be an object")
    return value


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise Phase2Error(f"{name} must be a non-empty list")
    return value


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Phase2Error(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise Phase2Error(f"{name} must be finite")
    return result


def validate_config(config: Mapping[str, Any], phase1_config: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "task_identity",
        "source_of_truth",
        "phase_boundaries",
        "pilot_reuse_policy",
        "raw_truth_contract",
        "pilot_design",
        "coverage_contract",
        "sample_size_audit",
        "outputs",
    }
    missing = sorted(required - set(config))
    if missing:
        raise Phase2Error(f"Phase 2 config missing sections: {missing}")
    phase1.validate_contract(phase1_config)
    phase1_hash = phase1.canonical_hash(phase1_config)
    source = _require_mapping(config["source_of_truth"], "source_of_truth")
    if source.get("phase1_contract_hash") != phase1_hash:
        raise Phase2Error("Phase 1 contract hash mismatch")

    identity = _require_mapping(config["task_identity"], "task_identity")
    if identity.get("status") != "pilot_feasibility_audit_only":
        raise Phase2Error("Phase 2 status must remain pilot-feasibility-only")
    phase = _require_mapping(config["phase_boundaries"], "phase_boundaries")
    allowed = set(_require_list(phase.get("allowed_work"), "allowed_work"))
    prohibited = set(_require_list(phase.get("prohibited_work"), "prohibited_work"))
    if allowed & prohibited:
        raise Phase2Error("allowed and prohibited work overlap")
    mandatory_prohibited = {
        "formal_corpus_generation",
        "predictor_feature_extraction",
        "model_implementation",
        "model_training",
        "model_selection",
        "selection_lock_creation",
        "formal_validation_or_holdout_evaluation",
        "task4_feature_import",
        "task4_1_truth_use",
        "formal_gt_or_relation_field_use",
        "game_structure_classification",
        "irreversibility_proof",
        "action_module_connection",
    }
    if not mandatory_prohibited <= prohibited:
        raise Phase2Error(
            f"Phase 2 prohibitions missing: {sorted(mandatory_prohibited - prohibited)}"
        )

    reuse = _require_mapping(config["pilot_reuse_policy"], "pilot_reuse_policy")
    if reuse.get("pilot_trajectories_may_be_reused_for_formal_fit_validation_or_holdout") is not False:
        raise Phase2Error("pilot trajectories must not be reused in the formal corpus")
    if reuse.get("pilot_thresholds_may_be_retuned_after_outcome_read") is not False:
        raise Phase2Error("pilot thresholds must be frozen before outcome reads")
    if reuse.get("formal_corpus_requires_new_disjoint_schedule_background_world_and_seed_values") is not True:
        raise Phase2Error("formal corpus must use wholly new condition values")

    truth = _require_mapping(config["raw_truth_contract"], "raw_truth_contract")
    if truth.get("only_label_source") != (
        "persisted_raw_state_arrays_recomputed_against_raw_stable_reference"
    ):
        raise Phase2Error("raw state recomputation must remain the only label source")
    forbidden_sources = set(
        _require_list(
            truth.get("source_label_files_forbidden_until_after_recomputed_outcome_freeze"),
            "source label files",
        )
    )
    if forbidden_sources != {"summary.json", "truth.jsonl", "metrics.jsonl"}:
        raise Phase2Error("all source label files must remain blind until recomputation")
    required_arrays = set(_require_list(truth.get("required_state_arrays"), "required arrays"))
    required_for_risk = {
        "distribution",
        "damage",
        "rigidity",
        "friction",
        "viscosity",
        "recovery_speed",
        "route_support",
        "viability_reserve",
        "negative_viability_pressure",
        "last_flow",
    }
    if required_arrays != required_for_risk:
        raise Phase2Error("raw risk recomputation array set changed")
    weights = _require_mapping(truth.get("risk_score_weights"), "risk score weights")
    if not math.isclose(sum(_finite(v, f"risk weight {k}") for k, v in weights.items()), 1.0):
        raise Phase2Error("risk score weights must sum to one")

    design = _require_mapping(config["pilot_design"], "pilot_design")
    if list(design.get("split_order", [])) != list(SPLITS):
        raise Phase2Error("split order must remain fit, validation, holdout")
    transitions = design.get("transitions")
    if isinstance(transitions, bool) or not isinstance(transitions, int) or transitions < 32:
        raise Phase2Error("pilot transitions must be an integer >= 32")
    specifications = _require_mapping(
        design.get("split_specifications"), "split specifications"
    )
    all_seeds: list[int] = []
    for split in SPLITS:
        specification = _require_mapping(specifications.get(split), f"{split} specification")
        seeds = _require_list(specification.get("seeds"), f"{split} seeds")
        if len(seeds) != 4 or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds):
            raise Phase2Error(f"{split} requires four integer environment-group seeds")
        all_seeds.extend(seeds)
    if len(all_seeds) != len(set(all_seeds)):
        raise Phase2Error("pilot seeds must be disjoint across splits")

    coverage = _require_mapping(config["coverage_contract"], "coverage_contract")
    required_outcomes = set(_require_list(coverage.get("required_outcome_families"), "outcomes"))
    phase1_outcomes = set(phase1_config["corpus_contract"]["required_outcome_families"])
    if required_outcomes != phase1_outcomes:
        raise Phase2Error("Phase 2 outcome families must exactly match Phase 1")
    schedules = _require_mapping(design.get("schedule_families"), "schedule families")
    if set(schedules) != required_outcomes:
        raise Phase2Error("one pilot schedule family is required per intended outcome")
    pair_common: dict[str, tuple[int, int, float]] = {}
    pair_roles: dict[str, set[str]] = {}
    for family in schedules.values():
        family = _require_mapping(family, "schedule family")
        pair_id = family.get("pair_id")
        if not pair_id:
            continue
        common = (int(family["start"]), int(family["duration"]), float(family["strength"]))
        previous = pair_common.setdefault(str(pair_id), common)
        if previous != common:
            raise Phase2Error(f"same-current pair {pair_id} must share its entire prefix schedule")
        pair_roles.setdefault(str(pair_id), set()).add(str(family.get("pair_role")))
    for pair_id, roles in pair_roles.items():
        if roles != {"recovering_future", "deteriorating_future"}:
            raise Phase2Error(f"same-current pair {pair_id} must contain both future roles")
    hard_tags = {
        str(tag)
        for family in schedules.values()
        for tag in _require_mapping(family, "schedule family").get("hard_case_tags", [])
    }
    required_hard = set(coverage["required_hard_negative_families"]) | set(
        coverage["required_hard_positive_families"]
    )
    if not required_hard <= hard_tags:
        raise Phase2Error(f"hard-case design missing: {sorted(required_hard - hard_tags)}")
    groups = _require_mapping(design.get("outcome_family_group"), "outcome family group")
    if set(groups) != required_outcomes or any(int(value) not in range(4) for value in groups.values()):
        raise Phase2Error("each intended outcome must map to environment group 0..3")
    backgrounds = _require_list(
        design.get("background_regime_templates"), "background regime templates"
    )
    if len(backgrounds) != 4:
        raise Phase2Error("four background-regime templates are required")
    world_profiles = _require_mapping(
        design.get("world_parameter_profiles"), "world parameter profiles"
    )
    profile_hashes: dict[str, set[str]] = {}
    for split in SPLITS:
        profiles = _require_list(world_profiles.get(split), f"{split} world profiles")
        if len(profiles) != 4:
            raise Phase2Error(f"{split} requires four world profiles")
        profile_hashes[split] = set()
        for profile in profiles:
            profile = _require_mapping(profile, "world profile")
            unknown = set(profile) - WORLD_OVERRIDE_FIELDS
            if unknown:
                raise Phase2Error(f"unsupported world overrides: {sorted(unknown)}")
            for name, value in profile.items():
                _finite(value, name)
            profile_hashes[split].add(canonical_hash(profile))
        if len(profile_hashes[split]) != 4:
            raise Phase2Error(f"{split} world profiles must be distinct")
    for left_index, left in enumerate(SPLITS):
        for right in SPLITS[left_index + 1 :]:
            if profile_hashes[left] & profile_hashes[right]:
                raise Phase2Error("world-profile contents overlap across splits")
    return {
        "status": "valid",
        "phase1_contract_hash": phase1_hash,
        "phase2_contract_hash": canonical_hash(config),
        "required_outcome_count": len(required_outcomes),
        "hard_case_count": len(required_hard),
    }


def load_config(path: str | Path = DEFAULT_CONFIG) -> tuple[dict[str, Any], dict[str, Any]]:
    config = _json_load(path)
    phase1_path = ROOT / config["source_of_truth"]["phase1_contract"]
    phase1_config = phase1.load_contract(phase1_path)
    validate_config(config, phase1_config)
    return config, phase1_config


def _zero_external() -> dict[str, float]:
    return {name: 0.0 for name in EXTERNAL_FIELDS}


def _clip_external(values: Mapping[str, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for name in EXTERNAL_FIELDS:
        low, high = (-1.0, 1.0) if name in EXTERNAL_FIELDS[:2] else (0.0, 1.0)
        result[name] = float(np.clip(float(values.get(name, 0.0)), low, high))
    return result


def _add_external(left: Mapping[str, float], right: Mapping[str, float]) -> dict[str, float]:
    return _clip_external({name: float(left[name]) + float(right[name]) for name in EXTERNAL_FIELDS})


def _burden(strength: float, *, shock_scale: float = 0.25) -> dict[str, float]:
    return _clip_external(
        {
            "external_resource_supply": -0.82 * strength,
            "external_demand": 0.58 * strength,
            "external_competition_pressure": 0.72 * strength,
            "external_information_noise": 0.62 * strength,
            "external_shock": shock_scale * strength,
            "external_constraint_pressure": 0.72 * strength,
        }
    )


def _scale_external(values: Mapping[str, float], scale: float) -> dict[str, float]:
    return _clip_external({name: float(values[name]) * scale for name in EXTERNAL_FIELDS})


def _background_series(
    split: str, group: int, transitions: int, config: Mapping[str, Any]
) -> list[dict[str, float]]:
    design = config["pilot_design"]
    template = design["background_regime_templates"][group]
    adjustment = float(design["split_background_adjustments"][split])
    amplitude = float(template["amplitude"]) * adjustment
    offset = float(template["offset"]) * adjustment
    kind = str(template["kind"])
    rows: list[dict[str, float]] = []
    for step in range(transitions + 1):
        phase = 2.0 * math.pi * step / max(transitions, 1)
        values = _zero_external()
        if kind == "near_zero_stationary":
            values["external_resource_supply"] = amplitude * math.sin(phase)
            values["external_demand"] = -0.5 * amplitude * math.sin(phase)
            values["external_information_noise"] = abs(amplitude) * 0.25
        elif kind == "nonzero_safe_reference":
            values["external_resource_supply"] = offset + 0.3 * amplitude * math.sin(phase)
            values["external_demand"] = -0.45 * offset
            values["external_information_noise"] = abs(amplitude) * 0.2
        elif kind == "moving_distribution_center":
            values["external_resource_supply"] = amplitude * math.sin(phase)
            values["external_demand"] = amplitude * math.cos(phase)
            values["external_competition_pressure"] = max(0.0, offset + amplitude * 0.2 * math.sin(2 * phase))
            values["external_information_noise"] = max(0.0, amplitude * 0.25)
        elif kind == "different_normal_variability":
            block = 1.0 if (step // 8) % 2 == 0 else -1.0
            values["external_resource_supply"] = offset + block * amplitude
            values["external_demand"] = -offset - 0.5 * block * amplitude
            values["external_competition_pressure"] = max(0.0, amplitude * (0.4 + 0.2 * block))
            values["external_information_noise"] = max(0.0, amplitude * 0.35)
        else:
            raise Phase2Error(f"unknown background kind {kind}")
        rows.append(_clip_external(values))
    return rows


def _disturbance_series(
    family_id: str,
    split: str,
    transitions: int,
    config: Mapping[str, Any],
) -> tuple[list[dict[str, float]], int | None]:
    design = config["pilot_design"]
    family = design["schedule_families"][family_id]
    modifier = design["split_specifications"][split]["schedule_modifier"]
    start = int(family["start"]) + int(modifier["start_shift"])
    duration = max(3, int(family["duration"]) + int(modifier["duration_shift"]))
    end = min(transitions, start + duration)
    strength = float(family["strength"]) * float(modifier["strength_scale"])
    kind = str(family["kind"])
    rows = [_zero_external() for _ in range(transitions + 1)]
    pair_cutoff: int | None = None

    if kind == "noisy_safe":
        for step in range(start, min(end, transitions + 1)):
            oscillation = math.sin(2.0 * math.pi * (step - start) / max(duration, 1))
            rows[step] = _clip_external(
                {
                    "external_resource_supply": 0.35 * strength * oscillation,
                    "external_demand": -0.2 * strength * oscillation,
                    "external_information_noise": 0.18 * strength * abs(oscillation),
                }
            )
    elif kind in {"shared_prefix_then_recovery", "shared_prefix_then_persistent"}:
        common = _burden(strength, shock_scale=0.18)
        for step in range(start, end):
            rows[step] = common
        pair_cutoff = end if family.get("pair_id") else None
        if kind == "shared_prefix_then_persistent":
            for step in range(end, transitions + 1):
                progress = min(1.0, (step - end + 1) / 12.0)
                rows[step] = _burden(strength * (0.75 + 0.5 * progress), shock_scale=0.12)
    elif kind == "pulse_then_residual":
        pulse = _burden(strength, shock_scale=0.3)
        for step in range(start, end):
            rows[step] = pulse
        residual = _scale_external(pulse, float(family["residual_fraction"]))
        for step in range(end, transitions + 1):
            rows[step] = residual
    elif kind == "pulse_residual_then_clear":
        pulse = _burden(strength, shock_scale=0.28)
        for step in range(start, end):
            rows[step] = pulse
        clear_step = min(transitions + 1, end + int(family["clear_delay"]))
        residual = _scale_external(pulse, float(family["residual_fraction"]))
        for step in range(end, clear_step):
            rows[step] = residual
    elif kind == "pulse_recover_relapse":
        pulse = _burden(strength, shock_scale=0.3)
        for step in range(start, end):
            rows[step] = pulse
        relapse_start = min(transitions + 1, end + int(family["relapse_delay"]))
        relapse_end = min(transitions + 1, relapse_start + int(family["relapse_duration"]))
        relapse = _burden(strength * 1.08, shock_scale=0.22)
        for step in range(relapse_start, relapse_end):
            rows[step] = relapse
    elif kind == "gradual_fixation_without_shock":
        for step in range(start, transitions + 1):
            progress = min(1.0, (step - start + 1) / max(duration, 1))
            level = strength * (0.25 + 0.75 * progress)
            values = _burden(level, shock_scale=0.0)
            values["external_constraint_pressure"] = min(
                1.0, float(family["constraint_scale"]) * level
            )
            values["external_competition_pressure"] = min(
                1.0, float(family["competition_scale"]) * level
            )
            rows[step] = _clip_external(values)
    elif kind == "gradual_then_collapse":
        for step in range(start, end):
            progress = (step - start + 1) / max(duration, 1)
            rows[step] = _burden(strength * (0.35 + 0.65 * progress), shock_scale=0.45)
        for step in range(end, transitions + 1):
            rows[step] = _burden(min(1.2, 1.08 * strength), shock_scale=0.8)
    else:
        raise Phase2Error(f"unknown schedule kind {kind}")
    return rows, pair_cutoff


def _compress_external_series(rows: Sequence[Mapping[str, float]]) -> dict[str, Any]:
    if len(rows) < 2:
        raise Phase2Error("external series must contain at least two states")
    segments: list[dict[str, Any]] = []
    start = 0
    current = _clip_external(rows[0])
    for step in range(1, len(rows)):
        candidate = _clip_external(rows[step])
        if candidate != current:
            segments.append(
                {"start": start, "end": step, "event": "observed_external_input", **current}
            )
            start = step
            current = candidate
    segments.append(
        {"start": start, "end": None, "event": "observed_external_input", **current}
    )
    return {
        "description": "Task 3 Rev1 pilot; family names remain provenance only.",
        "segments": segments,
    }


def _state_chain_hash(trajectory_dir: str | Path) -> tuple[str, int]:
    directory = Path(trajectory_dir)
    files = sorted((directory / "states").glob("step_*.npz"))
    if not files:
        raise Phase2Error(f"{directory} contains no raw states")
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode("utf-8"))
        digest.update(bytes.fromhex(_file_hash(path)))
    return digest.hexdigest(), len(files)


def _state_content_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with np.load(path, allow_pickle=False) as bundle:
        for name in sorted(bundle.files):
            value = np.ascontiguousarray(bundle[name])
            digest.update(name.encode("utf-8"))
            digest.update(str(value.shape).encode("ascii"))
            digest.update(str(value.dtype).encode("ascii"))
            digest.update(value.tobytes())
    return digest.hexdigest()


def _generate_raw_trajectory(
    output: Path,
    trajectory_id: str,
    scenario_id: str,
    scenario: Mapping[str, Any],
    seed: int,
    split: str,
    transitions: int,
    world_overrides: Mapping[str, float],
    generation_config: Mapping[str, Any],
    raw_contract: Mapping[str, Any],
) -> dict[str, Any]:
    # Importing the existing generator is deliberately delayed.  Independent
    # audit functions below remain usable without the world implementation.
    import task3_2_2_continuous_trajectory as t2

    trajectory_dir = output / "trajectories" / trajectory_id
    if trajectory_dir.exists():
        shutil.rmtree(trajectory_dir)
    (trajectory_dir / "states").mkdir(parents=True)
    world_config = {"seed": int(seed), **{key: float(value) for key, value in world_overrides.items()}}
    world = t2.DistributionTerrainV322World(t2.DistributionTerrainV322Config(**world_config))
    required_arrays = list(raw_contract["step_record"]["required_state_arrays"])
    dtype = str(generation_config["numeric"]["state_dtype"])
    metadata = {
        "trajectory_id": trajectory_id,
        "scenario_id": scenario_id,
        "seed": int(seed),
        "initial_state_id": "distribution_terrain_v3_2_2_default_reset",
        "world_module": generation_config["world"]["module"],
        "world_class": generation_config["world"]["class"],
        "world_version": generation_config["world"]["working_version"],
        "config_version": "task3_2_3_rev1_phase2_pilot",
        "total_steps": int(transitions),
        "dataset_split": split,
        "world_config_overrides": world_config,
    }
    trajectory_digest = hashlib.sha256()
    step_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, float]] = []
    for step in range(transitions + 1):
        external, events = t2._segment_at(scenario, step)
        world.set_external_factors(external)
        state_ref = f"states/step_{step:06d}.npz"
        available = t2._snapshot_world(
            world,
            trajectory_dir / state_ref,
            required_arrays,
            dtype,
            trajectory_digest,
        )
        metrics = t2._state_metrics(world, external)
        metrics["step"] = float(step)
        metric_rows.append(metrics)
        response = t2._observed_response(step, metrics)
        model_input = {
            "state_ref": state_ref,
            "history_available_through_step": None if step == 0 else step - 1,
            "observed_external_input": external,
            "observed_events": events,
            "observed_action": None,
            "observed_response": response,
        }
        step_rows.append(
            {
                "trajectory_id": trajectory_id,
                "step": step,
                "phase": "pre_transition",
                "state_ref": state_ref,
                "history_available_through_step": None if step == 0 else step - 1,
                "observed_external_input": external,
                "observed_events": events,
                "observed_action": None,
                "observed_response": response,
                "state_arrays_available": available,
                "model_input": model_input,
            }
        )
        if step < transitions:
            world.step()
    # Existing labels are retained only to prove that Phase 2 can ignore them.
    provisional = t2._analyse_outcome(metric_rows, generation_config["provisional_outcome_rules"])
    truth_rows = t2._truth_rows(trajectory_id, transitions, provisional)
    summary = {
        "trajectory_id": trajectory_id,
        "profile": "task3_2_3_rev1_phase2_pilot",
        "scenario_id": scenario_id,
        "scenario_description": scenario.get("description", ""),
        "seed": int(seed),
        "dataset_split": split,
        "transitions": int(transitions),
        "trajectory_fingerprint": trajectory_digest.hexdigest(),
        "outcome": provisional,
        "initial_metrics": metric_rows[0],
        "final_metrics": metric_rows[-1],
        "source_labels_are_not_phase2_truth": True,
    }
    t2._json_dump(trajectory_dir / "metadata.json", metadata)
    t2._write_jsonl(trajectory_dir / "steps.jsonl", step_rows)
    t2._write_jsonl(trajectory_dir / "truth.jsonl", truth_rows)
    t2._write_jsonl(trajectory_dir / "metrics.jsonl", metric_rows)
    t2._json_dump(trajectory_dir / "summary.json", summary)
    t2._write_trajectory_svg(
        trajectory_dir / "trajectory.svg",
        f"{trajectory_id}: provisional source label only",
        metric_rows,
    )
    validation = t2.validate_trajectory_directory(trajectory_dir, raw_contract, generation_config)
    validation["phase2_independent_outcome_not_yet_read"] = True
    t2._json_dump(trajectory_dir / "validation.json", validation)
    return summary


def _write_manifest(root: str | Path) -> dict[str, Any]:
    directory = Path(root)
    files: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        files.append(
            {
                "path": path.relative_to(directory).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _file_hash(path),
            }
        )
    manifest = {
        "file_count": len(files),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in files),
        "files": files,
    }
    _json_dump(directory / "manifest.json", manifest)
    return manifest


def generate_pilot(
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    import task3_2_2_continuous_trajectory as t2
    from task3_2_1_macro_dynamics_contract import load_contract as load_raw_contract

    config, phase1_config = load_config(config_path)
    generation_config = t2.load_generation_config(t2.DEFAULT_CONFIG)
    raw_contract = load_raw_contract(ROOT / generation_config["contract_path"])
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    design = config["pilot_design"]
    transitions = int(design["transitions"])
    rows: list[dict[str, Any]] = []
    reference_ids: dict[tuple[str, int], str] = {}

    for split in SPLITS:
        split_specification = design["split_specifications"][split]
        seeds = [int(seed) for seed in split_specification["seeds"]]
        profiles = design["world_parameter_profiles"][split]
        for group in range(4):
            seed = seeds[group]
            background = _background_series(split, group, transitions, config)
            background_id = f"{split}__background_group_{group}"
            world_profile_id = f"{split}__world_profile_{group}"
            world_profile = profiles[group]
            reference_id = f"traj_phase2_{split}_reference_g{group}_seed{seed:03d}"
            reference_ids[(split, group)] = reference_id
            scenario = _compress_external_series(background)
            _generate_raw_trajectory(
                output,
                reference_id,
                f"phase2_reference_group_{group}",
                scenario,
                seed,
                split,
                transitions,
                world_profile,
                generation_config,
                raw_contract,
            )
            state_hash, state_count = _state_chain_hash(output / "trajectories" / reference_id)
            rows.append(
                {
                    "trajectory_id": reference_id,
                    "relative_path": f"trajectories/{reference_id}",
                    "split": split,
                    "seed": seed,
                    "schedule_template_id": f"{split}__stable_reference_g{group}",
                    "schedule_content_hash": canonical_hash([_zero_external()] * (transitions + 1)),
                    "disturbance_family_id": "stable_reference",
                    "intended_outcome_family": "safe_continuation",
                    "background_regime_id": background_id,
                    "background_content_hash": canonical_hash(background),
                    "world_parameter_profile_id": world_profile_id,
                    "world_parameter_content_hash": canonical_hash(world_profile),
                    "applied_external_series_hash": canonical_hash(background),
                    "reference_trajectory_id": reference_id,
                    "is_stable_reference": True,
                    "include_in_outcome_coverage": False,
                    "hard_case_tags": [],
                    "repetition": None,
                    "environment_group": group,
                    "pair_instance_id": None,
                    "pair_role": None,
                    "pair_cutoff_step": None,
                    "raw_state_chain_hash": state_hash,
                    "state_count": state_count,
                }
            )

        repetitions = int(split_specification["repetitions_per_intended_outcome"])
        for repetition in range(repetitions):
            for family_id in config["coverage_contract"]["required_outcome_families"]:
                base_group = int(design["outcome_family_group"][family_id])
                rotation = int(design["fit_repetition_environment_rotation"]) if split == "fit" else 0
                group = (base_group + repetition * rotation) % 4
                seed = seeds[group]
                background = _background_series(split, group, transitions, config)
                disturbance, pair_cutoff = _disturbance_series(
                    family_id, split, transitions, config
                )
                applied = [
                    _add_external(background[step], disturbance[step])
                    for step in range(transitions + 1)
                ]
                scenario = _compress_external_series(applied)
                trajectory_id = (
                    f"traj_phase2_{split}_{family_id}_r{repetition}_g{group}_seed{seed:03d}"
                )
                _generate_raw_trajectory(
                    output,
                    trajectory_id,
                    f"phase2_{family_id}",
                    scenario,
                    seed,
                    split,
                    transitions,
                    design["world_parameter_profiles"][split][group],
                    generation_config,
                    raw_contract,
                )
                state_hash, state_count = _state_chain_hash(output / "trajectories" / trajectory_id)
                family = design["schedule_families"][family_id]
                pair_id = family.get("pair_id")
                pair_instance = (
                    f"{split}__{pair_id}__r{repetition}__g{group}" if pair_id else None
                )
                rows.append(
                    {
                        "trajectory_id": trajectory_id,
                        "relative_path": f"trajectories/{trajectory_id}",
                        "split": split,
                        "seed": seed,
                        "schedule_template_id": f"{split}__{family_id}__r{repetition}",
                        "schedule_content_hash": canonical_hash(disturbance),
                        "disturbance_family_id": family_id,
                        "intended_outcome_family": family_id,
                        "background_regime_id": f"{split}__background_group_{group}",
                        "background_content_hash": canonical_hash(background),
                        "world_parameter_profile_id": f"{split}__world_profile_{group}",
                        "world_parameter_content_hash": canonical_hash(
                            design["world_parameter_profiles"][split][group]
                        ),
                        "applied_external_series_hash": canonical_hash(applied),
                        "reference_trajectory_id": reference_ids[(split, group)],
                        "is_stable_reference": False,
                        "include_in_outcome_coverage": True,
                        "hard_case_tags": list(family.get("hard_case_tags", [])),
                        "repetition": repetition,
                        "environment_group": group,
                        "pair_instance_id": pair_instance,
                        "pair_role": family.get("pair_role"),
                        "pair_cutoff_step": pair_cutoff,
                        "raw_state_chain_hash": state_hash,
                        "state_count": state_count,
                    }
                )

    manifest = {
        "manifest_version": "task3_2_3_rev1_phase2_pilot_v1",
        "phase1_contract_hash": phase1.canonical_hash(phase1_config),
        "phase2_contract_hash": canonical_hash(config),
        "raw_outcome_fields_present": False,
        "source_labels_are_not_truth": True,
        "trajectories": rows,
    }
    validate_pilot_manifest(manifest, output, config, check_state_hashes=True)
    _json_dump(output / config["outputs"]["pilot_manifest"], manifest)
    split_counts = {
        split: sum(row["split"] == split for row in rows) for split in SPLITS
    }
    summary = {
        "status": "generated_and_raw_validated",
        "trajectory_count": len(rows),
        "target_trajectory_count": sum(bool(row["include_in_outcome_coverage"]) for row in rows),
        "reference_trajectory_count": sum(bool(row["is_stable_reference"]) for row in rows),
        "split_counts": split_counts,
        "transitions_per_trajectory": transitions,
        "outcome_labels_read": False,
        "formal_corpus": False,
    }
    _json_dump(output / config["outputs"]["generation_summary"], summary)
    generation_manifest = _write_manifest(output)
    return {**summary, "manifest_file_count": generation_manifest["file_count"]}


def validate_pilot_manifest(
    manifest: Mapping[str, Any],
    corpus_dir: str | Path,
    config: Mapping[str, Any],
    *,
    check_state_hashes: bool,
) -> dict[str, Any]:
    if manifest.get("manifest_version") != "task3_2_3_rev1_phase2_pilot_v1":
        raise Phase2Error("unsupported pilot manifest version")
    if manifest.get("phase1_contract_hash") != config["source_of_truth"][
        "phase1_contract_hash"
    ]:
        raise Phase2Error("pilot manifest Phase 1 contract hash mismatch")
    if manifest.get("phase2_contract_hash") != canonical_hash(config):
        raise Phase2Error("pilot manifest Phase 2 contract hash mismatch")
    if manifest.get("raw_outcome_fields_present") is not False:
        raise Phase2Error("pilot design manifest must not contain raw outcomes")
    if manifest.get("source_labels_are_not_truth") is not True:
        raise Phase2Error("pilot manifest must keep source labels non-authoritative")
    rows = _require_list(manifest.get("trajectories"), "pilot trajectories")
    seen: set[str] = set()
    by_id: dict[str, Mapping[str, Any]] = {}
    axis_splits = {
        "schedule_template_id": {},
        "background_regime_id": {},
        "world_parameter_profile_id": {},
    }
    content_splits = {
        "background_content_hash": {},
        "world_parameter_content_hash": {},
    }
    target_schedule_content_splits: dict[str, str] = {}
    root = Path(corpus_dir)
    for value in rows:
        row = _require_mapping(value, "pilot row")
        if "outcome_family" in row:
            raise Phase2Error("self-certified outcome_family is forbidden in the pilot manifest")
        trajectory_id = str(row.get("trajectory_id", ""))
        if not trajectory_id or trajectory_id in seen:
            raise Phase2Error("trajectory IDs must be unique and non-empty")
        seen.add(trajectory_id)
        by_id[trajectory_id] = row
        split = str(row.get("split", ""))
        if split not in SPLITS:
            raise Phase2Error(f"unsupported split {split}")
        relative = Path(str(row.get("relative_path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise Phase2Error("trajectory relative_path must remain inside the corpus")
        trajectory_dir = root / relative
        if not trajectory_dir.is_dir():
            raise Phase2Error(f"missing trajectory directory {relative}")
        for axis in axis_splits:
            axis_value = str(row.get(axis, ""))
            if not axis_value:
                raise Phase2Error(f"{trajectory_id} missing {axis}")
            previous = axis_splits[axis].setdefault(axis_value, split)
            if previous != split:
                raise Phase2Error(f"OOD axis overlap: {axis}={axis_value}")
        for content_axis in content_splits:
            content_value = str(row.get(content_axis, ""))
            if not content_value:
                raise Phase2Error(f"{trajectory_id} missing {content_axis}")
            previous = content_splits[content_axis].setdefault(content_value, split)
            if previous != split:
                raise Phase2Error(f"OOD content overlap: {content_axis}={content_value}")
        if bool(row.get("include_in_outcome_coverage")):
            schedule_hash = str(row.get("schedule_content_hash", ""))
            if not schedule_hash:
                raise Phase2Error(f"{trajectory_id} missing schedule_content_hash")
            previous = target_schedule_content_splits.setdefault(schedule_hash, split)
            if previous != split:
                raise Phase2Error(
                    f"OOD content overlap: schedule_content_hash={schedule_hash}"
                )
        if check_state_hashes:
            actual_hash, count = _state_chain_hash(trajectory_dir)
            if actual_hash != row.get("raw_state_chain_hash"):
                raise Phase2Error(f"raw state hash mismatch for {trajectory_id}")
            if count != int(row.get("state_count", -1)):
                raise Phase2Error(f"raw state count mismatch for {trajectory_id}")
    for row in rows:
        reference_id = str(row.get("reference_trajectory_id", ""))
        if reference_id not in by_id:
            raise Phase2Error(f"missing stable reference {reference_id}")
        reference = by_id[reference_id]
        for field in (
            "split",
            "seed",
            "background_regime_id",
            "background_content_hash",
            "world_parameter_profile_id",
            "world_parameter_content_hash",
        ):
            if row.get(field) != reference.get(field):
                raise Phase2Error(
                    f"{row['trajectory_id']} reference mismatch for {field}"
                )
        if reference.get("is_stable_reference") is not True:
            raise Phase2Error("reference_trajectory_id must point to a stable reference")
    return {
        "status": "valid",
        "trajectory_count": len(rows),
        "target_count": sum(bool(row.get("include_in_outcome_coverage")) for row in rows),
        "reference_count": sum(bool(row.get("is_stable_reference")) for row in rows),
        "ood_axis_check": "passed",
        "raw_state_hash_check": "passed" if check_state_hashes else "not_run",
    }


def _raw_state_metrics(
    trajectory_dir: str | Path,
    config: Mapping[str, Any],
) -> list[dict[str, float]]:
    directory = Path(trajectory_dir)
    truth = config["raw_truth_contract"]
    required = set(truth["required_state_arrays"])
    expected_shape = tuple(int(value) for value in truth["expected_state_shape"])
    mass_tolerance = float(truth["mass_tolerance"])
    negative_tolerance = float(truth["negative_mass_tolerance"])
    weights = truth["risk_score_weights"]
    state_files = sorted((directory / "states").glob("step_*.npz"))
    if not state_files:
        raise Phase2Error(f"{directory} has no state files")
    metrics: list[dict[str, float]] = []
    for expected_step, path in enumerate(state_files):
        if path.name != f"step_{expected_step:06d}.npz":
            raise Phase2Error(f"non-contiguous raw state files in {directory}")
        with np.load(path, allow_pickle=False) as bundle:
            missing = sorted(required - set(bundle.files))
            if missing:
                raise Phase2Error(f"{path} missing raw arrays: {missing}")
            arrays = {name: np.asarray(bundle[name], dtype=np.float64) for name in required}
        for name, array in arrays.items():
            if array.shape != expected_shape:
                raise Phase2Error(f"{path}:{name} shape mismatch")
            if not np.all(np.isfinite(array)):
                raise Phase2Error(f"{path}:{name} contains non-finite values")
        distribution = arrays["distribution"]
        if float(distribution.min()) < -negative_tolerance:
            raise Phase2Error(f"{path}:distribution contains negative mass")
        if abs(float(distribution.sum()) - 1.0) > mass_tolerance:
            raise Phase2Error(f"{path}:distribution mass mismatch")

        def weighted(name: str) -> float:
            return float(np.sum(distribution * arrays[name]))

        weighted_values = {
            "damage": weighted("damage"),
            "rigidity": weighted("rigidity"),
            "friction": weighted("friction"),
            "viscosity": weighted("viscosity"),
            "recovery_speed": weighted("recovery_speed"),
            "route_support": weighted("route_support"),
            "viability_reserve": weighted("viability_reserve"),
            "negative_viability_pressure": weighted("negative_viability_pressure"),
        }
        risk = (
            float(weights["damage"]) * weighted_values["damage"]
            + float(weights["rigidity"]) * weighted_values["rigidity"]
            + float(weights["friction"]) * weighted_values["friction"]
            + float(weights["viscosity"]) * weighted_values["viscosity"]
            + float(weights["one_minus_recovery_speed"])
            * (1.0 - weighted_values["recovery_speed"])
            + float(weights["one_minus_route_support"])
            * (1.0 - weighted_values["route_support"])
            + float(weights["one_minus_viability_reserve"])
            * (1.0 - weighted_values["viability_reserve"])
            + float(weights["negative_viability_pressure"])
            * weighted_values["negative_viability_pressure"]
        )
        metrics.append(
            {
                "step": float(expected_step),
                "risk_score": float(risk),
                "concentration": float(np.sum(distribution**2)),
                "moved_mass": float(np.sum(arrays["last_flow"])),
                "weighted_rigidity": weighted_values["rigidity"],
            }
        )
    return metrics


def _first_sustained(
    values: Sequence[float],
    predicate: Any,
    length: int,
    *,
    start: int = 0,
) -> int | None:
    run = 0
    for index in range(start, len(values)):
        run = run + 1 if bool(predicate(values[index])) else 0
        if run >= length:
            return index - length + 1
    return None


def classify_relative_metrics(
    metrics: Sequence[Mapping[str, float]],
    reference_metrics: Sequence[Mapping[str, float]],
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    if not metrics or len(metrics) != len(reference_metrics):
        raise Phase2Error("target and stable reference metrics must have equal non-zero length")
    risk = np.asarray([row["risk_score"] for row in metrics], dtype=np.float64)
    reference_risk = np.asarray(
        [row["risk_score"] for row in reference_metrics], dtype=np.float64
    )
    relative = risk - reference_risk
    concentration = np.asarray([row["concentration"] for row in metrics], dtype=np.float64)
    reference_concentration = np.asarray(
        [row["concentration"] for row in reference_metrics], dtype=np.float64
    )
    mobility = np.asarray([row["moved_mass"] for row in metrics], dtype=np.float64)
    reference_mobility = np.asarray(
        [row["moved_mass"] for row in reference_metrics], dtype=np.float64
    )
    rigidity = np.asarray([row["weighted_rigidity"] for row in metrics], dtype=np.float64)
    reference_rigidity = np.asarray(
        [row["weighted_rigidity"] for row in reference_metrics], dtype=np.float64
    )
    baseline_count = min(int(rules["baseline_steps"]), len(relative))
    tail_count = min(int(rules["tail_steps"]), len(relative))
    baseline = float(np.mean(relative[:baseline_count]))
    threshold = baseline + float(rules["elevated_relative_risk_delta"])
    onset = _first_sustained(
        relative,
        lambda value: value >= threshold,
        int(rules["hazard_sustained_steps"]),
    )
    peak_step = int(np.argmax(relative))
    peak = float(relative[peak_step])
    tail = float(np.mean(relative[-tail_count:]))
    absolute_tail = float(np.mean(risk[-tail_count:]))
    recovery_search_start = (
        min(len(relative), int(onset) + int(rules["hazard_sustained_steps"]))
        if onset is not None
        else min(len(relative), peak_step + 1)
    )
    recovery_step = _first_sustained(
        relative,
        lambda value: value <= baseline + float(rules["recovery_tolerance"]),
        int(rules["recovery_sustained_steps"]),
        start=recovery_search_start,
    )
    first_episode_peak_step = (
        int(onset)
        + int(np.argmax(relative[int(onset) : recovery_step]))
        if onset is not None and recovery_step is not None and recovery_step > int(onset)
        else peak_step
    )
    relapse_step: int | None = None
    if recovery_step is not None:
        relapse_step = _first_sustained(
            relative,
            lambda value: value >= threshold,
            int(rules["hazard_sustained_steps"]),
            start=min(
                len(relative),
                recovery_step + int(rules["relapse_minimum_gap_steps"]),
            ),
        )
    peak_elevation = peak - baseline
    recovered_fraction = (
        float(np.clip((peak - tail) / peak_elevation, -1.0, 1.0))
        if peak_elevation > 1e-12
        else 0.0
    )
    concentration_ratio = float(
        np.mean(concentration[-tail_count:])
        / max(float(np.mean(reference_concentration[-tail_count:])), 1e-12)
    )
    mobility_ratio = float(
        np.mean(mobility[-tail_count:])
        / max(
            float(np.mean(reference_mobility[-tail_count:])),
            float(rules["mobility_floor"]),
        )
    )
    rigidity_delta = float(np.mean((rigidity - reference_rigidity)[-tail_count:]))
    collapse = (
        absolute_tail >= float(rules["collapse_absolute_tail_risk"])
        and tail >= float(rules["collapse_relative_tail_risk"])
    )
    fixation = (
        onset is not None
        and concentration_ratio >= float(rules["fixation_concentration_ratio"])
        and mobility_ratio <= float(rules["fixation_mobility_ratio"])
        and rigidity_delta >= float(rules["fixation_rigidity_delta"])
    )
    recovery_delay = (
        None if recovery_step is None else int(recovery_step - first_episode_peak_step)
    )

    if collapse:
        outcome = "collapse_candidate"
    elif fixation:
        outcome = "fixation_candidate"
    elif relapse_step is not None:
        outcome = "relapse"
    elif onset is None:
        outcome = "safe_continuation"
    elif recovery_step is not None and recovered_fraction >= float(
        rules["full_recovery_fraction_minimum"]
    ):
        outcome = (
            "full_recovery"
            if recovery_delay is not None
            and recovery_delay <= int(rules["full_recovery_maximum_delay_steps"])
            else "delayed_recovery"
        )
    elif recovered_fraction >= float(rules["partial_recovery_fraction_minimum"]):
        outcome = "partial_recovery"
    elif tail >= threshold:
        outcome = "persistent_deterioration"
    else:
        outcome = "unresolved"

    tail_window = relative[-tail_count:]
    slope = float(np.polyfit(np.arange(len(tail_window)), tail_window, 1)[0]) if len(tail_window) > 1 else 0.0
    tolerance = float(rules["direction_slope_tolerance"])
    direction = "worsening" if slope > tolerance else "recovering" if slope < -tolerance else "neutral"
    persistence = outcome in {
        "relapse",
        "persistent_deterioration",
        "fixation_candidate",
        "collapse_candidate",
    }
    return {
        "observed_outcome_family": outcome,
        "hazard_onset_step": onset,
        "time_to_hazard_onset_from_start": onset,
        "maximum_relative_risk_depth": float(max(0.0, peak_elevation)),
        "risk_direction": direction,
        "persistence_or_recovery_difficulty_candidate": persistence,
        "peak_step": peak_step,
        "first_episode_peak_step": first_episode_peak_step,
        "recovery_step": recovery_step,
        "recovery_delay_steps": recovery_delay,
        "relapse_step": relapse_step,
        "relative_baseline_risk": baseline,
        "relative_tail_risk": tail,
        "absolute_tail_risk": absolute_tail,
        "peak_relative_risk": peak,
        "recovered_fraction": recovered_fraction,
        "concentration_ratio": concentration_ratio,
        "mobility_ratio": mobility_ratio,
        "rigidity_delta": rigidity_delta,
        "classification_source": "raw_state_arrays_only",
    }


def recompute_pilot_outcomes(
    corpus_dir: str | Path,
    manifest: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    # This function intentionally touches only the design manifest and states/*.npz.
    root = Path(corpus_dir)
    rows = list(manifest["trajectories"])
    by_id = {str(row["trajectory_id"]): row for row in rows}
    metric_cache: dict[str, list[dict[str, float]]] = {}

    def metrics_for(trajectory_id: str) -> list[dict[str, float]]:
        if trajectory_id not in metric_cache:
            row = by_id[trajectory_id]
            metric_cache[trajectory_id] = _raw_state_metrics(root / row["relative_path"], config)
        return metric_cache[trajectory_id]

    recomputed: list[dict[str, Any]] = []
    for design_row in sorted(rows, key=lambda row: str(row["trajectory_id"])):
        trajectory_id = str(design_row["trajectory_id"])
        reference_id = str(design_row["reference_trajectory_id"])
        outcome = classify_relative_metrics(
            metrics_for(trajectory_id),
            metrics_for(reference_id),
            config["raw_truth_contract"]["classification_rules"],
        )
        recomputed.append(
            {
                "trajectory_id": trajectory_id,
                "split": design_row["split"],
                "is_stable_reference": bool(design_row["is_stable_reference"]),
                "include_in_outcome_coverage": bool(
                    design_row["include_in_outcome_coverage"]
                ),
                "intended_outcome_family": design_row["intended_outcome_family"],
                "reference_trajectory_id": reference_id,
                "disturbance_family_id": design_row["disturbance_family_id"],
                "background_regime_id": design_row["background_regime_id"],
                "world_parameter_profile_id": design_row["world_parameter_profile_id"],
                "repetition": design_row["repetition"],
                "hard_case_tags": list(design_row["hard_case_tags"]),
                **outcome,
            }
        )
    return {
        "phase2_contract_hash": canonical_hash(config),
        "raw_files_used": ["states/step_*.npz"],
        "source_label_files_used": [],
        "rows": recomputed,
    }


def _coverage_audit(
    recomputed: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    required = list(config["coverage_contract"]["required_outcome_families"])
    minimums = config["coverage_contract"]["minimum_observed_per_outcome"]
    rows = [row for row in recomputed["rows"] if row["include_in_outcome_coverage"]]
    counts = {split: {family: 0 for family in required} for split in SPLITS}
    unresolved = {split: 0 for split in SPLITS}
    matrix = {
        split: {family: {observed: 0 for observed in [*required, "unresolved"]} for family in required}
        for split in SPLITS
    }
    for row in rows:
        split = str(row["split"])
        observed = str(row["observed_outcome_family"])
        intended = str(row["intended_outcome_family"])
        if observed in counts[split]:
            counts[split][observed] += 1
        else:
            unresolved[split] += 1
        matrix[split][intended][observed] += 1
    missing = {
        split: [
            family
            for family in required
            if counts[split][family] < int(minimums[split])
        ]
        for split in SPLITS
    }
    return {
        "independent_unit": "trajectory",
        "window_count_used_as_independent_sample": 0,
        "observed_outcome_counts": counts,
        "unresolved_counts": unresolved,
        "intended_to_observed_matrix": matrix,
        "minimum_required": minimums,
        "missing_observed_coverage": missing,
        "coverage_gate": all(not missing[split] for split in SPLITS),
    }


def _ood_audit(manifest: Mapping[str, Any]) -> dict[str, Any]:
    rows = manifest["trajectories"]
    axes = (
        "schedule_template_id",
        "background_regime_id",
        "world_parameter_profile_id",
    )
    content_axes = ("background_content_hash", "world_parameter_content_hash")
    details: dict[str, Any] = {}
    passed = True
    for axis in (*axes, *content_axes):
        values = {split: {str(row[axis]) for row in rows if row["split"] == split} for split in SPLITS}
        overlaps = []
        for index, left in enumerate(SPLITS):
            for right in SPLITS[index + 1 :]:
                common = sorted(values[left] & values[right])
                if common:
                    overlaps.append({"left": left, "right": right, "values": common})
        details[axis] = {"unique_counts": {split: len(values[split]) for split in SPLITS}, "overlaps": overlaps}
        passed = passed and not overlaps
    schedule_values = {
        split: {
            str(row["schedule_content_hash"])
            for row in rows
            if row["split"] == split and row["include_in_outcome_coverage"]
        }
        for split in SPLITS
    }
    schedule_overlaps = []
    for index, left in enumerate(SPLITS):
        for right in SPLITS[index + 1 :]:
            common = sorted(schedule_values[left] & schedule_values[right])
            if common:
                schedule_overlaps.append(
                    {"left": left, "right": right, "values": common}
                )
    details["target_schedule_content_hash"] = {
        "unique_counts": {
            split: len(schedule_values[split]) for split in SPLITS
        },
        "overlaps": schedule_overlaps,
        "stable_reference_zero_schedules_excluded": True,
    }
    passed = passed and not schedule_overlaps
    seed_values = {split: {int(row["seed"]) for row in rows if row["split"] == split} for split in SPLITS}
    seed_overlaps = []
    for index, left in enumerate(SPLITS):
        for right in SPLITS[index + 1 :]:
            common = sorted(seed_values[left] & seed_values[right])
            if common:
                seed_overlaps.append({"left": left, "right": right, "values": common})
    passed = passed and not seed_overlaps
    return {
        "axes": details,
        "seed_overlaps": seed_overlaps,
        "seed_only_split_accepted": False,
        "ood_gate": passed,
    }


def _same_current_pair_audit(
    corpus_dir: str | Path,
    manifest: Mapping[str, Any],
    recomputed: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(corpus_dir)
    outcome_by_id = {row["trajectory_id"]: row for row in recomputed["rows"]}
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in manifest["trajectories"]:
        if row.get("pair_instance_id"):
            groups.setdefault(str(row["pair_instance_id"]), []).append(row)
    audits: list[dict[str, Any]] = []
    identity_gate = True
    opposite_count = 0
    for pair_id, rows in sorted(groups.items()):
        if len(rows) != 2:
            raise Phase2Error(f"same-current pair {pair_id} must contain exactly two trajectories")
        cutoffs = {int(row["pair_cutoff_step"]) for row in rows}
        if len(cutoffs) != 1:
            raise Phase2Error(f"same-current pair {pair_id} cutoff mismatch")
        cutoff = next(iter(cutoffs))
        hashes = {
            row["trajectory_id"]: _state_content_hash(
                root / row["relative_path"] / "states" / f"step_{cutoff:06d}.npz"
            )
            for row in rows
        }
        identical = len(set(hashes.values())) == 1
        identity_gate = identity_gate and identical
        observed = {
            row["pair_role"]: outcome_by_id[row["trajectory_id"]]["observed_outcome_family"]
            for row in rows
        }
        opposite = len(set(observed.values())) == 2
        opposite_count += int(opposite)
        audits.append(
            {
                "pair_instance_id": pair_id,
                "split": rows[0]["split"],
                "cutoff_step": cutoff,
                "state_hashes": hashes,
                "same_current_state": identical,
                "observed_outcomes": observed,
                "opposite_future_observed": opposite,
            }
        )
    return {
        "pair_count": len(audits),
        "pairs": audits,
        "same_current_identity_gate": identity_gate and bool(audits),
        "opposite_future_pair_count": opposite_count,
        "opposite_future_observation_gate": opposite_count == len(audits) and bool(audits),
    }


def _hard_case_audit(
    manifest: Mapping[str, Any],
    recomputed: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    required_negative = list(config["coverage_contract"]["required_hard_negative_families"])
    required_positive = list(config["coverage_contract"]["required_hard_positive_families"])
    outcome_by_id = {row["trajectory_id"]: row for row in recomputed["rows"]}
    tag_rows: dict[str, list[dict[str, Any]]] = {tag: [] for tag in [*required_negative, *required_positive]}
    for row in manifest["trajectories"]:
        for tag in row["hard_case_tags"]:
            if tag in tag_rows:
                tag_rows[tag].append(
                    {
                        "trajectory_id": row["trajectory_id"],
                        "split": row["split"],
                        "observed_outcome_family": outcome_by_id[row["trajectory_id"]][
                            "observed_outcome_family"
                        ],
                    }
                )
    missing = sorted(tag for tag, rows in tag_rows.items() if not rows)
    # Fit repetitions deliberately apply the same disturbance family to a new
    # background/world group.  Whether the observed outcome changes is evidence,
    # not a forced pass condition.
    fit_by_family: dict[str, list[Mapping[str, Any]]] = {}
    for row in manifest["trajectories"]:
        if row["split"] == "fit" and row["include_in_outcome_coverage"]:
            fit_by_family.setdefault(str(row["disturbance_family_id"]), []).append(row)
    background_pairs: list[dict[str, Any]] = []
    for family, rows in sorted(fit_by_family.items()):
        if len(rows) < 2:
            continue
        unique_backgrounds = len({row["background_regime_id"] for row in rows})
        unique_outcomes = {
            outcome_by_id[row["trajectory_id"]]["observed_outcome_family"] for row in rows
        }
        background_pairs.append(
            {
                "disturbance_family_id": family,
                "background_regime_count": unique_backgrounds,
                "observed_outcomes": sorted(unique_outcomes),
                "different_background_outcome_observed": len(unique_outcomes) > 1,
            }
        )
    return {
        "hard_negative_families": required_negative,
        "hard_positive_families": required_positive,
        "tagged_trajectories": tag_rows,
        "missing_design_tags": missing,
        "hard_case_design_gate": not missing,
        "same_disturbance_different_background_audit": background_pairs,
        "different_background_outcome_family_count": sum(
            int(row["different_background_outcome_observed"]) for row in background_pairs
        ),
    }


def _wilson(successes: int, total: int, confidence: float) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    z = statistics.NormalDist().inv_cdf(0.5 + confidence / 2.0)
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denominator
    radius = z * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total)) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def _prevalence_variance_audit(
    recomputed: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    settings = config["sample_size_audit"]
    design = config["pilot_design"]
    confidence = float(settings["wilson_confidence"])
    rows = [row for row in recomputed["rows"] if row["include_in_outcome_coverage"]]
    split_rows = {split: [row for row in rows if row["split"] == split] for split in SPLITS}
    outcome_prevalence: dict[str, Any] = {}
    for split in SPLITS:
        total = len(split_rows[split])
        outcome_prevalence[split] = {}
        for family in config["coverage_contract"]["required_outcome_families"]:
            count = sum(row["observed_outcome_family"] == family for row in split_rows[split])
            lower, upper = _wilson(count, total, confidence)
            outcome_prevalence[split][family] = {
                "count": count,
                "trajectory_count": total,
                "prevalence": count / total if total else None,
                "wilson_interval": [lower, upper],
            }

    support: dict[str, Any] = {}
    recommended_counts: list[int] = []
    for split in SPLITS:
        support[split] = {}
        for anchor in design["prediction_anchor_steps"]:
            support[split][str(anchor)] = {}
            for horizon in design["prediction_horizons"]:
                eligible = [
                    row
                    for row in split_rows[split]
                    if row["hazard_onset_step"] is None
                    or int(row["hazard_onset_step"]) > int(anchor)
                ]
                positives = sum(
                    row["hazard_onset_step"] is not None
                    and int(row["hazard_onset_step"]) <= int(anchor) + int(horizon)
                    for row in eligible
                )
                negatives = len(eligible) - positives
                lower, upper = _wilson(positives, len(eligible), confidence)
                recommendation = None
                if lower is not None and upper is not None and lower > 0.0 and upper < 1.0:
                    positive_n = math.ceil(
                        int(settings["minimum_positive_trajectories_per_horizon"]) / lower
                    )
                    negative_n = math.ceil(
                        int(settings["minimum_negative_trajectories_per_horizon"])
                        / (1.0 - upper)
                    )
                    recommendation = max(positive_n, negative_n)
                    recommended_counts.append(recommendation)
                support[split][str(anchor)][str(horizon)] = {
                    "eligible_trajectories": len(eligible),
                    "positive_trajectories": positives,
                    "negative_trajectories": negatives,
                    "prevalence": positives / len(eligible) if eligible else None,
                    "wilson_interval": [lower, upper],
                    "recommended_formal_trajectory_count": recommendation,
                }

    depths = np.asarray(
        [float(row["maximum_relative_risk_depth"]) for row in rows], dtype=np.float64
    )
    event_values = np.asarray(
        [row["hazard_onset_step"] is not None for row in rows], dtype=np.float64
    )
    rng = np.random.default_rng(int(settings["bootstrap_seed"]))
    repetitions = int(settings["bootstrap_repetitions"])
    depth_means: list[float] = []
    event_means: list[float] = []
    if len(rows):
        for _ in range(repetitions):
            indices = rng.integers(0, len(rows), size=len(rows))
            depth_means.append(float(np.mean(depths[indices])))
            event_means.append(float(np.mean(event_values[indices])))
    bootstrap = {
        "trajectory_count": len(rows),
        "maximum_relative_risk_depth_mean": float(np.mean(depths)) if len(depths) else None,
        "maximum_relative_risk_depth_variance": float(np.var(depths, ddof=1)) if len(depths) > 1 else None,
        "depth_mean_bootstrap_95_interval": (
            [float(np.quantile(depth_means, 0.025)), float(np.quantile(depth_means, 0.975))]
            if depth_means
            else [None, None]
        ),
        "hazard_trajectory_prevalence": float(np.mean(event_values)) if len(event_values) else None,
        "hazard_prevalence_bootstrap_95_interval": (
            [float(np.quantile(event_means, 0.025)), float(np.quantile(event_means, 0.975))]
            if event_means
            else [None, None]
        ),
        "bootstrap_unit": "trajectory",
        "bootstrap_repetitions": repetitions,
    }
    all_support_estimable = all(
        cell["recommended_formal_trajectory_count"] is not None
        for split in support.values()
        for anchor in split.values()
        for cell in anchor.values()
    )
    return {
        "independent_unit": "trajectory",
        "windows_are_not_independent_samples": True,
        "outcome_prevalence": outcome_prevalence,
        "anchor_horizon_support": support,
        "bootstrap": bootstrap,
        "all_anchor_horizon_counts_estimable": all_support_estimable,
        "maximum_recommended_formal_trajectory_count": max(recommended_counts)
        if recommended_counts
        else None,
        "formal_count_status": "recommendation_only_not_frozen",
    }


def _source_label_disagreement_audit(
    corpus_dir: str | Path,
    manifest: Mapping[str, Any],
    recomputed: Mapping[str, Any],
    frozen_recomputed_hash: str,
) -> dict[str, Any]:
    if canonical_hash(recomputed) != frozen_recomputed_hash:
        raise Phase2Error("recomputed outcome payload changed before source-label audit")
    root = Path(corpus_dir)
    outcome_by_id = {row["trajectory_id"]: row for row in recomputed["rows"]}
    source_mapping = {
        "stable": "safe_continuation",
        "natural_recovery": "full_recovery",
        "delayed_recovery": "delayed_recovery",
        "persistent_deterioration": "persistent_deterioration",
        "fixation_candidate": "fixation_candidate",
        "collapse_or_divergence_candidate": "collapse_candidate",
    }
    rows: list[dict[str, Any]] = []
    for design_row in manifest["trajectories"]:
        if not design_row["include_in_outcome_coverage"]:
            continue
        summary = _json_load(root / design_row["relative_path"] / "summary.json")
        source = str(summary["outcome"]["coarse_outcome"])
        mapped = source_mapping.get(source, "unmapped_source_label")
        observed = outcome_by_id[design_row["trajectory_id"]]["observed_outcome_family"]
        rows.append(
            {
                "trajectory_id": design_row["trajectory_id"],
                "source_provisional_label": source,
                "source_label_mapped_for_comparison": mapped,
                "recomputed_outcome_family": observed,
                "agrees": mapped == observed,
            }
        )
    return {
        "recomputed_outcome_hash_frozen_before_source_read": frozen_recomputed_hash,
        "source_labels_used_for_recomputation": False,
        "comparison_only": True,
        "agreement_count": sum(bool(row["agrees"]) for row in rows),
        "disagreement_count": sum(not bool(row["agrees"]) for row in rows),
        "rows": rows,
    }


def _build_audit_payloads(
    corpus_dir: str | Path,
    manifest: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    recomputed = recompute_pilot_outcomes(corpus_dir, manifest, config)
    recomputed_hash = canonical_hash(recomputed)
    coverage = _coverage_audit(recomputed, config)
    ood = _ood_audit(manifest)
    hard = _hard_case_audit(manifest, recomputed, config)
    pairs = _same_current_pair_audit(corpus_dir, manifest, recomputed)
    prevalence = _prevalence_variance_audit(recomputed, config)
    source_disagreement = _source_label_disagreement_audit(
        corpus_dir, manifest, recomputed, recomputed_hash
    )
    formal_ready = bool(
        coverage["coverage_gate"]
        and ood["ood_gate"]
        and hard["hard_case_design_gate"]
        and pairs["same_current_identity_gate"]
        and pairs["opposite_future_observation_gate"]
        and prevalence["all_anchor_horizon_counts_estimable"]
    )
    blockers: list[str] = []
    if not coverage["coverage_gate"]:
        blockers.append("observed_outcome_coverage_incomplete")
    if not ood["ood_gate"]:
        blockers.append("ood_axis_overlap")
    if not hard["hard_case_design_gate"]:
        blockers.append("hard_case_design_incomplete")
    if not pairs["same_current_identity_gate"]:
        blockers.append("same_current_prefix_identity_failed")
    if not pairs["opposite_future_observation_gate"]:
        blockers.append("same_current_opposite_future_not_observed_for_all_pairs")
    if not prevalence["all_anchor_horizon_counts_estimable"]:
        blockers.append("formal_sample_count_not_estimable_for_all_anchor_horizons")
    decision = {
        "task": "Task 3.2-3 Rev1 Phase 2",
        "audit_execution_gate": "passed",
        "formal_corpus_ready": formal_ready,
        "formal_sample_count_frozen": False,
        "formal_sample_count_recommendation": prevalence[
            "maximum_recommended_formal_trajectory_count"
        ],
        "blockers": blockers,
        "recomputed_outcome_hash": recomputed_hash,
        "pilot_may_be_reused_for_formal_modeling": False,
        "predictor_implemented_or_selected": False,
        "task4_or_task4_1_information_used": False,
        "scientific_claim": (
            "B_pilot_corpus_feasibility_supported"
            if formal_ready
            else "C_pilot_corpus_requires_redesign_before_formal_prediction"
        ),
    }
    outputs = config["outputs"]
    return {
        outputs["recomputed_outcomes"]: recomputed,
        outputs["coverage_audit"]: coverage,
        outputs["ood_audit"]: ood,
        outputs["hard_case_audit"]: hard,
        outputs["same_current_pair_audit"]: pairs,
        outputs["prevalence_variance_audit"]: prevalence,
        outputs["source_label_disagreement_audit"]: source_disagreement,
        outputs["phase2_decision"]: decision,
    }


def audit_pilot(
    corpus_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    config, _ = load_config(config_path)
    root = Path(corpus_dir)
    manifest = _json_load(root / config["outputs"]["pilot_manifest"])
    manifest_validation = validate_pilot_manifest(
        manifest, root, config, check_state_hashes=True
    )
    payloads = _build_audit_payloads(root, manifest, config)
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for filename, value in payloads.items():
        _json_dump(output / filename, value)
    artifact_manifest = _write_manifest(output)
    decision = payloads[config["outputs"]["phase2_decision"]]
    return {
        "status": "audited",
        "manifest_validation": manifest_validation,
        "formal_corpus_ready": decision["formal_corpus_ready"],
        "scientific_claim": decision["scientific_claim"],
        "blockers": decision["blockers"],
        "audit_manifest_file_count": artifact_manifest["file_count"],
    }


def validate_audit(
    corpus_dir: str | Path,
    audit_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    config, _ = load_config(config_path)
    root = Path(corpus_dir)
    audit = Path(audit_dir)
    manifest = _json_load(root / config["outputs"]["pilot_manifest"])
    manifest_validation = validate_pilot_manifest(
        manifest, root, config, check_state_hashes=True
    )
    expected = _build_audit_payloads(root, manifest, config)
    for filename, value in expected.items():
        if _json_load(audit / filename) != value:
            raise Phase2Error(f"persisted audit mismatch: {filename}")
    stored_manifest = _json_load(audit / config["outputs"]["audit_manifest"])
    actual_files = {
        path.relative_to(audit).as_posix(): path
        for path in sorted(audit.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    expected_rows = {row["path"]: row for row in stored_manifest["files"]}
    if set(actual_files) != set(expected_rows):
        raise Phase2Error("audit artifact manifest file set mismatch")
    for relative, path in actual_files.items():
        if _file_hash(path) != expected_rows[relative]["sha256"]:
            raise Phase2Error(f"audit artifact hash mismatch: {relative}")
    decision = expected[config["outputs"]["phase2_decision"]]
    if decision["audit_execution_gate"] != "passed":
        raise Phase2Error("Phase 2 execution gate did not pass")
    if decision["formal_sample_count_frozen"] is not False:
        raise Phase2Error("Phase 2 must not silently freeze a formal count")
    return {
        "status": "valid",
        "manifest_validation": manifest_validation,
        "recomputed_outcome_hash": decision["recomputed_outcome_hash"],
        "formal_corpus_ready": decision["formal_corpus_ready"],
        "scientific_claim": decision["scientific_claim"],
        "blockers": decision["blockers"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    contract = commands.add_parser("validate-contract")
    contract.add_argument("--config", default=str(DEFAULT_CONFIG))
    generate = commands.add_parser("generate")
    generate.add_argument("--output", required=True)
    generate.add_argument("--config", default=str(DEFAULT_CONFIG))
    audit = commands.add_parser("audit")
    audit.add_argument("--input", required=True)
    audit.add_argument("--output", required=True)
    audit.add_argument("--config", default=str(DEFAULT_CONFIG))
    validate = commands.add_parser("validate")
    validate.add_argument("--input", required=True)
    validate.add_argument("--audit", required=True)
    validate.add_argument("--config", default=str(DEFAULT_CONFIG))
    run = commands.add_parser("run")
    run.add_argument("--output", required=True)
    run.add_argument("--audit-output", required=True)
    run.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    if args.command == "validate-contract":
        config, phase1_config = load_config(args.config)
        result = validate_config(config, phase1_config)
    elif args.command == "generate":
        result = generate_pilot(args.output, args.config)
    elif args.command == "audit":
        result = audit_pilot(args.input, args.output, args.config)
    elif args.command == "validate":
        result = validate_audit(args.input, args.audit, args.config)
    else:
        generation = generate_pilot(args.output, args.config)
        audit_result = audit_pilot(args.output, args.audit_output, args.config)
        validation = validate_audit(args.output, args.audit_output, args.config)
        result = {"generation": generation, "audit": audit_result, "validation": validation}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_CONFIG",
    "Phase2Error",
    "audit_pilot",
    "canonical_hash",
    "classify_relative_metrics",
    "generate_pilot",
    "load_config",
    "recompute_pilot_outcomes",
    "validate_audit",
    "validate_config",
    "validate_pilot_manifest",
]
