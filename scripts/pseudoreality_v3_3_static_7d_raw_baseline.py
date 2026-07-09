"""Static 7D raw baseline for PseudoReality v3.3 provisional freeze.

This is not G_t itself. It is a prerequisite validation artifact used to
check which public coarse indicators are sufficient for later G_t generation.

The baseline starts from the static v3.3-provisional internal distribution
implemented by ``DistributionTerrainV322World`` and builds a sparse 7D reference
histogram:

- d1..d5: source 5D v3.x coordinate bins, kept as coordinate bins only;
- d6: distribution-position bin, derived from cell-mass rank;
- d7: distribution-shape-position bin, derived from local mass contrast.

The two added dimensions are geometric, not semantic. They encode where a cell
sits within the distribution shape, without interpreting the axes as resource,
pressure, payoff, or governance labels.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322Config, DistributionTerrainV322World

SOURCE_DIMENSION_COLUMNS = tuple(f"d{index}_bin" for index in range(1, 6))
GEOMETRY_DIMENSION_COLUMNS = (
    "d6_distribution_position_bin",
    "d7_distribution_shape_position_bin",
)
BASELINE_DIMENSION_COLUMNS = SOURCE_DIMENSION_COLUMNS + GEOMETRY_DIMENSION_COLUMNS


def _rank_bins(values: np.ndarray, *, n_bins: int) -> tuple[np.ndarray, np.ndarray]:
    """Return rank scores in [0, 1] and integer bins in [0, n_bins - 1]."""

    if n_bins < 2:
        raise ValueError("n_bins must be at least 2")
    flat = np.asarray(values, dtype=float).ravel()
    order = np.argsort(flat, kind="mergesort")
    scores = np.empty_like(flat, dtype=float)
    if len(flat) == 1:
        scores[order] = 0.0
    else:
        scores[order] = np.arange(len(flat), dtype=float) / float(len(flat) - 1)
    bins = np.clip(np.floor(scores * n_bins), 0, n_bins - 1).astype(int)
    return scores.reshape(values.shape), bins.reshape(values.shape)


def _neighbor_mean(values: np.ndarray) -> np.ndarray:
    """Mean of direct +/-1 grid neighbors over all source dimensions."""

    array = np.asarray(values, dtype=float)
    neighbor_sum = np.zeros_like(array, dtype=float)
    neighbor_count = np.zeros_like(array, dtype=float)
    for axis in range(array.ndim):
        source = [slice(None)] * array.ndim
        target = [slice(None)] * array.ndim

        source[axis] = slice(1, None)
        target[axis] = slice(0, -1)
        neighbor_sum[tuple(target)] += array[tuple(source)]
        neighbor_count[tuple(target)] += 1.0

        source[axis] = slice(0, -1)
        target[axis] = slice(1, None)
        neighbor_sum[tuple(target)] += array[tuple(source)]
        neighbor_count[tuple(target)] += 1.0

    return neighbor_sum / np.maximum(neighbor_count, 1.0)


def _entropy(mass: np.ndarray) -> float:
    positive = np.asarray(mass, dtype=float)
    positive = positive[positive > 0.0]
    return float(-np.sum(positive * np.log(positive)))


def _axis_marginals(distribution: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for dimension in BASELINE_DIMENSION_COLUMNS:
        grouped = distribution.groupby(dimension, as_index=False)["mass"].sum()
        for _, row in grouped.iterrows():
            rows.append(
                {
                    "dimension": dimension,
                    "bin": int(row[dimension]),
                    "mass": float(row["mass"]),
                }
            )
    return pd.DataFrame(rows)


def build_static_7d_raw_baseline(
    *,
    seed: int = 0,
    n_bins: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build a static 7D sparse reference distribution from v3.3-provisional data.

    Returns ``baseline_distribution``, ``source_cell_mapping``, ``summary``, and
    ``axis_marginals``. The returned baseline is a sparse 7D histogram: zero-mass
    7D cells are intentionally omitted.
    """

    if n_bins != 5:
        # The first baseline intentionally follows the v3.3 provisional freeze:
        # seven dimensions, five bins each. Other bin counts should be introduced
        # only after the 5-bin reference is stable.
        raise ValueError("v3.3 static raw baseline currently fixes n_bins=5")

    world = DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed, n_bins=n_bins))
    mass = np.asarray(world.distribution, dtype=float)
    mass = mass / max(float(mass.sum()), 1e-12)

    density_score, density_bin = _rank_bins(mass, n_bins=n_bins)
    neighbor_mean = _neighbor_mean(mass)
    local_shape_score_raw = np.abs(mass - neighbor_mean) / np.maximum(mass + neighbor_mean, 1e-12)
    shape_score, shape_bin = _rank_bins(local_shape_score_raw, n_bins=n_bins)

    index_grids = np.indices(world.shape)
    source_cell_mapping = pd.DataFrame(
        {
            "cell_id": np.arange(int(np.prod(world.shape)), dtype=int),
            **{column: index_grids[i].ravel().astype(int) for i, column in enumerate(SOURCE_DIMENSION_COLUMNS)},
            "d6_distribution_position_bin": density_bin.ravel().astype(int),
            "d7_distribution_shape_position_bin": shape_bin.ravel().astype(int),
            "mass": mass.ravel(),
            "distribution_position_score": density_score.ravel(),
            "distribution_shape_score": shape_score.ravel(),
            "local_shape_contrast_raw": local_shape_score_raw.ravel(),
        }
    )

    baseline_distribution = (
        source_cell_mapping.groupby(list(BASELINE_DIMENSION_COLUMNS), as_index=False)
        .agg(
            mass=("mass", "sum"),
            source_cell_count=("cell_id", "count"),
            distribution_position_score_mean=("distribution_position_score", "mean"),
            distribution_shape_score_mean=("distribution_shape_score", "mean"),
            local_shape_contrast_raw_mean=("local_shape_contrast_raw", "mean"),
        )
        .sort_values(list(BASELINE_DIMENSION_COLUMNS))
        .reset_index(drop=True)
    )

    mass_values = baseline_distribution["mass"].to_numpy(dtype=float)
    entropy = _entropy(mass_values)
    summary = pd.DataFrame(
        [
            {
                "model": "pseudoreality_v3_3_provisional_static_raw",
                "seed": seed,
                "source_dimension_count": 5,
                "geometry_dimension_count": 2,
                "baseline_dimension_count": 7,
                "n_bins": n_bins,
                "source_cell_count": int(np.prod(world.shape)),
                "baseline_sparse_cell_count": int(len(baseline_distribution)),
                "baseline_full_cell_count": int(n_bins ** len(BASELINE_DIMENSION_COLUMNS)),
                "mass_total": float(mass_values.sum()),
                "entropy": entropy,
                "effective_cell_count": float(np.exp(entropy)),
                "max_cell_mass": float(mass_values.max()),
                "top_1pct_mass_share": float(
                    np.sort(mass_values)[-max(1, int(np.ceil(0.01 * len(mass_values)))) :].sum()
                ),
                "d6_nonempty_bins": int(baseline_distribution["d6_distribution_position_bin"].nunique()),
                "d7_nonempty_bins": int(baseline_distribution["d7_distribution_shape_position_bin"].nunique()),
                "is_static_snapshot": True,
                "is_gt": False,
                "time_axis_included": False,
            }
        ]
    )
    return baseline_distribution, source_cell_mapping, summary, _axis_marginals(baseline_distribution)


