from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.pseudoreality_v3_3_external_envelope_fixed_pca_audit as audit  # noqa: E402

FORBIDDEN = ("selected", "final", "winner", "adopted", "best", "primary_selected")


def _mini_task3_corpus(seed: int = 0):
    rng = np.random.default_rng(seed)
    rows = []
    vectors = []
    for i, group in enumerate(("normal", "stress", "concentrated", "diffuse", "multi_peak", "boundary", "mixture")):
        for j in range(2):
            vec = rng.random(5**5) + (i + 1) * 1e-4
            vec = vec / vec.sum()
            rows.append({"snapshot_id": f"mini_{group}_{j}", "scenario_type": group, "corpus_type": "fit", "mass_total": 1.0})
            vectors.append(vec)
    rows.append({"snapshot_id": "mini_holdout", "scenario_type": "holdout", "corpus_type": "holdout", "mass_total": 1.0})
    vectors.append(np.ones(5**5) / (5**5))
    return pd.DataFrame(rows), np.vstack(vectors)


def _small_fit_scenarios(steps: int = 1):
    return [
        audit.ExternalScenario("fit_single_resource", "single_sustained_factor", "external_resource_supply", 0.5, steps, lambda _t: audit._with_factor("external_resource_supply", 0.5)),
        audit.ExternalScenario("fit_pulse_shock", "pulse_factor", "external_shock", 1.0, steps, lambda t: audit._with_factor("external_shock", 1.0) if t == 0 else audit.zero_factors()),
        audit.ExternalScenario("fit_reversal_demand", "reversal_factor", "external_demand", 1.0, steps, lambda t: audit._with_factor("external_demand", 1.0 if t == 0 else -1.0)),
        audit.ExternalScenario("fit_compound", "compound_pressure", "external_shock+external_constraint_pressure", 0.75, steps, lambda _t: {**audit.zero_factors(), "external_shock": 0.75, "external_constraint_pressure": 0.75}),
    ]


def _small_holdout_scenarios(steps: int = 1):
    return [
        audit.ExternalScenario("holdout_unseen_intensity", "unseen_factor_intensity", "external_information_noise", 0.60, steps, lambda _t: audit._with_factor("external_information_noise", 0.60)),
        audit.ExternalScenario("holdout_late_pulse", "different_pulse_timing", "external_shock", 1.0, steps, lambda _t: audit._with_factor("external_shock", 1.0)),
    ]


def test_script_uses_real_validation_data_generation_paths() -> None:
    source = Path("scripts/pseudoreality_v3_3_external_envelope_fixed_pca_audit.py").read_text()
    assert "def _factor_vector" not in source
    assert "def _lightweight_task3_fit_corpus" not in source
    assert "build_full_envelope_corpus(seed=seed)" in source
    scenario_source = inspect.getsource(audit._scenario_rows)
    assert "DistributionTerrainV322World" in scenario_source
    assert "DistributionTerrainV322Config" in scenario_source
    assert "world.set_external_factors" in scenario_source
    assert "world.step()" in scenario_source
    assert "snapshot_to_mass_vector(world.distribution)" in scenario_source


def test_external_envelope_fit_corpus_includes_real_task3_fit_and_external_rows(monkeypatch) -> None:
    monkeypatch.setattr(audit, "build_full_envelope_corpus", _mini_task3_corpus)
    monkeypatch.setattr(audit, "fit_external_scenarios", _small_fit_scenarios)
    monkeypatch.setattr(audit, "FIT_SEEDS", (0,))
    manifest, mass = audit.build_external_envelope_fit_corpus(seed=1, steps=1)
    assert len(manifest) == mass.shape[0]
    assert {"fit_no_external_reference", "fit_external"}.issubset(set(manifest["corpus_split"]))
    assert "holdout" not in set(manifest["scenario_group"])
    assert {"normal", "stress", "concentrated", "diffuse", "multi_peak", "boundary", "mixture"}.issubset(set(manifest["scenario_group"]))
    assert {"single_sustained_factor", "pulse_factor", "reversal_factor", "compound_pressure"}.issubset(set(manifest["scenario_group"]))


