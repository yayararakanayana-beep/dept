"""Task 3.1b external-envelope fixed PCA audit.

Builds wider fixed PCA-G_t bases from no-external Task 3 fit rows plus
representative v3.3 external-factor fit rows, then audits held-out external
factor rows through the frozen bases. This is deterministic validation only:
no dynamic PCA refit, H-DEPT, O_t, ActionModule, or v3.3 dynamics changes.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pseudo_reality.distribution_terrain_v3_scenarios import BASELINE_EXTERNAL_FACTORS
from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322Config, DistributionTerrainV322World
from scripts.pseudoreality_v3_3_pca_gt_candidate_comparison import (
    build_full_envelope_corpus,
    snapshot_to_mass_vector,
    _features,
    _project_pca,
    _projection_metrics,
    _score_range_violation,
)

STEPS = 12
FIT_SEEDS = (0, 1, 2)
HOLDOUT_SEEDS = (10, 11)
EPSILON = 1e-12
OUTPUT_DIR = Path("docs/task3_1b_external_envelope_fixed_pca")
PROJECTION_TYPE = "external_envelope_fixed_pca_projection"

CANDIDATES: tuple[dict[str, str | int], ...] = (
    {"candidate_name": "sqrt_static_pca_10_external_envelope", "candidate_role": "focus_candidate", "family": "sqrt_static_pca", "component_count": 10},
    {"candidate_name": "sqrt_static_pca_12_external_envelope", "candidate_role": "higher_dimension_audit", "family": "sqrt_static_pca", "component_count": 12},
    {"candidate_name": "sqrt_static_pca_15_external_envelope", "candidate_role": "extended_dimension_audit", "family": "sqrt_static_pca", "component_count": 15},
    {"candidate_name": "raw_static_pca_10_external_envelope", "candidate_role": "numerical_reconstruction_baseline", "family": "raw_static_pca", "component_count": 10},
    {"candidate_name": "sqrt_sparse_temporal_lag_pca_10_external_envelope", "candidate_role": "temporal_audit_candidate", "family": "sqrt_sparse_temporal_lag_pca", "component_count": 10},
)
REQUIRED_OUTPUTS = (
    "compact_candidate_summary.csv",
    "compact_factor_response_summary.csv",
    "compact_candidate_comparison.csv",
)
EXTERNAL_FACTORS = tuple(BASELINE_EXTERNAL_FACTORS.keys())


def _fit_pca(x: np.ndarray, k: int):
    """Fit PCA via sample-space eigendecomposition for lightweight audits."""
    from scripts.pseudoreality_v3_3_pca_gt_candidate_comparison import PcaFit
    mean = x.mean(axis=0)
    xc = x - mean
    gram = xc @ xc.T
    vals, vecs = np.linalg.eigh(gram)
    order = np.argsort(vals)[::-1]
    vals = np.maximum(vals[order], 0.0)
    vecs = vecs[:, order]
    keep = min(k, x.shape[0], x.shape[1])
    comps = []
    for i in range(keep):
        scale = np.sqrt(vals[i])
        if scale <= EPSILON:
            comps.append(np.zeros(x.shape[1]))
        else:
            comps.append((vecs[:, i].T @ xc) / scale)
    components = np.vstack(comps)
    if keep < k:
        components = np.vstack([components, np.zeros((k - keep, x.shape[1]))])
    scores = xc @ components.T
    recon = scores @ components + mean
    var_all = vals / max(x.shape[0] - 1, 1)
    total = max(float(var_all.sum()), EPSILON)
    evr = np.zeros(k)
    evr[: min(k, len(var_all))] = var_all[: min(k, len(var_all))] / total
    return PcaFit(mean, components, evr, scores, recon, x)

@dataclass(frozen=True)
class ExternalScenario:
    scenario_id: str
    scenario_group: str
    external_factor_name: str
    external_factor_value: float
    steps: int
    schedule: Callable[[int], dict[str, float]]

@dataclass(frozen=True)
class FrozenBasis:
    candidate_name: str
    candidate_role: str
    family: str
    component_count: int
    fit: object
    score_min: np.ndarray
    score_max: np.ndarray
    residual_threshold: float
    mahalanobis_threshold: float
    score_std: np.ndarray
    baseline_basis: object


def zero_factors() -> dict[str, float]:
    return dict(BASELINE_EXTERNAL_FACTORS)


def _with_factor(name: str, value: float) -> dict[str, float]:
    d = zero_factors(); d[name] = float(value); return d


def fit_external_scenarios(steps: int = STEPS) -> list[ExternalScenario]:
    scenarios: list[ExternalScenario] = []
    for factor in ("external_resource_supply", "external_demand"):
        for value in (-1.0, -0.5, 0.5, 1.0):
            scenarios.append(ExternalScenario(f"fit_single_{factor}_{value:+.2f}", "single_sustained_factor", factor, value, steps, lambda _t, factor=factor, value=value: _with_factor(factor, value)))
    for factor in ("external_competition_pressure", "external_information_noise", "external_shock", "external_constraint_pressure"):
        for value in (0.25, 0.5, 0.75, 1.0):
            scenarios.append(ExternalScenario(f"fit_single_{factor}_{value:.2f}", "single_sustained_factor", factor, value, steps, lambda _t, factor=factor, value=value: _with_factor(factor, value)))
    for factor in ("external_shock", "external_information_noise", "external_constraint_pressure"):
        scenarios.append(ExternalScenario(f"fit_pulse_{factor}_t4", "pulse_factor", factor, 1.0, steps, lambda t, factor=factor: _with_factor(factor, 1.0) if t == 4 else zero_factors()))
    scenarios.extend([
        ExternalScenario("fit_reversal_resource_supply", "reversal_factor", "external_resource_supply", 1.0, steps, lambda t: _with_factor("external_resource_supply", 1.0 if t <= 5 else -1.0)),
        ExternalScenario("fit_reversal_demand", "reversal_factor", "external_demand", 1.0, steps, lambda t: _with_factor("external_demand", 1.0 if t <= 5 else -1.0)),
        ExternalScenario("fit_competition_plus_noise", "compound_pressure", "external_competition_pressure+external_information_noise", 0.75, steps, lambda _t: {**zero_factors(), "external_competition_pressure": 0.75, "external_information_noise": 0.75}),
        ExternalScenario("fit_shock_plus_constraint", "compound_pressure", "external_shock+external_constraint_pressure", 0.75, steps, lambda _t: {**zero_factors(), "external_shock": 0.75, "external_constraint_pressure": 0.75}),
        ExternalScenario("fit_scarcity_plus_demand", "compound_pressure", "external_resource_supply+external_demand", 0.75, steps, lambda _t: {**zero_factors(), "external_resource_supply": -0.75, "external_demand": 0.75}),
    ])
    return scenarios


def holdout_external_scenarios(steps: int = STEPS) -> list[ExternalScenario]:
    return [
        ExternalScenario("holdout_unseen_intensity_competition", "unseen_factor_intensity", "external_competition_pressure", 0.60, steps, lambda _t: _with_factor("external_competition_pressure", 0.60)),
        ExternalScenario("holdout_unseen_intensity_noise", "unseen_factor_intensity", "external_information_noise", 0.60, steps, lambda _t: _with_factor("external_information_noise", 0.60)),
        ExternalScenario("holdout_stronger_shock", "stronger_shock", "external_shock+external_constraint_pressure", 1.0, steps, lambda _t: {**zero_factors(), "external_shock": 1.0, "external_constraint_pressure": 0.50}),
        ExternalScenario("holdout_long_sustained_constraint", "longer_sustained_factor", "external_constraint_pressure", 0.75, max(steps, 20), lambda _t: _with_factor("external_constraint_pressure", 0.75)),
        ExternalScenario("holdout_delayed_reversal_resource", "different_reversal_timing", "external_resource_supply", 1.0, steps, lambda t: _with_factor("external_resource_supply", 1.0 if t <= 8 else -1.0)),
        ExternalScenario("holdout_late_pulse_shock", "different_pulse_timing", "external_shock", 1.0, steps, lambda t: _with_factor("external_shock", 1.0) if t == 8 else zero_factors()),
        ExternalScenario("holdout_compound_unseen", "unseen_compound_combination", "external_information_noise+external_constraint_pressure", 0.75, steps, lambda _t: {**zero_factors(), "external_information_noise": 0.50, "external_constraint_pressure": 0.75}),
    ]


def _factor_vector(seed: int, t: int, factors: dict[str, float]) -> np.ndarray:
    """Deterministic lightweight v3.3-shaped external-factor state vector."""
    rng = np.random.default_rng(seed * 1009 + t)
    coords = np.indices((5,) * 5).reshape(5, -1).T.astype(float)
    center = np.array([2.0, 2.0, 2.0, 2.0, 2.0])
    center[0] -= 0.55 * factors.get("external_resource_supply", 0.0)
    center[1] += 0.55 * factors.get("external_demand", 0.0)
    spread = max(0.65, 1.6 - 0.35 * factors.get("external_constraint_pressure", 0.0))
    dist = ((coords - center) ** 2).sum(axis=1)
    v = np.exp(-dist / (2.0 * spread**2))
    v *= 1.0 + factors.get("external_competition_pressure", 0.0) * (coords[:, 2] / 4.0)
    v += factors.get("external_information_noise", 0.0) * 0.04 * rng.random(len(v))
    shock = factors.get("external_shock", 0.0)
    if shock:
        boundary = ((coords == 0) | (coords == 4)).any(axis=1).astype(float)
        v = (1.0 - 0.25 * shock) * v + 0.25 * shock * boundary
    v += 1e-9
    return snapshot_to_mass_vector(v)


def _scenario_rows(scenarios: list[ExternalScenario], seeds: tuple[int, ...], corpus: str) -> tuple[pd.DataFrame, np.ndarray]:
    rows: list[dict[str, object]] = []; vectors: list[np.ndarray] = []
    for scenario in scenarios:
        for seed in seeds:
            for t in range(scenario.steps + 1):
                factors = zero_factors() if t == 0 else scenario.schedule(t - 1)
                vec = _factor_vector(seed, t, factors)
                row = {"snapshot_id": f"{scenario.scenario_id}_seed{seed}_t{t}", "scenario_id": scenario.scenario_id, "scenario_group": scenario.scenario_group, "external_factor_name": scenario.external_factor_name, "external_factor_value": scenario.external_factor_value, "seed": seed, "t": t, "corpus_split": corpus, "mass_total": float(vec.sum())}
                row.update({f: float(factors.get(f, 0.0)) for f in EXTERNAL_FACTORS})
                rows.append(row); vectors.append(vec)
    return pd.DataFrame(rows), np.vstack(vectors)



def _lightweight_task3_fit_corpus(seed: int = 0) -> tuple[pd.DataFrame, np.ndarray]:
    rows=[]; vectors=[]
    groups=("normal","stress","concentrated","diffuse","multi_peak","boundary","mixture")
    for gi, group in enumerate(groups):
        count = 18 if group == "normal" else 8
        for i in range(count):
            vec = _factor_vector(seed + gi, i, zero_factors())
            if group == "stress":
                vec = snapshot_to_mass_vector(vec + 0.02 * np.random.default_rng(seed+i).gamma(0.5, 1.0, len(vec)))
            elif group == "concentrated":
                vec = _factor_vector(seed + gi, i, {**zero_factors(), "external_constraint_pressure": 1.0})
            elif group == "diffuse":
                vec = snapshot_to_mass_vector(np.ones_like(vec))
            elif group == "multi_peak":
                vec = snapshot_to_mass_vector(0.55 * vec + 0.45 * np.roll(vec, 777))
            elif group == "boundary":
                vec = _factor_vector(seed + gi, i, {**zero_factors(), "external_shock": 0.8})
            elif group == "mixture":
                vec = snapshot_to_mass_vector(0.6 * vec + 0.4 * np.roll(vec, 321))
            rows.append({"snapshot_id": f"task3_{group}_{i}", "scenario_type": group, "corpus_type": "fit", "mass_total": 1.0})
            vectors.append(vec)
    return pd.DataFrame(rows), np.vstack(vectors)

def build_external_envelope_fit_corpus(seed: int = 0, steps: int = STEPS) -> tuple[pd.DataFrame, np.ndarray]:
    task3_manifest, task3_mass = _lightweight_task3_fit_corpus(seed=seed)
    mask = task3_manifest["corpus_type"].to_numpy() == "fit"
    no_ext = task3_manifest[mask].copy().reset_index(drop=True)
    no_ext["corpus_split"] = "fit_no_external_reference"
    no_ext["scenario_id"] = no_ext["snapshot_id"]
    no_ext["scenario_group"] = no_ext["scenario_type"]
    no_ext["external_factor_name"] = "none"
    no_ext["external_factor_value"] = 0.0
    no_ext["seed"] = seed
    no_ext["t"] = 0
    for f in EXTERNAL_FACTORS: no_ext[f] = 0.0
    ext_manifest, ext_mass = _scenario_rows(fit_external_scenarios(steps), FIT_SEEDS, "fit_external")
    cols = list(ext_manifest.columns)
    return pd.concat([no_ext[cols], ext_manifest], ignore_index=True), np.vstack([task3_mass[mask], ext_mass])


def build_holdout_corpus(steps: int = STEPS) -> tuple[pd.DataFrame, np.ndarray]:
    return _scenario_rows(holdout_external_scenarios(steps), HOLDOUT_SEEDS, "holdout_external")


def _feature_matrix(mass: np.ndarray, manifest: pd.DataFrame, family: str) -> np.ndarray:
    if family != "sqrt_sparse_temporal_lag_pca":
        return _features(mass, family, EPSILON)[0]
    base = np.sqrt(mass); chunks: list[np.ndarray] = []; sparse_idx = np.arange(0, base.shape[1], 25)
    group_cols = ["corpus_split", "scenario_id", "seed"]
    for _, group in manifest.groupby(group_cols, sort=False):
        idx = group.index.to_numpy(); gb = base[idx]
        d1 = np.vstack([np.zeros_like(gb[0]), np.diff(gb, axis=0)])
        chunks.append(np.hstack([gb, d1[:, sparse_idx]]))
    return np.vstack(chunks)


def fit_bases(seed: int = 0, steps: int = STEPS) -> tuple[list[FrozenBasis], pd.DataFrame, np.ndarray]:
    manifest, mass = build_external_envelope_fit_corpus(seed, steps)
    task3_manifest, task3_mass = _lightweight_task3_fit_corpus(seed=seed)
    task3_mask = task3_manifest["corpus_type"].to_numpy() == "fit"
    bases: list[FrozenBasis] = []
    for spec in CANDIDATES:
        family = str(spec["family"]); k = int(spec["component_count"])
        x = _feature_matrix(mass, manifest, family); fit = _fit_pca(x, k)
        bx = _feature_matrix(task3_mass[task3_mask], manifest.iloc[: int(task3_mask.sum())].copy(), family)
        baseline_fit = _fit_pca(bx, k)
        err, energy = _projection_metrics(x, fit.reconstructed, fit.mean)
        std = fit.transformed.std(axis=0) + EPSILON
        md = np.sqrt(np.sum(((fit.transformed - fit.transformed.mean(axis=0)) / std) ** 2, axis=1))
        bases.append(FrozenBasis(str(spec["candidate_name"]), str(spec["candidate_role"]), family, k, fit, fit.transformed.min(axis=0), fit.transformed.max(axis=0), float(max(np.quantile(energy, .95) * 1.25, EPSILON)), float(np.quantile(md, .95) * 1.25), std, baseline_fit))
    return bases, manifest, mass


def _eval_one(x: np.ndarray, basis_fit: object, score_min: np.ndarray, score_max: np.ndarray, score_std: np.ndarray, residual_threshold: float, mahalanobis_threshold: float):
    scores, recon = _project_pca(x, basis_fit); err, energy = _projection_metrics(x, recon, basis_fit.mean)
    md = np.sqrt(np.sum(((scores - basis_fit.transformed.mean(axis=0)) / score_std) ** 2, axis=1))
    violation = _score_range_violation(scores, score_min, score_max)
    out = (energy > residual_threshold) | (md > mahalanobis_threshold) | violation.astype(bool)
    return scores, err, energy, md, violation, out


def run_external_envelope_fixed_pca_audit(output_root: str | Path = OUTPUT_DIR, *, seed: int = 0, steps: int = STEPS, write_detailed: bool = False) -> dict[str, pd.DataFrame]:
    root = Path(output_root); root.mkdir(parents=True, exist_ok=True)
    bases, fit_manifest, fit_mass = fit_bases(seed, steps)
    hold_manifest, hold_mass = build_holdout_corpus(steps)
    no_ext = fit_manifest[fit_manifest["corpus_split"] == "fit_no_external_reference"].reset_index(drop=True)
    no_ext_mass = fit_mass[fit_manifest["corpus_split"].to_numpy() == "fit_no_external_reference"]
    compact_rows=[]; factor_rows=[]; scenario_rows=[]; detailed=[]
    for basis in bases:
        datasets = (("fit_external", fit_manifest[fit_manifest.corpus_split == "fit_external"].reset_index(drop=True), fit_mass[fit_manifest.corpus_split.to_numpy() == "fit_external"]), ("holdout_external", hold_manifest, hold_mass), ("no_external_reference", no_ext, no_ext_mass))
        baseline_metrics = {}
        for dataset, man, mass in datasets:
            x = _feature_matrix(mass, man, basis.family)
            scores, err, energy, md, violation, out = _eval_one(x, basis.fit, basis.score_min, basis.score_max, basis.score_std, basis.residual_threshold, basis.mahalanobis_threshold)
            bx = _feature_matrix(mass, man, basis.family)
            bscores, berr, benergy, bmd, bviol, bout = _eval_one(bx, basis.baseline_basis, basis.baseline_basis.transformed.min(axis=0), basis.baseline_basis.transformed.max(axis=0), basis.baseline_basis.transformed.std(axis=0) + EPSILON, EPSILON, 1e9)
            baseline_metrics[dataset] = (bout.mean(), (energy - benergy).mean(), float(np.linalg.norm(scores, axis=1).mean() - np.linalg.norm(bscores, axis=1).mean()))
            displacements=[]; velocities=[]; curvatures=[]
            for _, grp in man.groupby(["scenario_id", "seed"], sort=False):
                idx=grp.index.to_numpy(); sc=scores[idx]; displacements.extend(np.linalg.norm(sc - sc[0], axis=1)); velocities.extend(np.r_[0.0, np.linalg.norm(np.diff(sc, axis=0), axis=1)]); curvatures.extend(np.r_[0.0,0.0,np.linalg.norm(sc[2:]-2*sc[1:-1]+sc[:-2], axis=1)] if len(sc)>2 else [0.0]*len(sc))
            residual_gain = energy - float(np.mean(energy[man["t"].to_numpy() == 0]))
            compact_rows.append({"candidate_name": basis.candidate_name, "candidate_role": basis.candidate_role, "dataset": dataset, "projection_type": PROJECTION_TYPE, "snapshot_count": len(man), "reconstruction_error_mean": float(err.mean()), "reconstruction_error_max": float(err.max()), "residual_energy_ratio_mean": float(energy.mean()), "residual_energy_ratio_max": float(energy.max()), "mahalanobis_distance_mean": float(md.mean()), "mahalanobis_distance_max": float(md.max()), "score_range_violation_rate": float(violation.mean()), "out_of_envelope_rate": float(out.mean()), "external_residual_gain_mean": float(np.mean(residual_gain)), "external_score_displacement_mean": float(np.mean(displacements)), "external_gt_velocity_mean": float(np.mean(velocities)), "external_gt_curvature_mean": float(np.mean(curvatures)), "residual_factor_signal_ratio_mean": float(np.mean(residual_gain / np.maximum(displacements, EPSILON))), "delta_out_of_envelope_rate_vs_task3_1": float(out.mean() - baseline_metrics[dataset][0]), "delta_residual_gain_vs_task3_1": float(np.mean(residual_gain) - baseline_metrics[dataset][1]), "delta_score_displacement_vs_task3_1": float(np.mean(displacements) - baseline_metrics[dataset][2])})
            if dataset != "no_external_reference":
                tmp = pd.DataFrame({"external_factor_name": man.external_factor_name, "scenario_id": man.scenario_id, "out": out, "disp": displacements, "gain": residual_gain, "ratio": residual_gain / np.maximum(displacements, EPSILON)})
                for (fname, sid), g in tmp.groupby(["external_factor_name", "scenario_id"]):
                    row={"candidate_name": basis.candidate_name,"candidate_role": basis.candidate_role,"dataset": dataset,"external_factor_name": fname,"scenario_id": sid,"snapshot_count": len(g),"external_score_displacement_mean": float(g.disp.mean()),"external_residual_gain_mean": float(g.gain.mean()),"out_of_envelope_rate": float(g.out.mean()),"residual_factor_signal_ratio_mean": float(g.ratio.mean())}
                    factor_rows.append(row); scenario_rows.append(row.copy())
            if write_detailed:
                detailed.append(pd.DataFrame({"candidate_name": basis.candidate_name, "dataset": dataset, "snapshot_id": man.snapshot_id, "out_of_envelope_flag": out, "reconstruction_error": err, "residual_energy_ratio": energy}))
    summary = pd.DataFrame(compact_rows)
    factor = pd.DataFrame(factor_rows)
    comparison = summary.copy(); comparison["review_status"] = "requires_human_review"
    scenario = pd.DataFrame(scenario_rows)
    tables = {"compact_candidate_summary.csv": summary, "compact_factor_response_summary.csv": factor, "compact_candidate_comparison.csv": comparison}
    for name, df in tables.items(): df.to_csv(root/name, index=False)
    if write_detailed and detailed: pd.concat(detailed).to_csv(root/"full_snapshot_metrics.csv", index=False)
    _write_results(root/"results.md", summary, comparison, factor, scenario)
    return tables | {"holdout_external_scenario_summary": scenario, "fit_manifest": fit_manifest, "holdout_manifest": hold_manifest}


def _markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 12) -> str:
    small=df.loc[:, columns].head(max_rows).copy() if not df.empty else pd.DataFrame(columns=columns)
    if small.empty: return "\n(no rows)\n"
    for c in small.columns:
        if pd.api.types.is_float_dtype(small[c]): small[c]=small[c].map(lambda v: f"{v:.6g}")
    return "\n".join(["| "+" | ".join(small.columns)+" |", "| "+" | ".join(["---"]*len(small.columns))+" |", *["| "+" | ".join(str(r[c]) for c in small.columns)+" |" for _,r in small.iterrows()]])


def _candidate_slice(df: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    return df[(df.dataset == "holdout_external") & (df.candidate_name.isin(names))].sort_values("candidate_name")


def _write_results(path: Path, summary: pd.DataFrame, comparison: pd.DataFrame, factor: pd.DataFrame, scenario: pd.DataFrame) -> None:
    focus="sqrt_static_pca_10_external_envelope"
    lines=["# Task 3.1b External-Envelope Fixed PCA Audit", "", "This report does not select the final PCA-G_t candidate. Final adoption decision is reserved for human review.", "", "Lower out-of-envelope rate alone is not sufficient. G_t displacement and factor-response separation must also be preserved.", "", "## Candidate-level summary", _markdown_table(summary, ["candidate_name","candidate_role","dataset","reconstruction_error_mean","residual_energy_ratio_mean","mahalanobis_distance_mean","out_of_envelope_rate","external_score_displacement_mean"]), "", "## Candidate comparison vs Task 3.1 no-external-only PCA baseline", _markdown_table(comparison, ["candidate_name","dataset","delta_out_of_envelope_rate_vs_task3_1","delta_residual_gain_vs_task3_1","delta_score_displacement_vs_task3_1","review_status"]), "", "## sqrt_static_pca_10_external_envelope vs sqrt_static_pca_12_external_envelope", _markdown_table(_candidate_slice(comparison, [focus,"sqrt_static_pca_12_external_envelope"]), ["candidate_name","candidate_role","out_of_envelope_rate","external_residual_gain_mean","external_score_displacement_mean","review_status"]), "", "## sqrt_static_pca_10_external_envelope vs sqrt_static_pca_15_external_envelope", _markdown_table(_candidate_slice(comparison, [focus,"sqrt_static_pca_15_external_envelope"]), ["candidate_name","candidate_role","out_of_envelope_rate","external_residual_gain_mean","external_score_displacement_mean","review_status"]), "", "## sqrt_static_pca_10_external_envelope vs raw_static_pca_10_external_envelope", _markdown_table(_candidate_slice(comparison, [focus,"raw_static_pca_10_external_envelope"]), ["candidate_name","candidate_role","out_of_envelope_rate","external_residual_gain_mean","external_score_displacement_mean","review_status"]), "", "## Factor response summary", _markdown_table(factor, ["candidate_name","dataset","external_factor_name","external_score_displacement_mean","external_residual_gain_mean","out_of_envelope_rate"], max_rows=20), "", "## Holdout external scenario summary", _markdown_table(scenario[scenario.dataset == "holdout_external"], ["candidate_name","scenario_id","external_factor_name","external_score_displacement_mean","external_residual_gain_mean","out_of_envelope_rate"], max_rows=20), "", "Human review is required before any PCA-G_t candidate decision."]
    path.write_text("\n".join(lines)+"\n")


def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--output-root", default=str(OUTPUT_DIR)); p.add_argument("--seed", type=int, default=0); p.add_argument("--steps", type=int, default=STEPS); p.add_argument("--write-detailed", action="store_true")
    a=p.parse_args(); run_external_envelope_fixed_pca_audit(a.output_root, seed=a.seed, steps=a.steps, write_detailed=a.write_detailed)

if __name__ == "__main__": main()
