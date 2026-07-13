"""P2-4: 連続関係場座標の未来前兆性監査。"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from .audit import build_precursor_audit
from .common import RelationFieldPredictionP2PrecursorAuditError, load_contract as _load_contract
from .validator import validate_precursor_audit

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT=ROOT/"configs"/"relation_field_prediction_p2_precursor_audit_contract.json"

def load_contract(path:str|Path=DEFAULT_CONTRACT)->dict[str,Any]:return _load_contract(path)

def build_relation_field_prediction_p2_precursor_audit(case_manifest_path:str|Path,output:str|Path,*,contract_path:str|Path=DEFAULT_CONTRACT)->Path:
    return build_precursor_audit(case_manifest_path,output,contract=load_contract(contract_path))

def validate_relation_field_prediction_p2_precursor_audit(audit_dir:str|Path,case_manifest_path:str|Path,*,contract_path:str|Path=DEFAULT_CONTRACT)->dict[str,Any]:
    return validate_precursor_audit(audit_dir,case_manifest_path,contract=load_contract(contract_path))

__all__=["RelationFieldPredictionP2PrecursorAuditError","DEFAULT_CONTRACT","load_contract","build_relation_field_prediction_p2_precursor_audit","validate_relation_field_prediction_p2_precursor_audit"]
