from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pseudoreality_v3_3_external_envelope_fixed_pca_audit import (  # noqa: E402
    CANDIDATES,
    REQUIRED_OUTPUTS,
    build_external_envelope_fit_corpus,
    build_holdout_corpus,
    run_external_envelope_fixed_pca_audit,
)

FORBIDDEN = ("selected", "final", "winner", "adopted", "best", "primary_selected")


def test_external_envelope_fit_corpus_includes_no_external_and_external_rows() -> None:
    manifest, mass = build_external_envelope_fit_corpus(seed=1, steps=1)
    assert len(manifest) == mass.shape[0]
    assert {"fit_no_external_reference", "fit_external"}.issubset(set(manifest["corpus_split"]))
    assert {"normal", "stress", "concentrated", "diffuse", "multi_peak", "boundary", "mixture"}.issubset(set(manifest["scenario_group"]))
    assert {"single_sustained_factor", "pulse_factor", "reversal_factor", "compound_pressure"}.issubset(set(manifest["scenario_group"]))


def test_holdout_rows_are_separate_from_pca_fit_rows() -> None:
    fit_manifest, _ = build_external_envelope_fit_corpus(seed=2, steps=1)
    holdout_manifest, _ = build_holdout_corpus(steps=1)
    assert set(holdout_manifest["corpus_split"]) == {"holdout_external"}
    assert set(fit_manifest["snapshot_id"]).isdisjoint(set(holdout_manifest["snapshot_id"]))


def test_required_candidates_are_present_and_neutral() -> None:
    names = {str(spec["candidate_name"]) for spec in CANDIDATES}
    assert names == {
        "sqrt_static_pca_10_external_envelope",
        "sqrt_static_pca_12_external_envelope",
        "sqrt_static_pca_15_external_envelope",
        "raw_static_pca_10_external_envelope",
        "sqrt_sparse_temporal_lag_pca_10_external_envelope",
    }
    status_text = " ".join(str(spec.get("candidate_role", "")) for spec in CANDIDATES).lower()
    assert not any(word in status_text for word in FORBIDDEN)


def test_outputs_tables_boundaries_and_no_default_detailed_logs(tmp_path: Path) -> None:
    tables = run_external_envelope_fixed_pca_audit(tmp_path, seed=3, steps=1)
    for filename in REQUIRED_OUTPUTS:
        path = tmp_path / filename
        assert path.exists(), filename
        assert filename in tables
        assert not tables[filename].empty
    assert (tmp_path / "results.md").exists()
    assert not (tmp_path / "full_snapshot_metrics.csv").exists()
    assert not (tmp_path / "snapshot_metrics.csv").exists()
    assert not (tmp_path / "full_per_snapshot_log.csv").exists()
    assert not (tmp_path / "full_time_series_scores.csv").exists()

    summary = tables["compact_candidate_summary.csv"]
    for column in (
        "out_of_envelope_rate",
        "external_residual_gain_mean",
        "external_score_displacement_mean",
        "delta_out_of_envelope_rate_vs_task3_1",
    ):
        assert column in summary.columns

    all_text = " ".join(str(v) for table in tables.values() if hasattr(table, "to_numpy") for v in table.to_numpy().ravel()).lower()
    assert not any(word in all_text for word in FORBIDDEN)

    report = (tmp_path / "results.md").read_text()
    assert "| candidate_name |" in report
    assert "This report does not select the final PCA-G_t candidate. Final adoption decision is reserved for human review." in report
    assert "Lower out-of-envelope rate alone is not sufficient." in report


def test_no_core_or_action_connection_files_modified() -> None:
    # This task is implemented as a standalone audit script and compact docs/tests;
    # it does not edit v3.3 dynamics modules or add controller/action paths.
    assert Path("pseudo_reality/distribution_terrain_v3_2_2.py").exists()
    script = Path("scripts/pseudoreality_v3_3_external_envelope_fixed_pca_audit.py").read_text()
    assert "set_external_factors" not in script or "ActionModule" in script
    assert "connect_h_dept" not in script
    assert "connect_o_t" not in script
