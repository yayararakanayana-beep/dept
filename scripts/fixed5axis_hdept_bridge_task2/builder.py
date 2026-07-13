"""Task 2成果物の原子的生成とCLI。"""
from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from .canonical import _load_causal_input
from .contracts import (
    DEFAULT_BRIDGE_CONTRACT, DEFAULT_EVIDENCE_MAP, DEFAULT_FEATURE_REGISTRY,
    DEFAULT_FIXED5_CONTRACT, DEFAULT_SCHEMA, OUTPUT_FILES,
    Fixed5AxisHDEPTBridgeError, _sha256_file, _write_json,
    load_bridge_contract, load_calibration, load_evidence_map,
    load_feature_registry, load_fixed5_contract,
)
from .features import extract_feature_records
from .h11 import construct_h11

def _validate_bundle_shape(bundle: Mapping[str, Any], registry: Mapping[str, Any], evidence_map: Mapping[str, Any]) -> None:
    if bundle.get('contract_version') != 'fixed5axis_hdept_observation_bridge_rc1':
        raise Fixed5AxisHDEPTBridgeError('bundle contract mismatch')
    features = bundle.get('features')
    if not isinstance(features, list) or [item.get('feature_id') for item in features] != [entry['id'] for entry in registry['features']]:
        raise Fixed5AxisHDEPTBridgeError('bundle feature order mismatch')
    if list(bundle.get('h11', {})) != list(evidence_map['axis_order']):
        raise Fixed5AxisHDEPTBridgeError('bundle H11 axis order mismatch')
    for record in features:
        if record['available']:
            if record['value'] is None or record['reason_unavailable'] is not None:
                raise Fixed5AxisHDEPTBridgeError('available feature record mismatch')
        elif record['value'] is not None or record['confidence'] != 0.0 or (not record['reason_unavailable']):
            raise Fixed5AxisHDEPTBridgeError('unavailable feature record mismatch')
    for axis in bundle['h11'].values():
        if not axis['available'] and (not (axis['value'] is None and axis['transport_value'] == 0.5 and axis['transport_value_is_neutral_placeholder'] and (axis['confidence'] == 0.0))):
            raise Fixed5AxisHDEPTBridgeError('unavailable H11 axis transport mismatch')
    if bundle['global_observation_status'] == 'READY':
        raise Fixed5AxisHDEPTBridgeError('Task 2 must not emit global READY')


def _manifest(root: Path) -> dict[str, Any]:
    files = []
    for name in OUTPUT_FILES:
        path = root / name
        files.append({'path': name, 'sha256': _sha256_file(path), 'size_bytes': path.stat().st_size})
    return {'contract_version': 'fixed5axis_hdept_observation_bridge_rc1', 'builder_version': 'fixed5axis_hdept_observation_bridge_task2_rc1', 'hash_algorithm': 'sha256', 'files': files}


