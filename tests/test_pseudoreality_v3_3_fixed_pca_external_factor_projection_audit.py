from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pseudoreality_v3_3_fixed_pca_external_factor_projection_audit import (  # noqa: E402
    AUDIT_CANDIDATES,
    PROJECTION_TYPE,
    REQUIRED_CSVS,
    fit_frozen_candidate_bases,
    generate_external_factor_scenarios,
    run_fixed_pca_external_factor_projection_audit,
)


def test_fixed_bases_use_task3_no_external_fit_corpus_only() -> None:
    bases = fit_frozen_candidate_bases(seed=4)
    assert {basis.candidate_name for basis in bases} == {str(spec["candidate_name"]) for spec in AUDIT_CANDIDATES}
    # Task 3 corpus has 121 fit rows and 6 holdout rows by default; the frozen
    # PCA fit must use the fit rows only and therefore must not include external
    # scenario snapshots or Task 3 holdout rows.
    assert {basis.fit.feature_matrix.shape[0] for basis in bases} == {121}
    assert all(basis.residual_threshold > 0.0 for basis in bases)


def test_external_scenario_groups_are_generated() -> None:
    scenarios = generate_external_factor_scenarios()
    groups = {scenario.scenario_group for scenario in scenarios}
    assert {"baseline", "single_sustained_factor", "pulse_shock", "reversal", "compound_pressure"}.issubset(groups)
    names = {scenario.external_factor_name for scenario in scenarios}
    assert "external_shock" in names
    assert "external_resource_supply+external_demand" in names


def test_external_projection_outputs_and_boundaries(tmp_path: Path) -> None:
    tables = run_fixed_pca_external_factor_projection_audit(tmp_path, seed=5, steps=3)

    for filename in REQUIRED_CSVS:
        assert (tmp_path / filename).exists(), filename
        assert filename in tables
        assert not tables[filename].empty or filename.endswith("out_of_envelope_audit.csv")
    assert (tmp_path / "results.md").exists()

    snapshot = tables["v3_3_fixed_pca_external_projection_snapshot_metrics.csv"]
    assert set(snapshot["projection_type"]) == {PROJECTION_TYPE}
    assert "external_residual_gain" in snapshot.columns
    assert "external_score_displacement" in snapshot.columns
    assert "external_gt_velocity" in snapshot.columns
    assert "external_gt_curvature" in snapshot.columns

    summary = tables["v3_3_fixed_pca_external_projection_summary.csv"]
    roles = dict(zip(summary["candidate_name"], summary["candidate_role"], strict=True))
    assert roles["sqrt_static_pca_10"] == "audit_focus_candidate"
    assert "selected" not in " ".join(summary.astype(str).to_numpy().ravel()).lower()

    comparison = tables["v3_3_fixed_pca_external_projection_candidate_comparison.csv"]
    assert set(comparison["review_status"]) == {"requires_human_review"}

    report = (tmp_path / "results.md").read_text()
    assert "does not select the final PCA-G_t candidate" in report
    assert "Human review required before candidate adoption" in report
    assert "H-DEPT" not in report
    assert "ActionModule" not in report
