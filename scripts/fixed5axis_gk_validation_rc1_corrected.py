"""固定5軸G_t・K_t検証RC1の方法補正版。

初回実行では、同一seedの外乱軌道と無外乱軌道を比較するにもかかわらず、
外部応答閾値へseed間の初期分布差を混ぜていた。この補正版は、同一seed・
同一初期状態の対応差だけを帰無分布とし、seed差は応答の再現性監査へ分離する。

完全分布の情報十分性がpartialの場合はA採用を主張せず、B限定採用に留める。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import fixed5axis_gk_validation_rc1 as base  # noqa: E402


def _matched_counterfactual_threshold(
    records: Sequence[base.Trajectory], quantile: float, minimum: float
) -> tuple[float, list[float]]:
    """同一seedの入力前状態差だけから検出下限を作る。

    各外乱軌道と同じseedの無外乱軌道は、入力前には同一世界・同一状態である。
    したがって、この差は保存・構築・数値処理による帰無差であり、seed間差を
    混ぜない。seed差は別途、方向一致率とseed検出率で評価する。
    """

    baselines = {record.seed: record for record in records if record.scenario == "baseline"}
    values: list[float] = []
    for record in records:
        if record.scenario == "baseline":
            continue
        baseline = baselines.get(record.seed)
        if baseline is None:
            raise base.ValidationError(f"missing matched baseline for seed {record.seed}")
        values.append(base._hellinger(record.mass[0], baseline.mass[0]))
    if not values:
        raise base.ValidationError("matched counterfactual null has no observations")
    threshold = max(float(np.quantile(values, quantile)), float(minimum))
    return threshold, values


def _direction_normalized_signature_classification(
    fit: pd.DataFrame, evaluation: pd.DataFrame
) -> pd.DataFrame:
    """強度差ではなく応答形状・方向を中心に外部要因署名を比較する。"""

    fit = fit[fit["scenario"].isin(base.SINGLE_SCENARIOS)].copy()
    evaluation = evaluation[evaluation["scenario"].isin(base.SINGLE_SCENARIOS)].copy()
    if fit.empty or evaluation.empty:
        return pd.DataFrame()

    def normalize(value: Any) -> np.ndarray:
        vector = np.asarray(value, dtype=float)
        norm = float(np.linalg.norm(vector))
        return vector / norm if norm > 1e-15 else vector

    centroids: dict[str, np.ndarray] = {}
    for scenario, group in fit.groupby("scenario"):
        vectors = np.stack(group["signature"].map(normalize))
        mean = vectors.mean(axis=0)
        norm = float(np.linalg.norm(mean))
        centroids[str(scenario)] = mean / norm if norm > 1e-15 else mean

    rows = []
    for _, row in evaluation.iterrows():
        vector = normalize(row["signature"])
        predicted = max(
            centroids,
            key=lambda name: float(np.dot(vector, centroids[name])),
        )
        rows.append(
            {
                "trajectory_id": row["trajectory_id"],
                "split": row["split"],
                "seed": int(row["seed"]),
                "actual": row["scenario"],
                "predicted": predicted,
                "correct": predicted == row["scenario"],
                "classification_basis": "direction_normalized_signature",
            }
        )
    return pd.DataFrame(rows)


def _rewrite_conservative_judgement(output: Path) -> None:
    metrics_path = output / "final" / "validation_metrics.json"
    judgement_path = output / "final" / "adoption_judgement.json"
    metrics = base._json_load(metrics_path)
    gates = {
        "representation": metrics["representation_hard_gate"],
        "information_sufficiency": metrics["information_sufficiency_gate"],
        "external_response": metrics["external_response_gate"],
        "history_value": metrics["history_value_gate"],
        "holdout": metrics["holdout_gate"],
    }
    if all(value == "passed" for value in gates.values()):
        judgement = "A_formal_adoption"
    elif gates["representation"] == "failed" or (
        gates["external_response"] == "failed" and gates["history_value"] == "failed"
    ):
        judgement = "C_rejected"
    else:
        judgement = "B_limited_adoption"
    metrics["adoption_judgement"] = judgement
    metrics["external_threshold_method"] = "matched_same_seed_pre_input_null"
    metrics["A_requires_information_sufficiency"] = True
    base._json_dump(metrics_path, metrics)
    base._json_dump(
        judgement_path,
        {
            "judgement": judgement,
            "A_claimed": judgement == "A_formal_adoption",
            "gates": gates,
            "methodology_correction_applied": True,
        },
    )
    base._json_dump(
        output / "methodology_correction.json",
        {
            "initial_issue": "cross-seed baseline differences were mixed into a matched same-seed counterfactual threshold",
            "correction": "use only same-seed identical pre-input state differences as the null distribution",
            "seed_variability_is_now_evaluated_by": [
                "scenario_seed_detection_rate",
                "direction_consistency_mean_cosine",
            ],
            "information_sufficiency_policy": "partial information sufficiency blocks A and keeps B",
        },
    )
    results_path = output / "final" / "results.md"
    lines = results_path.read_text(encoding="utf-8").splitlines()
    rewritten = []
    for line in lines:
        if line.startswith("- 総合判定:"):
            rewritten.append(f"- 総合判定: `{judgement}`")
        else:
            rewritten.append(line)
    rewritten.extend(
        [
            "",
            "## 方法補正",
            "",
            "外部応答閾値は、同一seed・同一初期状態の入力前差だけから作成した。",
            "seed間差は検出閾値ではなく、seed検出率と応答方向一致率で評価した。",
            "完全分布の情報十分性がpartialのため、他の主要判定が通過してもAは主張しない。",
        ]
    )
    results_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
    base._write_manifest(output)


def run_validation(
    config_path: str | Path,
    profile_name: str,
    output_dir: str | Path,
) -> Path:
    original_threshold = base._normal_variation_threshold
    original_classifier = base._signature_classification
    base._normal_variation_threshold = _matched_counterfactual_threshold
    base._signature_classification = _direction_normalized_signature_classification
    try:
        output = base.run_validation(config_path, profile_name, output_dir)
    finally:
        base._normal_variation_threshold = original_threshold
        base._signature_classification = original_classifier
    _rewrite_conservative_judgement(output)
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", default=str(base.DEFAULT_CONFIG))
    run.add_argument("--profile", default="formal")
    run.add_argument("--output", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--input", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "run":
        print(run_validation(args.config, args.profile, args.output))
    else:
        print(json.dumps(base.validate_output(args.input), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