def export_static_7d_raw_baseline(
    output_root: str | Path,
    *,
    seed: int = 0,
    n_bins: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Export the static 7D reference distribution and supporting tables."""

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    baseline_distribution, source_cell_mapping, summary, axis_marginals = build_static_7d_raw_baseline(
        seed=seed,
        n_bins=n_bins,
    )
    baseline_distribution.to_csv(root / "v3_3_static_7d_raw_baseline_distribution.csv", index=False)
    source_cell_mapping.to_csv(root / "v3_3_static_7d_raw_source_cell_mapping.csv", index=False)
    summary.to_csv(root / "v3_3_static_7d_raw_summary.csv", index=False)
    axis_marginals.to_csv(root / "v3_3_static_7d_raw_axis_marginals.csv", index=False)
    return baseline_distribution, source_cell_mapping, summary, axis_marginals


def compact_readout(summary: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "model",
        "seed",
        "baseline_dimension_count",
        "n_bins",
        "source_cell_count",
        "baseline_sparse_cell_count",
        "baseline_full_cell_count",
        "mass_total",
        "entropy",
        "effective_cell_count",
        "d6_nonempty_bins",
        "d7_nonempty_bins",
        "is_gt",
        "time_axis_included",
    ]
    return summary[columns]


if __name__ == "__main__":
    _baseline, _mapping, _summary, _marginals = export_static_7d_raw_baseline(
        "outputs/pseudoreality-v3-validation/v3-3-static-7d-raw-baseline",
        seed=0,
        n_bins=5,
    )
    print(compact_readout(_summary).to_string(index=False))
