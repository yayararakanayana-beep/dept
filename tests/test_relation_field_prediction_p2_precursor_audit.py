from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/"scripts") not in sys.path:sys.path.insert(0,str(ROOT/"scripts"))

from relation_field_prediction_p2_precursor_audit import (
    RelationFieldPredictionP2PrecursorAuditError,
    load_contract,
    validate_relation_field_prediction_p2_precursor_audit,
)
from relation_field_prediction_p2_precursor_audit.common import (
    canonical_digest,dump_json,resolve_case_manifest,tree_hash,write_manifest,
)
from relation_field_prediction_p2_precursor_audit.metrics import (
    average_precision,deterministic_permutation,grouped_bootstrap,roc_auc,
)
from relation_field_prediction_p2_precursor_audit import validator as independent


def test_contract_and_independent_import_boundary()->None:
    contract=load_contract()
    assert contract["evaluation"]["horizons"]==[1,2,4]
    assert contract["evaluation"]["model_fitting_forbidden"] is True
    assert contract["evaluation"]["cross_target_aggregation_forbidden"] is True
    assert set(contract["targets"])=={"overconvergence","fixation","divergence","recovery_margin_reduction"}
    tree=ast.parse((ROOT/"scripts"/"relation_field_prediction_p2_precursor_audit"/"validator.py").read_text())
    imported=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):imported.extend(alias.name for alias in node.names)
        elif isinstance(node,ast.ImportFrom):imported.append(node.module or "")
    assert not any(name.endswith(".audit") or name.endswith(".metrics") or name.endswith(".decision") for name in imported)


def test_tie_aware_auc_and_average_precision()->None:
    assert roc_auc([0.9,0.8,0.2,0.1],[True,True,False,False])==1.0
    assert roc_auc([0.5,0.5],[True,False])==0.5
    assert average_precision([0.9,0.8,0.2,0.1],[True,False,True,False])==pytest.approx((1.0+2/3)/2)
    assert average_precision([0.5,0.5],[True,False])==0.5
    assert roc_auc([1,2],[True,True]) is None
    assert average_precision([1,2],[False,False]) is None


def test_group_bootstrap_is_deterministic()->None:
    kwargs=dict(replicates=100,confidence=.95,seed_key={"x":1})
    first=grouped_bootstrap([.1,.2,.8,.9],[False,False,True,True],["a","a","b","b"],**kwargs)
    second=grouped_bootstrap([.1,.2,.8,.9],[False,False,True,True],["a","a","b","b"],**kwargs)
    assert first==second
    assert deterministic_permutation([1,2,3,4],{"key":"same"})==deterministic_permutation([1,2,3,4],{"key":"same"})


def _source(root:Path,name:str)->Path:
    path=root/name;path.mkdir(parents=True);(path/"payload.txt").write_text(name+"\n",encoding="utf-8");return path


