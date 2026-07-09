from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pseudoreality_v3_3_full_info_macro_correlation_validation import (  # noqa: E402
    build_full_info_macro_correlation_validation,
    compact_readout,
    export_full_info_macro_correlation_validation,
)
from scripts.pseudoreality_v3_3_static_7d_raw_baseline import BASELINE_DIMENSION_COLUMNS  # noqa: E402


def test_extracts_pair_functions() -> None:
    tables = build_full_info_macro_correlation_validation(seed=0, steps=3, top_n=20)
    distribution_log, snapshot_summary, single_marginals = tables[0], tables[1], tables[2]
    pair_functions, pair_scores, rule_candidates = tables[3], tables[4], tables[5]
    trend_alignment, summary = tables[6], tables[7]

    assert int(summary.loc[0, "baseline_dimension_count"]) == 7
    assert not bool(summary.loc[0, "is_gt"])
    assert bool(summary.loc[0, "uses_full_information_distribution"])
    assert bool(summary.loc[0, "uses_short_log"])

    assert distribution_log["t"].nunique() == 4
    assert snapshot_summary["t"].nunique() == 4
    assert not single_marginals.empty
    assert not pair_functions.empty
    assert not pair_scores.empty
    assert not rule_candidates.empty
    assert not trend_alignment.empty

    expected_pair_count = len(BASELINE_DIMENSION_COLUMNS) * (len(BASELINE_DIMENSION_COLUMNS) - 1) // 2
    assert int(summary.loc[0, "pair_score_count"]) == expected_pair_count
    assert pair_scores[["dimension_a", "dimension_b"]].drop_duplicates().shape[0] == expected_pair_count
    assert len(rule_candidates) == 20

    assert np.isfinite(pair_scores["mutual_information"]).all()
    assert float(pair_scores["mutual_information"].max()) > 0.0
    assert np.isfinite(pair_functions["residual_mass"]).all()
    assert np.isclose(distribution_log.groupby("t")["mass"].sum().min(), 1.0)
    assert np.isclose(distribution_log.groupby("t")["mass"].sum().max(), 1.0)


def test_exports_expected_tables(tmp_path: Path) -> None:
    tables = export_full_info_macro_correlation_validation(tmp_path, seed=0, steps=3, top_n=20)
    assert not compact_readout(tables[-1]).empty
    expected_files = (
        "v3_3_full_info_7d_distribution_log.csv",
        "v3_3_full_info_log_snapshot_summary.csv",
        "v3_3_full_info_single_dimension_marginals.csv",
        "v3_3_full_info_pairwise_correlation_functions.csv",
        "v3_3_full_info_pairwise_information_scores.csv",
        "v3_3_full_info_macro_rule_candidates.csv",
        "v3_3_full_info_trend_alignment.csv",
        "v3_3_full_info_macro_correlation_summary.csv",
    )
    for filename in expected_files:
        assert (tmp_path / filename).exists()
