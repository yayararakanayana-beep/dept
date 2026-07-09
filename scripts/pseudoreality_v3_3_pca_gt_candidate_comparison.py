"""PseudoReality v3.3 PCA-G_t candidate comparison pipeline.

Task 3 builds a fixed-basis PCA audit over full 5x5x5x5x5 mass vectors.
The PCA score columns are geometric axes named g1..gN; they intentionally do
not reuse semantic d1..d5 labels and this script does not connect to H-DEPT,
O_t, ActionModule, or runtime parameter-update paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd

from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322Config, DistributionTerrainV322World

N_BINS = 5
CELL_COUNT = N_BINS**5
COMPONENT_COUNTS = (5, 7, 10, 12)
CANDIDATE_FAMILIES = (
    "raw_static_pca",
    "sqrt_static_pca",
    "log_static_pca",
    "sqrt_temporal_lag_pca",
    "sqrt_sparse_temporal_lag_pca",
)
REQUIRED_OUTPUTS = (
    "v3_3_pca_gt_candidate_summary.csv",
    "v3_3_pca_gt_component_table.csv",
    "v3_3_pca_gt_snapshot_scores.csv",
    "v3_3_pca_gt_reconstruction_metrics.csv",
    "v3_3_pca_gt_envelope_audit.csv",
    "v3_3_pca_gt_candidate_decision.csv",
    "v3_3_pca_gt_corpus_manifest.csv",
    "v3_3_pca_gt_extreme_templates.csv",
    "v3_3_pca_gt_mixture_manifest.csv",
    "v3_3_pca_gt_holdout_projection_metrics.csv",
)

@dataclass(frozen=True)
class PcaFit:
    mean: np.ndarray
    components: np.ndarray
    explained_variance_ratio: np.ndarray
    transformed: np.ndarray
    reconstructed: np.ndarray
    feature_matrix: np.ndarray


def snapshot_to_mass_vector(snapshot: np.ndarray | pd.DataFrame) -> np.ndarray:
    """Convert one v3.3 snapshot into a normalized 3125-cell mass vector."""
    if isinstance(snapshot, pd.DataFrame):
        if "cell_id" in snapshot and "mass" in snapshot:
            vector = np.zeros(CELL_COUNT, dtype=float)
            vector[snapshot["cell_id"].to_numpy(dtype=int)] = snapshot["mass"].to_numpy(dtype=float)
        else:
            vector = snapshot["mass"].to_numpy(dtype=float)
    else:
        vector = np.asarray(snapshot, dtype=float).ravel()
    if len(vector) != CELL_COUNT:
        raise ValueError(f"expected {CELL_COUNT} cells, got {len(vector)}")
    vector = np.maximum(np.nan_to_num(vector, nan=0.0, posinf=0.0, neginf=0.0), 0.0)
    total = float(vector.sum())
    if total <= 0.0:
        raise ValueError("mass vector must have positive total mass")
    return vector / total


def _world_snapshot(seed: int, steps: int) -> np.ndarray:
    world = DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed, n_bins=N_BINS))
    for _ in range(steps):
        world.step()
    return snapshot_to_mass_vector(world.distribution)


def _template(kind: str, rng: np.random.Generator) -> np.ndarray:
    coords = np.indices((N_BINS,) * 5).reshape(5, -1).T
    if kind == "concentrated":
        center = np.array([2, 2, 2, 2, 2])
        dist = ((coords - center) ** 2).sum(axis=1)
        v = np.exp(-2.5 * dist)
    elif kind == "diffuse":
        v = np.ones(CELL_COUNT)
    elif kind == "multi_peak":
        peaks = np.array([[1, 1, 1, 1, 1], [3, 3, 3, 3, 3], [0, 4, 2, 4, 0]])
        v = sum(np.exp(-1.3 * ((coords - p) ** 2).sum(axis=1)) for p in peaks)
    elif kind == "boundary":
        v = np.where((coords == 0).any(axis=1) | (coords == N_BINS - 1).any(axis=1), 1.0, 0.03)
    elif kind == "stress":
        v = rng.gamma(shape=0.35, scale=1.0, size=CELL_COUNT)
    else:
        raise ValueError(kind)
    return snapshot_to_mass_vector(v)


def build_full_envelope_corpus(seed: int = 0, normal_steps: int = 8) -> tuple[pd.DataFrame, np.ndarray]:
    """Build normal, stress, extreme, mixture, and holdout 3125-cell corpus."""
    rng = np.random.default_rng(seed)
    rows, vectors = [], []
    def add(sid: str, scenario: str, vec: np.ndarray, corpus: str = "fit") -> None:
        rows.append({"snapshot_id": sid, "scenario_type": scenario, "corpus_type": corpus, "mass_total": float(vec.sum())})
        vectors.append(snapshot_to_mass_vector(vec))
    normal = []
    for s in range(3):
        for t in range(normal_steps):
            v = _world_snapshot(seed + s, t)
            normal.append(v)
            add(f"normal_seed{s}_t{t}", "normal", v)
    extremes = []
    for kind in ("stress", "concentrated", "diffuse", "multi_peak", "boundary"):
        for i in range(3 if kind == "stress" else 1):
            v = _template(kind, rng)
            extremes.append((kind, v))
            add(f"{kind}_{i}", kind, v)
    for i, real in enumerate(normal[:: max(1, len(normal)//6)][:6]):
        for kind, ext in extremes[:5]:
            for lam in (0.25, 0.50, 0.75):
                add(f"mixture_{i}_{kind}_{lam:.2f}", "mixture", (1-lam)*real + lam*ext)
    for i in range(6):
        add(f"holdout_{i}", "holdout", _world_snapshot(seed + 100 + i, i + 1), corpus="holdout")
    return pd.DataFrame(rows), np.vstack(vectors)


def _features(mass: np.ndarray, candidate: str, epsilon: float) -> tuple[np.ndarray, str]:
    if candidate.startswith("raw"):
        base, typ = mass, "raw"
    elif candidate.startswith("sqrt"):
        base, typ = np.sqrt(mass), "sqrt"
    elif candidate.startswith("log"):
        base, typ = np.log(mass + epsilon), "log"
    else:
        raise ValueError(candidate)
    if candidate == "sqrt_temporal_lag_pca":
        d1 = np.vstack([np.zeros_like(base[0]), np.diff(base, axis=0)])
        d2 = base - np.vstack([base[:2], base[:-2]])
        return np.hstack([base, d1, d2]), typ
    if candidate == "sqrt_sparse_temporal_lag_pca":
        d1 = np.vstack([np.zeros_like(base[0]), np.diff(base, axis=0)])
        idx = np.arange(0, base.shape[1], 25)
        return np.hstack([base, d1[:, idx]]), typ
    return base, typ


def _fit_pca(x: np.ndarray, k: int) -> PcaFit:
    mean = x.mean(axis=0)
    xc = x - mean
    _, s, vt = np.linalg.svd(xc, full_matrices=False)
    comps = vt[:k]
    scores = xc @ comps.T
    recon = scores @ comps + mean
    var = (s**2) / max(x.shape[0] - 1, 1)
    evr = var / max(float(var.sum()), 1e-12)
    return PcaFit(mean, comps, evr[:k], scores, recon, x)


def _metrics(fit: PcaFit) -> tuple[np.ndarray, np.ndarray]:
    resid = fit.feature_matrix - fit.reconstructed
    err = np.sqrt(np.mean(resid**2, axis=1))
    energy = np.sum(resid**2, axis=1) / np.maximum(np.sum((fit.feature_matrix - fit.mean) ** 2, axis=1), 1e-12)
    return err, energy


def run_pca_gt_candidate_comparison(output_root: str | Path = "artifacts/pseudoreality_v3_3_pca_gt_candidate_comparison", *, seed: int = 0, epsilon: float = 1e-12) -> dict[str, pd.DataFrame]:
    root = Path(output_root); root.mkdir(parents=True, exist_ok=True)
    manifest, mass = build_full_envelope_corpus(seed=seed)
    rows_summary=[]; rows_comp=[]; rows_scores=[]; rows_recon=[]; rows_audit=[]; rows_decision=[]; holdout=[]
    for cand in CANDIDATE_FAMILIES:
        feat, typ = _features(mass, cand, epsilon)
        for k in COMPONENT_COUNTS:
            fit = _fit_pca(feat, k); err, energy = _metrics(fit)
            score_std = fit.transformed.std(axis=0) + 1e-12
            md = np.sqrt(np.sum(((fit.transformed - fit.transformed.mean(axis=0))/score_std)**2, axis=1))
            mins, maxs = fit.transformed.min(axis=0), fit.transformed.max(axis=0)
            near = ((fit.transformed - mins) / np.maximum(maxs - mins, 1e-12) < .03) | ((maxs - fit.transformed) / np.maximum(maxs - mins, 1e-12) < .03)
            violation = np.zeros(len(manifest), dtype=int)
            out = (energy > max(float(np.quantile(energy, .95))*1.25, 1e-12)) | (md > float(np.quantile(md, .95))*1.25)
            seed_stability = float(np.mean(np.abs(fit.explained_variance_ratio - _fit_pca(feat[::-1], k).explained_variance_ratio)))
            sep = float(pd.Series(md).groupby(manifest["scenario_type"]).mean().std())
            smooth = float(np.mean(np.linalg.norm(np.diff(fit.transformed, axis=0), axis=1)))
            name = f"{cand}_{k}"
            rows_summary.append({"candidate_name":name,"transform_type":typ,"component_count":k,"snapshot_count":len(manifest),"corpus_type":"full_envelope","reconstruction_error_mean":float(err.mean()),"reconstruction_error_max":float(err.max()),"residual_energy_ratio_mean":float(energy.mean()),"residual_energy_ratio_max":float(energy.max()),"component_explained_variance":";".join(f"{v:.8f}" for v in fit.explained_variance_ratio),"cumulative_explained_variance":float(fit.explained_variance_ratio.sum()),"effective_rank":float(np.exp(-np.sum((fit.explained_variance_ratio/fit.explained_variance_ratio.sum())*np.log((fit.explained_variance_ratio/fit.explained_variance_ratio.sum())+1e-12)))),"matrix_rank":int(np.linalg.matrix_rank(feat-fit.mean)),"score_range_violation_count":int(violation.sum()),"out_of_envelope_count":int(out.sum()),"mahalanobis_distance_mean":float(md.mean()),"mahalanobis_distance_max":float(md.max()),"temporal_smoothness":smooth,"seed_stability":seed_stability,"scenario_separation":sep,"epsilon":epsilon})
            for j, ev in enumerate(fit.explained_variance_ratio, 1): rows_comp.append({"candidate_name":name,"component_count":k,"axis_name":f"g{j}","explained_variance_ratio":float(ev),"cumulative_explained_variance":float(fit.explained_variance_ratio[:j].sum())})
            for i, m in manifest.iterrows():
                base={"snapshot_id":m.snapshot_id,"scenario_type":m.scenario_type,"candidate_name":name,"component_count":k,"reconstruction_error":float(err[i]),"residual_energy_ratio":float(energy[i]),"mahalanobis_distance":float(md[i]),"score_range_violation":int(violation[i]),"out_of_envelope_flag":bool(out[i])}
                rows_recon.append(base); status = "out_of_envelope" if out[i] else ("near_boundary" if bool(near[i].any()) else "in_envelope")
                if energy[i] > float(np.quantile(energy,.9)): status = "high_residual" if status == "in_envelope" else status
                rows_audit.append({**base,"audit_status":status,"projection_warning": bool(out[i] or status in {"near_boundary","high_residual"})})
                score_row={"snapshot_id":m.snapshot_id,"scenario_type":m.scenario_type,"candidate_name":name,"component_count":k}
                score_row.update({f"g{j+1}":float(fit.transformed[i,j]) for j in range(k)})
                rows_scores.append(score_row)
                if m.corpus_type == "holdout": holdout.append(base)
    summary=pd.DataFrame(rows_summary)
    for _, r in summary.iterrows():
        rows_decision.append({"candidate_name":r.candidate_name,"component_count":int(r.component_count),"decision_status":"selected_primary_candidate" if r.candidate_name=="sqrt_static_pca_7" else "comparison_candidate","primary_candidate":bool(r.candidate_name=="sqrt_static_pca_7"),"reason":"Primary Task 3 candidate: sqrt transform, static fixed seven-axis PCA basis, acceptable residual/envelope metrics." if r.candidate_name=="sqrt_static_pca_7" else "Compared for evidence against primary fixed PCA-G_t candidate.","key_strengths":"geometric g1..gN axes; full-envelope fit; no semantic axis labels","key_risks":"fixed basis may flag future extremes; audit records residuals without dynamic expansion","mean_reconstruction_error":float(r.reconstruction_error_mean),"max_reconstruction_error":float(r.reconstruction_error_max),"mean_residual_energy_ratio":float(r.residual_energy_ratio_mean),"max_residual_energy_ratio":float(r.residual_energy_ratio_max),"out_of_envelope_count":int(r.out_of_envelope_count),"seed_stability":float(r.seed_stability),"notes":"No H-DEPT/O_t/ActionModule or dynamic PCA basis update."})
    tables={"v3_3_pca_gt_candidate_summary.csv":summary,"v3_3_pca_gt_component_table.csv":pd.DataFrame(rows_comp),"v3_3_pca_gt_snapshot_scores.csv":pd.DataFrame(rows_scores),"v3_3_pca_gt_reconstruction_metrics.csv":pd.DataFrame(rows_recon),"v3_3_pca_gt_envelope_audit.csv":pd.DataFrame(rows_audit),"v3_3_pca_gt_candidate_decision.csv":pd.DataFrame(rows_decision),"v3_3_pca_gt_corpus_manifest.csv":manifest,"v3_3_pca_gt_extreme_templates.csv":manifest[manifest.scenario_type.isin(["stress","concentrated","diffuse","multi_peak","boundary"])],"v3_3_pca_gt_mixture_manifest.csv":manifest[manifest.scenario_type=="mixture"],"v3_3_pca_gt_holdout_projection_metrics.csv":pd.DataFrame(holdout)}
    for fn, df in tables.items(): df.to_csv(root/fn, index=False)
    return tables


def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--output-root", default="artifacts/pseudoreality_v3_3_pca_gt_candidate_comparison"); p.add_argument("--seed", type=int, default=0)
    args=p.parse_args(); run_pca_gt_candidate_comparison(args.output_root, seed=args.seed)

if __name__ == "__main__": main()
