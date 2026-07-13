"""47特徴の生成と利用可能性記録。"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

from .contracts import Fixed5AxisHDEPTBridgeError
from .geometry import (
    _component_masses, _entropy, _frame_state, _grid, _js_distance,
    _w1_axis_marginals,
)

def _unavailable(entry: Mapping[str, Any], reason: str, support_count: int) -> dict[str, Any]:
    return {'feature_id': entry['id'], 'group': entry['g'], 'value': None, 'available': False, 'confidence': 0.0, 'support_count': int(max(support_count, 0)), 'minimum_history_frames': int(entry['n']), 'derivation_status': entry['s'], 'evidence_source': entry['src'], 'reason_unavailable': reason}


def _available(entry: Mapping[str, Any], value: float, support_count: int) -> dict[str, Any]:
    return {'feature_id': entry['id'], 'group': entry['g'], 'value': float(value), 'available': True, 'confidence': float(entry['cap']), 'support_count': int(support_count), 'minimum_history_frames': int(entry['n']), 'derivation_status': entry['s'], 'evidence_source': entry['src'], 'reason_unavailable': None}


def extract_feature_records(frames: np.ndarray, ledger: Sequence[Mapping[str, str]], registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    if len(frames) != len(ledger) or len(frames) < 1:
        raise Fixed5AxisHDEPTBridgeError('feature extraction requires aligned non-empty causal history')
    recent_count = min(len(frames), max(5, int(registry['builder_parameters']['oscillation_window'])))
    recent_frames = frames[-recent_count:]
    recent_ledger = ledger[-recent_count:]
    states = [_frame_state(frame, registry, expensive=index == len(recent_frames) - 1) for index, frame in enumerate(recent_frames)]
    current = states[-1]
    params = registry['builder_parameters']
    axis_floor = float(params['axis_variance_floor'])
    trace = float(np.trace(current['covariance']))
    eigenvalues = current['eigenvalues']
    variances = np.diag(current['covariance']).copy()
    registry_entries = {entry['id']: entry for entry in registry['features']}
    values: dict[str, float] = {}
    reasons: dict[str, str] = {}
    values['raw_dimension'] = 5.0
    values['active_axis_count'] = float(np.count_nonzero(variances > axis_floor))
    if float(np.sum(variances)) > axis_floor:
        axis_weights = variances / float(np.sum(variances))
        values['axis_weight_entropy'] = _entropy(axis_weights) / math.log(5.0)
        l1 = float(np.sum(np.abs(variances)))
        l2 = float(np.linalg.norm(variances))
        values['axis_weight_sparsity'] = float((math.sqrt(5.0) - l1 / max(l2, 1e-30)) / (math.sqrt(5.0) - 1.0))
    else:
        reasons['axis_weight_entropy'] = 'zero_total_axis_variance'
        reasons['axis_weight_sparsity'] = 'zero_axis_variance_vector'
    correlations: list[float] = []
    for left in range(5):
        for right in range(left + 1, 5):
            if variances[left] > axis_floor and variances[right] > axis_floor:
                correlations.append(float(current['covariance'][left, right] / math.sqrt(variances[left] * variances[right])))
    if correlations:
        values['axis_redundancy'] = float(np.mean(np.abs(correlations)))
        values['mean_axis_correlation'] = float(np.mean(correlations))
    else:
        reasons['axis_redundancy'] = 'fewer_than_two_active_axes'
        reasons['mean_axis_correlation'] = 'fewer_than_two_active_axes'
    if trace > axis_floor:
        spectrum = eigenvalues / trace
        values['effective_rank'] = math.exp(_entropy(spectrum))
        values['participation_ratio'] = trace * trace / float(np.sum(eigenvalues * eigenvalues))
        values['spectral_entropy'] = _entropy(spectrum) / math.log(5.0)
        values['dominant_eigen_share'] = float(eigenvalues[0] / trace)
        values['spectral_gap'] = float((eigenvalues[0] - eigenvalues[1]) / trace)
        values['anisotropy'] = float(1.0 - eigenvalues[-1] / eigenvalues[0]) if eigenvalues[0] > axis_floor else 0.0
    else:
        for key in ('effective_rank', 'participation_ratio', 'spectral_entropy', 'dominant_eigen_share', 'spectral_gap', 'anisotropy'):
            reasons[key] = 'zero_total_covariance'
    values['covariance_trace'] = trace
    epsilon = float(params['covariance_regularization_epsilon'])
    sign, logdet = np.linalg.slogdet(current['covariance'] + epsilon * np.eye(5))
    if sign > 0:
        values['covariance_logdet'] = float(logdet)
    else:
        reasons['covariance_logdet'] = 'regularized_covariance_not_positive_definite'
    values['compactness'] = float(np.clip(1.0 - trace / 1.25, 0.0, 1.0))
    values['mean_pairwise_distance'] = float(current['mean_pairwise_distance'])
    values['pairwise_distance_variance'] = float(current['pairwise_distance_variance'])
    values['entropy'] = float(current['entropy'])
    flat = recent_frames[-1].reshape(-1)
    peak = float(np.max(flat))
    active_threshold = max(float(params['active_cell_absolute_floor']), peak * float(params['active_cell_relative_to_peak_floor']))
    active = flat >= active_threshold
    active_density = current['density'][active]
    if active_density.size:
        density_mean = float(np.mean(active_density))
        density_peak = float(np.max(active_density))
        values['knn_density_variance'] = float(np.var(active_density) / max(density_mean * density_mean, 1e-30))
        values['density_peak_ratio'] = density_peak / max(density_mean, 1e-30)
        values['outlier_ratio'] = float(np.mean(active_density < float(params['outlier_density_fraction_of_peak']) * density_peak))
    else:
        for key in ('knn_density_variance', 'density_peak_ratio', 'outlier_ratio'):
            reasons[key] = 'no_active_cells'
    grid_indices = _grid()['indices']
    boundary = np.any((grid_indices == 0) | (grid_indices == 4), axis=1)
    values['tail_mass'] = float(np.sum(flat[boundary], dtype=np.float64))
    major_masses = list(current['major_masses'])
    values['mode_count'] = float(len(major_masses))
    if len(major_masses) == 1:
        values['cluster_balance'] = 1.0
    elif len(major_masses) > 1:
        normalized = np.asarray(major_masses, dtype=np.float64)
        normalized /= float(np.sum(normalized))
        values['cluster_balance'] = _entropy(normalized) / math.log(len(major_masses))
    else:
        reasons['cluster_balance'] = 'no_major_components'
    times = [int(row['t']) for row in recent_ledger]
    velocities: list[np.ndarray] = []
    step_lengths: list[float] = []
    if len(states) >= 2:
        dt = times[-1] - times[-2]
        if dt <= 0:
            raise Fixed5AxisHDEPTBridgeError('non-positive delta_t in selected causal history')
        centroid_delta = states[-1]['centroid'] - states[-2]['centroid']
        values['mean_drift_norm'] = float(np.linalg.norm(centroid_delta) / dt)
        values['covariance_drift_norm'] = float(np.linalg.norm(states[-1]['covariance'] - states[-2]['covariance'], ord='fro') / dt)
        values['wasserstein_velocity'] = _w1_axis_marginals(states[-2]['marginals'], states[-1]['marginals']) / dt
        values['jsd_velocity'] = _js_distance(recent_frames[-2], recent_frames[-1]) / dt
        values['entropy_velocity'] = abs(states[-1]['entropy'] - states[-2]['entropy']) / dt
        values['density_velocity'] = float(np.linalg.norm(states[-1]['density'] - states[-2]['density']) / dt)
        if trace > axis_floor:
            prev_trace = float(np.sum(states[-2]['eigenvalues']))
            if prev_trace > axis_floor:
                prev_effective = math.exp(_entropy(states[-2]['eigenvalues'] / prev_trace))
                values['effective_rank_velocity'] = abs(values['effective_rank'] - prev_effective) / dt
            else:
                reasons['effective_rank_velocity'] = 'previous_zero_total_covariance'
        else:
            reasons['effective_rank_velocity'] = 'current_zero_total_covariance'
        for index in range(1, len(states)):
            delta = times[index] - times[index - 1]
            velocity = (states[index]['centroid'] - states[index - 1]['centroid']) / delta
            velocities.append(velocity)
            step_lengths.append(float(np.linalg.norm(states[index]['centroid'] - states[index - 1]['centroid'])))
        prev_values = states[-2]['eigenvalues']
        curr_values = states[-1]['eigenvalues']
        prev_total, curr_total = (float(np.sum(prev_values)), float(np.sum(curr_values)))
        if prev_total > axis_floor and curr_total > axis_floor:
            threshold = float(params['principal_subspace_explained_variance_floor'])
            prev_k = int(np.searchsorted(np.cumsum(prev_values) / prev_total, threshold) + 1)
            curr_k = int(np.searchsorted(np.cumsum(curr_values) / curr_total, threshold) + 1)
            tolerance = float(params['eigenvalue_degeneracy_tolerance'])

            def degenerate(vals: np.ndarray, k: int, total: float) -> bool:
                return k < len(vals) and abs(float(vals[k - 1] - vals[k])) <= tolerance * max(total, 1.0)
            if not degenerate(prev_values, prev_k, prev_total) and (not degenerate(curr_values, curr_k, curr_total)):
                left = states[-2]['eigenvectors'][:, :prev_k]
                right = states[-1]['eigenvectors'][:, :curr_k]
                singular = np.linalg.svd(left.T @ right, compute_uv=False)
                singular = np.clip(singular, -1.0, 1.0)
                values['principal_subspace_angle'] = float(np.max(np.arccos(singular)) / (0.5 * math.pi))
            else:
                reasons['principal_subspace_angle'] = 'eigenvalue_degeneracy_at_subspace_cutoff'
        else:
            reasons['principal_subspace_angle'] = 'zero_covariance_subspace'
    else:
        for key in ('mean_drift_norm', 'covariance_drift_norm', 'wasserstein_velocity', 'jsd_velocity', 'entropy_velocity', 'density_velocity', 'effective_rank_velocity', 'principal_subspace_angle'):
            reasons[key] = 'requires_at_least_two_contiguous_frames'
    velocity_floor = float(params['velocity_norm_floor'])
    if len(velocities) >= 2:
        previous_velocity, current_velocity = (velocities[-2], velocities[-1])
        previous_norm, current_norm = (float(np.linalg.norm(previous_velocity)), float(np.linalg.norm(current_velocity)))
        if previous_norm > velocity_floor and current_norm > velocity_floor:
            cosine = float(np.clip(np.dot(previous_velocity, current_velocity) / (previous_norm * current_norm), -1.0, 1.0))
            angle = math.acos(cosine) / math.pi
            values['direction_cosine'] = cosine
            values['motion_angle'] = angle
            current_dt = times[-1] - times[-2]
            values['acceleration_norm'] = float(np.linalg.norm(current_velocity - previous_velocity) / current_dt)
            mean_length = 0.5 * (step_lengths[-1] + step_lengths[-2])
            values['trajectory_curvature'] = angle / max(mean_length, float(params['curvature_length_floor']))
        else:
            for key in ('direction_cosine', 'motion_angle', 'acceleration_norm', 'trajectory_curvature'):
                reasons[key] = 'consecutive_centroid_velocity_below_floor'
    else:
        for key in ('direction_cosine', 'motion_angle', 'acceleration_norm', 'trajectory_curvature'):
            reasons[key] = 'requires_at_least_three_contiguous_frames'
    if len(recent_frames) >= int(params['oscillation_window']) and len(velocities) >= 2:
        comparisons = 0
        reversals = 0
        for previous_velocity, current_velocity in zip(velocities, velocities[1:]):
            for axis in range(5):
                if abs(float(previous_velocity[axis])) <= velocity_floor or abs(float(current_velocity[axis])) <= velocity_floor:
                    continue
                comparisons += 1
                reversals += int(previous_velocity[axis] * current_velocity[axis] < 0.0)
        if comparisons:
            values['oscillation_index'] = reversals / comparisons
        else:
            reasons['oscillation_index'] = 'no_eligible_axis_velocity_comparisons'
    else:
        reasons['oscillation_index'] = 'requires_full_causal_oscillation_window'
    records: list[dict[str, Any]] = []
    for entry in registry['features']:
        feature_id = entry['id']
        if entry['s'] in {'reserved_prediction_subcontract', 'reserved_recovery_subcontract'}:
            records.append(_unavailable(entry, f"{entry['s']}_not_implemented_in_task2", len(frames)))
        elif feature_id in values:
            value = float(values[feature_id])
            if not math.isfinite(value):
                records.append(_unavailable(entry, 'derived_non_finite_value', len(frames)))
            else:
                records.append(_available(entry, value, min(len(frames), max(int(entry['n']), 1))))
        else:
            records.append(_unavailable(entry, reasons.get(feature_id, 'required_evidence_unavailable'), len(frames)))
    return records
