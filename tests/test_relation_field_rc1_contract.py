from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELATION_CONTRACT = ROOT / "configs" / "relation_field_rc1_contract.json"
FOUNDATION_CONTRACT = ROOT / "configs" / "fixed5axis_gk_rc1_contract.json"
HUMAN_CONTRACT = ROOT / "docs" / "relation_field_rc1" / "CONTRACT.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_relation_field_contract_is_frozen_and_matches_fixed_axis_foundation() -> None:
    relation = _load(RELATION_CONTRACT)
    foundation = _load(FOUNDATION_CONTRACT)

    assert relation["contract_version"] == "relation_field_rc1"
    assert relation["status"] == "frozen_for_rf2_to_rf4"
    assert relation["foundation_contract"] == "configs/fixed5axis_gk_rc1_contract.json"
    assert relation["axes"]["order"] == foundation["axes"]["order"]
    assert relation["axes"]["bins"] == foundation["axes"]["bins"]
    assert relation["axes"]["shape"] == foundation["axes"]["shape"]
    assert relation["axes"]["cell_count"] == foundation["axes"]["cell_count"] == 3125


def test_contract_forbids_leakage_and_internal_external_preclassification() -> None:
    contract = _load(RELATION_CONTRACT)
    forbidden = set(contract["input_boundary"]["forbidden_numeric_inputs"])
    prohibitions = set(contract["prohibitions"])

    assert contract["definition"]["internal_external_preclassification_forbidden"] is True
    assert contract["input_boundary"]["additional_logs_are_required_for_generation"] is False
    assert contract["input_boundary"]["additional_logs_may_be_used_for_posthoc_interpretation"] is True
    assert {
        "scenario_id",
        "seed",
        "dataset_split",
        "observed_external_input_log",
        "terrain_truth",
        "flow_truth",
        "risk_truth",
        "future_state",
    } <= forbidden
    assert "preclassify_internal_vs_external_cause" in prohibitions
    assert "label_novel_drive_as_external_without_independent_evidence" in prohibitions
    assert "use_future_state_for_field_at_t" in prohibitions


def test_causal_cutoff_and_observed_transition_semantics_are_explicit() -> None:
    contract = _load(RELATION_CONTRACT)
    causality = contract["causality"]

    assert "G_0_through_G_t" in causality["field_at_t_may_use"]
    assert "G_after_t" in causality["field_at_t_must_not_use"]
    transition = causality["observed_transition_field"]
    assert transition["requires"] == ["G_from_t", "G_to_t"]
    assert transition["time_index"] == "to_t"
    assert transition["must_not_claim_forecast"] is True
    assert transition["must_not_read_after_to_t"] is True


def test_required_components_uncertainty_and_residual_contract_are_fixed() -> None:
    contract = _load(RELATION_CONTRACT)
    components = contract["components"]

    assert components["local_flow"]["status"] == "rf3_required"
    assert components["local_flow"]["representation"] == (
        "directed_nonnegative_edge_flow_with_derived_signed_net"
    )
    assert components["unresolved_residual"]["must_be_preserved"] is True
    assert components["unresolved_residual"]["must_not_be_forced_into_existing_components"] is True
    assert components["novel_drive"]["must_not_be_labeled_external_by_default"] is True
    assert components["novel_drive"]["must_not_create_net_mass_in_rc1"] is True
    assert components["uncertainty"]["required_types"] == [
        "identifiability",
        "evidence_sufficiency",
        "temporal_stability",
        "out_of_range",
    ]


def test_storage_contract_and_rf4_checkpoint_are_fixed() -> None:
    contract = _load(RELATION_CONTRACT)
    storage = contract["storage"]

    assert storage["field_directory"] == "fields/t_<t:06d>"
    assert storage["required_rf3_rf4_files"] == [
        "identity.json",
        "local_flow_edges.csv",
        "local_flow.npz",
        "reconstruction.json",
        "unresolved_residual.npz",
        "uncertainty.json",
        "manifest.json",
    ]
    assert storage["derived_artifact_recomputable"] is True
    assert storage["canonical_gt_kt_copy_forbidden"] is True
    assert storage["source_writeback_forbidden"] is True
    assert storage["atomic_write_required"] is True
    assert storage["overwrite_existing_field_forbidden"] is True
    assert contract["task_sequence"]["checkpoint_after_rf4"] is True
    assert contract["task_sequence"]["rf5_to_rf10_locked_but_not_started"] is True


def test_normalized_mass_scope_does_not_claim_open_system_source_sink_inference() -> None:
    contract = _load(RELATION_CONTRACT)
    mass = contract["mass_semantics"]

    assert mass["rc1_distribution_is_normalized"] is True
    assert mass["rc1_infers_relative_distribution_dynamics_only"] is True
    assert mass["net_source_sink_inference_supported"] is False
    assert mass["non_normalized_mass_extension_deferred"] is True


def test_human_contract_contains_fixed_boundaries() -> None:
    text = HUMAN_CONTRACT.read_text(encoding="utf-8")

    for required in (
        "内部・外部を事前分類しない",
        "観測済み単一遷移場",
        "未解決残差",
        "RF-4完了後",
        "リスク予測",
        "原本への書戻しを禁止",
    ):
        assert required in text
