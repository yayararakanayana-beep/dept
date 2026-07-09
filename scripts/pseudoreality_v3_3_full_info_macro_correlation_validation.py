"""Full-information macro correlation extraction for PseudoReality v3.3.

This validation is still upstream of G_t. It asks a narrower question:

Can we extract stable macro correlation functions from the full 7D information
baseline plus a short internal log?

The extracted functions are treated as rule/game-structure candidates. They are
not hand-labeled phenomena. They are pairwise mass relations measured against an
independence baseline, then tracked over a short log to see whether the relation
is stable enough to serve as a macro rule candidate.

This script intentionally uses a short log by default. It does not run the long
horizon v3 validation suite.
"""

from __future__ import annotations

from itertools import combinations, product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322Config, DistributionTerrainV322World
from scripts.pseudoreality_v3_3_static_7d_raw_baseline import (
    BASELINE_DIMENSION_COLUMNS,
    SOURCE_DIMENSION_COLUMNS,
    _neighbor_mean,
    _rank_bins,
)

GEOMETRY_DIMENSION_COLUMNS = tuple(column for column in BASELINE_DIMENSION_COLUMNS if column not in SOURCE_DIMENSION_COLUMNS)


def _entropy(mass: np.ndarray) -> float:
    positive = np.asarray(mass, dtype=float)
    positive = positive[positive > 0.0]
    return float(-np.sum(positive * np.log(positive)))


def _distribution_from_world_mass(
    mass: np.ndarray,
    *,
    t: int,
    seed: int,
    n_bins: int,
) -> pd.DataFrame:
    """Convert one 5D v3.3 mass snapshot into the 7D sparse baseline form."""

    mass = np.asarray(mass, dtype=float)
    mass = np.maximum(np.nan_to_num(mass, nan=0.0, posinf=0.0, neginf=0.0), 0.0)
    mass = mass / max(float(mass.sum()), 1e-12)

    density_score, density_bin = _rank_bins(mass, n_bins=n_bins)
    neighbor_mean = _neighbor_mean(mass)
    local_shape_score_raw = np.abs(mass - neighbor_mean) / np.maximum(mass + neighbor_mean, 1e-12)
    shape_score, shape_bin = _rank_bins(local_shape_score_raw, n_bins=n_bins)

    index_grids = np.indices(mass.shape)
    source_cell_mapping = pd.DataFrame(
        {
            "t": int(t),
            "seed": int(seed),
            "cell_id": np.arange(int(np.prod(mass.shape)), dtype=int),
            **{column: index_grids[i].ravel().astype(int) for i, column in enumerate(SOURCE_DIMENSION_COLUMNS)},
            "d6_distribution_position_bin": density_bin.ravel().astype(int),
            "d7_distribution_shape_position_bin": shape_bin.ravel().astype(int),
            "mass": mass.ravel(),
            "distribution_position_score": density_score.ravel(),
            "distribution_shape_score": shape_score.ravel(),
            "local_shape_contrast_raw": local_shape_score_raw.ravel(),
        }
    )
    return (
        source_cell_mapping.groupby(["t", "seed", *BASELINE_DIMENSION_COLUMNS], as_index=False)
        .agg(
            mass=("mass", "sum"),
            source_cell_count=("cell_id", "count"),
            distribution_position_score_mean=("distribution_position_score", "mean"),
            distribution_shape_score_mean=("distribution_shape_score", "mean"),
            local_shape_contrast_raw_mean=("local_shape_contrast_raw", "mean"),
        )
        .sort_values(["t", *BASELINE_DIMENSION_COLUMNS])
        .reset_index(drop=True)
    )


