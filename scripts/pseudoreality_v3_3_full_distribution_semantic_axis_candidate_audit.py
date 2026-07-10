"""Task 3.1d full-distribution semantic axis candidate audit.

Audits broad, reproducible semantic axis candidates computed from the real
PseudoReality v3.3/v3.2.2 full distribution path. This is decision support only:
no Core dimensions are selected, no fixed 5-axis Core is built, and PCA is not
used as the primary log basis.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
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

OUTPUT_DIR = Path("docs/task3_1d_full_distribution_semantic_axis_candidate_audit")
TASK3_1C_DIR = Path("docs/task3_1c_external_envelope_residual_decomposition")
TASK3_1C_RESIDUAL = TASK3_1C_DIR / "compact_residual_decomposition_summary.csv"
TASK3_1C_TERRAIN = TASK3_1C_DIR / "compact_residual_terrain_summary.csv"
TASK3_1C_FLAGS = TASK3_1C_DIR / "compact_auto_audit_flag_reason_summary.csv"
EPS = 1e-12
TERRAIN_FIELDS = (
    "short_payoff", "medium_payoff", "effective_medium_payoff", "friction", "viscosity", "damage",
    "rigidity", "recovery_speed", "route_support", "operating_cost", "cost_reduction_gain",
    "viability_reserve", "negative_viability_pressure", "released_mass", "release_reallocation_flow",
)
AUX_FIELDS = (
    "information_memory", "exploration_option_value", "exploration_net_expected_value", "expected_value_advantage",
    "short_gain_information_conversion", "short_path_decline_information", "exploration_experience_information", "last_flow",
)


@dataclass(frozen=True)
class AxisDef:
    axis_id: str
    axis_name: str
    axis_family: str
    definition: str
    source_fields: str
    uses_distribution_mass: bool = True
    uses_terrain: bool = False
    uses_auxiliary_terrain: bool = False
    uses_history: bool = False
    uses_external_factor: bool = False
    is_interaction_axis: bool = False


def _norm(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, float)
    r = float(np.max(x) - np.min(x))
    return (x - float(np.min(x))) / (r + EPS)


def _corr(a, b) -> float:
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if len(a) < 2 or np.std(a) <= EPS or np.std(b) <= EPS:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _q(a, p) -> float:
    return float(np.quantile(np.asarray(a, float), p)) if len(a) else 0.0


def _state(world: DistributionTerrainV322World):
    fields = {k: getattr(world, k).reshape(-1).astype(float) for k in TERRAIN_FIELDS + AUX_FIELDS if hasattr(world, k)}
    mass = world.distribution.reshape(-1).astype(float)
    coords = np.indices(world.shape).reshape(len(world.shape), -1).astype(float)
    coords = np.vstack([_norm(c) for c in coords])
    return mass, fields, coords


def axis_catalog() -> list[AxisDef]:
    axes: list[AxisDef] = []
    for name, definition in [
        ("mass_concentration", "sum_i mass_i(t)^2"),
        ("distribution_entropy", "-sum_i mass_i(t)*log(mass_i(t))"),
        ("center_dim0", "sum_i mass_i(t)*x0_i"),
        ("center_dim1", "sum_i mass_i(t)*x1_i"),
        ("center_dim2", "sum_i mass_i(t)*x2_i"),
        ("center_dim3", "sum_i mass_i(t)*x3_i"),
        ("center_dim4", "sum_i mass_i(t)*x4_i"),
        ("spatial_spread", "sum_i mass_i(t)*||x_i-center(t)||^2"),
    ]:
        axes.append(AxisDef(f"distribution_shape_{len(axes) + 1:02d}", name, "distribution_shape", definition, "distribution,cell_coordinates"))
    for f in ("short_payoff", "medium_payoff", "effective_medium_payoff", "friction", "viscosity", "rigidity", "recovery_speed", "route_support", "operating_cost", "cost_reduction_gain", "viability_reserve"):
        axes.append(AxisDef(f"terrain_semantic_{f}", f"mass_weighted_{f}", "terrain_semantic", f"sum_i mass_i(t) * normalized({f}_i(t))", f"distribution,{f}", True, True))
    for a, b in [("short_payoff", "friction"), ("medium_payoff", "viscosity"), ("effective_medium_payoff", "operating_cost"), ("route_support", "cost_reduction_gain"), ("viability_reserve", "negative_viability_pressure"), ("released_mass", "release_reallocation_flow")]:
        axes.append(AxisDef(f"terrain_interaction_{a}_x_{b}", f"{a}_by_{b}", "terrain_interaction", f"sum_i mass_i(t) * normalized({a}_i(t)) * normalized({b}_i(t))", f"distribution,{a},{b}", True, True, False, False, False, True))
    for f in ("information_memory", "exploration_option_value", "exploration_net_expected_value", "expected_value_advantage", "last_flow"):
        axes.append(AxisDef(f"temporal_response_{f}", f"history_weighted_{f}", "temporal_response", f"sum_i mass_i(t) * normalized({f}_i(t)); velocity/curvature audited by scenario history", f"distribution,{f},scenario_history", True, False, True, True))
    for f in EXTERNAL_FACTORS:
        axes.append(AxisDef(f"external_response_{f}", f"mass_response_to_{f}", "external_response", f"sum_i mass_i(t)*normalized(friction_i(t)+viscosity_i(t)+damage_i(t))*{f}(t)", f"distribution,friction,viscosity,damage,{f}", True, True, False, False, True, True))
    for f in ("positive_residual_proxy", "negative_residual_proxy", "residual_energy_proxy"):
        axes.append(AxisDef(f"residual_response_{f}", f, "residual_response", f"internal proxy only: full distribution mass_i(t) minus generated t0 baseline; {f}", "distribution,scenario_history,no_external_baseline", True, False, False, True, False))
    return axes


def _axis_values(axes: list[AxisDef], mass, fields, coords, row, baseline):
    vals = {}
    center = np.array([np.sum(mass * c) for c in coords])
    stress = _norm(fields.get("friction", 0) + fields.get("viscosity", 0) + fields.get("damage", 0))
    resid = mass - baseline
    for ax in axes:
        n = ax.axis_name
        if n == "mass_concentration":
            v = np.sum(mass * mass)
        elif n == "distribution_entropy":
            v = -np.sum(mass * np.log(mass + EPS))
        elif n.startswith("center_dim"):
            v = center[int(n[-1])]
        elif n == "spatial_spread":
            v = np.sum(mass * np.sum((coords - center[:, None]) ** 2, axis=0))
        elif ax.axis_family == "terrain_semantic":
            v = np.sum(mass * _norm(fields[n.replace("mass_weighted_", "")]))
        elif ax.axis_family == "terrain_interaction":
            a, b = n.split("_by_")
            v = np.sum(mass * _norm(fields[a]) * _norm(fields[b]))
        elif ax.axis_family == "temporal_response":
            v = np.sum(mass * _norm(fields[n.replace("history_weighted_", "")]))
        elif ax.axis_family == "external_response":
            v = np.sum(mass * stress) * float(row.get(n.replace("mass_response_to_", ""), 0.0))
        elif n == "positive_residual_proxy":
            v = np.sum(np.maximum(resid, 0))
        elif n == "negative_residual_proxy":
            v = np.sum(np.maximum(-resid, 0))
        else:
            v = np.sum(resid * resid)
        vals[ax.axis_id] = float(v)
    return vals


def _select_for_mode(items: list, reduced_run: bool, limit: int) -> list:
    return list(items)[:limit] if reduced_run else list(items)


def build_corpus(*, steps: int = STEPS, n_bins: int | None = None, reduced_run: bool = False):
    rows = []
    states = []
    fit_scenarios = fit_external_scenarios(steps)
    holdout_scenarios = holdout_external_scenarios(steps)
    used_fit = _select_for_mode(fit_scenarios, reduced_run, 4)
    used_holdout = _select_for_mode(holdout_scenarios, reduced_run, 2)
    used_fit_seeds = tuple(_select_for_mode(list(FIT_SEEDS), reduced_run, 1))
    used_holdout_seeds = tuple(_select_for_mode(list(HOLDOUT_SEEDS), reduced_run, 1))
    config_kwargs = {"n_bins": n_bins} if n_bins is not None else {}
    for sc, seeds, dataset in [(s, used_fit_seeds, "fit_external") for s in used_fit] + [(s, used_holdout_seeds, "holdout_external") for s in used_holdout]:
        for seed in seeds:
            world = DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed, **config_kwargs))
            for t in range(sc.steps + 1):
                factors = zero_factors() if t == 0 else sc.schedule(t - 1)
                if t > 0:
                    world.set_external_factors(factors)
                    world.step()
                mass, fields, coords = _state(world)
                row = {
                    "dataset": dataset,
                    "scenario_id": sc.scenario_id,
                    "scenario_group": sc.scenario_group,
                    "external_factor_name": sc.external_factor_name,
                    "external_factor_value": sc.external_factor_value,
                    "seed": seed,
                    "t": t,
                    "n_bins": world.config.n_bins,
                    "source_path": "production_world_distribution_terrain_v3_2_2",
                }
                row.update({f: float(factors.get(f, 0.0)) for f in EXTERNAL_FACTORS})
                rows.append(row)
                states.append((mass, fields, coords))
    baseline = np.mean([s[0] for r, s in zip(rows, states) if r["t"] == 0], axis=0)
    axes = axis_catalog()
    val_rows = [row | _axis_values(axes, *state, row, baseline) for row, state in zip(rows, states)]
    meta = {
        "steps": steps,
        "n_bins": int(val_rows[0]["n_bins"]),
        "available_fit_scenario_count": len(fit_scenarios),
        "used_fit_scenario_count": len(used_fit),
        "available_holdout_scenario_count": len(holdout_scenarios),
        "used_holdout_scenario_count": len(used_holdout),
        "available_fit_seed_count": len(FIT_SEEDS),
        "used_fit_seed_count": len(used_fit_seeds),
        "available_holdout_seed_count": len(HOLDOUT_SEEDS),
        "used_holdout_seed_count": len(used_holdout_seeds),
        "reduced_run": bool(reduced_run),
    }
    return axes, pd.DataFrame(val_rows), meta


def load_task3_1c_outputs() -> dict[str, pd.DataFrame]:
    return {
        "residual": pd.read_csv(TASK3_1C_RESIDUAL),
        "terrain": pd.read_csv(TASK3_1C_TERRAIN),
        "flags": pd.read_csv(TASK3_1C_FLAGS),
    }


def velocity_frame(values, axes):
    df = values.copy()
    for ax in axes:
        df[f"{ax.axis_id}_velocity"] = 0.0
        df[f"{ax.axis_id}_curvature"] = 0.0
    for _, g in df.groupby(["dataset", "scenario_id", "seed"], sort=False):
        idx = g.index.to_numpy()
        for ax in axes:
            x = g[ax.axis_id].to_numpy()
            df.loc[idx, f"{ax.axis_id}_velocity"] = np.r_[0, np.diff(x)]
            df.loc[idx, f"{ax.axis_id}_curvature"] = np.r_[0, 0, np.diff(x, 2)] if len(x) > 2 else np.zeros(len(x))
    return df


def _task3_1c_dataset_metrics(task3: dict[str, pd.DataFrame]) -> pd.DataFrame:
    residual = task3["residual"].groupby("dataset", as_index=False).agg(
        task3_1c_residual_mean=("residual_energy_ratio_mean", "mean"),
        task3_1c_residual_max=("residual_energy_ratio_max", "max"),
    )
    flags = task3["flags"].groupby("dataset", as_index=False).agg(
        task3_1c_auto_flag_rate=("auto_audit_flag_rate", "mean"),
        task3_1c_residual_exceed=("residual_exceed_rate", "mean"),
        task3_1c_mahalanobis_exceed=("mahalanobis_exceed_rate", "mean"),
        task3_1c_score_range_violation=("score_range_violation_rate", "mean"),
    )
    terrain = task3["terrain"].copy()
    terrain["positive_count"] = terrain["top_positive_residual_cells_summary"].fillna("").astype(str).str.len().gt(0).astype(float)
    terrain["negative_count"] = terrain["top_negative_residual_cells_summary"].fillna("").astype(str).str.len().gt(0).astype(float)
    terrain = terrain.groupby("dataset", as_index=False).agg(
        task3_1c_positive_terrain=("positive_count", "mean"),
        task3_1c_negative_terrain=("negative_count", "mean"),
        task3_1c_terrain_concentration=("residual_concentration_score", "mean"),
    )
    return residual.merge(flags, on="dataset", how="outer").merge(terrain, on="dataset", how="outer")


def _relation_to_task3(axis_values: pd.Series, values: pd.DataFrame, task3_by_dataset: pd.DataFrame, metric: str) -> float:
    joined = values[["dataset"]].merge(task3_by_dataset[["dataset", metric]], on="dataset", how="left")
    return _corr(axis_values.to_numpy(), joined[metric].fillna(0.0).to_numpy())


def summarize(axes, values, task3_outputs: dict[str, pd.DataFrame]):
    vdf = velocity_frame(values, axes)
    ids = [a.axis_id for a in axes]
    catalog = pd.DataFrame([a.__dict__ for a in axes])
    val_summary = pd.DataFrame([{"axis_id": i, "value_mean": vdf[i].mean(), "value_std": vdf[i].std(), "value_min": vdf[i].min(), "value_max": vdf[i].max()} for i in ids])
    task3_by_dataset = _task3_1c_dataset_metrics(task3_outputs)

    red, cond = [], []
    for n, i in enumerate(ids):
        for j in ids[n + 1:]:
            gc = _corr(vdf[i], vdf[j])
            vc = _corr(vdf[f"{i}_velocity"], vdf[f"{j}_velocity"])
            cc = _corr(vdf[f"{i}_curvature"], vdf[f"{j}_curvature"])
            rs = abs(_corr(vdf[i], vdf["residual_response_residual_energy_proxy"]) - _corr(vdf[j], vdf["residual_response_residual_energy_proxy"]))
            score = (abs(gc) + abs(vc) + abs(cc)) / 3 * (1 - rs)
            red.append({"axis_i": i, "axis_j": j, "global_correlation": gc, "velocity_correlation": vc, "curvature_correlation": cc, "residual_relation_similarity": 1 - rs, "redundancy_score": score})
            scen = [_corr(g[i], g[j]) for _, g in vdf.groupby("scenario_id")]
            er = abs(_corr(vdf[i], vdf[list(EXTERNAL_FACTORS)].abs().sum(axis=1)) - _corr(vdf[j], vdf[list(EXTERNAL_FACTORS)].abs().sum(axis=1)))
            tr = abs(vdf[f"{i}_velocity"].mean() - vdf[f"{j}_velocity"].mean())
            hs = abs(_corr(vdf[vdf.dataset == "holdout_external"][i], vdf[vdf.dataset == "holdout_external"][j]) - gc)
            sep = min(1, er + abs(tr) + rs + hs)
            action = "keep_separate" if sep > .25 else ("merge_candidate" if abs(gc) > .95 else "needs_review")
            cond.append({"axis_i": i, "axis_j": j, "global_correlation": gc, "scenario_correlation_min": min(scen), "scenario_correlation_max": max(scen), "external_response_difference": er, "temporal_response_difference": tr, "residual_response_difference": rs, "holdout_separation_score": hs, "conditional_separation_score": sep, "recommended_pair_action": action})
    red_df, cond_df = pd.DataFrame(red), pd.DataFrame(cond)

    ext = []
    for i in ids:
        for key, g in vdf.groupby(["external_factor_name", "scenario_group"]):
            fit = vdf[(vdf.dataset == "fit_external") & (vdf.external_factor_name == key[0])][i].mean()
            hold = vdf[(vdf.dataset == "holdout_external") & (vdf.external_factor_name == key[0])][i].mean()
            x = g.sort_values("t")[i].to_numpy()
            ext.append({"axis_id": i, "external_factor_name": key[0], "scenario_group": key[1], "response_mean": float(np.mean(x)), "response_peak": float(np.max(np.abs(x))), "response_slope": float(x[-1] - x[0]), "response_persistence": float(np.mean(np.abs(x) > _q(np.abs(x), .75))), "fit_response_mean": float(fit) if pd.notna(fit) else 0, "holdout_response_mean": float(hold) if pd.notna(hold) else 0, "response_generalization_gap": float(abs((fit if pd.notna(fit) else 0) - (hold if pd.notna(hold) else 0)))})
    ext_df = pd.DataFrame(ext)

    temp = []
    for i in ids:
        for key, g in vdf.groupby(["scenario_id", "seed", "dataset"]):
            x = g.sort_values("t")[i].to_numpy()
            vel = np.r_[0, np.diff(x)]
            acc = np.r_[0, 0, np.diff(x, 2)] if len(x) > 2 else np.zeros(len(x))
            temp.append({"axis_id": i, "scenario_id": key[0], "seed": key[1], "dataset": key[2], "response_start": x[0], "response_peak": float(np.max(np.abs(x))), "response_end": x[-1], "velocity_mean": float(np.mean(np.abs(vel))), "velocity_peak": float(np.max(np.abs(vel))), "acceleration_peak": float(np.max(np.abs(acc))), "curvature_mean": float(np.mean(np.abs(acc))), "curvature_peak": float(np.max(np.abs(acc))), "reversal_score": float(np.mean(np.sign(vel[1:]) != np.sign(vel[:-1])) if len(vel) > 1 else 0), "recovery_score": float(abs(x[-1] - x[0]) / (np.max(np.abs(x - x[0])) + EPS)), "persistence_score": float(np.mean(np.abs(x) > _q(np.abs(x), .75))), "oscillation_score": float(np.mean(np.diff(np.sign(vel)) != 0) if len(vel) > 1 else 0)})
    temp_df = pd.DataFrame(temp)

    re = vdf["residual_response_residual_energy_proxy"]
    residual = []
    task3_metrics = [
        "task3_1c_residual_mean", "task3_1c_residual_max", "task3_1c_positive_terrain", "task3_1c_negative_terrain",
        "task3_1c_auto_flag_rate", "task3_1c_residual_exceed", "task3_1c_mahalanobis_exceed", "task3_1c_score_range_violation",
    ]
    matched_relation_rows = 0
    total_relation_rows = 0
    for i in ids:
        for ds, g in vdf.groupby("dataset"):
            relation_values = {m: _relation_to_task3(vdf[i], vdf, task3_by_dataset, m) for m in task3_metrics}
            join_status = "matched" if ds in set(task3_by_dataset["dataset"]) else "unmatched"
            matched_relation_rows += int(join_status == "matched")
            total_relation_rows += 1
            residual.append({
                "axis_id": i,
                "candidate_name": i,
                "dataset": ds,
                "correlation_with_positive_residual": _corr(g[i], g["residual_response_positive_residual_proxy"]),
                "correlation_with_negative_residual": _corr(g[i], g["residual_response_negative_residual_proxy"]),
                "correlation_with_residual_energy": _corr(g[i], g["residual_response_residual_energy_proxy"]),
                "correlation_with_positive_residual_proxy": _corr(g[i], g["residual_response_positive_residual_proxy"]),
                "correlation_with_negative_residual_proxy": _corr(g[i], g["residual_response_negative_residual_proxy"]),
                "correlation_with_residual_energy_proxy": _corr(g[i], g["residual_response_residual_energy_proxy"]),
                "residual_peak_alignment": float(np.argmax(vdf[i].to_numpy()) == np.argmax(re.to_numpy())),
                "residual_persistence_alignment": float(abs(_corr(vdf[i].abs() > _q(vdf[i].abs(), .75), re > _q(re, .75)))),
                "holdout_residual_relation": _corr(vdf[vdf.dataset == "holdout_external"][i], vdf[vdf.dataset == "holdout_external"]["residual_response_residual_energy_proxy"]),
                "residual_explanation_score": abs(_corr(vdf[i], re)),
                "task3_1c_residual_mean_relation": relation_values["task3_1c_residual_mean"],
                "task3_1c_residual_max_relation": relation_values["task3_1c_residual_max"],
                "task3_1c_positive_terrain_relation": relation_values["task3_1c_positive_terrain"],
                "task3_1c_negative_terrain_relation": relation_values["task3_1c_negative_terrain"],
                "task3_1c_auto_flag_rate_relation": relation_values["task3_1c_auto_flag_rate"],
                "task3_1c_residual_exceed_relation": relation_values["task3_1c_residual_exceed"],
                "task3_1c_mahalanobis_exceed_relation": relation_values["task3_1c_mahalanobis_exceed"],
                "task3_1c_score_range_violation_relation": relation_values["task3_1c_score_range_violation"],
                "task3_1c_join_status": join_status,
                "task3_1c_join_key": f"dataset={ds}",
            })
    residual_df = pd.DataFrame(residual)

    macro = []
    for i in ids:
        macro.append({"axis_id": i, "captures_velocity": abs(_corr(vdf[f"{i}_velocity"], re)), "captures_acceleration": abs(_corr(vdf[f"{i}_curvature"], re)), "captures_curvature": abs(_corr(vdf[f"{i}_curvature"], re)), "captures_reversal": float(vdf[f"{i}_velocity"].lt(0).mean()), "captures_recovery": float(vdf.groupby(["scenario_id", "seed"])[i].apply(lambda x: abs(x.iloc[-1] - x.iloc[0]) / (abs(x).max() + EPS)).mean()), "captures_persistence": float((vdf[i].abs() > _q(vdf[i].abs(), .75)).mean()), "captures_oscillation": float(vdf.groupby(["scenario_id", "seed"])[f"{i}_velocity"].apply(lambda x: np.mean(np.diff(np.sign(x)) != 0) if len(x) > 1 else 0).mean()), "captures_boundary_shift": abs(_corr(vdf[i], vdf["external_constraint_pressure"])), "captures_concentration": abs(_corr(vdf[i], vdf["distribution_shape_01"])), "captures_release": abs(_corr(vdf[i], vdf.get("terrain_semantic_released_mass", pd.Series(0, index=vdf.index)))), "captures_reallocation": abs(_corr(vdf[i], vdf.get("terrain_semantic_release_reallocation_flow", pd.Series(0, index=vdf.index)))), "macro_dynamics_preservation_score": float(min(1, val_summary.loc[val_summary.axis_id == i, "value_std"].iloc[0] + abs(_corr(vdf[i], re)) + abs(_corr(vdf[f"{i}_velocity"], re))))})
    macro_df = pd.DataFrame(macro)

    cls = []
    ext_peak = ext_df.sort_values("response_peak", ascending=False).groupby("axis_id").head(1).set_index("axis_id")
    red_peak = red_df.assign(abs_score=red_df.redundancy_score.abs()).sort_values("abs_score", ascending=False).groupby("axis_i").head(1).set_index("axis_i")
    cond_peak = cond_df.sort_values("conditional_separation_score", ascending=False).groupby("axis_i").head(1).set_index("axis_i")
    residual_by_axis = residual_df.groupby("axis_id", as_index=False).agg({
        "task3_1c_residual_mean_relation": lambda x: float(np.max(np.abs(x))),
        "task3_1c_residual_max_relation": lambda x: float(np.max(np.abs(x))),
        "task3_1c_auto_flag_rate_relation": lambda x: float(np.max(np.abs(x))),
        "residual_explanation_score": "max",
    }).set_index("axis_id")
    macro_idx = macro_df.set_index("axis_id")
    for i in ids:
        ex_factor = str(ext_peak.loc[i, "external_factor_name"]) if i in ext_peak.index else "none"
        ex_score = float(ext_peak.loc[i, "response_peak"]) if i in ext_peak.index else 0.0
        rel_sources = {
            "task3_1c_residual_mean": float(residual_by_axis.loc[i, "task3_1c_residual_mean_relation"]),
            "task3_1c_residual_max": float(residual_by_axis.loc[i, "task3_1c_residual_max_relation"]),
            "task3_1c_auto_flag_rate": float(residual_by_axis.loc[i, "task3_1c_auto_flag_rate_relation"]),
            "internal_proxy_residual_energy": float(residual_by_axis.loc[i, "residual_explanation_score"]),
        }
        rel_source = max(rel_sources, key=lambda k: abs(rel_sources[k]))
        rel_score = abs(rel_sources[rel_source])
        macro_sources = macro_idx.loc[i].drop("macro_dynamics_preservation_score").abs().to_dict()
        macro_signal = max(macro_sources, key=macro_sources.get)
        macro_score = float(macro_sources[macro_signal])
        partner = str(red_peak.loc[i, "axis_j"]) if i in red_peak.index else "none"
        red_score = float(red_peak.loc[i, "redundancy_score"]) if i in red_peak.index else 0.0
        sep = float(cond_peak.loc[i, "conditional_separation_score"]) if i in cond_peak.index else 0.0
        sep_text = f"max conditional separation {sep:.3f} vs {cond_peak.loc[i, 'axis_j']}" if i in cond_peak.index else "no pair separation evidence"
        preservation = float(macro_idx.loc[i, "macro_dynamics_preservation_score"])
        classification = "core_candidate" if preservation > .35 and rel_score > .20 else ("hold_candidate" if preservation > .15 or sep > .25 else "audit_only")
        detail = f"{i} classified {classification}: top external response {ex_factor}={ex_score:.4f}; strongest residual relation {rel_source}={rel_score:.4f}; strongest macro signal {macro_signal}={macro_score:.4f}; redundancy partner {partner} score={red_score:.4f}; {sep_text}."
        cls.append({"axis_id": i, "classification": classification, "reason": detail, "redundancy_status": "audited_not_dropped", "conditional_separation_status": "audited_keep_if_separable", "residual_relevance_status": "relevant" if rel_score > .2 else "low_or_contextual", "macro_dynamics_status": "preserves_some_dynamics" if preservation > .15 else "audit_context_only", "recommended_next_action": "review_with_full_distribution_before_any_core_selection", "top_external_response_factor": ex_factor, "top_external_response_score": ex_score, "strongest_residual_relation_source": rel_source, "strongest_residual_relation_score": rel_score, "strongest_macro_dynamics_signal": macro_signal, "strongest_macro_dynamics_score": macro_score, "highest_redundancy_partner": partner, "highest_redundancy_score": red_score, "conditional_separation_evidence": sep_text, "classification_reason_detail": detail})
    cls_df = pd.DataFrame(cls)

    relation_meta = {
        "task3_1c_matched_relation_rows": matched_relation_rows,
        "task3_1c_total_relation_rows": total_relation_rows,
        "task3_1c_unmatched_rate": 1 - matched_relation_rows / max(total_relation_rows, 1),
        "task3_1c_join_key": "dataset",
    }
    return {
        "candidate_axis_catalog.csv": catalog,
        "axis_value_summary.csv": val_summary,
        "axis_redundancy_summary.csv": red_df,
        "axis_conditional_separation_summary.csv": cond_df,
        "axis_external_response_summary.csv": ext_df,
        "axis_temporal_response_summary.csv": temp_df,
        "axis_residual_relation_summary.csv": residual_df,
        "axis_macro_dynamics_preservation_summary.csv": macro_df,
        "axis_classification_summary.csv": cls_df,
    }, relation_meta


def _manifest_rows(tables, corpus_meta, task3_outputs, relation_meta, *, official_docs_artifact: bool, reduced_run: bool) -> pd.DataFrame:
    short_run = bool(reduced_run or corpus_meta["steps"] == 3 or corpus_meta["n_bins"] == 3 or corpus_meta["used_fit_scenario_count"] != corpus_meta["available_fit_scenario_count"] or corpus_meta["used_holdout_scenario_count"] != corpus_meta["available_holdout_scenario_count"] or corpus_meta["used_fit_seed_count"] != corpus_meta["available_fit_seed_count"] or corpus_meta["used_holdout_seed_count"] != corpus_meta["available_holdout_seed_count"])
    rows = []
    for artifact_name in [*tables.keys(), "results.md", "artifact_manifest.csv"]:
        rows.append({
            "artifact_name": artifact_name,
            "generation_command": "python scripts/pseudoreality_v3_3_full_distribution_semantic_axis_candidate_audit.py",
            "official_docs_artifact": bool(official_docs_artifact),
            "reduced_run": bool(reduced_run),
            "short_run_configuration": short_run,
            "n_bins": corpus_meta["n_bins"],
            "steps": corpus_meta["steps"],
            "available_fit_scenario_count": corpus_meta["available_fit_scenario_count"],
            "used_fit_scenario_count": corpus_meta["used_fit_scenario_count"],
            "available_holdout_scenario_count": corpus_meta["available_holdout_scenario_count"],
            "used_holdout_scenario_count": corpus_meta["used_holdout_scenario_count"],
            "available_fit_seed_count": corpus_meta["available_fit_seed_count"],
            "used_fit_seed_count": corpus_meta["used_fit_seed_count"],
            "available_holdout_seed_count": corpus_meta["available_holdout_seed_count"],
            "used_holdout_seed_count": corpus_meta["used_holdout_seed_count"],
            "snapshot_count": int(sum(len(df) for name, df in tables.items() if name == "axis_value_summary.csv")) if False else int(corpus_meta["snapshot_count"]),
            "dataset_count": corpus_meta["dataset_count"],
            "used_full_distribution": True,
            "used_task3_1c_outputs": True,
            "task3_1c_residual_decomposition_path": str(TASK3_1C_RESIDUAL),
            "task3_1c_residual_terrain_path": str(TASK3_1C_TERRAIN),
            "task3_1c_auto_audit_flag_reason_path": str(TASK3_1C_FLAGS),
            "task3_1c_residual_rows_loaded": len(task3_outputs["residual"]),
            "task3_1c_terrain_rows_loaded": len(task3_outputs["terrain"]),
            "task3_1c_flag_reason_rows_loaded": len(task3_outputs["flags"]),
            "source_data_path": "DistributionTerrainV322World production path; full world.distribution snapshots; Task 3.1c compact residual artifacts",
            "notes": f"task3_1c_join_key={relation_meta['task3_1c_join_key']}; matched_relation_rows={relation_meta['task3_1c_matched_relation_rows']}; unmatched_rate={relation_meta['task3_1c_unmatched_rate']:.6f}",
        })
    return pd.DataFrame(rows)


def _write_results(root, corpus_meta, task3_outputs, relation_meta, official_docs_artifact, reduced_run):
    text = f'''# Task 3.1d Full-Distribution Semantic Axis Candidate Audit

This report does not select final Core dimensions.
This report does not compress the full distribution into a fixed 5-axis Core.
This report does not use PCA as the primary log basis.
This report only audits semantic axis candidates extracted from the full distribution.
Axis classifications are decision-support labels, not final adoption decisions.
The goal is to preserve information needed for later macro-dynamics extraction.

このレポートは最終Core次元を確定しない。
このレポートはフル分布を固定5軸Coreへ圧縮しない。
このレポートはPCAを主ログ基盤として採用しない。
このレポートはフル分布から抽出した意味論軸候補を監査するだけである。
軸分類は判断材料であり、最終採用判断ではない。
目的は、後段のマクロ力学抽出に必要な情報を保存することである。

## Artifact provenance

- Generation command: `python scripts/pseudoreality_v3_3_full_distribution_semantic_axis_candidate_audit.py`
- Source data path: production PseudoReality path using `DistributionTerrainV322World`, `DistributionTerrainV322Config`, `world.set_external_factors(...)`, `world.step()`, and full `world.distribution` mass snapshots; Task 3.1c compact residual artifacts are read but not overwritten.
- Full distribution source: yes
- PCA used as primary log basis: no
- Fixed 5-axis Core selected: no
- Final Core dimensions selected: no
- Axis classifications are final decisions: no
- Detailed logs written by default: no

## Artifact scale

- n_bins: {corpus_meta['n_bins']}
- steps: {corpus_meta['steps']}
- available fit scenario count: {corpus_meta['available_fit_scenario_count']}
- used fit scenario count: {corpus_meta['used_fit_scenario_count']}
- available holdout scenario count: {corpus_meta['available_holdout_scenario_count']}
- used holdout scenario count: {corpus_meta['used_holdout_scenario_count']}
- available fit seed count: {corpus_meta['available_fit_seed_count']}
- used fit seed count: {corpus_meta['used_fit_seed_count']}
- available holdout seed count: {corpus_meta['available_holdout_seed_count']}
- used holdout seed count: {corpus_meta['used_holdout_seed_count']}
- snapshot count: {corpus_meta['snapshot_count']}
- reduced run: {str(reduced_run).lower()}
- official docs artifact: {str(official_docs_artifact).lower()}

## Task 3.1c linkage

- residual decomposition file: `{TASK3_1C_RESIDUAL}`
- residual terrain file: `{TASK3_1C_TERRAIN}`
- auto audit flag reason file: `{TASK3_1C_FLAGS}`
- residual rows loaded: {len(task3_outputs['residual'])}
- terrain rows loaded: {len(task3_outputs['terrain'])}
- flag reason rows loaded: {len(task3_outputs['flags'])}
- join key: {relation_meta['task3_1c_join_key']}
- matched relation rows: {relation_meta['task3_1c_matched_relation_rows']}
- unmatched rate: {relation_meta['task3_1c_unmatched_rate']:.6f}

## Classification note

- Axis classifications are decision-support labels only.
- Classification reasons are derived from measured external response, residual relation, macro-dynamics preservation, redundancy, and conditional separation.
- No Core dimensions are selected in this task.
'''
    (root / "results.md").write_text(text)


def run_audit(output_root=OUTPUT_DIR, *, steps: int = STEPS, n_bins: int | None = None, reduced_run: bool = False, write_detailed: bool = False):
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    axes, values, corpus_meta = build_corpus(steps=steps, n_bins=n_bins, reduced_run=reduced_run)
    corpus_meta["snapshot_count"] = len(values)
    corpus_meta["dataset_count"] = values["dataset"].nunique()
    task3_outputs = load_task3_1c_outputs()
    tables, relation_meta = summarize(axes, values, task3_outputs)
    official_docs_artifact = not reduced_run
    manifest = _manifest_rows(tables, corpus_meta, task3_outputs, relation_meta, official_docs_artifact=official_docs_artifact, reduced_run=reduced_run)
    tables["artifact_manifest.csv"] = manifest
    for name, df in tables.items():
        df.to_csv(root / name, index=False)
    if write_detailed:
        values.to_csv(root / "detailed_axis_timeseries.csv", index=False)
    _write_results(root, corpus_meta, task3_outputs, relation_meta, official_docs_artifact, reduced_run)
    return tables


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-root", default=str(OUTPUT_DIR))
    p.add_argument("--steps", type=int, default=STEPS)
    p.add_argument("--n-bins", type=int, default=None)
    p.add_argument("--reduced-run", action="store_true", help="Development-only reduced run; never commit as official docs artifact.")
    p.add_argument("--write-detailed", action="store_true")
    a = p.parse_args()
    run_audit(a.output_root, steps=a.steps, n_bins=a.n_bins, reduced_run=a.reduced_run, write_detailed=a.write_detailed)


if __name__ == "__main__":
    main()
