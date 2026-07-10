import json
from pathlib import Path

import numpy as np
import pandas as pd

DOC = Path("docs/task3_1e_external_factor_augmented_full_distribution_design")
SCRIPT = Path("scripts/pseudoreality_v3_3_external_factor_augmented_full_distribution_design.py")
REQUIRED = [
    "results.md",
    "artifact_manifest.csv",
    "full_distribution_schema.csv",
    "external_factor_action_type_catalog.csv",
    "full_distribution_state_manifest.csv",
    "full_distribution_state_index.csv",
    "full_distribution_mass_matrix.jsonl",
    "distribution_group_summary.csv",
    "external_factor_metadata_summary.csv",
]


def _manifest():
    return pd.read_csv(DOC / "full_distribution_state_manifest.csv")


def _artifact():
    return pd.read_csv(DOC / "artifact_manifest.csv").iloc[0]


def _as_bool(x):
    return str(x).lower() == "true"


def _jsonl_rows():
    with (DOC / "full_distribution_mass_matrix.jsonl").open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_required_files_exist():
    for name in REQUIRED:
        assert (DOC / name).exists(), name


def test_distribution_group_policy():
    m = _manifest()
    assert "distribution_group" in m.columns
    assert set(m.distribution_group).issubset({"base_v3_3", "external_augmented"})
    assert "base_v3_3" in set(m.distribution_group)
    assert "external_augmented" in set(m.distribution_group)
    assert (m.distribution_group == "base_v3_3").sum() > 0
    assert (m.distribution_group == "external_augmented").sum() > 0
    assert "combined_full" not in set(m.distribution_group)
    s = pd.read_csv(DOC / "distribution_group_summary.csv")
    assert set(s.distribution_group).issubset({"base_v3_3", "external_augmented", "combined_full"})


def test_external_factor_metadata_not_axes():
    m = _manifest()
    base = m[m.distribution_group == "base_v3_3"]
    ext = m[m.distribution_group == "external_augmented"]
    assert (ext.external_factor_family.astype(str) != "none").all()
    assert (base.external_factor_family.astype(str) == "none").all()
    assert (base.external_factor_count.astype(int) == 0).all()
    schema = pd.read_csv(DOC / "full_distribution_schema.csv")
    ef = schema[schema.field_name.str.startswith("external_factor_")]
    assert not ef.empty
    assert (ef.is_axis.astype(str).str.lower() == "false").all()
    assert (ef.is_metadata.astype(str).str.lower() == "true").all()
    catalog = pd.read_csv(DOC / "external_factor_action_type_catalog.csv")
    assert (catalog.metadata_only_not_axis.astype(str).str.lower() == "true").all()


def test_base_pair_key_matches_base_rows():
    m = _manifest()
    assert m.base_pair_key.astype(str).str.len().gt(0).all()
    base_keys = set(m.loc[m.distribution_group == "base_v3_3", "base_pair_key"])
    assert base_keys
    ext = m[m.distribution_group == "external_augmented"]
    assert set(ext.base_pair_key).issubset(base_keys)
    assert int(_artifact().base_pair_key_unmatched_external_count) == 0


def test_mass_matrix_integrity():
    m = _manifest()
    assert np.allclose(m.mass_sum.astype(float), 1.0, atol=1e-6)
    assert (m.cell_count.astype(int) > 0).all()
    assert (m.nonzero_cell_count.astype(int) > 0).all()
    assert (DOC / "full_distribution_mass_matrix.jsonl").exists()
    assert not (DOC / "full_distribution_mass_matrix.npz").exists()
    assert not list(DOC.glob("*.npz"))
    assert not list(DOC.glob("*.npy"))
    rows = _jsonl_rows()
    assert len(rows) == len(m)
    cell_count = int(m.cell_count.iloc[0])
    for row in rows:
        vector = np.asarray(row["mass_vector"], dtype=float)
        assert len(vector) == cell_count == int(row["cell_count"])
        assert np.isclose(vector.sum(), 1.0, atol=1e-6)
        assert np.isfinite(vector).all()
        assert (vector >= 0).all()


