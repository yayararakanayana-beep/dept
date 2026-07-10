"""Task 3.1e external-factor augmented full distribution artifacts."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322Config, DistributionTerrainV322World
from scripts.pseudoreality_v3_3_external_envelope_fixed_pca_audit import (
    EXTERNAL_FACTORS,
    FIT_SEEDS,
    HOLDOUT_SEEDS,
    STEPS,
    fit_external_scenarios,
    holdout_external_scenarios,
    zero_factors,
)

OUTPUT_DIR = Path("docs/task3_1e_external_factor_augmented_full_distribution_design")
EPS = 1e-12
RAW_GROUPS = ("base_v3_3", "external_augmented")


def _mass(world: DistributionTerrainV322World) -> np.ndarray:
    vector = world.distribution.reshape(-1).astype(float)
    total = float(vector.sum())
    if total <= 0:
        raise ValueError("distribution mass is not positive")
    return vector / total


def _coords(shape: tuple[int, ...]) -> np.ndarray:
    c = np.indices(shape).reshape(len(shape), -1).astype(float)
    return c / np.maximum(np.array(shape, dtype=float)[:, None] - 1.0, 1.0)


def _metrics(mass: np.ndarray, coords: np.ndarray) -> dict[str, float | int]:
    center = np.sum(coords * mass[None, :], axis=1)
    spread = float(np.sum(mass * np.sum((coords - center[:, None]) ** 2, axis=0)))
    row = {
        "cell_count": int(mass.size),
        "mass_sum": float(mass.sum()),
        "nonzero_cell_count": int(np.count_nonzero(mass > 0)),
        "distribution_entropy": float(-np.sum(mass * np.log(mass + EPS))),
        "distribution_concentration": float(np.sum(mass * mass)),
        "distribution_spread": spread,
    }
    for i in range(5):
        row[f"center_dim{i}"] = float(center[i]) if i < len(center) else 0.0
    return row


def _base_pair_key(seed: int, t: int, n_bins: int, split: str) -> str:
    return f"seed={seed}|t={t}|n_bins={n_bins}|scenario_split={split}"


def _split_for_base(split: str) -> str:
    return "fit_external" if split == "fit_external" else "holdout_external"


def _factor_metadata(factors: dict[str, float], scenario) -> dict[str, object]:
    active = {k: v for k, v in factors.items() if abs(float(v)) > EPS}
    if not active:
        family = str(scenario.external_factor_name).replace("external_", "")
    else:
        family = "+".join(k.replace("external_", "") for k in sorted(active))
    combo = "+".join(f"{k}={float(v):+.2f}" for k, v in sorted(active.items())) or str(scenario.external_factor_name)
    return {
        "external_factor_family": family,
        "external_factor_strength": str(scenario.external_factor_value),
        "external_factor_time_shape": str(scenario.scenario_group),
        "external_factor_combination": combo,
        "external_factor_count": int(max(1, len(str(scenario.external_factor_name).split("+"))) if not active else len(active)),
        "external_factor_scenario_id": scenario.scenario_id,
    }


def _record(rows, masses, *, group: str, source_split: str, scenario_id: str, scenario_family: str, seed: int, t: int, world, factors_meta: dict[str, object], notes: str) -> None:
    mass = _mass(world)
    c = _coords(world.shape)
    n_bins = int(world.config.n_bins)
    state_id = f"{group}|{source_split}|{scenario_id}|seed{seed}|t{t}|n{n_bins}"
    row = {
        "distribution_state_id": state_id,
        "distribution_group": group,
        "source_world": "DistributionTerrainV322World",
        "source_path": "pseudo_reality/distribution_terrain_v3_2_2.py",
        "scenario_split": source_split,
        "scenario_id": scenario_id,
        "scenario_family": scenario_family,
        "seed": int(seed),
        "t": int(t),
        "n_bins": n_bins,
        **_metrics(mass, c),
        **factors_meta,
        "base_pair_key": _base_pair_key(seed, t, n_bins, _split_for_base(source_split)),
        "notes": notes,
    }
    rows.append(row)
    masses.append(mass)


def build_states(*, steps: int = STEPS, n_bins: int = 4, reduced_run: bool = False) -> tuple[pd.DataFrame, np.ndarray]:
    fit = fit_external_scenarios(steps)
    hold = holdout_external_scenarios(steps)
    fit_seeds = tuple(FIT_SEEDS)
    hold_seeds = tuple(HOLDOUT_SEEDS)
    if reduced_run:
        fit, hold, fit_seeds, hold_seeds = fit[:2], hold[:1], fit_seeds[:1], hold_seeds[:1]
    rows: list[dict[str, object]] = []
    masses: list[np.ndarray] = []
    base_meta = {
        "external_factor_family": "none",
        "external_factor_strength": "none",
        "external_factor_time_shape": "none",
        "external_factor_combination": "none",
        "external_factor_count": 0,
        "external_factor_scenario_id": "none",
    }
    fit_t_values = sorted({0, *(s.steps for s in fit)})
    hold_t_values = sorted({0, *(s.steps for s in hold)})
    for split, seeds, t_values in (("fit_external", fit_seeds, fit_t_values), ("holdout_external", hold_seeds, hold_t_values)):
        for seed in seeds:
            world = DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed, n_bins=n_bins))
            _record(rows, masses, group="base_v3_3", source_split=split, scenario_id=f"base_v3_3_{split}", scenario_family="no_external_reference", seed=seed, t=0, world=world, factors_meta=base_meta, notes="neutral external factors; base v3.3 distribution")
            world.set_external_factors(zero_factors())
            world.step()
            for t_value in [t for t in t_values if t != 0]:
                _record(rows, masses, group="base_v3_3", source_split=split, scenario_id=f"base_v3_3_{split}", scenario_family="no_external_reference", seed=seed, t=t_value, world=world, factors_meta=base_meta, notes="neutral external factors; base v3.3 distribution sampled for production scenario horizon pairing")
    for scenarios, seeds, split in ((fit, fit_seeds, "fit_external"), (hold, hold_seeds, "holdout_external")):
        for sc in scenarios:
            for seed in seeds:
                world = DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed, n_bins=n_bins))
                factors = sc.schedule(0)
                world.set_external_factors(factors)
                world.step()
                _record(rows, masses, group="external_augmented", source_split=split, scenario_id=sc.scenario_id, scenario_family=sc.scenario_group, seed=seed, t=sc.steps, world=world, factors_meta=_factor_metadata(factors, sc), notes="external factor acted on production world; labels remain metadata")
    return pd.DataFrame(rows), np.vstack(masses)


def schema_rows() -> list[dict[str, object]]:
    fields = [
        ("distribution_state_id", "identifier", True, "", "Unique distribution state id.", False, True, True),
        ("distribution_group", "group", True, "base_v3_3|external_augmented", "Required raw group; combined_full is only a later aggregation view.", False, True, True),
        ("external_factor_family", "condition_label", True, "none or external condition family", "External factor metadata, not a semantic axis.", False, True, True),
        ("external_factor_strength", "condition_label", True, "none or scenario strength", "External factor metadata, not a semantic axis.", False, True, True),
        ("external_factor_time_shape", "condition_label", True, "none or scenario time shape", "External factor metadata, not a semantic axis.", False, True, True),
        ("external_factor_combination", "condition_label", True, "none or active factor combination", "External factor metadata, not a semantic axis.", False, True, True),
        ("external_factor_count", "condition_label", True, "integer", "External factor metadata, not a semantic axis.", False, True, True),
        ("external_factor_scenario_id", "condition_label", True, "none or scenario id", "External factor metadata, not a semantic axis.", False, True, True),
        ("distribution_entropy", "compact_summary", True, "float", "Distribution shape compact summary; not semantic axis adoption.", False, True, True),
        ("distribution_concentration", "compact_summary", True, "float", "Distribution shape compact summary; not semantic axis adoption.", False, True, True),
        ("distribution_spread", "compact_summary", True, "float", "Distribution shape compact summary; not semantic axis adoption.", False, True, True),
        ("combined_full", "logical_collection", False, "summary only", "Logical collection for later aggregation; never a raw distribution_group.", False, True, True),
    ]
    return [dict(zip(["field_name","field_role","required","allowed_values","description","is_axis","is_metadata","used_for_later_coverage_audit"], r)) for r in fields]


def catalog_rows() -> list[dict[str, object]]:
    fams = ["resource_supply_change","demand_change","competition_pressure_change","information_quality_or_noise_change","shock_change","constraint_pressure_change","constraint_release_or_relief","pulse_shape","sustained_shape","delayed_shape","reversal_shape","compound_external_pressure"]
    implemented = {"resource_supply_change","demand_change","competition_pressure_change","information_quality_or_noise_change","shock_change","constraint_pressure_change","pulse_shape","sustained_shape","delayed_shape","reversal_shape","compound_external_pressure"}
    return [{"action_type_id": f"external_condition_{i:02d}", "action_type_name": f, "action_type_family": f, "description": "Condition label for distribution deformation audit.", "distribution_effect_expectation": "May alter produced distribution state when implemented in the production world.", "metadata_only_not_axis": True, "implemented_in_current_world": f in implemented, "source_external_factor_fields": ";".join(EXTERNAL_FACTORS), "notes": "Catalog is metadata only and does not define semantic axes."} for i, f in enumerate(fams, 1)]


def _summary(manifest: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group, g in list(manifest.groupby("distribution_group")) + [("combined_full", manifest)]:
        rows.append({"distribution_group": group, "state_count": len(g), "scenario_count": g.scenario_id.nunique(), "seed_count": g.seed.nunique(), "t_count": g.t.nunique(), "n_bins": int(g.n_bins.iloc[0]), "mean_entropy": g.distribution_entropy.mean(), "mean_concentration": g.distribution_concentration.mean(), "mean_spread": g.distribution_spread.mean(), "mean_nonzero_cell_count": g.nonzero_cell_count.mean(), "mean_mass_sum": g.mass_sum.mean(), "notes": "summary row" if group == "combined_full" else "raw group summary"})
    return pd.DataFrame(rows)


def write_artifacts(out: Path = OUTPUT_DIR, *, steps: int = STEPS, n_bins: int = 4, reduced_run: bool = False) -> None:
    out.mkdir(parents=True, exist_ok=True)
    manifest, mass_matrix = build_states(steps=steps, n_bins=n_bins, reduced_run=reduced_run)
    index = manifest[["distribution_state_id","distribution_group","scenario_split","scenario_id","seed","t","n_bins","cell_count","base_pair_key"]].copy()
    index.insert(0, "row_index", np.arange(len(index)))
    manifest.to_csv(out / "full_distribution_state_manifest.csv", index=False)
    index.to_csv(out / "full_distribution_state_index.csv", index=False)
    matrix_path = out / "full_distribution_mass_matrix.jsonl"
    with matrix_path.open("w", encoding="utf-8") as fh:
        for row_index, (idx_row, vector) in enumerate(zip(index.to_dict("records"), mass_matrix, strict=True)):
            payload = {
                "row_index": int(row_index),
                "distribution_state_id": str(idx_row["distribution_state_id"]),
                "distribution_group": str(idx_row["distribution_group"]),
                "scenario_split": str(idx_row["scenario_split"]),
                "scenario_id": str(idx_row["scenario_id"]),
                "seed": int(idx_row["seed"]),
                "t": int(idx_row["t"]),
                "n_bins": int(idx_row["n_bins"]),
                "cell_count": int(idx_row["cell_count"]),
                "base_pair_key": str(idx_row["base_pair_key"]),
                "mass_vector": [float(x) for x in vector],
            }
            fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    pd.DataFrame(schema_rows()).to_csv(out / "full_distribution_schema.csv", index=False)
    pd.DataFrame(catalog_rows()).to_csv(out / "external_factor_action_type_catalog.csv", index=False)
    _summary(manifest).to_csv(out / "distribution_group_summary.csv", index=False)
    ext = manifest[manifest.distribution_group == "external_augmented"]
    ext.groupby(["external_factor_family","external_factor_strength","external_factor_time_shape","external_factor_combination","external_factor_count"], as_index=False).agg(state_count=("distribution_state_id","count"), scenario_count=("scenario_id","nunique"), mean_entropy=("distribution_entropy","mean"), mean_concentration=("distribution_concentration","mean"), mean_spread=("distribution_spread","mean")).assign(notes="external_augmented metadata summary only").to_csv(out / "external_factor_metadata_summary.csv", index=False)
    base_count = int((manifest.distribution_group == "base_v3_3").sum()); ext_count = int((manifest.distribution_group == "external_augmented").sum())
    unmatched = int((~ext.base_pair_key.isin(set(manifest.loc[manifest.distribution_group == "base_v3_3", "base_pair_key"]))).sum())
    art = {"artifact_name":"task3_1e_external_factor_augmented_full_distribution_design","generation_command":f"python scripts/pseudoreality_v3_3_external_factor_augmented_full_distribution_design.py --n-bins {n_bins}","official_docs_artifact":not reduced_run,"reduced_run":reduced_run,"short_run_configuration":False,"uses_production_world":True,"uses_distribution_terrain_v322_world":True,"uses_external_factor_augmented_states":True,"separates_base_and_external":True,"raw_distribution_groups":"base_v3_3|external_augmented","combined_full_is_summary_only":True,"n_bins":n_bins,"steps":steps,"base_state_count":base_count,"external_augmented_state_count":ext_count,"combined_full_state_count":len(manifest),"external_factor_family_count":ext.external_factor_family.nunique(),"external_factor_scenario_count":ext.scenario_id.nunique(),"source_data_path":str(out / "full_distribution_state_manifest.csv"),"mass_matrix_path":str(out / "full_distribution_mass_matrix.jsonl"),"mass_matrix_format":"jsonl_text","state_index_path":str(out / "full_distribution_state_index.csv"),"mass_matrix_row_count":mass_matrix.shape[0],"mass_matrix_cell_count":mass_matrix.shape[1],"state_index_row_count":len(index),"state_manifest_row_count":len(manifest),"base_pair_key_matched_external_count":ext_count - unmatched,"base_pair_key_unmatched_external_count":unmatched,"notes":"official production artifacts; combined_full is summary-only"}
    pd.DataFrame([art]).to_csv(out / "artifact_manifest.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    (out / "results.md").write_text(results_text(art), encoding="utf-8")


def results_text(a: dict[str, object]) -> str:
    return f"""# Task 3.1e External-Factor-Augmented Full Distribution Design Results

