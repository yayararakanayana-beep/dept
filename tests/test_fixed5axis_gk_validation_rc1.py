from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from fixed5axis_gk_validation_rc1 import (  # noqa: E402
    ValidationError,
    _external_vector,
    load_validation_config,
    validate_output,
)
from fixed5axis_gk_validation_rc1_corrected import run_validation  # noqa: E402


def test_validation_contract_and_external_strength() -> None:
    config, profile = load_validation_config(
        ROOT / "configs" / "fixed5axis_gk_validation_rc1.json", "smoke"
    )
    assert profile["scenario_names"][0] == "baseline"
    baseline = _external_vector(config, "fit", "baseline", True)
    shortage = _external_vector(config, "validation", "resource_shortage", True)
    noise = _external_vector(config, "holdout", "information_noise", True)
    assert all(value == 0.0 for value in baseline.values())
    assert shortage["external_resource_supply"] == pytest.approx(-0.65)
    assert noise["external_information_noise"] == pytest.approx(0.80)


def test_smoke_validation_produces_locked_auditable_artifact(tmp_path: Path) -> None:
    output = run_validation(
        ROOT / "configs" / "fixed5axis_gk_validation_rc1.json",
        "smoke",
        tmp_path / "artifact",
    )
    result = validate_output(output)
    assert result["status"] == "valid"

    roundtrip = json.loads(
        (output / "representation_integrity" / "exact_roundtrip.json").read_text(
            encoding="utf-8"
        )
    )
    deterministic = json.loads(
        (output / "representation_integrity" / "deterministic_rebuild.json").read_text(
            encoding="utf-8"
        )
    )
    lock_validation = json.loads(
        (output / "threshold_lock_validation.json").read_text(encoding="utf-8")
    )
    metrics = json.loads(
        (output / "final" / "validation_metrics.json").read_text(encoding="utf-8")
    )
    correction = json.loads(
        (output / "methodology_correction.json").read_text(encoding="utf-8")
    )

    assert roundtrip["all_frames_exact"] is True
    assert roundtrip["maximum_absolute_error"] == 0.0
    assert deterministic["all_equal"] is True
    assert lock_validation["selection_used_fit_and_validation_only"] is True
    assert lock_validation["holdout_opened_before_lock"] is False
    assert metrics["representation_hard_gate"] == "passed"
    assert metrics["holdout_gate"] == "passed"
    assert metrics["external_threshold_method"] == "matched_same_seed_pre_input_null"
    assert metrics["A_requires_information_sufficiency"] is True
    assert correction["information_sufficiency_policy"].startswith("partial")
    assert metrics["adoption_judgement"] in {
        "A_formal_adoption",
        "B_limited_adoption",
        "C_rejected",
    }
    assert not (output / "work").exists()


def test_manifest_tamper_is_detected(tmp_path: Path) -> None:
    output = run_validation(
        ROOT / "configs" / "fixed5axis_gk_validation_rc1.json",
        "smoke",
        tmp_path / "artifact",
    )
    path = output / "final" / "results.md"
    path.write_text(path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="manifest mismatch"):
        validate_output(output)