def test_holdout_rows_are_separate_from_pca_fit_rows(monkeypatch) -> None:
    monkeypatch.setattr(audit, "build_full_envelope_corpus", _mini_task3_corpus)
    monkeypatch.setattr(audit, "fit_external_scenarios", _small_fit_scenarios)
    monkeypatch.setattr(audit, "holdout_external_scenarios", _small_holdout_scenarios)
    monkeypatch.setattr(audit, "FIT_SEEDS", (0,))
    monkeypatch.setattr(audit, "HOLDOUT_SEEDS", (10,))
    fit_manifest, _ = audit.build_external_envelope_fit_corpus(seed=2, steps=1)
    holdout_manifest, _ = audit.build_holdout_corpus(steps=1)
    assert set(holdout_manifest["corpus_split"]) == {"holdout_external"}
    assert set(fit_manifest["snapshot_id"]).isdisjoint(set(holdout_manifest["snapshot_id"]))


def test_required_candidates_are_present_and_neutral() -> None:
    names = {str(spec["candidate_name"]) for spec in audit.CANDIDATES}
    assert names == {
        "sqrt_static_pca_10_external_envelope",
        "sqrt_static_pca_12_external_envelope",
        "sqrt_static_pca_15_external_envelope",
        "raw_static_pca_10_external_envelope",
        "sqrt_sparse_temporal_lag_pca_10_external_envelope",
    }
    role_text = " ".join(str(spec.get("candidate_role", "")) for spec in audit.CANDIDATES).lower()
    assert not any(word in role_text for word in FORBIDDEN)


def test_outputs_tables_boundaries_and_no_default_detailed_logs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "build_full_envelope_corpus", _mini_task3_corpus)
    monkeypatch.setattr(audit, "fit_external_scenarios", _small_fit_scenarios)
    monkeypatch.setattr(audit, "holdout_external_scenarios", _small_holdout_scenarios)
    monkeypatch.setattr(audit, "FIT_SEEDS", (0,))
    monkeypatch.setattr(audit, "HOLDOUT_SEEDS", (10,))

    tables = audit.run_external_envelope_fixed_pca_audit(tmp_path, seed=3, steps=1)
    for filename in audit.REQUIRED_OUTPUTS:
        path = tmp_path / filename
        assert path.exists(), filename
        assert filename in tables
        assert not tables[filename].empty
    assert (tmp_path / "results.md").exists()
    for detailed_name in ("full_snapshot_metrics.csv", "snapshot_metrics.csv", "full_per_snapshot_log.csv", "full_time_series_scores.csv"):
        assert not (tmp_path / detailed_name).exists()

    summary = tables["compact_candidate_summary.csv"]
    for column in (
        "out_of_envelope_rate",
        "external_residual_gain_mean",
        "external_score_displacement_mean",
        "delta_out_of_envelope_rate_vs_task3_1",
    ):
        assert column in summary.columns
    assert set(summary["dataset"]) == {"fit_external", "holdout_external", "no_external_reference"}
    assert summary.groupby("dataset")["candidate_name"].nunique().to_dict() == {
        "fit_external": 5,
        "holdout_external": 5,
        "no_external_reference": 5,
    }

    status_text = " ".join(str(v) for column in ("candidate_role", "review_status") for v in tables["compact_candidate_comparison.csv"][column].to_numpy()).lower()
    assert not any(word in status_text for word in FORBIDDEN)

    report = (tmp_path / "results.md").read_text()
    assert "| candidate_name |" in report
    assert "This report does not select the final PCA-G_t candidate. Final adoption decision is reserved for human review." in report
    assert "Lower out-of-envelope rate alone is not sufficient. G_t displacement and factor-response separation must also be preserved." in report
    assert report.count("_external_envelope |") >= 15


def test_no_core_or_action_connection_files_modified() -> None:
    changed = {line.strip() for line in __import__("subprocess").check_output(["git", "diff", "--name-only", "HEAD~1..HEAD"], text=True).splitlines()}
    assert "pseudo_reality/distribution_terrain_v3_2_2.py" not in changed
    source = Path("scripts/pseudoreality_v3_3_external_envelope_fixed_pca_audit.py").read_text().lower()
    assert "connect_h_dept" not in source
    assert "connect_o_t" not in source
    assert "actionmodule(" not in source
