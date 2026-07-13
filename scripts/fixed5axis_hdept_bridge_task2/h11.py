"""凍結校正による H11_STRUCTURED 観測生成。"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .contracts import _sigmoid

def _calibrated_features(records: Sequence[Mapping[str, Any]], registry: Mapping[str, Any], calibration: Mapping[str, Any] | None) -> dict[str, float]:
    if calibration is None:
        return {}
    result: dict[str, float] = {}
    for index, (entry, record) in enumerate(zip(registry['features'], records, strict=True)):
        if not bool(entry.get('score', True)) or float(entry['cap']) <= 0.0 or (not record['available']):
            continue
        center, scale = (float(calibration['center'][index]), float(calibration['scale'][index]))
        value = (float(record['value']) - center) / scale
        value = float(np.clip(value, float(calibration['clip_lower'][index]), float(calibration['clip_upper'][index])))
        result[entry['id']] = value
    return result


def _component_score(component_id: str, evidence_map: Mapping[str, Any], calibrated: Mapping[str, float]) -> tuple[float | None, dict[str, float]]:
    definition = evidence_map['base_components'][component_id]
    positive = list(definition['positive'])
    negative = list(definition['negative'])
    present_positive = [feature for feature in positive if feature in calibrated]
    present_negative = [feature for feature in negative if feature in calibrated]
    if positive and (not present_positive):
        return (None, {})
    if negative and (not present_negative):
        return (None, {})
    score = 0.0
    weights: dict[str, float] = {}
    if present_positive:
        score += float(np.mean([calibrated[feature] for feature in present_positive]))
        for feature in present_positive:
            weights[feature] = weights.get(feature, 0.0) + 1.0 / len(present_positive)
    if present_negative:
        score -= float(np.mean([calibrated[feature] for feature in present_negative]))
        for feature in present_negative:
            weights[feature] = weights.get(feature, 0.0) + 1.0 / len(present_negative)
    return (score, weights)


def construct_h11(records: Sequence[Mapping[str, Any]], registry: Mapping[str, Any], evidence_map: Mapping[str, Any], calibration: Mapping[str, Any] | None, history_frame_count: int) -> tuple[dict[str, Any], str]:
    calibrated = _calibrated_features(records, registry, calibration)
    record_by_id = {record['feature_id']: record for record in records}
    registry_order = {entry['id']: index for index, entry in enumerate(registry['features'])}
    axes: dict[str, Any] = {}
    available_axis_count = 0
    for axis_id in evidence_map['axis_order']:
        axis = evidence_map['h11_axes'][axis_id]
        construction = axis['construction']
        component_weights = {construction['component']: 1.0} if construction['type'] == 'base_component' else {str(key): float(value) for key, value in construction['components'].items()}
        raw = 0.0
        all_components = True
        feature_weights: dict[str, float] = {}
        referenced: set[str] = set()
        for component_id, component_weight in component_weights.items():
            definition = evidence_map['base_components'][component_id]
            referenced.update(definition['positive'])
            referenced.update(definition['negative'])
            component_score, weights = _component_score(component_id, evidence_map, calibrated)
            if component_score is None:
                all_components = False
                continue
            raw += component_weight * component_score
            for feature_id, weight in weights.items():
                feature_weights[feature_id] = feature_weights.get(feature_id, 0.0) + abs(component_weight) * abs(weight)
        ordered_refs = sorted(referenced, key=registry_order.__getitem__)
        available_refs = [feature for feature in ordered_refs if feature in calibrated]
        coverage = len(available_refs) / len(ordered_refs) if ordered_refs else 1.0
        minimum_history = int(axis['minimum_history_frames'])
        available = bool(calibration is not None and history_frame_count >= minimum_history and all_components and (coverage >= float(axis['limited_coverage_min'])))
        if available:
            value = _sigmoid(float(evidence_map['scoring'].get('gamma', 1.0)) * raw)
            denominator = sum((feature_weights.get(feature, 0.0) for feature in available_refs))
            if denominator > 0.0:
                weighted_confidence = sum((feature_weights.get(feature, 0.0) * float(record_by_id[feature]['confidence']) for feature in available_refs)) / denominator
            else:
                weighted_confidence = 0.0
            confidence = float(np.clip(coverage * weighted_confidence, 0.0, 1.0))
            status = 'LIMITED'
            available_axis_count += 1
            transport = value
            placeholder = False
        else:
            value = None
            confidence = 0.0
            status = 'UNAVAILABLE'
            transport = 0.5
            placeholder = True
        axes[axis_id] = {'value': value, 'transport_value': transport, 'transport_value_is_neutral_placeholder': placeholder, 'available': available, 'confidence': confidence, 'evidence_coverage': float(coverage), 'status': status, 'evidence_feature_ids': ordered_refs, 'claim_limit': axis['claim'], 'watchpoints': list(axis['watchpoints'])}
    if history_frame_count < 2:
        global_status = 'INSUFFICIENT_HISTORY'
    elif calibration is None or available_axis_count == 0:
        global_status = 'HOLD_RECOMMENDED'
    else:
        global_status = 'LIMITED'
    return (axes, global_status)
