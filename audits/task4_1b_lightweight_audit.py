"""Task 3.2-4.1b lightweight sensitivity and cause-separation audit.

The audit reuses the frozen Task 4.1 formal artifact, regenerates only the
source trajectory corpus, reads fit/validation states only, and runs at most
500 new counterfactual branches. It does not retrain predictors, replace the
formal truth, read holdout state files, write back source trajectories, update
the Parameter Box, or connect the Action Module.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT, ROOT / "scripts", ROOT / "audits"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import task3_2_4_1_structural_risk as t41  # noqa: E402

DEFAULT_CONFIG = ROOT / "audit_configs" / "task4_1b_lightweight_audit.json"
ALLOWED_DECISIONS = {
    "rev1_truth_definition_only",
    "rev1_branch_assumption_and_truth",
    "rev1_boundary_search_and_truth",
    "current_task4_1_usable_with_explicit_limits",
    "insufficient_evidence_for_rev1_scope",
}


class AuditError(ValueError):
    pass


def _json_load(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_dump(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        target.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if str(key) not in fields:
                fields.append(str(key))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _json_load(path)
    required = {
        "task_id",
        "base_task_config",
        "representative_selection",
        "continuation_conditions",
        "continuation_horizon_steps",
        "phase_b_replicates",
        "phase_c",
        "phase_d",
        "phase_e",
        "budget",
        "decision_thresholds",
        "boundaries",
    }
    missing = sorted(required - set(config))
    if missing:
        raise AuditError(f"Task 4.1b config missing {missing}")
    budget = config["budget"]
    planned = sum(int(budget[name]) for name in ("phase_b", "phase_c", "phase_d", "phase_e"))
    if planned > int(budget["absolute_maximum"]):
        raise AuditError("planned branch budget exceeds absolute maximum")
    if config["boundaries"].get("holdout_state_read") is not False:
        raise AuditError("holdout state read must remain forbidden")
    if int(config["representative_selection"]["group_size"]) != 6:
        raise AuditError("representative group size must remain six")
    return config


@dataclass
class BranchBudget:
    maximum: int
    used: int = 0

    def reserve(self, count: int) -> None:
        if count < 0:
            raise AuditError("branch reservation cannot be negative")
        if self.used + count > self.maximum:
            raise AuditError(
                f"Task 4.1b branch budget exceeded: {self.used + count} > {self.maximum}"
            )
        self.used += count


def _resolve_formal_root(path: str | Path) -> Path:
    root = Path(path)
    if (root / "summary.json").is_file():
        return root
    for candidate in sorted(root.rglob("summary.json")):
        if (candidate.parent / "shrinking_equilibrium_candidates.csv").is_file():
            return candidate.parent
    raise AuditError("Task 4.1 formal artifact root was not found")


def _add_candidate_labels(frame: pd.DataFrame, base_config: Mapping[str, Any]) -> pd.DataFrame:
    settings = base_config["structural_truth"]
    rows: list[dict[str, Any]] = []
    for _, group in frame.groupby("trajectory_id", sort=False):
        previous: Mapping[str, Any] | None = None
        for source in group.sort_values("snapshot_step").to_dict(orient="records"):
            row = dict(source)
            if previous is None:
                recovery_delta = escape_delta = irreversibility_delta = refixation_delta = 0.0
                r1 = r2 = r3 = 0
            else:
                evidence = [
                    float(row["escape_cost_delta"]) >= float(settings["shrinking_escape_cost_increase"]),
                    float(row["reachable_value_delta"]) <= -float(settings["shrinking_reachable_value_decline"]),
                    float(row["reachable_range_delta"]) <= -float(settings["shrinking_reachable_range_decline"]),
                    float(row["last_action_window_delta"]) <= -float(settings["shrinking_last_window_decline_steps"]),
                    float(row["maintenance_cost"]) > float(previous["maintenance_cost"]) + 0.01,
                ]
                recovery_delta = float(row["best_recovery_probability"]) - float(previous["best_recovery_probability"])
                escape_delta = float(row["escape_not_observed"]) - float(previous["escape_not_observed"])
                irreversibility_delta = float(row["provisional_irreversibility_level"]) - float(previous["provisional_irreversibility_level"])
                refixation_delta = float(row["refixation_probability"]) - float(previous["refixation_probability"])
                r1 = int(sum(bool(value) for value in evidence) >= int(settings["minimum_evidence_count"]))
                dangerous = (
                    recovery_delta < -1e-12
                    or float(row["last_action_window_delta"]) <= -float(settings["shrinking_last_window_decline_steps"])
                    or irreversibility_delta > 0.0
                    or escape_delta > 0.0
                    or refixation_delta > 0.0
                )
                r2 = int(r1 and dangerous)
                r3 = int(r1 and (irreversibility_delta > 0.0 or escape_delta > 0.0))
            row.update(
                {
                    "audit_recovery_probability_delta": recovery_delta,
                    "audit_escape_not_observed_delta": escape_delta,
                    "audit_irreversibility_delta": irreversibility_delta,
                    "audit_refixation_delta": refixation_delta,
                    "R0_current_shrinking": int(row["shrinking_equilibrium_candidate"]),
                    "R1_structural_contraction": r1,
                    "R2_dangerous_shrinking": r2,
                    "R3_irreversibility_progression": r3,
                }
            )
            rows.append(row)
            previous = row
    return pd.DataFrame(rows)


def _phase_a_tables(
    truth: pd.DataFrame,
    frontier: pd.DataFrame,
    base_config: Mapping[str, Any],
) -> tuple[pd.DataFrame, dict[str, list[dict[str, Any]]], dict[str, Any]]:
    audit = _add_candidate_labels(truth, base_config)
    labels = [
        "R0_current_shrinking",
        "R1_structural_contraction",
        "R2_dangerous_shrinking",
        "R3_irreversibility_progression",
    ]
    comparison = [
        {
            "candidate": name,
            "positive_count": int(audit[name].sum()),
            "positive_rate": float(audit[name].mean()),
        }
        for name in labels
    ]
    step_rows = [
        {
            "snapshot_step": int(step),
            "row_count": len(group),
            **{name: int(group[name].sum()) for name in labels},
        }
        for step, group in audit.groupby("snapshot_step", sort=True)
    ]
    scenario_rows = [
        {
            "scenario_id": scenario,
            "row_count": len(group),
            "escape_not_observed_count": int(group["escape_not_observed"].sum()),
            **{name: int(group[name].sum()) for name in labels},
        }
        for scenario, group in audit.groupby("scenario_id", sort=True)
    ]

    group_keys = ["trajectory_id", "scenario_id", "source_seed", "source_split", "snapshot_step"]
    metric_columns = [
        "mean_final_risk",
        "mean_final_current_value",
        "mean_final_route_support",
        "mean_final_recovery_speed",
        "mean_final_concentration",
    ]
    scale = np.asarray([0.2, 0.2, 0.2, 0.1, 0.01], dtype=np.float64)
    range_rows: list[dict[str, Any]] = []
    for key, group in frontier.groupby(group_keys, sort=False):
        matrix = group[metric_columns].to_numpy(dtype=np.float64) / scale
        distances = [
            float(np.linalg.norm(matrix[left] - matrix[right]))
            for left in range(len(matrix))
            for right in range(left + 1, len(matrix))
        ]
        geometric = float(np.mean(distances) if distances else 0.0)
        diversity = float(group.loc[group["recovery_probability"] > 0.0, "probe_family"].nunique() / 4.0)
        range_rows.append(
            {
                "trajectory_id": key[0],
                "scenario_id": key[1],
                "seed": int(key[2]),
                "split": key[3],
                "snapshot_step": int(key[4]),
                "geometric_outcome_spread": geometric,
                "successful_family_diversity": diversity,
                "reconstructed_reachable_range": geometric + diversity,
            }
        )
    range_frame = pd.DataFrame(range_rows).merge(
        audit[["trajectory_id", "snapshot_step", "reachable_range"]],
        on=["trajectory_id", "snapshot_step"],
        validate="one_to_one",
    )
    range_frame["reconstruction_error"] = (
        range_frame["reconstructed_reachable_range"] - range_frame["reachable_range"]
    ).abs()

    features = ["current_risk", "current_value", "maintenance_cost"]
    values = audit[features].to_numpy(dtype=np.float64)
    normalized = (values - values.mean(axis=0)) / np.where(values.std(axis=0) > 1e-12, values.std(axis=0), 1.0)
    pair_rows: list[dict[str, Any]] = []
    for left in range(len(audit)):
        for right in range(left + 1, len(audit)):
            a = audit.iloc[left]
            b = audit.iloc[right]
            if int(a["snapshot_step"]) != int(b["snapshot_step"]) or a["trajectory_id"] == b["trajectory_id"]:
                continue
            different = (
                int(a["escape_not_observed"]) != int(b["escape_not_observed"])
                or abs(int(a["provisional_irreversibility_level"]) - int(b["provisional_irreversibility_level"])) >= 2
                or abs(float(a["best_recovery_probability"]) - float(b["best_recovery_probability"])) >= 0.5
            )
            if different:
                pair_rows.append(
                    {
                        "left_trajectory_id": a["trajectory_id"],
                        "right_trajectory_id": b["trajectory_id"],
                        "snapshot_step": int(a["snapshot_step"]),
                        "current_state_distance": float(np.linalg.norm(normalized[left] - normalized[right])),
                        "left_escape_not_observed": int(a["escape_not_observed"]),
                        "right_escape_not_observed": int(b["escape_not_observed"]),
                        "left_irreversibility": int(a["provisional_irreversibility_level"]),
                        "right_irreversibility": int(b["provisional_irreversibility_level"]),
                    }
                )
    pair_rows.sort(key=lambda row: (row["current_state_distance"], row["left_trajectory_id"], row["right_trajectory_id"]))
    time_only = (audit["snapshot_step"].to_numpy(dtype=int) >= 28).astype(int)
    recovery = audit["best_recovery_probability"].to_numpy(dtype=float)
    refixation = audit["refixation_probability"].to_numpy(dtype=float)
    component_correlation = float(
        range_frame[["geometric_outcome_spread", "successful_family_diversity"]].corr().iloc[0, 1]
    )
    if not math.isfinite(component_correlation):
        component_correlation = 1.0
    diagnostics = {
        "row_count": len(audit),
        "time_only_step_ge_28_accuracy_for_R0": float(np.mean(time_only == audit["R0_current_shrinking"].to_numpy(dtype=int))),
        "escape_not_observed_count": int(audit["escape_not_observed"].sum()),
        "recovery_refixation_complement_rate": float(np.mean(np.isclose(recovery + refixation, 1.0, atol=1e-12))),
        "reachable_range_component_correlation": component_correlation,
        "reachable_range_max_reconstruction_error": float(range_frame["reconstruction_error"].max()),
    }
    tables = {
        "phase_a_relabel_comparison.csv": comparison,
        "phase_a_step_confounding.csv": step_rows,
        "phase_a_scenario_audit.csv": scenario_rows,
        "phase_a_reachable_range_decomposition.csv": range_frame.to_dict(orient="records"),
        "phase_a_matched_pairs.csv": pair_rows[:20],
    }
    return audit, tables, diagnostics


def _farthest_select(frame: pd.DataFrame, count: int, feature_columns: Sequence[str]) -> pd.DataFrame:
    if len(frame) < count:
        raise AuditError(f"representative group has {len(frame)} rows; {count} required")
    ordered = frame.sort_values(["trajectory_id", "snapshot_step"]).reset_index(drop=True)
    matrix = np.nan_to_num(ordered[list(feature_columns)].to_numpy(dtype=np.float64))
    matrix = (matrix - matrix.mean(axis=0)) / np.where(matrix.std(axis=0) > 1e-12, matrix.std(axis=0), 1.0)
    selected = [int(np.argmin(np.linalg.norm(matrix - matrix.mean(axis=0), axis=1)))]
    while len(selected) < count:
        distances = np.asarray(
            [min(float(np.linalg.norm(matrix[index] - matrix[pick])) for pick in selected) for index in range(len(matrix))]
        )
        distances[selected] = -1.0
        selected.append(int(np.argmax(distances)))
    return ordered.iloc[selected].copy()


def select_representatives(audit: pd.DataFrame, config: Mapping[str, Any]) -> pd.DataFrame:
    allowed = audit[audit["split"].isin(["fit", "validation"])].copy()
    if len(allowed) != len(audit):
        raise AuditError("Phase A input unexpectedly contains non-fit/validation rows")
    size = int(config["representative_selection"]["group_size"])
    features = list(config["representative_selection"]["feature_columns"])
    groups = [
        (
            "stable_structure",
            allowed[
                (allowed["escape_not_observed"] == 0)
                & (allowed["provisional_irreversibility_level"] == 0)
                & (allowed["last_action_window"] >= 8)
                & (allowed["best_recovery_probability"] >= 1.0 - 1e-12)
            ],
        ),
        (
            "boundary_transition",
            allowed[
                allowed["provisional_irreversibility_level"].between(1, 3)
                | allowed["last_action_window"].between(0, 7)
                | allowed["best_recovery_probability"].between(1e-12, 1.0 - 1e-12)
            ],
        ),
        (
            "escape_not_observed",
            allowed[(allowed["escape_not_observed"] == 1) | (allowed["provisional_irreversibility_level"] == 4)],
        ),
    ]
    pieces: list[pd.DataFrame] = []
    for name, candidates in groups:
        selected = _farthest_select(candidates, size, features)
        selected.insert(0, "audit_group", name)
        pieces.append(selected)
    result = pd.concat(pieces, ignore_index=True)
    expected = {"stable_structure": 6, "boundary_transition": 6, "escape_not_observed": 6}
    if len(result) != 18 or result.groupby("audit_group").size().to_dict() != expected:
        raise AuditError("representative 18-state contract failed")
    if not set(result["split"]).issubset({"fit", "validation"}):
        raise AuditError("holdout state entered representative selection")
    return result


def _steps(entry: t41.Entry) -> dict[int, dict[str, Any]]:
    return {int(row["step"]): row for row in t41._read_jsonl(entry.path / "steps.jsonl")}


def _input_at(rows: Mapping[int, Mapping[str, Any]], step: int) -> dict[str, float]:
    record = rows.get(int(step))
    if record is None:
        return t41._neutral_input()
    return {name: float(record["observed_external_input"].get(name, 0.0)) for name in t41.EXTERNAL_FIELDS}


def _schedule(
    condition: str,
    entry: t41.Entry,
    stable_entry: t41.Entry,
    record: Mapping[str, Any],
    horizon: int,
    base_config: Mapping[str, Any],
) -> list[dict[str, float]]:
    current = {name: float(record["observed_external_input"].get(name, 0.0)) for name in t41.EXTERNAL_FIELDS}
    neutral = t41._neutral_input()
    if condition == "C0_current_input_fixed_then_neutral":
        duration = int(base_config["branch_probe"]["action_duration_steps"])
        return [dict(current) for _ in range(duration)] + [dict(neutral) for _ in range(horizon - duration)]
    if condition == "C1_immediate_neutral":
        return [dict(neutral) for _ in range(horizon)]
    source_rows = _steps(entry)
    stable_rows = _steps(stable_entry)
    start = int(record["step"])
    if condition == "C2_original_future_replay":
        return [_input_at(source_rows, start + offset) for offset in range(horizon)]
    if condition == "C3_same_seed_stable_future_replay":
        return [_input_at(stable_rows, start + offset) for offset in range(horizon)]
    raise AuditError(f"unknown continuation condition {condition}")


def _outcome(
    entry: t41.Entry,
    record: Mapping[str, Any],
    safe: Mapping[str, Any],
    replicate: int,
    base_config: Mapping[str, Any],
    schedule: Sequence[Mapping[str, float]],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    world = t41._restore_world(entry, record, replicate, base_config)
    timeline = [t41._metrics_from_world(world)]
    for external in schedule:
        world.set_external_factors(external)
        world.step()
        timeline.append(t41._metrics_from_world(world))
    flags = [t41.safe_state(row, safe) for row in timeline]
    first_safe = t41._first_sustained_safe(flags, int(safe["sustained_steps"]))
    final_safe = bool(all(flags[-int(safe["sustained_steps"]):]))
    ever_safe = first_safe is not None
    final = timeline[-1]
    return {
        "trajectory_id": entry.trajectory_id,
        "scenario_id": entry.scenario_id,
        "seed": entry.seed,
        "split": entry.split,
        "snapshot_step": int(record["step"]),
        "replicate": int(replicate),
        "recovered": int(final_safe),
        "ever_safe": int(ever_safe),
        "refixation": int(ever_safe and not final_safe),
        "first_sustained_safe_step": -1 if first_safe is None else int(first_safe),
        "peak_risk": float(max(row["risk_score"] for row in timeline)),
        "final_risk": float(final["risk_score"]),
        "final_current_value": float(final["current_value"]),
        "final_route_support": float(final["weighted_route_support"]),
        "final_recovery_speed": float(final["weighted_recovery_speed"]),
        "source_trajectory_writeback": 0,
        "parameter_box_write": 0,
        "action_module_connection": 0,
        **dict(metadata),
    }


def _entry_record(
    state: Mapping[str, Any], entries: Mapping[str, t41.Entry], base_config: Mapping[str, Any]
) -> tuple[t41.Entry, dict[str, Any]]:
    entry = entries[str(state["trajectory_id"])]
    records = {int(row["step"]): row for row in t41.snapshot_records(entry, base_config)}
    step = int(state["snapshot_step"])
    if step not in records:
        raise AuditError(f"snapshot {entry.trajectory_id}@{step} not found")
    return entry, records[step]


def run_phase_b(
    representatives: pd.DataFrame,
    entries: Mapping[str, t41.Entry],
    stable_by_seed: Mapping[int, t41.Entry],
    safe: Mapping[str, Any],
    config: Mapping[str, Any],
    base_config: Mapping[str, Any],
    budget: BranchBudget,
) -> list[dict[str, Any]]:
    conditions = list(config["continuation_conditions"])
    replicates = int(config["phase_b_replicates"])
    planned = len(representatives) * len(conditions) * replicates
    if planned != int(config["budget"]["phase_b"]):
        raise AuditError("Phase B planned branch count does not match frozen budget")
    budget.reserve(planned)
    rows: list[dict[str, Any]] = []
    horizon = int(config["continuation_horizon_steps"])
    for state in representatives.to_dict(orient="records"):
        entry, record = _entry_record(state, entries, base_config)
        for condition in conditions:
            branch_schedule = _schedule(
                condition, entry, stable_by_seed[entry.seed], record, horizon, base_config
            )
            for replicate in range(replicates):
                rows.append(
                    _outcome(
                        entry,
                        record,
                        safe,
                        replicate,
                        base_config,
                        branch_schedule,
                        {
                            "phase": "B",
                            "audit_group": state["audit_group"],
                            "continuation_condition": condition,
                            "runner_type": "continuation",
                        },
                    )
                )
    return rows


def _aggregate(rows: Sequence[Mapping[str, Any]], extra: Sequence[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    keys = ["trajectory_id", "snapshot_step", *extra]
    result = frame.groupby(keys, sort=False, dropna=False).agg(
        replicate_count=("recovered", "size"),
        recovery_rate=("recovered", "mean"),
        replicate_min=("recovered", "min"),
        replicate_max=("recovered", "max"),
        mean_peak_risk=("peak_risk", "mean"),
        mean_final_risk=("final_risk", "mean"),
        mean_final_current_value=("final_current_value", "mean"),
    ).reset_index()
    result["recovery_class"] = (result["recovery_rate"] >= 0.5).astype(int)
    result["replicate_disagreement"] = (result["replicate_min"] != result["replicate_max"]).astype(int)
    return result


def _phase_b_changes(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    aggregate = _aggregate(rows, ["continuation_condition"])
    pivot = aggregate.pivot_table(
        index=["trajectory_id", "snapshot_step"],
        columns="continuation_condition",
        values="recovery_class",
        aggfunc="first",
    ).reset_index()
    baseline = "C0_current_input_fixed_then_neutral"
    alternatives = [name for name in pivot.columns if isinstance(name, str) and name.startswith("C") and name != baseline]
    pivot["changed_from_C0"] = pivot.apply(
        lambda row: int(any(int(row[name]) != int(row[baseline]) for name in alternatives)), axis=1
    )
    return pivot


def _choose_p1(
    state: Mapping[str, Any], frontier: pd.DataFrame, base_config: Mapping[str, Any]
) -> tuple[str, float]:
    candidates = frontier[
        (frontier["trajectory_id"] == state["trajectory_id"])
        & (frontier["snapshot_step"] == int(state["snapshot_step"]))
        & (frontier["probe_family"] != "no_action")
    ].copy()
    threshold = float(base_config["structural_truth"]["recovery_probability_threshold"])
    successful = candidates[candidates["recovery_probability"] >= threshold]
    if not successful.empty:
        row = successful.sort_values(
            ["simultaneous_action_scale", "strength", "mean_escape_cost", "probe_family"]
        ).iloc[0]
        return str(row["probe_family"]), float(row["strength"])
    if not candidates.empty:
        row = candidates.sort_values(
            ["mean_final_risk", "simultaneous_action_scale", "strength", "probe_family"]
        ).iloc[0]
        return str(row["probe_family"]), float(row["strength"])
    return "resource_relief", 0.35


def _action_branch(
    entry: t41.Entry,
    record: Mapping[str, Any],
    safe: Mapping[str, Any],
    replicate: int,
    base_config: Mapping[str, Any],
    family: str,
    strength: float,
    delay: int,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    duration = int(base_config["branch_probe"]["action_duration_steps"])
    followup = int(safe["post_action_followup_steps"])
    rows = _steps(entry)
    start = int(record["step"])
    schedule: list[dict[str, float]] = []
    for offset in range(int(delay) + duration + followup):
        baseline = _input_at(rows, start + offset)
        schedule.append(
            t41.action_input(baseline, family, strength)
            if int(delay) <= offset < int(delay) + duration
            else baseline
        )
    return _outcome(
        entry,
        record,
        safe,
        replicate,
        base_config,
        schedule,
        {
            "runner_type": "action_original_future",
            "probe_family": family,
            "strength": float(strength),
            "delay_steps": int(delay),
            **dict(metadata),
        },
    )


def _phase_c_candidates(
    representatives: pd.DataFrame,
    changes: pd.DataFrame,
    phase_b_rows: Sequence[Mapping[str, Any]],
    frontier: pd.DataFrame,
) -> pd.DataFrame:
    changed = {
        (str(row["trajectory_id"]), int(row["snapshot_step"])): int(row["changed_from_C0"])
        for row in changes.to_dict(orient="records")
    }
    aggregate = _aggregate(phase_b_rows, ["continuation_condition"])
    regained: set[tuple[str, int]] = set()
    for key, group in aggregate.groupby(["trajectory_id", "snapshot_step"]):
        c0 = group[group["continuation_condition"] == "C0_current_input_fixed_then_neutral"]
        alternatives = group[group["continuation_condition"] != "C0_current_input_fixed_then_neutral"]
        if not c0.empty and int(c0.iloc[0]["recovery_class"]) == 0 and int(alternatives["recovery_class"].max()) == 1:
            regained.add((str(key[0]), int(key[1])))
    mixed: set[tuple[str, int]] = set()
    for key, group in frontier.groupby(["trajectory_id", "snapshot_step"]):
        if (group["recovery_probability"] >= 0.5).astype(int).nunique() > 1:
            mixed.add((str(key[0]), int(key[1])))
    rows: list[dict[str, Any]] = []
    for state in representatives.to_dict(orient="records"):
        key = (str(state["trajectory_id"]), int(state["snapshot_step"]))
        flags = [changed.get(key, 0), int(key in mixed), int(key in regained)]
        if any(flags):
            rows.append(
                {
                    **state,
                    "trigger_continuation_change": flags[0],
                    "trigger_existing_mixed_success": flags[1],
                    "trigger_recovery_regained": flags[2],
                    "trigger_count": sum(flags),
                }
            )
    return pd.DataFrame(rows)


def run_phase_c(
    candidates: pd.DataFrame,
    frontier: pd.DataFrame,
    entries: Mapping[str, t41.Entry],
    safe: Mapping[str, Any],
    config: Mapping[str, Any],
    base_config: Mapping[str, Any],
    budget: BranchBudget,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    if candidates.empty:
        return [], candidates
    selected = candidates.sort_values(
        ["trigger_count", "trajectory_id", "snapshot_step"], ascending=[False, True, True]
    ).head(int(config["phase_c"]["maximum_states"])).copy()
    rows: list[dict[str, Any]] = []
    delays = [int(value) for value in config["phase_c"]["delays"]]
    replicates = int(config["phase_c"]["replicates"])
    for state in selected.to_dict(orient="records"):
        entry, record = _entry_record(state, entries, base_config)
        p1_family, p1_strength = _choose_p1(state, frontier, base_config)
        probes = [
            ("P1_existing_lowest_scale", p1_family, p1_strength),
            ("P2_combined_medium", "combined_relief", 0.7),
            ("P3_combined_strong", "combined_relief", 1.0),
        ]
        for label, family, strength in probes:
            for delay in delays:
                budget.reserve(replicates)
                for replicate in range(replicates):
                    rows.append(
                        _action_branch(
                            entry,
                            record,
                            safe,
                            replicate,
                            base_config,
                            family,
                            strength,
                            delay,
                            {"phase": "C", "probe_label": label},
                        )
                    )
    return rows, selected


def _boundary_specs(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not rows:
        return []
    aggregate = _aggregate(rows, ["probe_label", "probe_family", "strength", "delay_steps"])
    candidates: list[dict[str, Any]] = []
    for key, group in aggregate.groupby(
        ["trajectory_id", "snapshot_step", "probe_label", "probe_family", "strength"]
    ):
        classes = {int(row["delay_steps"]): int(row["recovery_class"]) for row in group.to_dict(orient="records")}
        if 0 in classes and 4 in classes and classes[0] != classes[4]:
            candidates.append(
                {
                    "trajectory_id": key[0],
                    "snapshot_step": int(key[1]),
                    "boundary_type": "delay",
                    "probe_label": key[2],
                    "probe_family": key[3],
                    "strength": float(key[4]),
                    "low": 0.0,
                    "high": 4.0,
                    "low_class": classes[0],
                    "high_class": classes[4],
                }
            )
    combined = aggregate[aggregate["probe_label"].isin(["P2_combined_medium", "P3_combined_strong"])]
    for key, group in combined.groupby(["trajectory_id", "snapshot_step", "delay_steps"]):
        classes = {round(float(row["strength"]), 6): int(row["recovery_class"]) for row in group.to_dict(orient="records")}
        if 0.7 in classes and 1.0 in classes and classes[0.7] != classes[1.0]:
            candidates.append(
                {
                    "trajectory_id": key[0],
                    "snapshot_step": int(key[1]),
                    "boundary_type": "strength",
                    "probe_label": "combined_strength_boundary",
                    "probe_family": "combined_relief",
                    "delay_steps": int(key[2]),
                    "low": 0.7,
                    "high": 1.0,
                    "low_class": classes[0.7],
                    "high_class": classes[1.0],
                }
            )
    selected: list[dict[str, Any]] = []
    state_counts: dict[tuple[str, int], int] = {}
    states: list[tuple[str, int]] = []
    for row in sorted(candidates, key=lambda value: (value["trajectory_id"], value["snapshot_step"], value["boundary_type"])):
        key = (str(row["trajectory_id"]), int(row["snapshot_step"]))
        if key not in states and len(states) >= int(config["phase_d"]["maximum_states"]):
            continue
        if state_counts.get(key, 0) >= int(config["phase_d"]["maximum_boundaries_per_state"]):
            continue
        if key not in states:
            states.append(key)
        state_counts[key] = state_counts.get(key, 0) + 1
        selected.append(row)
    return selected


def run_phase_d(
    specs: Sequence[Mapping[str, Any]],
    entries: Mapping[str, t41.Entry],
    safe: Mapping[str, Any],
    config: Mapping[str, Any],
    base_config: Mapping[str, Any],
    budget: BranchBudget,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    replicates = int(config["phase_d"]["replicates"])
    for index, source in enumerate(specs):
        spec = dict(source)
        entry = entries[str(spec["trajectory_id"])]
        record = {int(row["step"]): row for row in t41.snapshot_records(entry, base_config)}[int(spec["snapshot_step"])]
        low, high = float(spec["low"]), float(spec["high"])
        low_class, high_class = int(spec["low_class"]), int(spec["high_class"])
        tried: set[float] = set()
        for refinement in range(int(config["phase_d"]["maximum_refinements"])):
            if spec["boundary_type"] == "delay":
                midpoint = float(int(round((low + high) / 2.0)))
                if midpoint <= low or midpoint >= high or midpoint in tried:
                    break
                family, strength, delay = str(spec["probe_family"]), float(spec["strength"]), int(midpoint)
            else:
                midpoint = round((low + high) / 2.0, 6)
                if midpoint <= low + 1e-9 or midpoint >= high - 1e-9 or midpoint in tried:
                    break
                family, strength, delay = "combined_relief", midpoint, int(spec["delay_steps"])
            tried.add(midpoint)
            budget.reserve(replicates)
            branch_rows = [
                _action_branch(
                    entry,
                    record,
                    safe,
                    replicate,
                    base_config,
                    family,
                    strength,
                    delay,
                    {
                        "phase": "D",
                        "probe_label": str(spec["probe_label"]),
                        "boundary_id": f"boundary_{index:02d}",
                        "boundary_type": spec["boundary_type"],
                        "refinement": refinement + 1,
                        "boundary_midpoint": midpoint,
                    },
                )
                for replicate in range(replicates)
            ]
            rows.extend(branch_rows)
            values = [int(row["recovered"]) for row in branch_rows]
            if min(values) != max(values):
                break
            midpoint_class = int(np.mean(values) >= 0.5)
            if midpoint_class == low_class:
                low, low_class = midpoint, midpoint_class
            elif midpoint_class == high_class:
                high, high_class = midpoint, midpoint_class
            else:
                break
            if high - low <= (float(spec["high"]) - float(spec["low"])) * 0.5:
                break
    return rows


def _disagreements(
    phase_b: Sequence[Mapping[str, Any]],
    phase_c: Sequence[Mapping[str, Any]],
    phase_d: Sequence[Mapping[str, Any]],
    maximum: int,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    if phase_b:
        for row in _aggregate(phase_b, ["continuation_condition"]).query("replicate_disagreement == 1").to_dict(orient="records"):
            cases.append({"runner_type": "continuation", **row})
    for name, rows in (("C", phase_c), ("D", phase_d)):
        if not rows:
            continue
        extras = ["probe_label", "probe_family", "strength", "delay_steps"]
        if name == "D":
            extras += ["boundary_id", "boundary_type", "boundary_midpoint"]
        for row in _aggregate(rows, extras).query("replicate_disagreement == 1").to_dict(orient="records"):
            cases.append({"runner_type": "action_original_future", **row})
    cases.sort(key=lambda row: (row["trajectory_id"], int(row["snapshot_step"]), row["runner_type"]))
    return cases[:maximum]


def run_phase_e(
    cases: Sequence[Mapping[str, Any]],
    entries: Mapping[str, t41.Entry],
    stable_by_seed: Mapping[int, t41.Entry],
    safe: Mapping[str, Any],
    config: Mapping[str, Any],
    base_config: Mapping[str, Any],
    budget: BranchBudget,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    extra = int(config["phase_e"]["additional_replicates_per_case"])
    horizon = int(config["continuation_horizon_steps"])
    for case_index, case in enumerate(cases):
        entry = entries[str(case["trajectory_id"])]
        record = {int(row["step"]): row for row in t41.snapshot_records(entry, base_config)}[int(case["snapshot_step"])]
        budget.reserve(extra)
        for replicate in range(2, 2 + extra):
            if case["runner_type"] == "continuation":
                rows.append(
                    _outcome(
                        entry,
                        record,
                        safe,
                        replicate,
                        base_config,
                        _schedule(
                            str(case["continuation_condition"]),
                            entry,
                            stable_by_seed[entry.seed],
                            record,
                            horizon,
                            base_config,
                        ),
                        {
                            "phase": "E",
                            "case_id": f"case_{case_index:02d}",
                            "runner_type": "continuation",
                            "continuation_condition": case["continuation_condition"],
                        },
                    )
                )
            else:
                rows.append(
                    _action_branch(
                        entry,
                        record,
                        safe,
                        replicate,
                        base_config,
                        str(case["probe_family"]),
                        float(case["strength"]),
                        int(case["delay_steps"]),
                        {
                            "phase": "E",
                            "case_id": f"case_{case_index:02d}",
                            "probe_label": case.get("probe_label", "boundary_replicate"),
                        },
                    )
                )
    return rows


def _decisions(
    audit: pd.DataFrame,
    phase_a: Mapping[str, Any],
    changes: pd.DataFrame,
    phase_c_rows: Sequence[Mapping[str, Any]],
    boundary_specs: Sequence[Mapping[str, Any]],
    phase_e_cases: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    threshold = config["decision_thresholds"]
    stable = audit[audit["scenario_id"] == "stable_continuation"]
    h1 = int(stable["R0_current_shrinking"].sum()) > 0 and int(stable["R2_dangerous_shrinking"].sum()) <= max(1, int(stable["R0_current_shrinking"].sum()) // 4)
    changed = int(changes["changed_from_C0"].sum())
    h2 = changed >= int(threshold["continuation_changed_state_count"])
    h3 = int(phase_a["escape_not_observed_count"]) > 0
    h4 = len(boundary_specs) > 0
    h5 = len(phase_e_cases) > 0
    h6 = float(phase_a["recovery_refixation_complement_rate"]) >= float(threshold["redundancy_complement_rate"])
    h7 = abs(float(phase_a["reachable_range_component_correlation"])) < float(threshold["range_component_correlation"])
    h8 = float(phase_a["time_only_step_ge_28_accuracy_for_R0"]) >= float(threshold["time_only_accuracy"])
    decisions = [
        {"hypothesis": "H1_split_structural_and_dangerous_shrinking", "decision": "adopt" if h1 else "retain_for_review", "evidence": f"stable R0={int(stable['R0_current_shrinking'].sum())}, R2={int(stable['R2_dangerous_shrinking'].sum())}"},
        {"hypothesis": "H2_multiple_continuation_assumptions", "decision": "adopt" if h2 else "not_required_by_current_sample", "evidence": f"changed states={changed}"},
        {"hypothesis": "H3_separate_escape_observed_and_conditional_cost", "decision": "adopt" if h3 else "not_required_by_current_sample", "evidence": f"escape not observed={int(phase_a['escape_not_observed_count'])}"},
        {"hypothesis": "H4_adaptive_boundary_search", "decision": "adopt" if h4 else "not_required_by_current_sample", "evidence": f"phase C branches={len(phase_c_rows)}, boundary specs={len(boundary_specs)}"},
        {"hypothesis": "H5_probability_only_at_stochastic_boundaries", "decision": "conditional" if h5 else "rename_as_success_indicator", "evidence": f"replicate-disagreement cases={len(phase_e_cases)}"},
        {"hypothesis": "H6_recovery_and_refixation_target_separation", "decision": "adopt" if h6 else "retain_both", "evidence": f"complement rate={float(phase_a['recovery_refixation_complement_rate']):.6f}"},
        {"hypothesis": "H7_split_reachable_range_components", "decision": "adopt" if h7 else "retain_combined_with_explicit_semantics", "evidence": f"component correlation={float(phase_a['reachable_range_component_correlation']):.6f}"},
        {"hypothesis": "H8_remove_time_confounding_from_truth_claim", "decision": "adopt" if h8 else "monitor", "evidence": f"time-only accuracy={float(phase_a['time_only_step_ge_28_accuracy_for_R0']):.6f}"},
    ]
    if h4:
        final = "rev1_boundary_search_and_truth"
    elif h2:
        final = "rev1_branch_assumption_and_truth"
    elif h1 or h3 or h6 or h7 or h8:
        final = "rev1_truth_definition_only"
    elif len(audit):
        final = "current_task4_1_usable_with_explicit_limits"
    else:
        final = "insufficient_evidence_for_rev1_scope"
    return decisions, final


def _write_manifest(root: Path) -> dict[str, Any]:
    files = [
        {
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    manifest = {
        "file_count": len(files),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in files),
        "files": files,
    }
    _json_dump(root / "manifest.json", manifest)
    return manifest


def _validate_manifest(root: Path) -> dict[str, Any]:
    manifest = _json_load(root / "manifest.json")
    for row in manifest["files"]:
        path = root / row["path"]
        if not path.is_file() or path.stat().st_size != int(row["size_bytes"]) or _file_sha256(path) != row["sha256"]:
            raise AuditError(f"manifest mismatch: {row['path']}")
    return manifest


def _validate_selection_lock(path: Path) -> dict[str, Any]:
    lock = _json_load(path)
    claimed = lock.pop("lock_hash", None)
    if claimed != _canonical_hash(lock):
        raise AuditError("representative selection lock hash mismatch")
    rows = lock.get("representative_states", [])
    if lock.get("holdout_state_read") is not False or len(rows) != 18 or not all(row.get("split") in {"fit", "validation"} for row in rows):
        raise AuditError("representative selection lock does not contain 18 fit/validation states")
    return {**lock, "lock_hash": claimed}


def run(
    corpus_dir: str | Path,
    formal_artifact_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    config = load_config(config_path)
    base_path = ROOT / config["base_task_config"]
    base_config = t41.load_config(base_path)
    formal_root = _resolve_formal_root(formal_artifact_dir)
    formal_validation = t41.validate_output(formal_root, base_path)
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    truth_all = pd.read_csv(formal_root / "shrinking_equilibrium_candidates.csv")
    frontier_all = pd.read_csv(formal_root / "recovery_frontier.csv")
    truth = truth_all[truth_all["split"].isin(["fit", "validation"])].copy()
    frontier = frontier_all[frontier_all["source_split"].isin(["fit", "validation"])].copy()
    if len(truth) != 72:
        raise AuditError(f"expected 72 fit/validation truth rows, found {len(truth)}")

    audit, tables, phase_a = _phase_a_tables(truth, frontier, base_config)
    for name, rows in tables.items():
        _write_csv(output / name, rows)
    _write_csv(output / "phase_a_candidate_truth.csv", audit.to_dict(orient="records"))
    _json_dump(output / "phase_a_diagnostics.json", phase_a)

    representatives = select_representatives(audit, config)
    _write_csv(output / "representative_18_states.csv", representatives.to_dict(orient="records"))
    lock_body = {
        "task_id": config["task_id"],
        "status": "locked_before_new_branch_execution",
        "formal_artifact_manifest_sha256": _file_sha256(formal_root / "manifest.json"),
        "audit_config_hash": _canonical_hash(config),
        "selection_method": "structural criteria plus deterministic farthest-point selection",
        "scenario_id_used_for_selection": False,
        "holdout_state_read": False,
        "representative_states": [
            {
                "audit_group": row["audit_group"],
                "trajectory_id": row["trajectory_id"],
                "snapshot_step": int(row["snapshot_step"]),
                "split": row["split"],
            }
            for row in representatives.to_dict(orient="records")
        ],
    }
    lock = {**lock_body, "lock_hash": _canonical_hash(lock_body)}
    _json_dump(output / "representative_selection_lock.json", lock)
    _validate_selection_lock(output / "representative_selection_lock.json")

    index = t41.CorpusIndex(corpus_dir, base_config)
    fit_entries = index.entries_for("fit")
    validation_entries = index.entries_for("validation")
    allowed_entries = fit_entries + validation_entries
    entries = {entry.trajectory_id: entry for entry in allowed_entries}
    stable_by_seed = {entry.seed: entry for entry in allowed_entries if entry.scenario_id == "stable_continuation"}
    safe = t41.calibrate_safe_region(fit_entries, base_config)
    _json_dump(output / "safe_region_schema.json", safe)

    source_checks: list[dict[str, Any]] = []
    for state in representatives.to_dict(orient="records"):
        entry, record = _entry_record(state, entries, base_config)
        with np.load(entry.path / str(record["state_ref"]), allow_pickle=False) as bundle:
            metrics = t41._metrics_from_arrays(bundle)
        risk_error = abs(float(metrics["risk_score"]) - float(state["current_risk"]))
        value_error = abs(float(metrics["current_value"]) - float(state["current_value"]))
        if risk_error > 1e-8 or value_error > 1e-8:
            raise AuditError(f"regenerated corpus mismatch for {entry.trajectory_id}@{record['step']}")
        source_checks.append(
            {
                "trajectory_id": entry.trajectory_id,
                "snapshot_step": int(record["step"]),
                "risk_error": risk_error,
                "current_value_error": value_error,
                "split": entry.split,
            }
        )
    _write_csv(output / "source_snapshot_consistency.csv", source_checks)

    budget = BranchBudget(int(config["budget"]["absolute_maximum"]))
    phase_b_rows = run_phase_b(representatives, entries, stable_by_seed, safe, config, base_config, budget)
    _write_csv(output / "phase_b_continuation_branches.csv", phase_b_rows)
    phase_b_summary = _aggregate(phase_b_rows, ["continuation_condition"])
    _write_csv(output / "phase_b_continuation_summary.csv", phase_b_summary.to_dict(orient="records"))
    changes = _phase_b_changes(phase_b_rows)
    _write_csv(output / "phase_b_changed_states.csv", changes.to_dict(orient="records"))

    candidates = _phase_c_candidates(representatives, changes, phase_b_rows, frontier)
    _write_csv(output / "phase_c_candidate_states.csv", candidates.to_dict(orient="records"))
    phase_c_rows, phase_c_selected = run_phase_c(candidates, frontier, entries, safe, config, base_config, budget)
    _write_csv(output / "phase_c_selected_states.csv", phase_c_selected.to_dict(orient="records"))
    _write_csv(output / "phase_c_action_branches.csv", phase_c_rows)
    _write_csv(
        output / "phase_c_action_summary.csv",
        _aggregate(phase_c_rows, ["probe_label", "probe_family", "strength", "delay_steps"]).to_dict(orient="records") if phase_c_rows else [],
    )

    boundary_specs = _boundary_specs(phase_c_rows, config)
    _write_csv(output / "phase_d_boundary_specs.csv", boundary_specs)
    phase_d_rows = run_phase_d(boundary_specs, entries, safe, config, base_config, budget)
    _write_csv(output / "phase_d_boundary_branches.csv", phase_d_rows)

    disagreement_cases = _disagreements(
        phase_b_rows, phase_c_rows, phase_d_rows, int(config["phase_e"]["maximum_cases"])
    )
    _write_csv(output / "phase_e_disagreement_cases.csv", disagreement_cases)
    phase_e_rows = run_phase_e(
        disagreement_cases, entries, stable_by_seed, safe, config, base_config, budget
    )
    _write_csv(output / "phase_e_probability_branches.csv", phase_e_rows)

    decisions, final_decision = _decisions(
        audit, phase_a, changes, phase_c_rows, boundary_specs, disagreement_cases, config
    )
    _write_csv(output / "hypothesis_decisions.csv", decisions)
    _json_dump(output / "hypothesis_decisions.json", {"decisions": decisions, "final_decision": final_decision})

    phase_counts = {
        "phase_b": len(phase_b_rows),
        "phase_c": len(phase_c_rows),
        "phase_d": len(phase_d_rows),
        "phase_e": len(phase_e_rows),
    }
    if sum(phase_counts.values()) != budget.used:
        raise AuditError("branch budget ledger/count mismatch")
    budget_summary = {
        **phase_counts,
        "total_new_branches": budget.used,
        "target_maximum": int(config["budget"]["target_maximum"]),
        "absolute_maximum": int(config["budget"]["absolute_maximum"]),
        "within_absolute_budget": budget.used <= int(config["budget"]["absolute_maximum"]),
    }
    _json_dump(output / "branch_budget.json", budget_summary)

    (output / "task4_1b_results.md").write_text(
        f"""# Task 3.2-4.1b 軽量感度・原因切り分け監査 結果

