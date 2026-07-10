"""Task 3.1 fixed PCA external-factor projection audit.

This script fits PCA bases only on the no-external Task 3 fit corpus, freezes
those bases, and projects separately generated external-factor v3.3 logs through
that fixed geometry. It does not select a final PCA-G_t candidate and does not
connect to H-DEPT, O_t, ActionModule, dynamic PCA updates, or parameter writes.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pseudo_reality.distribution_terrain_v3_scenarios import BASELINE_EXTERNAL_FACTORS
from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322Config, DistributionTerrainV322World
from scripts.pseudoreality_v3_3_pca_gt_candidate_comparison import (
    build_full_envelope_corpus,
    snapshot_to_mass_vector,
    _features,
    _fit_pca,
    _project_pca,
    _projection_metrics,
    _score_range_violation,
)

STEPS = 12
SEEDS = (0, 1, 2)
EPSILON = 1e-12
OUTPUT_DIR = Path("docs/task3_1_fixed_pca_external_factor_projection_audit")
PROJECTION_TYPE = "fixed_pca_external_projection"

AUDIT_CANDIDATES: tuple[dict[str, str | int], ...] = (
    {"candidate_name": "sqrt_static_pca_10", "candidate_role": "audit_focus_candidate", "family": "sqrt_static_pca", "component_count": 10},
    {"candidate_name": "sqrt_static_pca_7", "candidate_role": "continuity_baseline", "family": "sqrt_static_pca", "component_count": 7},
    {"candidate_name": "raw_static_pca_7", "candidate_role": "numerical_reconstruction_baseline", "family": "raw_static_pca", "component_count": 7},
    {"candidate_name": "sqrt_static_pca_12", "candidate_role": "higher_dimension_audit", "family": "sqrt_static_pca", "component_count": 12},
    {"candidate_name": "sqrt_sparse_temporal_lag_pca_10", "candidate_role": "temporal_audit_candidate", "family": "sqrt_sparse_temporal_lag_pca", "component_count": 10},
)

REQUIRED_CSVS = (
    "v3_3_fixed_pca_external_projection_summary.csv",
    "v3_3_fixed_pca_external_projection_snapshot_metrics.csv",
    "v3_3_fixed_pca_external_projection_factor_response.csv",
    "v3_3_fixed_pca_external_projection_candidate_comparison.csv",
    "v3_3_fixed_pca_external_projection_out_of_envelope_audit.csv",
)

EXTERNAL_FACTORS = tuple(BASELINE_EXTERNAL_FACTORS.keys())


@dataclass(frozen=True)
class ExternalScenario:
    scenario_id: str
    scenario_group: str
    external_factor_name: str
    external_factor_value: float
    schedule: Callable[[int], dict[str, float]]


@dataclass(frozen=True)
class FrozenCandidateBasis:
    candidate_name: str
    candidate_role: str
    family: str
    component_count: int
    fit: object
    score_min: np.ndarray
    score_max: np.ndarray
    residual_threshold: float
    mahalanobis_threshold: float
    score_std: np.ndarray


def zero_factors() -> dict[str, float]:
    return dict(BASELINE_EXTERNAL_FACTORS)


def _with_factor(name: str, value: float) -> dict[str, float]:
    factors = zero_factors()
    factors[name] = float(value)
    return factors


def generate_external_factor_scenarios() -> list[ExternalScenario]:
    scenarios: list[ExternalScenario] = [
        ExternalScenario("baseline_zero", "baseline", "none", 0.0, lambda _t: zero_factors())
    ]
    signed_values = (-1.0, -0.5, 0.5, 1.0)
    positive_values = (0.25, 0.5, 0.75, 1.0)
    for factor in ("external_resource_supply", "external_demand"):
        for value in signed_values:
            scenarios.append(
                ExternalScenario(
                    f"single_{factor}_{value:+.2f}",
                    "single_sustained_factor",
                    factor,
                    value,
                    lambda _t, factor=factor, value=value: _with_factor(factor, value),
                )
            )
    for factor in (
        "external_competition_pressure",
        "external_information_noise",
        "external_shock",
        "external_constraint_pressure",
    ):
        for value in positive_values:
            scenarios.append(
                ExternalScenario(
                    f"single_{factor}_{value:.2f}",
                    "single_sustained_factor",
                    factor,
                    value,
                    lambda _t, factor=factor, value=value: _with_factor(factor, value),
                )
            )
    for factor in ("external_shock", "external_information_noise", "external_constraint_pressure"):
        scenarios.append(
            ExternalScenario(
                f"pulse_{factor}_t4_1.00",
                "pulse_shock",
                factor,
                1.0,
                lambda t, factor=factor: _with_factor(factor, 1.0) if t == 4 else zero_factors(),
            )
        )
    scenarios.extend(
        [
            ExternalScenario(
                "resource_supply_reversal",
                "reversal",
                "external_resource_supply",
                1.0,
                lambda t: _with_factor("external_resource_supply", 1.0 if t <= 5 else -1.0),
            ),
            ExternalScenario(
                "demand_reversal",
                "reversal",
                "external_demand",
                1.0,
                lambda t: _with_factor("external_demand", 1.0 if t <= 5 else -1.0),
            ),
            ExternalScenario(
                "competition_plus_noise",
                "compound_pressure",
                "external_competition_pressure+external_information_noise",
                0.75,
                lambda _t: {**zero_factors(), "external_competition_pressure": 0.75, "external_information_noise": 0.75},
            ),
            ExternalScenario(
                "shock_plus_constraint",
                "compound_pressure",
                "external_shock+external_constraint_pressure",
                0.75,
                lambda _t: {**zero_factors(), "external_shock": 0.75, "external_constraint_pressure": 0.75},
            ),
            ExternalScenario(
                "scarcity_plus_demand",
                "compound_pressure",
                "external_resource_supply+external_demand",
                0.75,
                lambda _t: {**zero_factors(), "external_resource_supply": -0.75, "external_demand": 0.75},
            ),
        ]
    )
    return scenarios


def _snapshot_row(scenario: ExternalScenario, seed: int, t: int, vector: np.ndarray, factors: dict[str, float]) -> dict[str, object]:
    row: dict[str, object] = {
        "snapshot_id": f"{scenario.scenario_id}_seed{seed}_t{t}",
        "scenario_id": scenario.scenario_id,
        "scenario_group": scenario.scenario_group,
        "external_factor_name": scenario.external_factor_name,
        "external_factor_value": scenario.external_factor_value,
        "seed": seed,
        "t": t,
        "mass_total": float(vector.sum()),
    }
    row.update({factor: float(factors.get(factor, 0.0)) for factor in EXTERNAL_FACTORS})
    return row


def generate_external_factor_snapshot_log(seeds: tuple[int, ...] = SEEDS, steps: int = STEPS) -> tuple[pd.DataFrame, np.ndarray]:
    rows: list[dict[str, object]] = []
    vectors: list[np.ndarray] = []
    for scenario in generate_external_factor_scenarios():
        for seed in seeds:
            world = DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed, n_bins=5))
            factors = zero_factors()
            vector = snapshot_to_mass_vector(world.distribution)
            rows.append(_snapshot_row(scenario, seed, 0, vector, factors))
            vectors.append(vector)
            for step_t in range(steps):
                factors = scenario.schedule(step_t)
                world.set_external_factors(factors)
                world.step()
                vector = snapshot_to_mass_vector(world.distribution)
                rows.append(_snapshot_row(scenario, seed, step_t + 1, vector, factors))
                vectors.append(vector)
    return pd.DataFrame(rows), np.vstack(vectors)


def _feature_matrix_for_candidate(mass: np.ndarray, manifest: pd.DataFrame, family: str) -> np.ndarray:
    if family != "sqrt_sparse_temporal_lag_pca":
        return _features(mass, family, EPSILON)[0]
    base = np.sqrt(mass)
    chunks: list[np.ndarray] = []
    sparse_idx = np.arange(0, base.shape[1], 25)
    for _, group in manifest.groupby(["scenario_id", "seed"], sort=False):
        idx = group.index.to_numpy()
        group_base = base[idx]
        d1 = np.vstack([np.zeros_like(group_base[0]), np.diff(group_base, axis=0)])
        chunks.append(np.hstack([group_base, d1[:, sparse_idx]]))
    return np.vstack(chunks)


def fit_frozen_candidate_bases(seed: int = 0) -> list[FrozenCandidateBasis]:
    manifest, mass = build_full_envelope_corpus(seed=seed)
    fit_mask = manifest["corpus_type"].to_numpy() == "fit"
    bases: list[FrozenCandidateBasis] = []
    for spec in AUDIT_CANDIDATES:
        family = str(spec["family"])
        component_count = int(spec["component_count"])
        features = _features(mass, family, EPSILON)[0]
        fit_features = features[fit_mask]
        fit = _fit_pca(fit_features, component_count)
        err, energy = _projection_metrics(fit_features, fit.reconstructed, fit.mean)
        score_std = fit.transformed.std(axis=0) + EPSILON
        md = np.sqrt(np.sum(((fit.transformed - fit.transformed.mean(axis=0)) / score_std) ** 2, axis=1))
        bases.append(
            FrozenCandidateBasis(
                candidate_name=str(spec["candidate_name"]),
                candidate_role=str(spec["candidate_role"]),
                family=family,
                component_count=component_count,
                fit=fit,
                score_min=fit.transformed.min(axis=0),
                score_max=fit.transformed.max(axis=0),
                residual_threshold=float(np.quantile(energy, 0.95) * 1.25),
                mahalanobis_threshold=float(np.quantile(md, 0.95) * 1.25),
                score_std=score_std,
            )
        )
    return bases


def _markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 12) -> str:
    small = df.loc[:, columns].head(max_rows).copy()
    if small.empty:
        return "\n(no rows)\n"
    for column in small.columns:
        if pd.api.types.is_float_dtype(small[column]):
            small[column] = small[column].map(lambda value: f"{value:.6g}")
    header = "| " + " | ".join(small.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(small.columns)) + " |"
    body = ["| " + " | ".join(str(row[column]) for column in small.columns) + " |" for _, row in small.iterrows()]
    return "\n".join([header, sep, *body])


def run_fixed_pca_external_factor_projection_audit(
    output_root: str | Path = OUTPUT_DIR,
    *,
    seed: int = 0,
    steps: int = STEPS,
) -> dict[str, pd.DataFrame]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    bases = fit_frozen_candidate_bases(seed=seed)
    manifest, mass = generate_external_factor_snapshot_log(steps=steps)
    baseline_lookup: dict[tuple[str, int, int], dict[str, np.ndarray | float]] = {}
    snapshot_rows: list[dict[str, object]] = []

    for basis in bases:
        features = _feature_matrix_for_candidate(mass, manifest, basis.family)
        scores, reconstructed = _project_pca(features, basis.fit)
        err, energy = _projection_metrics(features, reconstructed, basis.fit.mean)
        md = np.sqrt(np.sum(((scores - basis.fit.transformed.mean(axis=0)) / basis.score_std) ** 2, axis=1))
        violation = _score_range_violation(scores, basis.score_min, basis.score_max)
        out = (energy > basis.residual_threshold) | (md > basis.mahalanobis_threshold) | violation.astype(bool)
        for i, row in manifest.iterrows():
            key = (basis.candidate_name, int(row.seed), int(row.t))
            if row.scenario_group == "baseline":
                baseline_lookup[key] = {"energy": float(energy[i]), "score": scores[i].copy()}

        previous_score: dict[tuple[str, int], np.ndarray] = {}
        previous_previous_score: dict[tuple[str, int], np.ndarray] = {}
        for i, row in manifest.iterrows():
            scenario_seed_key = (str(row.scenario_id), int(row.seed))
            baseline = baseline_lookup[(basis.candidate_name, int(row.seed), int(row.t))]
            external_residual_gain = float(energy[i] - float(baseline["energy"]))
            external_score_displacement = float(np.linalg.norm(scores[i] - np.asarray(baseline["score"])))
            if scenario_seed_key in previous_score:
                velocity = float(np.linalg.norm(scores[i] - previous_score[scenario_seed_key]))
            else:
                velocity = 0.0
            if scenario_seed_key in previous_score and scenario_seed_key in previous_previous_score:
                curvature = float(np.linalg.norm(scores[i] - 2.0 * previous_score[scenario_seed_key] + previous_previous_score[scenario_seed_key]))
            else:
                curvature = 0.0
            previous_previous_score[scenario_seed_key] = previous_score.get(scenario_seed_key, scores[i].copy())
            previous_score[scenario_seed_key] = scores[i].copy()
            residual_factor_signal_ratio = external_residual_gain / max(external_score_displacement, EPSILON)
            status = "out_of_envelope" if out[i] else "in_envelope"
            if not out[i] and energy[i] > basis.residual_threshold / 1.25:
                status = "high_residual"
            snapshot_rows.append(
                {
                    "candidate_name": basis.candidate_name,
                    "candidate_role": basis.candidate_role,
                    "scenario_id": row.scenario_id,
                    "scenario_group": row.scenario_group,
                    "external_factor_name": row.external_factor_name,
                    "external_factor_value": float(row.external_factor_value),
                    "seed": int(row.seed),
                    "t": int(row.t),
                    "snapshot_id": row.snapshot_id,
                    "projection_type": PROJECTION_TYPE,
                    "reconstruction_error": float(err[i]),
                    "residual_energy_ratio": float(energy[i]),
                    "mahalanobis_distance": float(md[i]),
                    "score_range_violation": int(violation[i]),
                    "out_of_envelope_flag": bool(out[i]),
                    "audit_status": status,
                    "external_residual_gain": external_residual_gain,
                    "external_score_displacement": external_score_displacement,
                    "external_gt_velocity": velocity,
                    "external_gt_curvature": curvature,
                    "residual_factor_signal_ratio": residual_factor_signal_ratio,
                }
            )
    snapshot_metrics = pd.DataFrame(snapshot_rows)
    non_baseline = snapshot_metrics[snapshot_metrics["scenario_group"] != "baseline"].copy()
    summary = (
        snapshot_metrics.groupby(["candidate_name", "candidate_role"], as_index=False)
        .agg(
            snapshot_count=("snapshot_id", "count"),
            reconstruction_error_mean=("reconstruction_error", "mean"),
            reconstruction_error_max=("reconstruction_error", "max"),
            residual_energy_ratio_mean=("residual_energy_ratio", "mean"),
            residual_energy_ratio_max=("residual_energy_ratio", "max"),
            external_residual_gain_mean=("external_residual_gain", "mean"),
            external_score_displacement_mean=("external_score_displacement", "mean"),
            external_gt_velocity_mean=("external_gt_velocity", "mean"),
            external_gt_curvature_mean=("external_gt_curvature", "mean"),
            out_of_envelope_rate=("out_of_envelope_flag", "mean"),
            score_range_violation_count=("score_range_violation", "sum"),
        )
        .sort_values(["candidate_role", "candidate_name"])
        .reset_index(drop=True)
    )
    factor_response = (
        non_baseline.groupby(["candidate_name", "candidate_role", "external_factor_name"], as_index=False)
        .agg(
            snapshot_count=("snapshot_id", "count"),
            mean_score_displacement=("external_score_displacement", "mean"),
            mean_residual_gain=("external_residual_gain", "mean"),
            mean_mahalanobis_distance=("mahalanobis_distance", "mean"),
            out_of_envelope_rate=("out_of_envelope_flag", "mean"),
            mean_residual_factor_signal_ratio=("residual_factor_signal_ratio", "mean"),
        )
        .sort_values(["candidate_name", "external_factor_name"])
        .reset_index(drop=True)
    )
    candidate_comparison = summary.copy()
    focus = summary[summary["candidate_name"] == "sqrt_static_pca_10"].iloc[0]
    candidate_comparison["delta_residual_gain_vs_sqrt_static_pca_10"] = candidate_comparison["external_residual_gain_mean"] - float(focus["external_residual_gain_mean"])
    candidate_comparison["delta_score_displacement_vs_sqrt_static_pca_10"] = candidate_comparison["external_score_displacement_mean"] - float(focus["external_score_displacement_mean"])
    candidate_comparison["review_status"] = "requires_human_review"
    ooe = snapshot_metrics[snapshot_metrics["out_of_envelope_flag"]].copy()
    if ooe.empty:
        ooe = snapshot_metrics.head(0).copy()

    tables = {
        "v3_3_fixed_pca_external_projection_summary.csv": summary,
        "v3_3_fixed_pca_external_projection_snapshot_metrics.csv": snapshot_metrics,
        "v3_3_fixed_pca_external_projection_factor_response.csv": factor_response,
        "v3_3_fixed_pca_external_projection_candidate_comparison.csv": candidate_comparison,
        "v3_3_fixed_pca_external_projection_out_of_envelope_audit.csv": ooe,
    }
    for filename, table in tables.items():
        table.to_csv(root / filename, index=False)
    _write_results_markdown(root / "results.md", summary, factor_response, candidate_comparison)
    return tables


def _comparison_rows(candidate_comparison: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    return candidate_comparison[candidate_comparison["candidate_name"].isin(names)].sort_values("candidate_name")


def _write_results_markdown(path: Path, summary: pd.DataFrame, factor_response: pd.DataFrame, candidate_comparison: pd.DataFrame) -> None:
    focus = "sqrt_static_pca_10"
    residual_by_factor = (
        factor_response[factor_response["candidate_name"] == focus]
        .sort_values("mean_residual_gain", ascending=False)
        .reset_index(drop=True)
    )
    displacement_by_factor = (
        factor_response[factor_response["candidate_name"] == focus]
        .sort_values("mean_score_displacement", ascending=False)
        .reset_index(drop=True)
    )
    lines = [
        "# Task 3.1 Fixed PCA External Factor Projection Audit",
        "",
        "This report audits external-factor projections into frozen Task 3 PCA bases.",
        "It does not select the final PCA-G_t candidate. Final adoption decision is reserved for human review.",
        "",
        "## Candidate-level summary",
        _markdown_table(summary, ["candidate_name", "candidate_role", "residual_energy_ratio_mean", "external_residual_gain_mean", "external_score_displacement_mean", "out_of_envelope_rate"]),
        "",
        "## External factor response summary",
        _markdown_table(factor_response, ["candidate_name", "external_factor_name", "mean_score_displacement", "mean_residual_gain", "out_of_envelope_rate"], max_rows=20),
        "",
        "## sqrt_static_pca_10 vs sqrt_static_pca_7",
        _markdown_table(_comparison_rows(candidate_comparison, ["sqrt_static_pca_10", "sqrt_static_pca_7"]), ["candidate_name", "candidate_role", "external_residual_gain_mean", "external_score_displacement_mean", "out_of_envelope_rate", "review_status"]),
        "",
        "## sqrt_static_pca_10 vs raw_static_pca_7",
        _markdown_table(_comparison_rows(candidate_comparison, ["sqrt_static_pca_10", "raw_static_pca_7"]), ["candidate_name", "candidate_role", "external_residual_gain_mean", "external_score_displacement_mean", "out_of_envelope_rate", "review_status"]),
        "",
        "## sqrt_static_pca_10 vs sqrt_static_pca_12",
        _markdown_table(_comparison_rows(candidate_comparison, ["sqrt_static_pca_10", "sqrt_static_pca_12"]), ["candidate_name", "candidate_role", "external_residual_gain_mean", "external_score_displacement_mean", "out_of_envelope_rate", "review_status"]),
        "",
        "## Out-of-envelope rates by candidate",
        _markdown_table(summary.sort_values("out_of_envelope_rate", ascending=False), ["candidate_name", "candidate_role", "out_of_envelope_rate", "score_range_violation_count"]),
        "",
        "## Residual gain by factor (sqrt_static_pca_10 audit focus)",
        _markdown_table(residual_by_factor, ["external_factor_name", "mean_residual_gain", "mean_mahalanobis_distance", "out_of_envelope_rate"], max_rows=20),
        "",
        "## Score displacement by factor (sqrt_static_pca_10 audit focus)",
        _markdown_table(displacement_by_factor, ["external_factor_name", "mean_score_displacement", "mean_residual_factor_signal_ratio", "out_of_envelope_rate"], max_rows=20),
        "",
        "Human review required before candidate adoption.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default=str(OUTPUT_DIR))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--steps", type=int, default=STEPS)
    args = parser.parse_args()
    run_fixed_pca_external_factor_projection_audit(args.output_root, seed=args.seed, steps=args.steps)


if __name__ == "__main__":
    main()
