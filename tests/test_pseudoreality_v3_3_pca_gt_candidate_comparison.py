from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pseudoreality_v3_3_pca_gt_candidate_comparison import (  # noqa: E402
    CANDIDATE_FAMILIES,
    COMPONENT_COUNTS,
    REQUIRED_OUTPUTS,
    build_full_envelope_corpus,
    run_pca_gt_candidate_comparison,
    snapshot_to_mass_vector,
)


def test_snapshot_to_3125_mass_vector_normalizes() -> None:
    raw = np.ones((5, 5, 5, 5, 5), dtype=float)
    vector = snapshot_to_mass_vector(raw)
    assert len(vector) == 3125
    assert np.isclose(vector.sum(), 1.0)
    assert np.all(vector >= 0.0)


def test_full_envelope_corpus_is_non_empty_and_normalized() -> None:
    manifest, matrix = build_full_envelope_corpus(seed=2, normal_steps=2)
    assert not manifest.empty
    assert matrix.shape[1] == 3125
    assert np.allclose(matrix.sum(axis=1), 1.0)
    assert {"normal", "stress", "concentrated", "diffuse", "multi_peak", "boundary", "mixture", "holdout"}.issubset(set(manifest["scenario_type"]))


def test_candidate_pipeline_generates_required_metrics_and_csvs(tmp_path: Path) -> None:
    tables = run_pca_gt_candidate_comparison(tmp_path, seed=3)

    for filename in REQUIRED_OUTPUTS:
        assert (tmp_path / filename).exists(), filename
        assert filename in tables
        assert isinstance(tables[filename], pd.DataFrame)
        assert not tables[filename].empty

    summary = tables["v3_3_pca_gt_candidate_summary.csv"]
    expected_names = {f"{family}_{count}" for family in CANDIDATE_FAMILIES for count in COMPONENT_COUNTS}
    assert expected_names.issubset(set(summary["candidate_name"]))
    assert "sqrt_static_pca_7" in set(summary["candidate_name"])
    assert summary["reconstruction_error_mean"].notna().all()
    assert summary["residual_energy_ratio_mean"].notna().all()

    decision = tables["v3_3_pca_gt_candidate_decision.csv"]
    primary = decision[decision["candidate_name"] == "sqrt_static_pca_7"].iloc[0]
    assert bool(primary["primary_candidate"])
    assert primary["decision_status"] in {
        "selected_primary_candidate",
        "provisional_primary_candidate",
        "risk_flagged_primary_candidate",
    }

    primary_summary = summary[summary["candidate_name"] == "sqrt_static_pca_7"].iloc[0]
    manifest = tables["v3_3_pca_gt_corpus_manifest.csv"]
    assert int(primary_summary["fit_snapshot_count"]) == int((manifest["corpus_type"] == "fit").sum())
    assert int(primary_summary["holdout_snapshot_count"]) == int((manifest["corpus_type"] == "holdout").sum())
    assert primary_summary["corpus_type"] == "fit_plus_holdout_projection"

    holdout = tables["v3_3_pca_gt_holdout_projection_metrics.csv"]
    assert set(holdout["projection_type"]) == {"true_holdout_projection"}
    assert set(holdout["snapshot_id"]).issubset(set(manifest.loc[manifest["corpus_type"] == "holdout", "snapshot_id"]))

    audit = tables["v3_3_pca_gt_envelope_audit.csv"]
    assert {"in_envelope", "near_boundary", "out_of_envelope", "high_residual"}.intersection(set(audit["audit_status"]))