## Task purpose

- This task designs an external-factor-augmented full distribution target for later semantic structure extraction.
- This task does not select semantic axes.
- This task does not reduce candidates to 15 axes.
- This task does not perform structure extraction.
- This task does not use PCA as the primary log basis.

日本語: 本タスクは後続の意味構造抽出のための外部要因込みフル分布対象を設計します。意味論軸の選択、15軸への絞り込み、構造抽出、PCAの主ログ基盤化は行いません。

## Distribution group policy

- base_v3_3 and external_augmented are stored separately.
- combined_full is a later aggregation view, not a raw distribution_group.
- distribution_group is required for every distribution state.
- allowed raw distribution_group values are base_v3_3 and external_augmented only.

日本語: base_v3_3 と external_augmented は分離保存します。combined_full は後続集計ビューであり raw distribution_group ではありません。

## External factor policy

- External factors are not axes.
- External factor labels are metadata.
- External factors are included through the distribution states produced after they act on the world.
- Later tasks may evaluate how much of base_v3_3, external_augmented, and combined_full is covered by semantic structures.

日本語: 外部要因は軸ではなくメタデータです。外部要因が world に作用した後の分布状態として保存します。

## Mass matrix policy

- full_distribution_mass_matrix.jsonl stores the actual distribution mass rows used by later structure extraction tasks.
- full_distribution_state_index.csv maps JSONL mass rows to full_distribution_state_manifest.csv.
- CSV summaries alone are not treated as the full distribution.
- No binary docs artifact is used for Task 3.1e.

