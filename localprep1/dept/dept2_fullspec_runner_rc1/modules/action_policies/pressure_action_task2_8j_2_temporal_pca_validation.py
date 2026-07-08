"""Task 2-8j-2: temporal PCA / sparse temporal PCA validation RC1.

Purpose:
    Validate whether the Task 2-8j-1 candidate feature log can support stable
    effective-dimension candidates.  This task fits PCA-like validation models
    over coarse candidate features, compares static vs temporal feature spaces,
    and emits reconstruction / stability / prediction-aid tables.

Boundary:
    - validation only
    - no effective dimension is adopted or frozen here
    - no dynamics-axis extraction
    - no action-weight conversion
    - no upper-pressure connection
    - no ActionFrame / ActionModule / FullSpec runtime / canonical write
    - no v2_hidden_trace as feature input
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_1_candidate_feature_log import (
    ALLOWED_INPUT_TRACES,
    FORBIDDEN_INPUT_TRACES,
    CandidateFeatureLogConfig,
    build_candidate_feature_log,
    validate_candidate_feature_log,
)


TASK2_8J_2_VERSION = "temporal_pca_effective_dimension_validation_rc1"
TASK2_8J_2_CONTRACT = (
    "Task2_8j_2_temporal_pca_sparse_pca_validation__effective_dimension_candidate_only__"
    "no_adoption_no_dynamics_axis_no_action_weight_conversion"
)

PCA_MODES = ("static_pca", "temporal_pca", "sparse_temporal_pca")

BOUNDARY_COLUMNS = [
    "task2_8j_2_version",
    "task2_8j_2_contract",
    "validation_only",
    "runtime_policy_input",
    "fullspec_runtime_connected",
    "upper_pressure_connected",
    "action_frame_created",
    "actionmodule_called",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "effective_dimension_adopted",
    "dynamics_axis_extracted",
    "action_weight_converted",
    "hidden_truth_input",
]

REQUIRED_COMPONENT_COLUMNS = BOUNDARY_COLUMNS + [
    "mode",
    "component_index",
    "n_samples",
    "n_features",
    "active_feature_count",
    "explained_variance_ratio",
    "cumulative_explained_variance_ratio",
    "reconstruction_error_ratio",
    "component_l2_norm",
    "top_feature_keys",
    "top_feature_weights",
]

REQUIRED_MODEL_SUMMARY_COLUMNS = BOUNDARY_COLUMNS + [
    "mode",
    "n_samples",
    "n_features",
    "n_components",
    "matrix_rank",
    "effective_rank",
    "total_explained_variance_ratio",
    "reconstruction_error_ratio",
    "mean_abs_component_correlation",
    "sparse_top_k",
    "validation_status",
]

REQUIRED_STABILITY_COLUMNS = BOUNDARY_COLUMNS + [
    "mode",
    "window_label",
    "t_min",
    "t_max",
    "n_samples",
    "n_components_compared",
    "subspace_similarity",
    "principal_angle_proxy",
    "projection_drift",
    "stability_status",
]

REQUIRED_PREDICTION_COLUMNS = BOUNDARY_COLUMNS + [
    "mode",
    "target_feature_key",
    "prediction_horizon",
    "train_rows",
    "test_rows",
    "rmse",
    "baseline_rmse",
    "r2_vs_mean_baseline",
    "prediction_status",
]


@dataclass(frozen=True)
class TemporalPCAValidationConfig:
    n_components: int = 6
    sparse_top_k: int = 12
    prediction_horizon: int = 3
    min_prediction_rows: int = 8


@dataclass
class PCAModel:
    mode: str
    matrix: pd.DataFrame
    standardized: np.ndarray
    means: np.ndarray
    scales: np.ndarray
    components: np.ndarray
    scores: np.ndarray
    explained_variance_ratio: np.ndarray
    reconstruction_error_ratio: float
    active_counts: list[int]


def _boundary_payload() -> dict:
    return {
        "task2_8j_2_version": TASK2_8J_2_VERSION,
        "task2_8j_2_contract": TASK2_8J_2_CONTRACT,
        "validation_only": True,
        "runtime_policy_input": False,
        "fullspec_runtime_connected": False,
        "upper_pressure_connected": False,
        "action_frame_created": False,
        "actionmodule_called": False,
        "canonical_write_performed": False,
        "gk_writeback_performed": False,
        "ot_writeback_performed": False,
        "effective_dimension_adopted": False,
        "dynamics_axis_extracted": False,
        "action_weight_converted": False,
        "hidden_truth_input": False,
    }


def _finite_array(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)


def _feature_key(row: pd.Series) -> str:
    return "::".join(
        [
            str(row["source_trace"]),
            str(row["feature_group"]),
            str(row["feature_name"]),
            str(row["stat_name"]),
            f"w{int(row['window_size'])}",
        ]
    )


def build_pca_feature_matrix(feature_log: pd.DataFrame, *, include_temporal: bool) -> pd.DataFrame:
    """Pivot candidate feature log into a PCA-ready wide matrix."""
    if feature_log is None or feature_log.empty:
        return pd.DataFrame()
    log = feature_log.copy()
    log = log[log["allowed_for_gt"].astype(bool)]
    log = log[~log["hidden_truth_input"].astype(bool)]
    log = log[~log["source_trace"].astype(str).isin(FORBIDDEN_INPUT_TRACES)]
    if not include_temporal:
        log = log[log["window_size"].astype(int) == 1]
    log["feature_key"] = log.apply(_feature_key, axis=1)
    index_cols = ["seed", "scenario", "t"]
    mat = log.pivot_table(index=index_cols, columns="feature_key", values="feature_value", aggfunc="mean")
    mat = mat.sort_index(axis=0).sort_index(axis=1)
    if mat.empty:
        return mat
    mat = mat.apply(pd.to_numeric, errors="coerce")
    # Fill by column mean first, then zero for completely missing columns.
    mat = mat.fillna(mat.mean(axis=0)).fillna(0.0)
    zero_var = [c for c in mat.columns if float(mat[c].std(ddof=0)) <= 1e-12]
    if zero_var:
        mat = mat.drop(columns=zero_var)
    return mat


def _standardize_matrix(mat: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = _finite_array(mat.to_numpy(dtype=float))
    means = values.mean(axis=0)
    scales = values.std(axis=0, ddof=0)
    scales = np.where(scales <= 1e-12, 1.0, scales)
    return (values - means) / scales, means, scales


def _effective_rank(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    singular = np.linalg.svd(x, full_matrices=False, compute_uv=False)
    singular = singular[singular > 1e-12]
    if len(singular) == 0:
        return 0.0
    p = singular / singular.sum()
    entropy = -float(np.sum(p * np.log(p + 1e-12)))
    return float(np.exp(entropy))


def _fit_dense_pca(mat: pd.DataFrame, mode: str, n_components: int) -> PCAModel:
    x, means, scales = _standardize_matrix(mat)
    max_components = max(1, min(int(n_components), x.shape[0] - 1, x.shape[1]))
    _u, s, vt = np.linalg.svd(x, full_matrices=False)
    components = vt[:max_components]
    scores = x @ components.T
    eig = (s**2) / max(x.shape[0] - 1, 1)
    total = float(eig.sum()) if eig.size else 1.0
    explained = eig[:max_components] / max(total, 1e-12)
    recon = scores @ components
    mse = float(np.mean((x - recon) ** 2)) if x.size else 0.0
    total_mse = float(np.mean(x**2)) if x.size else 1.0
    return PCAModel(
        mode=mode,
        matrix=mat,
        standardized=x,
        means=means,
        scales=scales,
        components=components,
        scores=scores,
        explained_variance_ratio=np.asarray(explained, dtype=float),
        reconstruction_error_ratio=float(mse / max(total_mse, 1e-12)),
        active_counts=[int(x.shape[1])] * max_components,
    )


def _fit_sparse_from_temporal(dense_model: PCAModel, sparse_top_k: int) -> PCAModel:
    x = dense_model.standardized
    sparse_components = []
    active_counts: list[int] = []
    for comp in dense_model.components:
        k = max(1, min(int(sparse_top_k), len(comp)))
        idx = np.argsort(np.abs(comp))[-k:]
        sparse = np.zeros_like(comp)
        sparse[idx] = comp[idx]
        norm = float(np.linalg.norm(sparse))
        if norm <= 1e-12:
            sparse = comp.copy()
            norm = float(np.linalg.norm(sparse)) or 1.0
        sparse = sparse / norm
        sparse_components.append(sparse)
        active_counts.append(int(np.count_nonzero(np.abs(sparse) > 1e-12)))
    components = np.asarray(sparse_components, dtype=float)
    scores = x @ components.T
    score_var = np.var(scores, axis=0, ddof=0)
    total_var = float(np.var(x, axis=0, ddof=0).sum())
    explained = score_var / max(total_var, 1e-12)
    # Sparse components are not strictly orthogonal.  The reconstruction ratio is
    # therefore a validation proxy, not a formal PCA optimum.
    recon = scores @ components
    mse = float(np.mean((x - recon) ** 2)) if x.size else 0.0
    total_mse = float(np.mean(x**2)) if x.size else 1.0
    return PCAModel(
        mode="sparse_temporal_pca",
        matrix=dense_model.matrix,
        standardized=x,
        means=dense_model.means,
        scales=dense_model.scales,
        components=components,
        scores=scores,
        explained_variance_ratio=np.asarray(explained, dtype=float),
        reconstruction_error_ratio=float(mse / max(total_mse, 1e-12)),
        active_counts=active_counts,
    )


def fit_pca_validation_models(
    feature_log: pd.DataFrame,
    cfg: TemporalPCAValidationConfig | None = None,
) -> dict[str, PCAModel]:
    cfg = cfg or TemporalPCAValidationConfig()
    static_matrix = build_pca_feature_matrix(feature_log, include_temporal=False)
    temporal_matrix = build_pca_feature_matrix(feature_log, include_temporal=True)
    models: dict[str, PCAModel] = {}
    models["static_pca"] = _fit_dense_pca(static_matrix, "static_pca", cfg.n_components)
    temporal_dense = _fit_dense_pca(temporal_matrix, "temporal_pca", cfg.n_components)
    models["temporal_pca"] = temporal_dense
    models["sparse_temporal_pca"] = _fit_sparse_from_temporal(temporal_dense, cfg.sparse_top_k)
    return models


def _safe_corr_abs_mean(scores: np.ndarray) -> float:
    if scores.shape[1] <= 1:
        return 0.0
    corr = np.corrcoef(scores.T)
    corr = _finite_array(corr)
    mask = ~np.eye(corr.shape[0], dtype=bool)
    return float(np.mean(np.abs(corr[mask]))) if mask.any() else 0.0


def build_pca_component_table(models: dict[str, PCAModel]) -> pd.DataFrame:
    rows = []
    for mode, model in models.items():
        cumulative = 0.0
        features = np.asarray(model.matrix.columns.astype(str).tolist(), dtype=object)
        for i, comp in enumerate(model.components):
            ratio = float(model.explained_variance_ratio[i]) if i < len(model.explained_variance_ratio) else 0.0
            cumulative = min(1.0, cumulative + max(0.0, ratio))
            top_n = min(10, len(comp))
            top_idx = np.argsort(np.abs(comp))[-top_n:][::-1]
            row = {
                **_boundary_payload(),
                "mode": mode,
                "component_index": int(i + 1),
                "n_samples": int(model.matrix.shape[0]),
                "n_features": int(model.matrix.shape[1]),
                "active_feature_count": int(model.active_counts[i]) if i < len(model.active_counts) else int(np.count_nonzero(comp)),
                "explained_variance_ratio": ratio,
                "cumulative_explained_variance_ratio": cumulative,
                "reconstruction_error_ratio": float(model.reconstruction_error_ratio),
                "component_l2_norm": float(np.linalg.norm(comp)),
                "top_feature_keys": ";".join(str(features[j]) for j in top_idx),
                "top_feature_weights": ";".join(f"{float(comp[j]):.6g}" for j in top_idx),
            }
            rows.append(row)
    return pd.DataFrame(rows, columns=REQUIRED_COMPONENT_COLUMNS)


def build_model_summary_table(models: dict[str, PCAModel], cfg: TemporalPCAValidationConfig) -> pd.DataFrame:
    rows = []
    for mode, model in models.items():
        rows.append(
            {
                **_boundary_payload(),
                "mode": mode,
                "n_samples": int(model.matrix.shape[0]),
                "n_features": int(model.matrix.shape[1]),
                "n_components": int(model.components.shape[0]),
                "matrix_rank": int(np.linalg.matrix_rank(model.standardized)),
                "effective_rank": _effective_rank(model.standardized),
                "total_explained_variance_ratio": float(np.clip(np.sum(model.explained_variance_ratio), 0.0, 1.0)),
                "reconstruction_error_ratio": float(model.reconstruction_error_ratio),
                "mean_abs_component_correlation": _safe_corr_abs_mean(model.scores),
                "sparse_top_k": int(cfg.sparse_top_k) if mode == "sparse_temporal_pca" else 0,
                "validation_status": "pass" if model.matrix.shape[0] >= 4 and model.matrix.shape[1] >= 2 else "weak_sample",
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_MODEL_SUMMARY_COLUMNS)


def _compare_subspaces(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0:
        return 0.0
    k = min(a.shape[0], b.shape[0], a.shape[1], b.shape[1])
    if k <= 0:
        return 0.0
    qa, _ = np.linalg.qr(a[:k].T)
    qb, _ = np.linalg.qr(b[:k].T)
    singular = np.linalg.svd(qa.T @ qb, full_matrices=False, compute_uv=False)
    return float(np.clip(np.mean(np.clip(singular, 0.0, 1.0)), 0.0, 1.0))


def _project_with_model(model: PCAModel, mat: pd.DataFrame) -> np.ndarray:
    aligned = mat.reindex(columns=model.matrix.columns, fill_value=0.0)
    values = _finite_array(aligned.to_numpy(dtype=float))
    x = (values - model.means) / model.scales
    return x @ model.components.T


def build_stability_table(models: dict[str, PCAModel], cfg: TemporalPCAValidationConfig) -> pd.DataFrame:
    rows = []
    for mode, model in models.items():
        mat = model.matrix
        if mat.empty or "t" not in mat.index.names:
            continue
        t_values = sorted(set(int(idx[2]) for idx in mat.index.tolist()))
        if len(t_values) < 6:
            continue
        splits = np.array_split(np.asarray(t_values, dtype=int), 3)
        for i, split in enumerate(splits):
            if len(split) == 0:
                continue
            label = f"segment_{i + 1}"
            sub_index = [idx for idx in mat.index if int(idx[2]) in set(int(x) for x in split)]
            sub_mat = mat.loc[sub_index]
            if sub_mat.shape[0] <= cfg.n_components or sub_mat.shape[1] < 2:
                continue
            sub_model = _fit_dense_pca(sub_mat, mode + "_segment", cfg.n_components)
            if mode == "sparse_temporal_pca":
                sub_model = _fit_sparse_from_temporal(sub_model, cfg.sparse_top_k)
            similarity = _compare_subspaces(model.components, sub_model.components)
            full_scores = _project_with_model(model, sub_mat)
            local_scores = sub_model.scores
            k = min(full_scores.shape[1], local_scores.shape[1])
            drift = float(np.mean(np.abs(full_scores[:, :k] - local_scores[:, :k]))) if k > 0 else 0.0
            rows.append(
                {
                    **_boundary_payload(),
                    "mode": mode,
                    "window_label": label,
                    "t_min": int(min(split)),
                    "t_max": int(max(split)),
                    "n_samples": int(sub_mat.shape[0]),
                    "n_components_compared": int(k),
                    "subspace_similarity": similarity,
                    "principal_angle_proxy": float(1.0 - similarity),
                    "projection_drift": drift,
                    "stability_status": "pass" if similarity >= 0.45 else "watch",
                }
            )
    return pd.DataFrame(rows, columns=REQUIRED_STABILITY_COLUMNS)


def _target_keys(mat: pd.DataFrame) -> list[str]:
    preferred = [
        "entity_trace::public_state::exploration::mean::w1",
        "entity_trace::public_state::reversibility::mean::w1",
        "entity_trace::public_state::relation_lock::mean::w1",
        "entity_trace::public_state::uncertainty::mean::w1",
        "v2_resource_trace::resource_structure::commons_health::value::w1",
        "v2_resource_trace::resource_structure::resource_pressure::value::w1",
        "v2_information_trace::information_structure::information_quality_mean::value::w1",
        "v2_information_trace::information_structure::coordination_lag_mean::value::w1",
    ]
    return [k for k in preferred if k in set(mat.columns.astype(str))]


def _linear_regression_predict(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    x_train = np.column_stack([np.ones(train_x.shape[0]), train_x])
    x_test = np.column_stack([np.ones(test_x.shape[0]), test_x])
    beta, *_ = np.linalg.lstsq(x_train, train_y, rcond=None)
    return x_test @ beta


def build_prediction_table(models: dict[str, PCAModel], cfg: TemporalPCAValidationConfig) -> pd.DataFrame:
    rows = []
    for mode, model in models.items():
        mat = model.matrix
        keys = _target_keys(mat)
        if not keys:
            continue
        score_df = pd.DataFrame(model.scores, index=mat.index, columns=[f"component_{i+1}" for i in range(model.scores.shape[1])])
        for key in keys:
            y_series = mat[key].copy()
            aligned_rows = []
            for seed, scenario in sorted(set((idx[0], idx[1]) for idx in mat.index.tolist())):
                sub_idx = [idx for idx in mat.index if idx[0] == seed and idx[1] == scenario]
                sub_idx = sorted(sub_idx, key=lambda x: int(x[2]))
                for pos, idx in enumerate(sub_idx):
                    future_pos = pos + int(cfg.prediction_horizon)
                    if future_pos >= len(sub_idx):
                        continue
                    future_idx = sub_idx[future_pos]
                    aligned_rows.append((idx, float(y_series.loc[future_idx])))
            if len(aligned_rows) < cfg.min_prediction_rows:
                continue
            idxs = [x[0] for x in aligned_rows]
            y = np.asarray([x[1] for x in aligned_rows], dtype=float)
            x = score_df.loc[idxs].to_numpy(dtype=float)
            t_values = np.asarray([int(idx[2]) for idx in idxs], dtype=int)
            cutoff = float(np.quantile(t_values, 0.67))
            train_mask = t_values <= cutoff
            test_mask = ~train_mask
            if train_mask.sum() < 4 or test_mask.sum() < 3:
                train_mask = np.arange(len(y)) < max(4, int(len(y) * 0.7))
                test_mask = ~train_mask
            if train_mask.sum() < 4 or test_mask.sum() < 3:
                continue
            pred = _linear_regression_predict(x[train_mask], y[train_mask], x[test_mask])
            y_test = y[test_mask]
            rmse = float(np.sqrt(np.mean((pred - y_test) ** 2)))
            baseline = float(np.mean(y[train_mask]))
            baseline_rmse = float(np.sqrt(np.mean((baseline - y_test) ** 2)))
            r2 = float(1.0 - (rmse**2 / max(baseline_rmse**2, 1e-12)))
            rows.append(
                {
                    **_boundary_payload(),
                    "mode": mode,
                    "target_feature_key": key,
                    "prediction_horizon": int(cfg.prediction_horizon),
                    "train_rows": int(train_mask.sum()),
                    "test_rows": int(test_mask.sum()),
                    "rmse": rmse,
                    "baseline_rmse": baseline_rmse,
                    "r2_vs_mean_baseline": r2,
                    "prediction_status": "pass" if np.isfinite(r2) else "invalid",
                }
            )
    return pd.DataFrame(rows, columns=REQUIRED_PREDICTION_COLUMNS)


def validate_temporal_pca_validation_tables(
    component_table: pd.DataFrame,
    model_summary: pd.DataFrame,
    stability_table: pd.DataFrame,
    prediction_table: pd.DataFrame,
    feature_log_errors: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if feature_log_errors:
        errors.extend(f"task2_8j_2_feature_log_error:{e}" for e in feature_log_errors)
    tables = {
        "component": (component_table, REQUIRED_COMPONENT_COLUMNS),
        "model_summary": (model_summary, REQUIRED_MODEL_SUMMARY_COLUMNS),
        "stability": (stability_table, REQUIRED_STABILITY_COLUMNS),
        "prediction": (prediction_table, REQUIRED_PREDICTION_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_2_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_2_missing_columns:{name}:" + ",".join(missing))
            continue
        if not bool(table["validation_only"].astype(bool).all()):
            errors.append(f"task2_8j_2_validation_only_not_all_true:{name}")
        for col in [
            "runtime_policy_input",
            "fullspec_runtime_connected",
            "upper_pressure_connected",
            "action_frame_created",
            "actionmodule_called",
            "canonical_write_performed",
            "gk_writeback_performed",
            "ot_writeback_performed",
            "effective_dimension_adopted",
            "dynamics_axis_extracted",
            "action_weight_converted",
            "hidden_truth_input",
        ]:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_2_forbidden_true:{name}:{col}")
    if component_table is not None and not component_table.empty:
        modes = set(component_table["mode"].astype(str).unique())
        missing_modes = sorted(set(PCA_MODES) - modes)
        if missing_modes:
            errors.append("task2_8j_2_missing_modes:" + ",".join(missing_modes))
        if bool((component_table["explained_variance_ratio"].astype(float) < -1e-9).any()):
            errors.append("task2_8j_2_negative_explained_variance_ratio")
        sparse = component_table[component_table["mode"].astype(str) == "sparse_temporal_pca"]
        if sparse.empty or not bool((sparse["active_feature_count"].astype(int) < sparse["n_features"].astype(int)).all()):
            errors.append("task2_8j_2_sparse_mode_not_sparse")
    return errors


def summarize_temporal_pca_validation(
    component_table: pd.DataFrame,
    model_summary: pd.DataFrame,
    stability_table: pd.DataFrame,
    prediction_table: pd.DataFrame,
) -> dict:
    return {
        "component_rows": int(len(component_table)) if component_table is not None else 0,
        "model_summary_rows": int(len(model_summary)) if model_summary is not None else 0,
        "stability_rows": int(len(stability_table)) if stability_table is not None else 0,
        "prediction_rows": int(len(prediction_table)) if prediction_table is not None else 0,
        "modes": sorted(component_table["mode"].astype(str).unique().tolist()) if component_table is not None and not component_table.empty else [],
        "best_total_explained_mode": str(model_summary.sort_values("total_explained_variance_ratio", ascending=False)["mode"].iloc[0]) if model_summary is not None and not model_summary.empty else "none",
        "best_reconstruction_mode": str(model_summary.sort_values("reconstruction_error_ratio", ascending=True)["mode"].iloc[0]) if model_summary is not None and not model_summary.empty else "none",
        "mean_stability_similarity": float(stability_table["subspace_similarity"].astype(float).mean()) if stability_table is not None and not stability_table.empty else 0.0,
        "mean_prediction_r2": float(prediction_table["r2_vs_mean_baseline"].astype(float).mean()) if prediction_table is not None and not prediction_table.empty else 0.0,
    }


def build_and_validate_temporal_pca_validation(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    pca_cfg: TemporalPCAValidationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    feature_cfg = feature_cfg or CandidateFeatureLogConfig(steps=24, seeds=(501, 502, 503), window_sizes=(1, 6, 12))
    pca_cfg = pca_cfg or TemporalPCAValidationConfig()
    feature_log = build_candidate_feature_log(feature_cfg)
    feature_errors = validate_candidate_feature_log(feature_log)
    models = fit_pca_validation_models(feature_log, pca_cfg)
    component_table = build_pca_component_table(models)
    model_summary = build_model_summary_table(models, pca_cfg)
    stability_table = build_stability_table(models, pca_cfg)
    prediction_table = build_prediction_table(models, pca_cfg)
    errors = validate_temporal_pca_validation_tables(
        component_table,
        model_summary,
        stability_table,
        prediction_table,
        feature_errors,
    )
    summary = summarize_temporal_pca_validation(component_table, model_summary, stability_table, prediction_table)
    summary["validation_errors"] = errors
    return component_table, model_summary, stability_table, prediction_table, errors, summary