def run_short_full_info_log(
    *,
    seed: int = 0,
    n_bins: int = 5,
    steps: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run a short v3.3-provisional log and return 7D distributions by t."""

    if n_bins != 5:
        raise ValueError("v3.3 full-info macro correlation validation currently fixes n_bins=5")
    if steps < 1:
        raise ValueError("steps must be at least 1")

    world = DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed, n_bins=n_bins))
    snapshots = [_distribution_from_world_mass(world.distribution, t=0, seed=seed, n_bins=n_bins)]
    summary_rows: list[dict[str, float | int]] = []

    def record_snapshot(t: int) -> None:
        mass = np.asarray(world.distribution, dtype=float)
        coords = world._coordinate_grids()
        row: dict[str, float | int] = {
            "t": int(t),
            "seed": int(seed),
            "mass_total": float(mass.sum()),
            "entropy": _entropy(mass.ravel()),
            "concentration": float(np.sum(mass**2)),
            "max_mass": float(mass.max()),
            "total_flow": float(getattr(world, "last_flow", np.zeros_like(mass)).sum()),
        }
        for axis_name, coord in zip(world.config.axes, coords, strict=True):
            center = float(np.sum(mass * coord))
            row[f"center_{axis_name}"] = center
            row[f"spread_{axis_name}"] = float(np.sqrt(np.sum(mass * (coord - center) ** 2)))
        row["route_support_weighted_mean"] = float(np.sum(mass * getattr(world, "route_support", np.zeros_like(mass))))
        row["expected_value_advantage_weighted_mean"] = float(
            np.sum(mass * getattr(world, "expected_value_advantage", np.zeros_like(mass)))
        )
        row["cost_reduction_gain_weighted_mean"] = float(np.sum(mass * getattr(world, "cost_reduction_gain", np.zeros_like(mass))))
        summary_rows.append(row)

    record_snapshot(0)
    for t in range(1, steps + 1):
        world.step()
        snapshots.append(_distribution_from_world_mass(world.distribution, t=t, seed=seed, n_bins=n_bins))
        record_snapshot(t)

    return pd.concat(snapshots, ignore_index=True), pd.DataFrame(summary_rows)


def extract_single_dimension_marginals(distribution_log: pd.DataFrame, *, n_bins: int = 5) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for (t, seed), frame in distribution_log.groupby(["t", "seed"], sort=True):
        for dimension in BASELINE_DIMENSION_COLUMNS:
            grouped = frame.groupby(dimension, as_index=False)["mass"].sum()
            mass_by_bin = dict(zip(grouped[dimension].astype(int), grouped["mass"].astype(float), strict=False))
            for bin_value in range(n_bins):
                rows.append(
                    {
                        "t": int(t),
                        "seed": int(seed),
                        "dimension": dimension,
                        "bin": int(bin_value),
                        "mass": float(mass_by_bin.get(bin_value, 0.0)),
                    }
                )
    return pd.DataFrame(rows)


def extract_pairwise_correlation_functions(
    distribution_log: pd.DataFrame,
    *,
    n_bins: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extract pairwise macro correlation functions against independence."""

    pair_rows: list[dict[str, float | int | str]] = []
    score_rows: list[dict[str, float | int | str]] = []
    bin_pairs = list(product(range(n_bins), repeat=2))

    for (t, seed), frame in distribution_log.groupby(["t", "seed"], sort=True):
        marginals: dict[str, np.ndarray] = {}
        for dimension in BASELINE_DIMENSION_COLUMNS:
            grouped = frame.groupby(dimension, as_index=False)["mass"].sum()
            values = np.zeros(n_bins, dtype=float)
            for _, row in grouped.iterrows():
                values[int(row[dimension])] = float(row["mass"])
            marginals[dimension] = values

        for dim_a, dim_b in combinations(BASELINE_DIMENSION_COLUMNS, 2):
            joint = np.zeros((n_bins, n_bins), dtype=float)
            grouped = frame.groupby([dim_a, dim_b], as_index=False)["mass"].sum()
            for _, row in grouped.iterrows():
                joint[int(row[dim_a]), int(row[dim_b])] = float(row["mass"])

            expected = np.outer(marginals[dim_a], marginals[dim_b])
            residual = joint - expected
            with np.errstate(divide="ignore", invalid="ignore"):
                lift = np.divide(joint, expected, out=np.zeros_like(joint), where=expected > 0.0)
                log_lift = np.log(np.divide(joint, expected, out=np.ones_like(joint), where=(joint > 0.0) & (expected > 0.0)))
            mi_terms = np.where(joint > 0.0, joint * log_lift, 0.0)

            pair_mi = float(np.sum(mi_terms))
            residual_l1 = float(np.sum(np.abs(residual)))
            residual_linf = float(np.max(np.abs(residual)))
            score_rows.append(
                {
                    "t": int(t),
                    "seed": int(seed),
                    "dimension_a": dim_a,
                    "dimension_b": dim_b,
                    "mutual_information": pair_mi,
                    "residual_l1": residual_l1,
                    "residual_linf": residual_linf,
                    "max_lift": float(np.max(lift)),
                    "max_abs_log_lift": float(np.max(np.abs(log_lift))),
                }
            )

            for bin_a, bin_b in bin_pairs:
                pair_rows.append(
                    {
                        "t": int(t),
                        "seed": int(seed),
                        "dimension_a": dim_a,
                        "dimension_b": dim_b,
                        "bin_a": int(bin_a),
                        "bin_b": int(bin_b),
                        "observed_mass": float(joint[bin_a, bin_b]),
                        "expected_independent_mass": float(expected[bin_a, bin_b]),
                        "residual_mass": float(residual[bin_a, bin_b]),
                        "abs_residual_mass": float(abs(residual[bin_a, bin_b])),
                        "lift": float(lift[bin_a, bin_b]),
                        "log_lift": float(log_lift[bin_a, bin_b]),
                        "mutual_information_term": float(mi_terms[bin_a, bin_b]),
                    }
                )

    return pd.DataFrame(pair_rows), pd.DataFrame(score_rows)


def extract_macro_rule_candidates(pair_functions: pd.DataFrame, *, top_n: int = 80) -> pd.DataFrame:
    """Aggregate pair-bin functions over the log and rank macro rule candidates."""

    grouped = pair_functions.groupby(["dimension_a", "dimension_b", "bin_a", "bin_b"], as_index=False).agg(
        observed_mass_mean=("observed_mass", "mean"),
        observed_mass_first=("observed_mass", "first"),
        observed_mass_last=("observed_mass", "last"),
        expected_mass_mean=("expected_independent_mass", "mean"),
        residual_mass_mean=("residual_mass", "mean"),
        abs_residual_mass_mean=("abs_residual_mass", "mean"),
        lift_mean=("lift", "mean"),
        log_lift_mean=("log_lift", "mean"),
        mutual_information_term_mean=("mutual_information_term", "mean"),
    )
    grouped["observed_mass_delta"] = grouped["observed_mass_last"] - grouped["observed_mass_first"]
    grouped["rule_score"] = (
        grouped["abs_residual_mass_mean"]
        + grouped["mutual_information_term_mean"].abs()
        + 0.25 * grouped["observed_mass_delta"].abs()
    )
    grouped["rule_direction"] = np.where(grouped["residual_mass_mean"] >= 0.0, "above_independence", "below_independence")
    return grouped.sort_values("rule_score", ascending=False).head(top_n).reset_index(drop=True)


def evaluate_trend_alignment(pair_functions: pd.DataFrame, rule_candidates: pd.DataFrame) -> pd.DataFrame:
    """Check whether rule-favored pair bins align with next-step mass movement."""

    key_columns = ["dimension_a", "dimension_b", "bin_a", "bin_b"]
    candidate_keys = rule_candidates[key_columns].drop_duplicates()
    candidate_pairs = pair_functions.merge(candidate_keys, on=key_columns, how="inner")
    candidate_pairs = candidate_pairs.sort_values([*key_columns, "t"]).copy()
    candidate_pairs["next_observed_mass"] = candidate_pairs.groupby(key_columns)["observed_mass"].shift(-1)
    candidate_pairs["observed_mass_delta_next"] = candidate_pairs["next_observed_mass"] - candidate_pairs["observed_mass"]
    candidate_pairs = candidate_pairs.dropna(subset=["observed_mass_delta_next"])
    candidate_pairs["alignment_weight"] = candidate_pairs["abs_residual_mass"]
    candidate_pairs["direction_alignment"] = np.sign(candidate_pairs["residual_mass"]) * np.sign(
        candidate_pairs["observed_mass_delta_next"]
    )
    candidate_pairs["weighted_direction_alignment"] = candidate_pairs["direction_alignment"] * candidate_pairs[
        "alignment_weight"
    ]

    rows: list[dict[str, float | int | str]] = []
    for t, frame in candidate_pairs.groupby("t", sort=True):
        weight_sum = float(frame["alignment_weight"].sum())
        rows.append(
            {
                "t": int(t),
                "candidate_count": int(len(frame)),
                "weighted_alignment_mean": float(frame["weighted_direction_alignment"].sum() / max(weight_sum, 1e-12)),
                "positive_alignment_share": float((frame["direction_alignment"] > 0.0).mean()),
                "negative_alignment_share": float((frame["direction_alignment"] < 0.0).mean()),
                "zero_alignment_share": float((frame["direction_alignment"] == 0.0).mean()),
                "mean_next_mass_delta": float(frame["observed_mass_delta_next"].mean()),
                "mean_abs_next_mass_delta": float(frame["observed_mass_delta_next"].abs().mean()),
            }
        )
    return pd.DataFrame(rows)


def build_full_info_macro_correlation_validation(
    *,
    seed: int = 0,
    n_bins: int = 5,
    steps: int = 10,
    top_n: int = 80,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return all full-information macro-correlation validation tables."""

    distribution_log, snapshot_summary = run_short_full_info_log(seed=seed, n_bins=n_bins, steps=steps)
    single_marginals = extract_single_dimension_marginals(distribution_log, n_bins=n_bins)
    pair_functions, pair_scores = extract_pairwise_correlation_functions(distribution_log, n_bins=n_bins)
    rule_candidates = extract_macro_rule_candidates(pair_functions, top_n=top_n)
    trend_alignment = evaluate_trend_alignment(pair_functions, rule_candidates)

    summary = pd.DataFrame(
        [
            {
                "model": "pseudoreality_v3_3_full_info_macro_correlation",
                "seed": int(seed),
                "n_bins": int(n_bins),
                "steps": int(steps),
                "snapshot_count": int(distribution_log["t"].nunique()),
                "baseline_dimension_count": int(len(BASELINE_DIMENSION_COLUMNS)),
                "pair_function_count": int(pair_functions[key_columns].drop_duplicates().shape[0])
                if (key_columns := ["dimension_a", "dimension_b", "bin_a", "bin_b"])
                else 0,
                "pair_score_count": int(pair_scores[["dimension_a", "dimension_b"]].drop_duplicates().shape[0]),
                "macro_rule_candidate_count": int(len(rule_candidates)),
                "max_pair_mutual_information": float(pair_scores["mutual_information"].max()),
                "mean_pair_mutual_information": float(pair_scores["mutual_information"].mean()),
                "max_pair_residual_l1": float(pair_scores["residual_l1"].max()),
                "mean_pair_residual_l1": float(pair_scores["residual_l1"].mean()),
                "mean_weighted_trend_alignment": float(trend_alignment["weighted_alignment_mean"].mean())
                if not trend_alignment.empty
                else 0.0,
                "is_gt": False,
                "uses_full_information_distribution": True,
                "uses_short_log": True,
                "runs_long_horizon_simulation": False,
            }
        ]
    )
    return distribution_log, snapshot_summary, single_marginals, pair_functions, pair_scores, rule_candidates, trend_alignment, summary


def export_full_info_macro_correlation_validation(
    output_root: str | Path,
    *,
    seed: int = 0,
    n_bins: int = 5,
    steps: int = 10,
    top_n: int = 80,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    tables = build_full_info_macro_correlation_validation(seed=seed, n_bins=n_bins, steps=steps, top_n=top_n)
    (
        distribution_log,
        snapshot_summary,
        single_marginals,
        pair_functions,
        pair_scores,
        rule_candidates,
        trend_alignment,
        summary,
    ) = tables
    distribution_log.to_csv(root / "v3_3_full_info_7d_distribution_log.csv", index=False)
    snapshot_summary.to_csv(root / "v3_3_full_info_log_snapshot_summary.csv", index=False)
    single_marginals.to_csv(root / "v3_3_full_info_single_dimension_marginals.csv", index=False)
    pair_functions.to_csv(root / "v3_3_full_info_pairwise_correlation_functions.csv", index=False)
    pair_scores.to_csv(root / "v3_3_full_info_pairwise_information_scores.csv", index=False)
    rule_candidates.to_csv(root / "v3_3_full_info_macro_rule_candidates.csv", index=False)
    trend_alignment.to_csv(root / "v3_3_full_info_trend_alignment.csv", index=False)
    summary.to_csv(root / "v3_3_full_info_macro_correlation_summary.csv", index=False)
    return tables


def compact_readout(summary: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "model",
        "seed",
        "steps",
        "snapshot_count",
        "baseline_dimension_count",
        "pair_score_count",
        "macro_rule_candidate_count",
        "max_pair_mutual_information",
        "mean_pair_mutual_information",
        "max_pair_residual_l1",
        "mean_weighted_trend_alignment",
        "is_gt",
        "runs_long_horizon_simulation",
    ]
    return summary[columns]


if __name__ == "__main__":
    *_tables, _summary = export_full_info_macro_correlation_validation(
        "outputs/pseudoreality-v3-3-macro-correlation/full-info",
        seed=0,
        n_bins=5,
        steps=10,
        top_n=80,
    )
    print(compact_readout(_summary).to_string(index=False))
