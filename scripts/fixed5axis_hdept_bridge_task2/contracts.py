"""Task 2 共通契約、固定値、JSON、校正読込み。"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BRIDGE_CONTRACT = ROOT / "configs" / "fixed5axis_hdept_observation_bridge_rc1_contract.json"
DEFAULT_FEATURE_REGISTRY = ROOT / "configs" / "fixed5axis_hdept_feature_registry_rc1.json"
DEFAULT_EVIDENCE_MAP = ROOT / "configs" / "fixed5axis_hdept_h11_evidence_map_rc1.json"
DEFAULT_FIXED5_CONTRACT = ROOT / "configs" / "fixed5axis_gk_rc1_contract.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "fixed5axis_hdept_observation_bridge_rc1.schema.json"

AXIS_NAMES = ("resource_slack", "information_quality", "pressure", "exploration_room", "reversibility")
AXIS_BINS = (0.0, 0.25, 0.5, 0.75, 1.0)
GT_SHAPE = (5, 5, 5, 5, 5)
CELL_COUNT = 3125
OUTPUT_FILES = ("identity.json", "features.json", "m_observation.json", "audit.json", "provenance.json")

class Fixed5AxisHDEPTBridgeError(ValueError):
    """固定5軸上位観測翻訳層 Task 2 の契約違反。"""


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + '\n').encode('utf-8')


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _bool_text(value: Any) -> bool:
    return str(value).strip().lower() == 'true'


def _finite_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise Fixed5AxisHDEPTBridgeError(f'{name} must be a finite number')
    result = float(value)
    if not math.isfinite(result):
        raise Fixed5AxisHDEPTBridgeError(f'{name} must be a finite number')
    return result


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        exp = math.exp(-value)
        return 1.0 / (1.0 + exp)
    exp = math.exp(value)
    return exp / (1.0 + exp)


def load_bridge_contract(path: str | Path=DEFAULT_BRIDGE_CONTRACT) -> dict[str, Any]:
    value = _json_load(Path(path))
    if value.get('contract_version') != 'fixed5axis_hdept_observation_bridge_rc1':
        raise Fixed5AxisHDEPTBridgeError('unsupported bridge contract_version')
    if value.get('status') != 'frozen_for_builder_implementation':
        raise Fixed5AxisHDEPTBridgeError('bridge contract is not frozen for builder implementation')
    return value


def load_feature_registry(path: str | Path=DEFAULT_FEATURE_REGISTRY) -> dict[str, Any]:
    value = _json_load(Path(path))
    if value.get('registry_id') != 'fixed5axis_hdept_feature_registry_rc1':
        raise Fixed5AxisHDEPTBridgeError('unsupported feature registry')
    features = value.get('features')
    if not isinstance(features, list) or len(features) != 47:
        raise Fixed5AxisHDEPTBridgeError('feature registry must contain exactly 47 features')
    ids = [str(item.get('id', '')) for item in features]
    if len(set(ids)) != 47 or any((not item for item in ids)):
        raise Fixed5AxisHDEPTBridgeError('feature registry IDs must be non-empty and unique')
    return value


def load_evidence_map(path: str | Path=DEFAULT_EVIDENCE_MAP) -> dict[str, Any]:
    value = _json_load(Path(path))
    if value.get('map_id') != 'fixed5axis_hdept_h11_evidence_map_rc1':
        raise Fixed5AxisHDEPTBridgeError('unsupported H11 evidence map')
    axes = value.get('axis_order')
    if not isinstance(axes, list) or len(axes) != 11 or set(axes) != set(value.get('h11_axes', {})):
        raise Fixed5AxisHDEPTBridgeError('H11 evidence map must define the ordered 11 axes')
    return value


def load_fixed5_contract(path: str | Path=DEFAULT_FIXED5_CONTRACT) -> dict[str, Any]:
    value = _json_load(Path(path))
    if value.get('contract_version') != 'fixed5axis_gk_rc1':
        raise Fixed5AxisHDEPTBridgeError('unsupported fixed5 G/K contract')
    axes = value.get('axes', {})
    if tuple(axes.get('order', ())) != AXIS_NAMES:
        raise Fixed5AxisHDEPTBridgeError('fixed5 axis order mismatch')
    if tuple((float(item) for item in axes.get('bins', ()))) != AXIS_BINS:
        raise Fixed5AxisHDEPTBridgeError('fixed5 axis bins mismatch')
    if tuple((int(item) for item in axes.get('shape', ()))) != GT_SHAPE:
        raise Fixed5AxisHDEPTBridgeError('fixed5 G_t shape mismatch')
    return value


def load_calibration(path: str | Path, registry: Mapping[str, Any], *, registry_hash: str) -> dict[str, Any]:
    calibration_path = Path(path)
    value = _json_load(calibration_path)
    required = {'calibration_version', 'feature_registry_hash', 'feature_order', 'center', 'scale', 'clip_lower', 'clip_upper', 'fit_dataset_ids', 'fit_trajectory_ids_hash', 'fit_time_boundary', 'normalization_method', 'creation_code_hash'}
    missing = sorted(required - set(value))
    if missing:
        raise Fixed5AxisHDEPTBridgeError(f'calibration missing fields: {missing}')
    ids = [entry['id'] for entry in registry['features']]
    if value['feature_registry_hash'] != registry_hash or value['feature_order'] != ids:
        raise Fixed5AxisHDEPTBridgeError('calibration feature registry identity mismatch')
    if value['normalization_method'] not in {'zscore', 'robust_zscore'}:
        raise Fixed5AxisHDEPTBridgeError('unsupported calibration normalization_method')
    for key in ('center', 'scale', 'clip_lower', 'clip_upper'):
        if not isinstance(value[key], list) or len(value[key]) != len(ids):
            raise Fixed5AxisHDEPTBridgeError(f'calibration {key} length mismatch')
    for index, entry in enumerate(registry['features']):
        scoring = bool(entry.get('score', True)) and float(entry['cap']) > 0.0
        if scoring:
            center = _finite_float(value['center'][index], f'center[{index}]')
            scale = _finite_float(value['scale'][index], f'scale[{index}]')
            lower = _finite_float(value['clip_lower'][index], f'clip_lower[{index}]')
            upper = _finite_float(value['clip_upper'][index], f'clip_upper[{index}]')
            if scale <= 0.0 or upper < lower:
                raise Fixed5AxisHDEPTBridgeError('invalid scoring calibration scale or clip bounds')
            value['center'][index], value['scale'][index] = (center, scale)
            value['clip_lower'][index], value['clip_upper'][index] = (lower, upper)
    value['calibration_file_hash'] = _sha256_file(calibration_path)
    return value