def build_observation(trajectory_dir: str | Path, current_t: int, output_dir: str | Path, *, calibration_path: str | Path | None=None, bridge_contract_path: str | Path=DEFAULT_BRIDGE_CONTRACT, feature_registry_path: str | Path=DEFAULT_FEATURE_REGISTRY, evidence_map_path: str | Path=DEFAULT_EVIDENCE_MAP, fixed5_contract_path: str | Path=DEFAULT_FIXED5_CONTRACT, schema_path: str | Path=DEFAULT_SCHEMA) -> Path:
    if isinstance(current_t, bool) or not isinstance(current_t, int) or current_t < 0:
        raise Fixed5AxisHDEPTBridgeError('current_t must be a non-negative integer')
    trajectory = Path(trajectory_dir)
    output = Path(output_dir)
    if output.exists():
        raise Fixed5AxisHDEPTBridgeError(f'append-only output already exists: {output}')
    bridge = load_bridge_contract(bridge_contract_path)
    registry = load_feature_registry(feature_registry_path)
    evidence_map = load_evidence_map(evidence_map_path)
    fixed5 = load_fixed5_contract(fixed5_contract_path)
    if not Path(schema_path).is_file():
        raise Fixed5AxisHDEPTBridgeError('bridge output schema is missing')
    registry_hash = _sha256_file(Path(feature_registry_path))
    evidence_hash = _sha256_file(Path(evidence_map_path))
    calibration = None if calibration_path is None else load_calibration(calibration_path, registry, registry_hash=registry_hash)
    causal = _load_causal_input(trajectory, current_t, fixed5, bridge)
    records = extract_feature_records(causal['frames'], causal['ledger'], registry)
    h11, global_status = construct_h11(records, registry, evidence_map, calibration, causal['history_frame_count'])
    input_identity = {'fixed5_contract_version': fixed5['contract_version'], 'gt_hash': causal['current_gt_hash'], 'history_chain_hash': causal['history_chain_hash'], 'history_start_t': causal['history_start_t'], 'history_end_t': causal['history_end_t'], 'history_frame_count': causal['history_frame_count'], 'feature_registry_hash': registry_hash, 'evidence_map_hash': evidence_hash, 'calibration_version': None if calibration is None else calibration['calibration_version']}
    audit = {'future_suffix_read': False, 'truth_used': False, 'external_log_used_as_numeric_evidence': False, 'ot_used': False, 'pressure_used_as_input': False, 'source_writeback_performed': False, 'neutral_placeholder_used_as_evidence': False, 'contract_status': 'pass', 'feature_count': len(records), 'available_feature_count': sum((bool(item['available']) for item in records)), 'proxy_feature_count': sum((item['derivation_status'] == 'adapted_fixed_grid_proxy' for item in records)), 'reserved_feature_count': sum((item['derivation_status'].startswith('reserved_') for item in records)), 'available_h11_axis_count': sum((bool(item['available']) for item in h11.values())), 'global_ready_emitted': False, 'full_source_manifest_hash_verification_skipped_to_preserve_prefix_causality': True}
    provenance = {'builder_version': 'fixed5axis_hdept_observation_bridge_task2_rc1', 'bridge_contract_hash': _sha256_file(Path(bridge_contract_path)), 'feature_registry_hash': registry_hash, 'evidence_map_hash': evidence_hash, 'schema_hash': _sha256_file(Path(schema_path)), 'calibration_file_hash': None if calibration is None else calibration['calibration_file_hash'], 'formal_source_files_read': ['gt_mass.npy prefix frames', 'history_ledger.csv through current_t', 'provenance.json', 'manifest.json'], 'source_manifest_declared_file_count': causal['manifest_declared_file_count'], 'history_selector': bridge['formal_input']['history_selector'], 'scientific_claim': 'B_limited_task2_builder_implementation_without_calibration_or_scientific_validation'}
    bundle = {'contract_version': bridge['contract_version'], 'trajectory_id': causal['trajectory_id'], 'current_t': current_t, 'input_identity': input_identity, 'features': records, 'h11': h11, 'global_observation_status': global_status, 'audit': audit}
    _validate_bundle_shape(bundle, registry, evidence_map)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f'.{output.name}.', dir=output.parent))
    try:
        _write_json(temporary / 'identity.json', {'contract_version': bridge['contract_version'], 'trajectory_id': causal['trajectory_id'], 'current_t': current_t, 'input_identity': input_identity})
        _write_json(temporary / 'features.json', {'contract_version': bridge['contract_version'], 'features': records})
        _write_json(temporary / 'm_observation.json', {'contract_version': bridge['contract_version'], 'h11': h11, 'global_observation_status': global_status})
        _write_json(temporary / 'audit.json', audit)
        _write_json(temporary / 'provenance.json', provenance)
        _write_json(temporary / 'manifest.json', _manifest(temporary))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trajectory-dir', required=True)
    parser.add_argument('--current-t', type=int, required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--calibration')
    parser.add_argument('--bridge-contract', default=str(DEFAULT_BRIDGE_CONTRACT))
    parser.add_argument('--feature-registry', default=str(DEFAULT_FEATURE_REGISTRY))
    parser.add_argument('--evidence-map', default=str(DEFAULT_EVIDENCE_MAP))
    parser.add_argument('--fixed5-contract', default=str(DEFAULT_FIXED5_CONTRACT))
    parser.add_argument('--schema', default=str(DEFAULT_SCHEMA))
    return parser


def main(argv: Sequence[str] | None=None) -> int:
    args = _parser().parse_args(argv)
    output = build_observation(args.trajectory_dir, args.current_t, args.output_dir, calibration_path=args.calibration, bridge_contract_path=args.bridge_contract, feature_registry_path=args.feature_registry, evidence_map_path=args.evidence_map, fixed5_contract_path=args.fixed5_contract, schema_path=args.schema)
    print(output)
    return 0