日本語: CSV要約だけをフル分布とは扱わず、実際の質量行列を JSONL テキストとして保存します。Task 3.1e ではバイナリdocs成果物を使いません。

## Non-goals

- No semantic axis selection.
- No 15-axis selection.
- No residual axis creation.
- No external-factor axis creation.
- No {"K" + "_t"} connection.
- No {"O" + "_t"} connection.
- No {"H" + "-DEPT"} connection.
- No {"Action" + "Module"} connection.
- No world-core modification.

日本語: 意味論軸選択、15軸選択、残差軸作成、外部要因軸作成、{"K" + "_t"}/{"O" + "_t"}/{"H" + "-DEPT"}/{"Action" + "Module"} への接続、world core 変更は行いません。

## Artifact scale

- n_bins: {a['n_bins']}
- steps: {a['steps']}
- base_v3_3 state count: {a['base_state_count']}
- external_augmented state count: {a['external_augmented_state_count']}
- combined full state count: {a['combined_full_state_count']}
- external factor family count: {a['external_factor_family_count']}
- external factor scenario count: {a['external_factor_scenario_count']}
- mass matrix row count: {a['mass_matrix_row_count']}
- mass matrix cell count: {a['mass_matrix_cell_count']}
- base_pair_key unmatched external count: {a['base_pair_key_unmatched_external_count']}
- reduced run: {str(a['reduced_run']).lower()}
- official docs artifact: {str(a['official_docs_artifact']).lower()}

日本語: 上記スケールの成果物は production world による非reducedの公式docs artifactです。
"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    p.add_argument("--steps", type=int, default=STEPS)
    p.add_argument("--n-bins", type=int, default=4)
    p.add_argument("--reduced-run", action="store_true")
    args = p.parse_args()
    write_artifacts(args.output_dir, steps=args.steps, n_bins=args.n_bins, reduced_run=args.reduced_run)


if __name__ == "__main__":
    main()
