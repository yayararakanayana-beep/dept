from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pseudoreality_v3_3_static_7d_raw_baseline import (  # noqa: E402
    BASELINE_DIMENSION_COLUMNS,
    build_static_7d_raw_baseline,
    compact_readout,
    export_static_7d_raw_baseline,
)


def test_v3_3_static_7d_raw_baseline_preserves_mass_and_declares_non_gt() -> None:
    baseline, mapping, summary, marginals = build_static_7d_raw_baseline(seed=0, n_bins=5)

    assert len(BASELINE_DIMENSION_COLUMNS) == 7
    assert int(summary.loc[0, "source_dimension_count"]) == 5
    assert int(summary.loc[0, "geometry_dimension_count"]) == 2
    assert int(summary.loc[0, "baseline_dimension_count"]) == 7
    assert int(summary.loc[0, "n_bins"]) == 5
    assert bool(summary.loc[0, "is_gt"]) == False
    assert bool(summary.loc[0, "time_axis_included"]) == False

    assert len(mapping) == 5**5
    assert len(baseline) <= 5**5
    assert int(summary.loc[0, "baseline_full_cell_count"]) == 5**7
    assert np.isclose(float(mapping["mass"].sum()), 1.0)
    assert np.isclose(float(baseline["mass"].sum()), 1.0)
    assert np.isclose(float(summary.loc[0, "mass_total"]), 1.0)

    for column in BASELINE_DIMENSION_COLUMNS:
        assert int(mapping[column].min()) >= 0
        assert int(mapping[column].max()) <= 4
        assert int(baseline[column].min()) >= 0
        assert int(baseline[column].max()) <= 4

    # d6/d7 are geometric bins derived from one static distribution. The required
    # contract is that they add nontrivial geometric position information without
    # requiring every bin to be occupied for every future seed/profile.
    assert int(summary.loc[0, "d6_nonempty_bins"]) >= 2
    assert int(summary.loc[0, "d7_nonempty_bins"]) >= 2
    assert set(marginals["dimension"]) == set(BASELINE_DIMENSION_COLUMNS)


def test_v3_3_static_7d_raw_baseline_exports_expected_tables(tmp_path: Path) -> None:
    baseline, mapping, summary, marginals = export_static_7d_raw_baseline(tmp_path, seed=0, n_bins=5)

    assert not baseline.empty
    assert not mapping.empty
    assert not summary.empty
    assert not marginals.empty
    assert not compact_readout(summary).empty

    assert (tmp_path / "v3_3_static_7d_raw_baseline_distribution.csv").exists()
    assert (tmp_path / "v3_3_static_7d_raw_source_cell_mapping.csv").exists()
    assert (tmp_path / "v3_3_static_7d_raw_summary.csv").exists()
    assert (tmp_path / "v3_3_static_7d_raw_axis_marginals.csv").exists()