- 新規分岐数: {budget.used}
- 代表状態: 18（各構造群6）
- holdout状態ファイル読取り: なし
- 予測器再学習・再選択: なし
- C0から回復判定が変化した状態数: {int(changes['changed_from_C0'].sum())}
- Phase C対象状態数: {len(phase_c_selected)}
- 境界細分化候補数: {len(boundary_specs)}
- 複製不一致追加監査件数: {len(disagreement_cases)}

## Rev1範囲判定

`{final_decision}`

この判定はTask 4.1の修正範囲を決めるための内部監査であり、新しい正式構造正解や運用可能性を主張しない。
""",
        encoding="utf-8",
    )
    (output / "task4_1b_rev1_scope.md").write_text(
        "# Task 4.1 Rev1 修正範囲\n\n"
        + f"最終判定: `{final_decision}`\n\n"
        + "## 仮説別判断\n\n"
        + "\n".join(
            f"- {row['hypothesis']}: **{row['decision']}** — {row['evidence']}" for row in decisions
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "task_id": config["task_id"],
        "status": "complete",
        "formal_artifact_validation": formal_validation,
        "representative_state_count": len(representatives),
        "representative_group_counts": representatives.groupby("audit_group").size().to_dict(),
        "holdout_state_read": False,
        "predictor_retraining": False,
        "formal_truth_replacement": False,
        "source_trajectory_writeback": False,
        "parameter_box_write": False,
        "action_module_connection": False,
        "branch_budget": budget_summary,
        "phase_a_diagnostics": phase_a,
        "phase_b_changed_state_count": int(changes["changed_from_C0"].sum()),
        "phase_c_state_count": len(phase_c_selected),
        "phase_d_boundary_count": len(boundary_specs),
        "phase_e_case_count": len(disagreement_cases),
        "hypothesis_decisions": decisions,
        "final_decision": final_decision,
        "representative_selection_lock_hash": lock["lock_hash"],
    }
    _json_dump(output / "summary.json", summary)
    _json_dump(
        output / "audit_contract.json",
        {
            "task_id": config["task_id"],
            "existing_formal_branches_reused": 6660,
            "new_branch_limit": int(config["budget"]["absolute_maximum"]),
            **config["boundaries"],
        },
    )
    _write_manifest(output)
    return summary


def validate_output(
    input_dir: str | Path, config_path: str | Path = DEFAULT_CONFIG
) -> dict[str, Any]:
    config = load_config(config_path)
    root = Path(input_dir)
    required = {
        "summary.json",
        "manifest.json",
        "audit_contract.json",
        "representative_18_states.csv",
        "representative_selection_lock.json",
        "branch_budget.json",
        "phase_a_diagnostics.json",
        "phase_a_candidate_truth.csv",
        "phase_b_continuation_branches.csv",
        "phase_b_continuation_summary.csv",
        "phase_b_changed_states.csv",
        "hypothesis_decisions.json",
        "hypothesis_decisions.csv",
        "task4_1b_results.md",
        "task4_1b_rev1_scope.md",
    }
    missing = sorted(name for name in required if not (root / name).is_file())
    if missing:
        raise AuditError(f"Task 4.1b output missing {missing}")
    manifest = _validate_manifest(root)
    lock = _validate_selection_lock(root / "representative_selection_lock.json")
    summary = _json_load(root / "summary.json")
    if summary.get("status") != "complete" or summary.get("final_decision") not in ALLOWED_DECISIONS:
        raise AuditError("Task 4.1b summary is invalid")
    if summary.get("holdout_state_read") is not False or summary.get("predictor_retraining") is not False:
        raise AuditError("Task 4.1b read/training boundary failed")
    if summary.get("source_trajectory_writeback") is not False:
        raise AuditError("Task 4.1b source writeback boundary failed")
    budget = summary["branch_budget"]
    if int(budget["phase_b"]) != 144 or int(budget["total_new_branches"]) > int(config["budget"]["absolute_maximum"]):
        raise AuditError("Task 4.1b branch budget failed")
    if summary.get("representative_state_count") != 18:
        raise AuditError("Task 4.1b representative count failed")
    if summary.get("representative_selection_lock_hash") != lock["lock_hash"]:
        raise AuditError("Task 4.1b summary/selection-lock mismatch")
    return {
        "status": "valid",
        "final_decision": summary["final_decision"],
        "total_new_branches": budget["total_new_branches"],
        "representative_state_count": summary["representative_state_count"],
        "holdout_state_read": False,
        "manifest_file_count": manifest["file_count"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--corpus", required=True)
    execute.add_argument("--formal-artifact", required=True)
    execute.add_argument("--output", required=True)
    execute.add_argument("--config", default=str(DEFAULT_CONFIG))
    check = sub.add_parser("validate")
    check.add_argument("--input", required=True)
    check.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    result = (
        run(args.corpus, args.formal_artifact, args.output, args.config)
        if args.command == "run"
        else validate_output(args.input, args.config)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AuditError",
    "BranchBudget",
    "load_config",
    "run",
    "select_representatives",
    "validate_output",
]
