from pathlib import Path

import pandas as pd

import scripts.pseudoreality_v3_3_external_envelope_residual_decomposition_audit as audit

SCRIPT = Path("scripts/pseudoreality_v3_3_external_envelope_residual_decomposition_audit.py")


def test_task3_1b_real_generation_path_is_reused_without_artificial_vectors():
    text = SCRIPT.read_text()
    assert "DistributionTerrainV322World" in text
    assert "world.set_external_factors" not in text  # delegated to Task 3.1b generator
    assert "build_external_envelope_fit_corpus" in text
    assert "build_holdout_corpus" in text
    assert "build_full_envelope_corpus" in text
    assert "snapshot_to_mass_vector" in text
    forbidden = ["artificial", "synthetic", "random vector", "np.random.normal"]
    assert not any(term in text for term in forbidden)


def test_no_dynamic_pca_or_h_dept_action_connections_added():
    text = SCRIPT.read_text()
    assert "dynamic PCA" not in text
    assert "IncrementalPCA" not in text
    assert "partial_fit" not in text
    assert "ActionModule" not in text
    assert "H-DEPT" not in text
    assert "O_t" not in text


def _patch_small_real_shape_inputs(monkeypatch):
    import numpy as np
    import pandas as pd
    from types import SimpleNamespace
    fit = SimpleNamespace(mean=np.zeros(3), components=np.eye(2, 3), transformed=np.array([[0.0, 0.0], [1.0, 0.5], [0.5, 1.0]]))
    basis = SimpleNamespace(candidate_name="sqrt_static_pca_10_external_envelope", candidate_role="focus_candidate", family="sqrt_static_pca", fit=fit, score_min=np.array([-1.0, -1.0]), score_max=np.array([1.0, 1.0]), score_std=np.ones(2), residual_threshold=0.1, mahalanobis_threshold=2.0)
    def man(split, sid):
        return pd.DataFrame({"snapshot_id":[f"{sid}_t0", f"{sid}_t1", f"{sid}_t2"], "scenario_id":[sid]*3, "scenario_group":["unit"]*3, "external_factor_name":["external_shock"]*3, "external_factor_value":[1.0]*3, "seed":[0]*3, "t":[0,1,2], "corpus_split":[split]*3, "mass_total":[1.0]*3})
    monkeypatch.setattr(audit, "fit_bases", lambda seed, steps: ([basis], pd.concat([man("fit_external", "fit_unit"), man("fit_no_external_reference", "no_ext")], ignore_index=True), np.array([[1.,0,0],[.8,.2,0],[.6,.3,.1],[1.,0,0],[.9,.1,0],[.8,.1,.1]])))
    monkeypatch.setattr(audit, "build_holdout_corpus", lambda steps: (man("holdout_external", "holdout_unit"), np.array([[1.,0,0],[.7,.2,.1],[.5,.4,.1]])))


def test_residual_decomposition_outputs_and_default_no_detailed_logs(tmp_path, monkeypatch):
    _patch_small_real_shape_inputs(monkeypatch)
    tables = audit.run_residual_decomposition_audit(tmp_path, steps=1)
    expected_files = {
        "compact_residual_decomposition_summary.csv",
        "compact_auto_audit_flag_reason_summary.csv",
        "compact_factor_residual_summary.csv",
        "compact_temporal_residual_summary.csv",
        "compact_residual_gt_relation_summary.csv",
        "compact_residual_terrain_summary.csv",
    }
    assert expected_files <= {p.name for p in tmp_path.iterdir()}
    assert not any((tmp_path / name).exists() for name in audit.DETAILED_NAMES)

    residual = pd.read_csv(tmp_path / "compact_residual_decomposition_summary.csv")
    assert {
        "residual_energy_ratio_mean", "residual_energy_ratio_median", "residual_energy_ratio_p90",
        "residual_energy_ratio_p95", "residual_energy_ratio_max", "mahalanobis_distance_p95",
        "score_range_violation_rate", "auto_audit_flag_rate",
    } <= set(residual.columns)

    flags = pd.read_csv(tmp_path / "compact_auto_audit_flag_reason_summary.csv")
    assert {
        "residual_threshold", "mahalanobis_threshold", "residual_exceed_rate",
        "mahalanobis_exceed_rate", "score_range_exceed_rate", "residual_only_rate",
        "mahalanobis_only_rate", "score_range_only_rate", "residual_and_mahalanobis_rate",
        "residual_and_score_range_rate", "mahalanobis_and_score_range_rate",
        "all_three_exceed_rate", "no_flag_rate", "auto_audit_flag_rate",
    } <= set(flags.columns)

    assert {"external_factor_name", "external_gt_velocity_mean"} <= set(pd.read_csv(tmp_path / "compact_factor_residual_summary.csv").columns)
    assert {"residual_persistence_rate", "flag_persistence_rate", "residual_slope"} <= set(pd.read_csv(tmp_path / "compact_temporal_residual_summary.csv").columns)
    assert {"correlation_residual_displacement", "high_residual_high_displacement_rate"} <= set(pd.read_csv(tmp_path / "compact_residual_gt_relation_summary.csv").columns)
    assert {"top_residual_mass_share", "residual_concentration_score"} <= set(pd.read_csv(tmp_path / "compact_residual_terrain_summary.csv").columns)


def test_results_md_is_diagnostic_not_candidate_decision(tmp_path, monkeypatch):
    _patch_small_real_shape_inputs(monkeypatch)
    audit.run_residual_decomposition_audit(tmp_path, steps=1)
    text = (tmp_path / "results.md").read_text()
    assert "This report does not select, reject, or adopt any PCA-G_t candidate." in text
    assert "Automatic audit flags are diagnostic signals, not final validity judgments." in text
    assert "このレポートはPCA-G_t候補を採用・不採用にするものではない。" in text
    banned = ["winner", "best", "adopted", "final decision", "採用不可", "失敗", "有効範囲外と確定"]
    assert not any(term in text for term in banned)
