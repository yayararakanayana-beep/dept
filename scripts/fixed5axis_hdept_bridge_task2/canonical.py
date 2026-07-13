"""固定5軸正本の因果的接頭部読込み。"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .contracts import (
    AXIS_BINS, AXIS_NAMES, GT_SHAPE, Fixed5AxisHDEPTBridgeError,
    _bool_text, _canonical_json, _json_load,
)

GT_DTYPE = np.dtype("<f8")
GENESIS_HASH = hashlib.sha256(b"fixed5axis_gk_rc1_history_genesis").hexdigest()

def _compute_gt_hash(*, contract_version: str, trajectory_id: str, t: int, distribution: np.ndarray, source_state_hash: str) -> str:
    digest = hashlib.sha256()
    for value in (contract_version, trajectory_id, str(int(t))):
        digest.update(value.encode('utf-8'))
        digest.update(b'\x00')
    digest.update(_canonical_json({'axes': AXIS_NAMES, 'bins': AXIS_BINS}))
    digest.update(b'\x00')
    digest.update(np.ascontiguousarray(distribution, dtype=GT_DTYPE).tobytes(order='C'))
    digest.update(b'\x00')
    digest.update(source_state_hash.encode('ascii'))
    return digest.hexdigest()


def _compute_history_chain_hash(previous: str, gt_hash: str, t: int) -> str:
    return hashlib.sha256(f'{previous}\x00{gt_hash}\x00{int(t)}'.encode('ascii')).hexdigest()


def _read_ledger_prefix(path: Path, current_t: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    found = False
    with path.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            t = int(row['t'])
            rows.append(dict(row))
            if t == current_t:
                found = True
                break
            if t > current_t:
                break
    if not found:
        raise Fixed5AxisHDEPTBridgeError(f'current_t={current_t} is not present in causal ledger prefix')
    return rows


def _validate_distribution(distribution: np.ndarray, fixed5: Mapping[str, Any]) -> np.ndarray:
    array = np.ascontiguousarray(np.asarray(distribution), dtype=GT_DTYPE)
    if array.shape != GT_SHAPE:
        raise Fixed5AxisHDEPTBridgeError(f'G_t shape {array.shape} != {GT_SHAPE}')
    if not np.all(np.isfinite(array)):
        raise Fixed5AxisHDEPTBridgeError('G_t contains non-finite values')
    if float(np.min(array)) < -float(fixed5['gt']['negative_tolerance']):
        raise Fixed5AxisHDEPTBridgeError('G_t contains negative mass')
    total = float(np.sum(array, dtype=np.float64))
    if abs(total - 1.0) > float(fixed5['gt']['mass_tolerance']):
        raise Fixed5AxisHDEPTBridgeError('G_t mass does not sum to one')
    return array


def _load_causal_input(trajectory_dir: Path, current_t: int, fixed5: Mapping[str, Any], bridge: Mapping[str, Any]) -> dict[str, Any]:
    storage = fixed5['storage']
    required = [storage['gt_file'], storage['history_ledger_file'], storage['provenance_file'], storage['manifest_file']]
    for name in required:
        if not (trajectory_dir / name).is_file():
            raise Fixed5AxisHDEPTBridgeError(f'missing canonical artifact file: {name}')
    for forbidden in ('truth.jsonl', 'summary.json', 'metrics.jsonl'):
        if (trajectory_dir / forbidden).exists():
            raise Fixed5AxisHDEPTBridgeError(f'forbidden canonical file present: {forbidden}')
    provenance = _json_load(trajectory_dir / storage['provenance_file'])
    manifest = _json_load(trajectory_dir / storage['manifest_file'])
    if provenance.get('contract_version') != fixed5['contract_version']:
        raise Fixed5AxisHDEPTBridgeError('fixed5 provenance contract mismatch')
    if tuple(provenance.get('axis_order', ())) != AXIS_NAMES:
        raise Fixed5AxisHDEPTBridgeError('fixed5 provenance axis order mismatch')
    if tuple((float(item) for item in provenance.get('axis_bins', ()))) != AXIS_BINS:
        raise Fixed5AxisHDEPTBridgeError('fixed5 provenance bins mismatch')
    if provenance.get('gt_phase') != fixed5['gt']['phase']:
        raise Fixed5AxisHDEPTBridgeError('fixed5 provenance phase mismatch')
    if provenance.get('forbidden_source_files_read'):
        raise Fixed5AxisHDEPTBridgeError('fixed5 provenance reports forbidden source reads')
    trajectory_id = str(provenance.get('trajectory_id', ''))
    if not trajectory_id:
        raise Fixed5AxisHDEPTBridgeError('fixed5 trajectory identity missing')
    if manifest.get('contract_version') != fixed5['contract_version']:
        raise Fixed5AxisHDEPTBridgeError('fixed5 manifest contract mismatch')
    prefix_rows = _read_ledger_prefix(trajectory_dir / storage['history_ledger_file'], current_t)
    mass = np.load(trajectory_dir / storage['gt_file'], mmap_mode='r', allow_pickle=False)
    if mass.ndim != 6 or tuple(mass.shape[1:]) != GT_SHAPE or mass.dtype != np.dtype('float64'):
        raise Fixed5AxisHDEPTBridgeError('canonical gt_mass.npy shape or dtype mismatch')
    if len(prefix_rows) > mass.shape[0]:
        raise Fixed5AxisHDEPTBridgeError('ledger prefix exceeds stored G_t frames')
    previous_gt_hash = ''
    chain_hash = GENESIS_HASH
    previous_t: int | None = None
    prefix_frames: list[np.ndarray] = []
    for index, row in enumerate(prefix_rows):
        if int(row['gt_row_index']) != index:
            raise Fixed5AxisHDEPTBridgeError('G/K row index mismatch in causal prefix')
        t = int(row['t'])
        if row['trajectory_id'] != trajectory_id:
            raise Fixed5AxisHDEPTBridgeError('multiple trajectory IDs in causal prefix')
        if row['phase'] != fixed5['gt']['phase']:
            raise Fixed5AxisHDEPTBridgeError('non-pre-transition G_t in causal prefix')
        source_matches = row.get('source_trajectory_id', trajectory_id) == trajectory_id
        if previous_t is None:
            expected_status, expected_delta = ('initial' if source_matches else 'source_mismatch', 0)
        else:
            expected_delta = t - previous_t
            if not source_matches:
                expected_status = 'source_mismatch'
            elif t == previous_t:
                expected_status = 'duplicate'
            elif t < previous_t:
                expected_status = 'out_of_order'
            elif t > previous_t + 1:
                expected_status = 'gap'
            else:
                expected_status = 'continuous'
        if row['continuity_status'] != expected_status or int(row['delta_t']) != expected_delta:
            raise Fixed5AxisHDEPTBridgeError('continuity metadata mismatch in causal prefix')
        canonical = _validate_distribution(np.asarray(mass[index]), fixed5)
        expected_hash = _compute_gt_hash(contract_version=fixed5['contract_version'], trajectory_id=trajectory_id, t=t, distribution=canonical, source_state_hash=row['source_state_hash'])
        if row['gt_hash'] != expected_hash or row['previous_gt_hash'] != previous_gt_hash:
            raise Fixed5AxisHDEPTBridgeError('G_t hash chain mismatch in causal prefix')
        chain_hash = _compute_history_chain_hash(chain_hash, expected_hash, t)
        if row['history_chain_hash'] != chain_hash:
            raise Fixed5AxisHDEPTBridgeError('history chain mismatch in causal prefix')
        prefix_frames.append(canonical)
        previous_gt_hash, previous_t = (expected_hash, t)
    current_row = prefix_rows[-1]
    allowed = set(bridge['formal_input']['accepted_current_continuity_status'])
    if current_row['continuity_status'] not in allowed or not _bool_text(current_row.get('admissible_for_research', '')):
        raise Fixed5AxisHDEPTBridgeError('current G_t is not admissible for research')
    start = len(prefix_rows) - 1
    while start > 0 and prefix_rows[start]['continuity_status'] == 'continuous':
        if prefix_rows[start - 1]['continuity_status'] not in {'initial', 'continuous'}:
            break
        start -= 1
    suffix_rows = prefix_rows[start:]
    suffix_frames = prefix_frames[start:]
    if suffix_rows[0]['continuity_status'] not in {'initial', 'continuous'}:
        suffix_rows = suffix_rows[1:]
        suffix_frames = suffix_frames[1:]
    if not suffix_rows:
        suffix_rows = [current_row]
        suffix_frames = [prefix_frames[-1]]
    return {'trajectory_id': trajectory_id, 'current_t': current_t, 'frames': np.stack(suffix_frames).astype(np.float64, copy=False), 'ledger': suffix_rows, 'current_gt_hash': current_row['gt_hash'], 'history_chain_hash': current_row['history_chain_hash'], 'history_start_t': int(suffix_rows[0]['t']), 'history_end_t': int(suffix_rows[-1]['t']), 'history_frame_count': len(suffix_rows), 'manifest_declared_file_count': int(manifest.get('file_count', -1)), 'provenance': provenance}
