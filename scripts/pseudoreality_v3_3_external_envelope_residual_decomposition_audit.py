"""Task 3.1c fixed-PCA external-factor residual decomposition audit.

This script reuses the Task 3.1b real v3.3 data path and frozen PCA bases,
then decomposes residuals and automatic audit flag reasons for human review.
It does not select, reject, or adopt any PCA-G_t candidate.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322World  # noqa: F401
from scripts.pseudoreality_v3_3_external_envelope_fixed_pca_audit import (
    EPSILON,
    OUTPUT_DIR as TASK3_1B_OUTPUT_DIR,
    STEPS,
    _eval_one,
    _feature_matrix,
    build_external_envelope_fit_corpus,
    build_holdout_corpus,
    fit_bases,
)
from scripts.pseudoreality_v3_3_pca_gt_candidate_comparison import (  # noqa: F401
    build_full_envelope_corpus,
    snapshot_to_mass_vector,
)

OUTPUT_DIR = Path("docs/task3_1c_external_envelope_residual_decomposition")
DETAILED_NAMES = ("full_snapshot_metrics.csv", "full_per_snapshot_log.csv", "full_time_series_scores.csv", "full_cell_residual_log.csv")


def _q(a: np.ndarray, p: float) -> float:
    return float(np.quantile(np.asarray(a, dtype=float), p)) if len(a) else 0.0


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    if len(a) < 2 or float(np.std(a)) <= EPSILON or float(np.std(b)) <= EPSILON:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _displacement_terms(scores: np.ndarray, man: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    disp = np.zeros(len(man)); vel = np.zeros(len(man)); curv = np.zeros(len(man))
    for _, grp in man.groupby(["scenario_id", "seed"], sort=False):
        idx = grp.index.to_numpy(); sc = scores[idx]
        disp[idx] = np.linalg.norm(sc - sc[0], axis=1)
        if len(sc) > 1:
            vel[idx[1:]] = np.linalg.norm(np.diff(sc, axis=0), axis=1)
        if len(sc) > 2:
            curv[idx[2:]] = np.linalg.norm(sc[2:] - 2 * sc[1:-1] + sc[:-2], axis=1)
    return disp, vel, curv


def _eval_dataset(basis, dataset: str, man: pd.DataFrame, mass: np.ndarray) -> pd.DataFrame:
    x = _feature_matrix(mass, man, basis.family)
    scores, err, energy, md, violation, flag = _eval_one(
        x, basis.fit, basis.score_min, basis.score_max, basis.score_std,
        basis.residual_threshold, basis.mahalanobis_threshold,
    )
    recon_residual = x - (scores @ basis.fit.components + basis.fit.mean)
    disp, vel, curv = _displacement_terms(scores, man)
    residual_exceed = energy > basis.residual_threshold
    mahal_exceed = md > basis.mahalanobis_threshold
    score_exceed = violation.astype(bool)
    out = man.copy().reset_index(drop=True)
    out["candidate_name"] = basis.candidate_name
    out["candidate_role"] = basis.candidate_role
    out["dataset"] = dataset
    out["residual_energy_ratio"] = energy
    out["mahalanobis_distance"] = md
    out["score_range_violation"] = score_exceed
    out["auto_audit_flag"] = flag
    out["residual_exceed"] = residual_exceed
    out["mahalanobis_exceed"] = mahal_exceed
    out["score_range_exceed"] = score_exceed
    out["residual_threshold"] = basis.residual_threshold
    out["mahalanobis_threshold"] = basis.mahalanobis_threshold
    out["external_score_displacement"] = disp
    out["external_gt_velocity"] = vel
    out["external_gt_curvature"] = curv
    out.attrs["residual_vectors"] = recon_residual
    return out


def _rate(s: pd.Series) -> float:
    return float(s.mean()) if len(s) else 0.0


def _candidate_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, g in df.groupby(["candidate_name", "candidate_role", "dataset"], sort=False):
        e = g.residual_energy_ratio.to_numpy(); md = g.mahalanobis_distance.to_numpy()
        rows.append(dict(zip(["candidate_name", "candidate_role", "dataset"], key)) | {
            "snapshot_count": len(g),
            "residual_energy_ratio_mean": float(e.mean()), "residual_energy_ratio_median": _q(e, .5), "residual_energy_ratio_p90": _q(e, .9), "residual_energy_ratio_p95": _q(e, .95), "residual_energy_ratio_max": float(e.max()),
            "mahalanobis_distance_mean": float(md.mean()), "mahalanobis_distance_median": _q(md, .5), "mahalanobis_distance_p90": _q(md, .9), "mahalanobis_distance_p95": _q(md, .95), "mahalanobis_distance_max": float(md.max()),
            "score_range_violation_rate": _rate(g.score_range_violation), "auto_audit_flag_rate": _rate(g.auto_audit_flag),
        })
    return pd.DataFrame(rows)


def _flag_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, g in df.groupby(["candidate_name", "candidate_role", "dataset"], sort=False):
        r, m, s = g.residual_exceed, g.mahalanobis_exceed, g.score_range_exceed
        rows.append(dict(zip(["candidate_name", "candidate_role", "dataset"], key)) | {
            "snapshot_count": len(g), "residual_threshold": float(g.residual_threshold.iloc[0]), "mahalanobis_threshold": float(g.mahalanobis_threshold.iloc[0]),
            "score_range_violation_rate": _rate(g.score_range_violation), "residual_exceed_rate": _rate(r), "mahalanobis_exceed_rate": _rate(m), "score_range_exceed_rate": _rate(s),
            "residual_only_rate": _rate(r & ~m & ~s), "mahalanobis_only_rate": _rate(~r & m & ~s), "score_range_only_rate": _rate(~r & ~m & s),
            "residual_and_mahalanobis_rate": _rate(r & m & ~s), "residual_and_score_range_rate": _rate(r & ~m & s), "mahalanobis_and_score_range_rate": _rate(~r & m & s),
            "all_three_exceed_rate": _rate(r & m & s), "no_flag_rate": _rate(~(r | m | s)), "auto_audit_flag_rate": _rate(g.auto_audit_flag),
        })
    return pd.DataFrame(rows)


def _factor_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    sub = df[df.dataset != "no_external_reference"]
    for key, g in sub.groupby(["external_factor_name", "scenario_id", "scenario_group", "candidate_name", "dataset"], sort=False):
        e = g.residual_energy_ratio.to_numpy()
        rows.append(dict(zip(["external_factor_name", "scenario_id", "scenario_group", "candidate_name", "dataset"], key)) | {
            "snapshot_count": len(g), "residual_energy_ratio_mean": float(e.mean()), "residual_energy_ratio_p90": _q(e, .9), "residual_energy_ratio_max": float(e.max()),
            "external_score_displacement_mean": float(g.external_score_displacement.mean()), "external_gt_velocity_mean": float(g.external_gt_velocity.mean()), "external_gt_curvature_mean": float(g.external_gt_curvature.mean()),
            "auto_audit_flag_rate": _rate(g.auto_audit_flag), "residual_exceed_rate": _rate(g.residual_exceed), "mahalanobis_exceed_rate": _rate(g.mahalanobis_exceed), "score_range_exceed_rate": _rate(g.score_range_exceed),
        })
    return pd.DataFrame(rows)


def _temporal_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for key, g in df.groupby(["scenario_id", "candidate_name", "seed", "dataset"], sort=False):
        g = g.sort_values("t"); e = g.residual_energy_ratio.to_numpy(); d = g.external_score_displacement.to_numpy(); f = g.auto_audit_flag.astype(float).to_numpy()
        rows.append(dict(zip(["scenario_id", "candidate_name", "seed", "dataset"], key)) | {
            "residual_start": float(e[0]), "residual_peak": float(e.max()), "residual_end": float(e[-1]), "residual_mean": float(e.mean()), "residual_slope": float(e[-1] - e[0]), "residual_peak_t": int(g.t.iloc[int(np.argmax(e))]), "residual_persistence_rate": _rate(g.residual_exceed),
            "displacement_start": float(d[0]), "displacement_peak": float(d.max()), "displacement_end": float(d[-1]), "displacement_mean": float(d.mean()),
            "flag_start": float(f[0]), "flag_peak": float(f.max()), "flag_end": float(f[-1]), "flag_persistence_rate": _rate(g.auto_audit_flag),
        })
    return pd.DataFrame(rows)


def _relation_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for key, g in df.groupby(["candidate_name", "dataset"], sort=False):
        e = g.residual_energy_ratio.to_numpy(); d = g.external_score_displacement.to_numpy(); hi_e = e > _q(e, .75); hi_d = d > _q(d, .75)
        rows.append(dict(zip(["candidate_name", "dataset"], key)) | {
            "correlation_residual_displacement": _corr(e, d), "correlation_residual_velocity": _corr(e, g.external_gt_velocity.to_numpy()), "correlation_residual_curvature": _corr(e, g.external_gt_curvature.to_numpy()),
            "high_residual_high_displacement_rate": float(np.mean(hi_e & hi_d)), "high_residual_low_displacement_rate": float(np.mean(hi_e & ~hi_d)), "low_residual_high_displacement_rate": float(np.mean(~hi_e & hi_d)), "low_residual_low_displacement_rate": float(np.mean(~hi_e & ~hi_d)),
        })
    return pd.DataFrame(rows)


def _terrain_summary(frames: list[pd.DataFrame]) -> pd.DataFrame:
    rows=[]
    for df in frames:
        rv = df.attrs["residual_vectors"]
        for key, g in df[df.dataset != "no_external_reference"].groupby(["candidate_name", "dataset", "external_factor_name", "scenario_id"], sort=False):
            idx = g.index.to_numpy(); mean_res = rv[idx].mean(axis=0); order = np.argsort(np.abs(mean_res))[::-1][:5]
            abs_total = float(np.sum(np.abs(mean_res)) + EPSILON); pos = [f"cell{int(i)}:{mean_res[i]:.4g}" for i in order if mean_res[i] > 0]; neg = [f"cell{int(i)}:{mean_res[i]:.4g}" for i in order if mean_res[i] < 0]
            rows.append(dict(zip(["candidate_name", "dataset", "external_factor_name", "scenario_id"], key)) | {
                "top_residual_cell_count": int(len(order)), "top_residual_mass_share": float(np.sum(np.abs(mean_res[order])) / abs_total),
                "top_positive_residual_cells_summary": "; ".join(pos[:5]), "top_negative_residual_cells_summary": "; ".join(neg[:5]),
                "residual_concentration_score": float(np.sum(np.square(mean_res[order])) / (np.sum(np.square(mean_res)) + EPSILON)),
            })
    return pd.DataFrame(rows)


def _markdown_table(df: pd.DataFrame, cols: list[str], max_rows: int = 12) -> str:
    if df.empty: return "\n(no rows)\n"
    small = df.loc[:, cols].head(max_rows).copy()
    for c in small.columns:
        if pd.api.types.is_float_dtype(small[c]): small[c] = small[c].map(lambda v: f"{v:.6g}")
    return "\n".join(["| " + " | ".join(small.columns) + " |", "| " + " | ".join(["---"]*len(small.columns)) + " |", *["| " + " | ".join(str(r[c]) for c in small.columns) + " |" for _, r in small.iterrows()]])


def _write_results(root: Path, summary, flag, factor, temporal, relation, terrain) -> None:
    lines = [
        "# Task 3.1c External-Envelope Residual Decomposition Audit", "",
        "This report does not select, reject, or adopt any PCA-G_t candidate.",
        "This report only decomposes residuals and automatic audit flags for human review.",
        "Automatic audit flags are diagnostic signals, not final validity judgments.", "",
        "このレポートはPCA-G_t候補を採用・不採用にするものではない。",
        "残差と自動監査フラグの理由を分解し、人間が判断するための材料を出すだけである。",
        "自動監査フラグは診断信号であり、最終的な有効・無効判断ではない。", "",
        "## Candidate residual decomposition", _markdown_table(summary, ["candidate_name","dataset","residual_energy_ratio_mean","residual_energy_ratio_p90","residual_energy_ratio_p95","auto_audit_flag_rate"], 20), "",
        "## Automatic audit flag reason decomposition", _markdown_table(flag, ["candidate_name","dataset","residual_exceed_rate","mahalanobis_exceed_rate","score_range_exceed_rate","all_three_exceed_rate","no_flag_rate"], 20), "",
        "## External factor residual decomposition", _markdown_table(factor, ["external_factor_name","scenario_id","candidate_name","dataset","residual_energy_ratio_mean","auto_audit_flag_rate"], 30), "",
        "## Temporal residual decomposition", _markdown_table(temporal, ["scenario_id","candidate_name","seed","dataset","residual_peak","residual_slope","residual_persistence_rate","flag_persistence_rate"], 30), "",
        "## Residual and G_t movement relation", _markdown_table(relation, ["candidate_name","dataset","correlation_residual_displacement","correlation_residual_velocity","correlation_residual_curvature"], 20), "",
        "## Residual terrain summary", _markdown_table(terrain, ["candidate_name","dataset","external_factor_name","scenario_id","top_residual_mass_share","residual_concentration_score"], 30), "",
        "No candidate decision is made in this report.",
    ]
    (root / "results.md").write_text("\n".join(lines) + "\n")


def run_residual_decomposition_audit(output_root: str | Path = OUTPUT_DIR, *, seed: int = 0, steps: int = STEPS, write_detailed: bool = False) -> dict[str, pd.DataFrame]:
    root = Path(output_root); root.mkdir(parents=True, exist_ok=True)
    # Keep Task 3.1b outputs as explicit inputs/antecedents when present.
    for name in ("compact_candidate_summary.csv", "compact_factor_response_summary.csv", "compact_candidate_comparison.csv"):
        _ = TASK3_1B_OUTPUT_DIR / name
    bases, fit_manifest, fit_mass = fit_bases(seed, steps)
    hold_manifest, hold_mass = build_holdout_corpus(steps)
    no_ext = fit_manifest[fit_manifest["corpus_split"] == "fit_no_external_reference"].reset_index(drop=True)
    no_ext_mass = fit_mass[fit_manifest["corpus_split"].to_numpy() == "fit_no_external_reference"]
    frames=[]
    for basis in bases:
        for dataset, man, mass in (
            ("fit_external", fit_manifest[fit_manifest.corpus_split == "fit_external"].reset_index(drop=True), fit_mass[fit_manifest.corpus_split.to_numpy() == "fit_external"]),
            ("holdout_external", hold_manifest.reset_index(drop=True), hold_mass),
            ("no_external_reference", no_ext, no_ext_mass),
        ):
            frames.append(_eval_dataset(basis, dataset, man, mass))
    concat_frames = []
    for frame in frames:
        clean = frame.copy()
        clean.attrs = {}
        concat_frames.append(clean)
    all_df = pd.concat(concat_frames, ignore_index=True)
    tables = {
        "compact_residual_decomposition_summary.csv": _candidate_summary(all_df),
        "compact_auto_audit_flag_reason_summary.csv": _flag_summary(all_df),
        "compact_factor_residual_summary.csv": _factor_summary(all_df),
        "compact_temporal_residual_summary.csv": _temporal_summary(all_df),
        "compact_residual_gt_relation_summary.csv": _relation_summary(all_df),
        "compact_residual_terrain_summary.csv": _terrain_summary(frames),
    }
    for name, table in tables.items(): table.to_csv(root / name, index=False)
    if write_detailed:
        all_df.to_csv(root / "full_per_snapshot_log.csv", index=False)
    _write_results(root, *tables.values())
    return tables


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-root", default=str(OUTPUT_DIR)); p.add_argument("--seed", type=int, default=0); p.add_argument("--steps", type=int, default=STEPS); p.add_argument("--write-detailed", action="store_true")
    a = p.parse_args(); run_residual_decomposition_audit(a.output_root, seed=a.seed, steps=a.steps, write_detailed=a.write_detailed)


if __name__ == "__main__":
    main()
