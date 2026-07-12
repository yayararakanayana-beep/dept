from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from relation_field_grid_rc1 import build_grid_artifact  # noqa: E402
from relation_field_single_transition_audit_rc1 import (  # noqa: E402
    RelationFieldAuditError,
    build_audit_artifact,
    load_contract,
    validate_audit_artifact,
)


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def audit_pair(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path]:
    root = tmp_path_factory.mktemp("rf4-audit")
    grid = build_grid_artifact(root / "grid")
    first = build_audit_artifact(grid, root / "audit_a")
    second = build_audit_artifact(grid, root / "audit_b")
    return grid, first, second


def test_rf4_contract_fixes_checkpoint_and_limited_scientific_adoption() -> None:
    contract = load_contract()

    assert contract["status"] == "formal_audit_for_rf4_checkpoint"
    assert contract["minimum_action_audit"]["primal_dual_gap_tolerance"] == 1e-8
    assert contract["alternative_solution_audit"]["secondary_objective_seeds"] == [0, 1, 2, 3, 4, 5]
    assert contract["solver_sensitivity_audit"]["methods"] == ["highs-ds", "highs-ipm", "highs"]
    assert contract["residual_penalty_audit"]["residual_preferred_penalties"] == [0.1]
    assert contract["locality_counterfactual"]["diagnostic_only"] is True
    assert contract["adoption_logic"]["scientific_relation_field_status_if_engineering_A"] == (
        "B_limited_adoption_as_single_transition_basis"
    )


def test_rf4_artifact_is_deterministic_and_formally_valid(
    audit_pair: tuple[Path, Path, Path],
) -> None:
    grid, first, second = audit_pair

    assert _tree_hashes(first) == _tree_hashes(second)
    validation = validate_audit_artifact(first, grid)
    assert validation["rf4_audit_gate"] == "passed"
    assert validation["engineering_basis_judgement"] == "A_pass"
    assert validation["scientific_relation_field_judgement"] == (
        "B_limited_adoption_as_single_transition_basis"
    )
    assert validation["continue_to_rf5_recommended"] is True


def test_all_synthetic_minimum_action_and_dual_certificates_pass(
    audit_pair: tuple[Path, Path, Path],
) -> None:
    _, artifact, _ = audit_pair
    scenarios = _read_jsonl(artifact / "scenario_results.jsonl")
    certificates = json.loads((artifact / "minimum_action_certificates.json").read_text(encoding="utf-8"))

    assert len(scenarios) == 7
    assert all(row["minimum_action_gate"] == "passed" for row in scenarios)
    expected = {
        "no_change": 0.0,
        "adjacent_unique": 0.25,
        "reverse_adjacent_unique": 0.25,
        "two_step_unique": 0.5,
        "square_ambiguous": 0.5,
        "cube_ambiguous": 0.75,
        "split_unique": 0.25,
    }
    assert {row["scenario"]: row["production_primary_objective"] for row in scenarios} == pytest.approx(expected)
    assert certificates["gate"] == "passed"
    assert all(abs(row["primal_dual_gap"]) <= 1e-8 for row in certificates["certificates"])
    assert all(row["maximum_edge_dual_violation"] <= 1e-9 for row in certificates["certificates"])
    assert all(row["maximum_residual_dual_violation"] <= 1e-9 for row in certificates["certificates"])


def test_alternative_optimum_audit_distinguishes_unique_and_ambiguous_cases(
    audit_pair: tuple[Path, Path, Path],
) -> None:
    _, artifact, _ = audit_pair
    report = json.loads((artifact / "alternative_solution_audit.json").read_text(encoding="utf-8"))
    rows = {row["scenario"]: row for row in report["scenario_results"]}

    assert report["gate"] == "passed"
    for name in ("no_change", "adjacent_unique", "two_step_unique", "split_unique"):
        assert rows[name]["alternative_optimum_detected"] is False
        assert rows[name]["unique_witness_count"] == 1
    for name in ("square_ambiguous", "cube_ambiguous"):
        assert rows[name]["alternative_optimum_detected"] is True
        assert rows[name]["unique_witness_count"] >= 2
        assert rows[name]["maximum_pairwise_net_flow_l1"] > 1e-6
        assert rows[name]["witness_search_exhaustive"] is False


def test_solver_methods_preserve_primary_objective_not_flow_identity(
    audit_pair: tuple[Path, Path, Path],
) -> None:
    _, artifact, _ = audit_pair
    report = json.loads((artifact / "solver_sensitivity.json").read_text(encoding="utf-8"))

    assert report["gate"] == "passed"
    assert all(row["primary_objective_spread"] <= 1e-9 for row in report["scenario_results"])
    assert all(row["flow_identity_required"] is False for row in report["scenario_results"])
    assert all(
        method["reconstruction_max_abs_error"] <= 1e-9
        for row in report["scenario_results"]
        for method in row["methods"]
    )


def test_residual_penalty_audit_exposes_model_choice(
    audit_pair: tuple[Path, Path, Path],
) -> None:
    _, artifact, _ = audit_pair
    report = json.loads((artifact / "residual_penalty_sensitivity.json").read_text(encoding="utf-8"))
    rows = {row["residual_penalty"]: row for row in report["results"]}

    assert report["gate"] == "passed"
    assert rows[5.25]["residual_l1"] <= 1e-9
    assert rows[0.5]["residual_l1"] <= 1e-9
    assert rows[0.1]["residual_l1"] >= 1.9
    assert rows[0.1]["total_directed_edge_flow"] <= 1e-9


def test_locality_counterfactual_is_explicit_limitation(
    audit_pair: tuple[Path, Path, Path],
) -> None:
    _, artifact, _ = audit_pair
    report = json.loads((artifact / "locality_counterfactual.json").read_text(encoding="utf-8"))

    assert report["gate"] == "passed"
    assert report["diagnostic_only"] is True
    assert report["locality_assumption_material"] is True
    assert report["local_grid_primary_objective"] == pytest.approx(0.5)
    assert report["counterfactual_primary_objective"] == pytest.approx(0.25)
    assert report["synthetic_shortcut_net_flow"] == pytest.approx(1.0)


def test_adoption_decision_keeps_engineering_and_scientific_claims_separate(
    audit_pair: tuple[Path, Path, Path],
) -> None:
    _, artifact, _ = audit_pair
    decision = json.loads((artifact / "adoption_decision.json").read_text(encoding="utf-8"))

    assert decision["engineering_basis_judgement"] == "A_pass"
    assert decision["scientific_relation_field_judgement"] == (
        "B_limited_adoption_as_single_transition_basis"
    )
    assert decision["continue_to_rf5_recommended"] is True
    assert len(decision["why_scientific_A_is_not_claimed"]) >= 4
    assert decision["gates"]["alternative_solution_expectations_pass"] is True
    assert decision["gates"]["locality_materiality_detected"] is True


def test_manifest_tampering_and_overwrite_are_rejected(
    tmp_path: Path,
    audit_pair: tuple[Path, Path, Path],
) -> None:
    grid, artifact, _ = audit_pair
    copied = tmp_path / "copied"
    shutil.copytree(artifact, copied)
    summary = copied / "summary.json"
    summary.write_text(summary.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(RelationFieldAuditError, match="manifest"):
        validate_audit_artifact(copied, grid)
    with pytest.raises(RelationFieldAuditError, match="already exists"):
        build_audit_artifact(grid, artifact)