def _synthetic_artifact(tmp_path:Path)->tuple[Path,Path]:
    contract=load_contract()
    p1=_source(tmp_path,"p1");p2=_source(tmp_path,"p2");prefix=_source(tmp_path,"prefix");full=_source(tmp_path,"full");grid=_source(tmp_path,"grid")
    case_manifest={"manifest_version":contract["input"]["case_manifest_version"],"cases":[{"case_id":"case-1","partition":"test","trajectory_group_id":"group-1","prefix_trajectory_dir":str(prefix),"full_trajectory_dir":str(full),"grid_artifact_dir":str(grid),"p1_series_dir":str(p1),"p2_series_dir":str(p2),"cutoff_t":4}]}
    manifest_path=tmp_path/"cases.json";dump_json(manifest_path,case_manifest)
    targets={};intervals={}
    for index,target_id in enumerate(sorted(contract["targets"])):
        value=float(index-1)
        targets[target_id]={"p2_structure_margin":value,"p2_structure_margin_first_difference":value/2,"p2_structure_margin_second_difference":value/4,"p2_component_only_margin":value-.1,"p1_boolean_candidate":float(value>0),"always_negative":0.0}
        intervals[target_id]={"lower":value-.2,"center":value,"upper":value+.2}
    applicability={coordinate_id:.5 for coordinate_id in contract["applicability_stratification"]["coordinate_ids"]}
    snapshot={"contract_version":contract["contract_version"],"prediction_snapshot_frozen_before_full_trajectory_read":True,"future_suffix_read_before_snapshot":False,"cases":[{"case_id":"case-1","partition":"test","trajectory_group_id":"group-1","cutoff_t":4,"prediction_scores":targets,"structure_intervals":intervals,"applicability":applicability,"p1_tree_hash":tree_hash(p1),"p2_tree_hash":tree_hash(p2),"prefix_trajectory_tree_hash":tree_hash(prefix),"p2_origin_manifest_sha256":"synthetic","future_suffix_read_before_snapshot":False}]}
    snapshot["prediction_snapshot_hash"]=canonical_digest(snapshot)
    horizon_payload={"future_concentration_outcome":True,"future_persistent_concentration_outcome":False,"future_dispersion_outcome":True,"future_recovery_failure_outcome":False,"future_recovery_failure_applicable":False}
    futures={"rf10_contract_version":"relation_field_predictive_validation_rc1","rf10_contract_hash":"synthetic","prediction_snapshot_hash":snapshot["prediction_snapshot_hash"],"future_read_started_after_snapshot":True,"cases":[{"case_id":"case-1","trajectory_group_id":"group-1","partition":"test","cutoff_t":4,"max_future_t_read":8,"full_trajectory_tree_hash":tree_hash(full),"prefix_frames_equal":True,"horizons":{str(h):copy.deepcopy(horizon_payload) for h in (1,2,4)}}]}
    samples=independent._reconstruct_samples(snapshot,futures,contract)
    metrics=independent._metric_rows(samples,contract)
    support=independent._support(samples,contract)
    decision=independent._decision(metrics,support,contract)
    decision.update({"precursor_accuracy_claim":False,"p3_predictor_fitted":False,"true_irreversibility_claim":False})
    output=tmp_path/"audit";output.mkdir()
    dump_json(output/contract["storage"]["contract_file"],contract)
    dump_json(output/contract["storage"]["frozen_case_manifest_file"],case_manifest)
    dump_json(output/contract["storage"]["prediction_snapshot_file"],snapshot)
    dump_json(output/contract["storage"]["future_outcomes_file"],futures)
    dump_json(output/contract["storage"]["sample_ledger_file"],{"sample_ledger_version":"relation_field_prediction_p2_precursor_samples_v1","prediction_snapshot_hash":snapshot["prediction_snapshot_hash"],"rows":samples})
    dump_json(output/contract["storage"]["metrics_file"],{"metrics_version":"relation_field_prediction_p2_precursor_metrics_v1","cross_target_aggregation_performed":False,"rows":metrics})
    dump_json(output/contract["storage"]["support_file"],support)
    dump_json(output/contract["storage"]["decision_file"],decision)
    dump_json(output/contract["storage"]["ablation_file"],{"rows":[]})
    dump_json(output/contract["storage"]["stratification_file"],{"rows":[]})
    dump_json(output/contract["storage"]["validation_file"],{"p2_4_audit_gate":"passed"})
    write_manifest(output,"relation_field_prediction_p2_precursor_audit_v1")
    return output,manifest_path


def test_independent_validator_and_support_block(tmp_path:Path)->None:
    output,manifest=_synthetic_artifact(tmp_path)
    result=validate_relation_field_prediction_p2_precursor_audit(output,manifest)
    assert result["p2_4_independent_validation_gate"]=="passed"
    assert result["decision_status"]=="blocked_support_insufficient"
    assert result["builder_metric_module_imported"] is False


def test_manifest_regenerated_metric_tampering_is_rejected(tmp_path:Path)->None:
    output,manifest=_synthetic_artifact(tmp_path);contract=load_contract();path=output/contract["storage"]["metrics_file"]
    payload=json.loads(path.read_text());payload["rows"][0]["roc_auc"]=.123;dump_json(path,payload);write_manifest(output,"relation_field_prediction_p2_precursor_audit_v1")
    with pytest.raises(RelationFieldPredictionP2PrecursorAuditError,match="metrics"):
        validate_relation_field_prediction_p2_precursor_audit(output,manifest)


def test_group_partition_crossing_is_rejected(tmp_path:Path)->None:
    contract=load_contract();case={field:"x" for field in contract["input"]["required_case_fields"]};case.update(case_id="a",partition="development",trajectory_group_id="same",cutoff_t=4)
    other=dict(case,case_id="b",partition="test")
    path=tmp_path/"cases.json";dump_json(path,{"manifest_version":contract["input"]["case_manifest_version"],"cases":[case,other]})
    with pytest.raises(RelationFieldPredictionP2PrecursorAuditError,match="crosses partitions"):
        resolve_case_manifest(path,contract)
