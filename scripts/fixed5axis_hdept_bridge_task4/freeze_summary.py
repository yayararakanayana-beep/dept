"""Task 4 full bundleから、Git管理向けの小型凍結要約を決定論的に生成する。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

SOURCE_FILES = {
    "fixed5axis_hdept_task4_calibration_rc1.json",
    "task4_calibration_audit.json",
    "task4_validation_report.json",
    "task4_final_confirmation_report.json",
    "task4_freeze_decision.json",
    "task4_manifest.json",
}
OUTPUT_FILES = {
    "fixed5axis_hdept_task4_calibration_rc1.json",
    "task4_diagnostic_findings.json",
    "task4_freeze_decision.json",
    "task4_freeze_manifest.json",
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _feature_degeneracy(report: Mapping[str, Any]) -> list[str]:
    cases = report["case_summaries"]
    feature_ids = list(cases[0]["features"])
    constant: list[str] = []
    for feature_id in feature_ids:
        values = [
            float(case["features"][feature_id])
            for case in cases
            if case["features"][feature_id] is not None
        ]
        if values and float(np.std(np.asarray(values, dtype=np.float64))) <= 1e-12:
            constant.append(feature_id)
    return constant


def _clip_saturation(
    calibration: Mapping[str, Any],
    reports: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    cases = [case for report in reports for case in report["case_summaries"]]
    output: dict[str, float] = {}
    for index, feature_id in enumerate(calibration["feature_order"]):
        center = calibration["center"][index]
        scale = calibration["scale"][index]
        if center is None or scale is None:
            continue
        lower = float(calibration["clip_lower"][index])
        upper = float(calibration["clip_upper"][index])
        values = [
            float(case["features"][feature_id])
            for case in cases
            if case["features"][feature_id] is not None
        ]
        if not values:
            continue
        saturated = 0
        for value in values:
            calibrated = (value - float(center)) / float(scale)
            clipped = min(max(calibrated, lower), upper)
            if abs(clipped - lower) <= 1e-12 or abs(clipped - upper) <= 1e-12:
                saturated += 1
        rate = saturated / len(values)
        if rate >= 0.25:
            output[feature_id] = rate
    return dict(sorted(output.items(), key=lambda item: (-item[1], item[0])))


def _hypothesis_metrics(report: Mapping[str, Any], hypothesis_id: str) -> Mapping[str, Any]:
    return next(item["metrics"] for item in report["hypotheses"] if item["id"] == hypothesis_id)


def _report_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "split": report["split"],
        "case_count": report["case_count"],
        "all_task3_validations_passed": report["all_task3_validations_passed"],
        "hypothesis_pass_count": report["hypothesis_pass_count"],
        "hypothesis_count": report["hypothesis_count"],
        "all_critical_hypotheses_passed": report["all_critical_hypotheses_passed"],
        "failed_hypotheses": [
            item for item in report["hypotheses"] if not item["passed"]
        ],
        "passed_hypothesis_ids": [
            item["id"] for item in report["hypotheses"] if item["passed"]
        ],
    }


def build_compact_freeze(source_bundle: str | Path, output_dir: str | Path) -> Path:
    source = Path(source_bundle)
    output = Path(output_dir)
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    files = {path.name for path in source.iterdir() if path.is_file()}
    if files != SOURCE_FILES:
        raise ValueError(f"source bundle file set mismatch: {sorted(files)}")

    calibration = _load(source / "fixed5axis_hdept_task4_calibration_rc1.json")
    audit = _load(source / "task4_calibration_audit.json")
    validation = _load(source / "task4_validation_report.json")
    confirmation = _load(source / "task4_final_confirmation_report.json")
    decision = _load(source / "task4_freeze_decision.json")

    output.mkdir(parents=True, exist_ok=False)
    _write(output / "fixed5axis_hdept_task4_calibration_rc1.json", calibration)
    _write(output / "task4_freeze_decision.json", decision)

    validation_failed = [item["id"] for item in validation["hypotheses"] if not item["passed"]]
    confirmation_failed = [item["id"] for item in confirmation["hypotheses"] if not item["passed"]]
    diagnostic = {
        "diagnostic_id": "fixed5axis_hdept_task4_diagnostic_findings_rc1",
        "status": "scientifically_not_approved",
        "scientific_gate_passed": False,
        "failed_hypothesis_ids": validation_failed,
        "replicated_in_final_confirmation": confirmation_failed,
        "validation_summary": _report_summary(validation),
        "final_confirmation_summary": _report_summary(confirmation),
        "calibration_audit_summary": {
            "status": audit["status"],
            "fit_trajectory_count": audit["fit_trajectory_count"],
            "minimum_available_samples_per_scored_feature": audit["minimum_available_samples_per_scored_feature"],
            "insufficient_scored_features": audit["insufficient_scored_features"],
            "fit_only_boundary_passed": audit["fit_only_boundary_passed"],
            "validation_or_confirmation_used_for_fit": audit["validation_or_confirmation_used_for_fit"],
        },
        "failure_classification": {
            "H2_structured_exploration": "H11 Exploration and StructuralDiversity did not separate structured exploration from locked fixation under the preregistered margin.",
            "H5_boundary_divergence": "Boundary divergence produced higher, not lower, Coherence than stable broad despite high boundary mass and lower Stability.",
        },
        "calibration_diagnostics": {
            "fit_trajectory_count": audit["fit_trajectory_count"],
            "fit_only_boundary_passed": audit["fit_only_boundary_passed"],
            "reproducible": decision["calibration_reproducible"],
            "scale_floor_fallback_features": [
                feature_id
                for feature_id, source_name in audit["scale_source"].items()
                if source_name == "scale_floor_fallback"
            ],
            "constant_features_on_validation_split": _feature_degeneracy(validation),
            "features_with_clip_saturation_rate_at_least_0_25_across_validation_and_confirmation": _clip_saturation(
                calibration, (validation, confirmation)
            ),
            "interpretation": "The calibration is mechanically reproducible but is not approved as a production scientific calibration because several structural features are degenerate and multiple calibrated features frequently clip at the registered bounds.",
        },
        "failure_evidence": {
            "H2_validation_metrics": _hypothesis_metrics(validation, "H2_structured_exploration"),
            "H2_final_confirmation_metrics": _hypothesis_metrics(confirmation, "H2_structured_exploration"),
            "H5_validation_metrics": _hypothesis_metrics(validation, "H5_boundary_divergence"),
            "H5_final_confirmation_metrics": _hypothesis_metrics(confirmation, "H5_boundary_divergence"),
        },
        "repair_candidates_not_applied": [
            "Revisit fixed-grid support connectivity and major-component thresholds because mode_count and cluster_balance were constant across all validation cases.",
            "Audit Exploration component weighting and calibration saturation; structured exploration had higher raw entropy/effective dimension than fixation but the calibrated composite did not preserve that ordering.",
            "Audit Coherence construction so compact boundary concentration cannot dominate tail-mass and instability evidence.",
            "Do not change Task 1-3 contracts or preregistered Task 4 thresholds inside this PR merely to make the gate pass.",
        ],
        "next_step_boundary": "A repair task must explicitly revise the scientific mapping or scenario coverage, then rerun a newly preregistered validation. Task 5 diagnostic connection is blocked by this Task 4 result.",
    }
    _write(output / "task4_diagnostic_findings.json", diagnostic)

    manifest = {
        "bundle_id": "fixed5axis_hdept_task4_compact_freeze_rc1",
        "hash_algorithm": "sha256",
        "files": [
            {
                "path": path.name,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in sorted(output.iterdir())
            if path.name != "task4_freeze_manifest.json"
        ],
    }
    _write(output / "task4_freeze_manifest.json", manifest)
    if {path.name for path in output.iterdir() if path.is_file()} != OUTPUT_FILES:
        raise AssertionError("compact freeze output file set mismatch")
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-bundle", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    print(build_compact_freeze(args.source_bundle, args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