def test_state_index_order_matches_manifest_and_jsonl():
    m = _manifest()
    idx = pd.read_csv(DOC / "full_distribution_state_index.csv")
    rows = _jsonl_rows()
    assert len(idx) == len(m) == len(rows)
    assert idx.row_index.tolist() == list(range(len(idx)))
    assert [r["row_index"] for r in rows] == list(range(len(rows)))
    assert idx.distribution_state_id.tolist() == m.distribution_state_id.tolist()
    assert [r["distribution_state_id"] for r in rows] == idx.distribution_state_id.tolist()

def test_artifact_manifest_cross_checks():
    m = _manifest()
    a = _artifact()
    assert _as_bool(a.official_docs_artifact)
    assert not _as_bool(a.reduced_run)
    assert not _as_bool(a.short_run_configuration)
    assert _as_bool(a.uses_production_world)
    assert _as_bool(a.uses_distribution_terrain_v322_world)
    assert _as_bool(a.uses_external_factor_augmented_states)
    assert _as_bool(a.separates_base_and_external)
    assert _as_bool(a.combined_full_is_summary_only)
    base_count = int((m.distribution_group == "base_v3_3").sum())
    ext_count = int((m.distribution_group == "external_augmented").sum())
    assert int(a.base_state_count) == base_count > 0
    assert int(a.external_augmented_state_count) == ext_count > 0
    assert int(a.combined_full_state_count) == base_count + ext_count == len(m)
    assert str(a.mass_matrix_format) == "jsonl_text"
    assert int(a.mass_matrix_row_count) == int(a.state_manifest_row_count) == len(m) == len(_jsonl_rows())
    assert int(a.state_index_row_count) == len(m)
    assert int(a.mass_matrix_cell_count) == int(m.cell_count.iloc[0])


def test_results_md_required_policy_text():
    text = (DOC / "results.md").read_text(encoding="utf-8")
    for phrase in [
        "does not select semantic axes",
        "does not reduce candidates to 15 axes",
        "does not perform structure extraction",
        "does not use PCA as the primary log basis",
        "External factors are not axes",
        "base_v3_3 and external_augmented are stored separately",
        "combined_full is a later aggregation view",
        "full_distribution_mass_matrix.jsonl stores the actual distribution mass rows",
        "CSV summaries alone are not treated as the full distribution",
        "No binary docs artifact is used for Task 3.1e",
        "No K_t connection",
        "No O_t connection",
        "No H-DEPT connection",
        "No ActionModule connection",
        "No world-core modification",
    ]:
        assert phrase in text


def test_forbidden_terms_split_by_artifact_type():
    script = SCRIPT.read_text(encoding="utf-8")
    for term in ["IncrementalPCA", "partial_fit", "NMF", "DictionaryLearning", "axis_classification_summary", "core_candidate", "selected_15_axes", "external_factor_axis", "residual_axis"]:
        assert term not in script
    for term in ["K_t", "O_t", "H-DEPT", "ActionModule"]:
        assert term not in script
    forbidden_csv = ["core_candidate", "selected_15_axes", "external_factor_axis", "residual_axis"]
    for csv_path in DOC.glob("*.csv"):
        frame = pd.read_csv(csv_path, dtype=str)
        tokens = set(frame.columns) | set(frame.fillna("").to_numpy().reshape(-1).tolist())
        for term in forbidden_csv:
            assert term not in tokens, f"{term} in {csv_path}"


def test_no_short_run_official_escape_hatches():
    a = _artifact()
    assert _as_bool(a.official_docs_artifact)
    assert not _as_bool(a.reduced_run)
    assert not _as_bool(a.short_run_configuration)
    assert _as_bool(a.uses_production_world)
    assert _as_bool(a.uses_distribution_terrain_v322_world)
    assert (DOC / "full_distribution_mass_matrix.jsonl").exists()
    assert not (DOC / "full_distribution_mass_matrix.npz").exists()
    assert not list(DOC.glob("*.npz"))
    assert not list(DOC.glob("*.npy"))
    assert (DOC / "full_distribution_state_manifest.csv").exists()
    m = _manifest()
    assert len(_jsonl_rows()) == len(m)
    script = SCRIPT.read_text(encoding="utf-8")
    for bad in ["default=3", "fit_external_scenarios(steps)[:", "holdout_external_scenarios(steps)[:", "FIT_SEEDS[:1]", "FIT_SEEDS[:2]", "HOLDOUT_SEEDS[:1]"]:
        assert bad not in script
