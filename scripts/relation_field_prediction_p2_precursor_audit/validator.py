from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .common import (
    RelationFieldPredictionP2PrecursorAuditError,
    canonical_bytes,
    canonical_digest,
    load_json,
    resolve_case_manifest,
    tree_hash,
    verify_manifest,
)

# Deliberately independent metric implementation. This module does not import audit.py,
# metrics.py, or decision.py.
def _arrays(scores: Sequence[float], outcomes: Sequence[bool]) -> tuple[np.ndarray, np.ndarray]:
    x=np.asarray(scores,dtype=float);y=np.asarray(outcomes,dtype=bool)
    if x.ndim!=1 or y.ndim!=1 or x.shape!=y.shape or np.any(~np.isfinite(x)):
        raise RelationFieldPredictionP2PrecursorAuditError("validator metric input mismatch")
    return x,y


def _auc(scores: Sequence[float], outcomes: Sequence[bool]) -> float|None:
    x,y=_arrays(scores,outcomes);p=x[y];n=x[~y]
    if p.size==0 or n.size==0:return None
    value=0.0
    for item in p:
        value+=np.count_nonzero(item>n)+0.5*np.count_nonzero(item==n)
    return float(value/(p.size*n.size))


def _ap(scores: Sequence[float], outcomes: Sequence[bool]) -> float|None:
    x,y=_arrays(scores,outcomes);positive=int(np.count_nonzero(y))
    if positive==0:return None
    order=np.argsort(-x,kind="mergesort");x=x[order];y=y[order]
    seen=true_seen=0;value=0.0;start=0
    while start<x.size:
        stop=start+1
        while stop<x.size and x[stop]==x[start]:stop+=1
        added=int(np.count_nonzero(y[start:stop]));seen+=stop-start;true_seen+=added
        if added:value+=(added/positive)*(true_seen/seen)
        start=stop
    return float(value)


def _classification(scores: Sequence[float], outcomes: Sequence[bool]) -> dict[str,Any]:
    x,y=_arrays(scores,outcomes);pred=x>0
    tp=int(np.count_nonzero(pred&y));fp=int(np.count_nonzero(pred&~y));tn=int(np.count_nonzero(~pred&~y));fn=int(np.count_nonzero(~pred&y));total=tp+fp+tn+fn
    def div(a:float,b:float)->float|None:return None if b==0 else float(a/b)
    precision=div(tp,tp+fp);recall=div(tp,tp+fn);specificity=div(tn,tn+fp);accuracy=div(tp+tn,total)
    balanced=None if recall is None or specificity is None else .5*(recall+specificity)
    denominator=math.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))
    return {"true_positive":tp,"false_positive":fp,"true_negative":tn,"false_negative":fn,"precision":precision,"recall":recall,"specificity":specificity,"accuracy":accuracy,"balanced_accuracy":balanced,"f1":div(2*tp,2*tp+fp+fn),"matthews_correlation":div(tp*tn-fp*fn,denominator),"brier_score":None if total==0 else float(np.mean((pred.astype(float)-y.astype(float))**2))}


def _point(scores: Sequence[float], outcomes: Sequence[bool]) -> dict[str,Any]:
    x,y=_arrays(scores,outcomes);p=x[y];n=x[~y]
    result={"sample_count":int(y.size),"positive_outcome_count":int(np.count_nonzero(y)),"negative_outcome_count":int(np.count_nonzero(~y)),"positive_prevalence":None if y.size==0 else float(np.mean(y)),"roc_auc":_auc(x,y),"average_precision":_ap(x,y),"positive_score_mean":None if p.size==0 else float(np.mean(p)),"negative_score_mean":None if n.size==0 else float(np.mean(n)),"positive_score_median":None if p.size==0 else float(np.median(p)),"negative_score_median":None if n.size==0 else float(np.median(n))}
    result.update(_classification(x,y));return result


def _seed(value: Mapping[str,Any])->int:
    return int.from_bytes(hashlib.sha256(canonical_bytes(value)).digest()[:8],"big")


def _bootstrap(scores:Sequence[float],outcomes:Sequence[bool],groups:Sequence[str],*,replicates:int,confidence:float,key:Mapping[str,Any])->dict[str,Any]:
    x,y=_arrays(scores,outcomes);g=np.asarray([str(v) for v in groups],dtype=object)
    unique=sorted(set(g.tolist()))
    if not unique:return {"requested_replicates":replicates,"trajectory_group_count":0,"roc_auc_valid_replicates":0,"average_precision_valid_replicates":0,"roc_auc_interval":None,"average_precision_interval":None}
    index={value:np.flatnonzero(g==value) for value in unique};rng=np.random.default_rng(_seed(key));aucs=[];aps=[]
    for _ in range(replicates):
        chosen=rng.choice(unique,size=len(unique),replace=True);selected=np.concatenate([index[str(v)] for v in chosen])
        auc=_auc(x[selected],y[selected]);ap=_ap(x[selected],y[selected])
        if auc is not None:aucs.append(auc)
        if ap is not None:aps.append(ap)
    alpha=(1-confidence)/2
    def interval(values:list[float])->list[float]|None:
        return None if not values else [float(np.quantile(values,alpha,method="linear")),float(np.quantile(values,1-alpha,method="linear"))]
    return {"requested_replicates":replicates,"trajectory_group_count":len(unique),"roc_auc_valid_replicates":len(aucs),"average_precision_valid_replicates":len(aps),"roc_auc_interval":interval(aucs),"average_precision_interval":interval(aps)}


def _permutation(values:Sequence[float],key:Mapping[str,Any])->list[float]:
    x=np.asarray(values,dtype=float);rng=np.random.default_rng(_seed(key));return x[rng.permutation(x.size)].astype(float).tolist()


def _reconstruct_samples(snapshot:Mapping[str,Any],futures:Mapping[str,Any],contract:Mapping[str,Any])->list[dict[str,Any]]:
    by_id={str(row["case_id"]):row for row in futures["cases"]};rows=[]
    for frozen in snapshot["cases"]:
        future=by_id[str(frozen["case_id"])]
        for horizon in contract["evaluation"]["horizons"]:
            payload=future["horizons"][str(int(horizon))]
            for target_id,target in contract["targets"].items():
                applicability=target.get("rf10_applicability_field")
                rows.append({"case_id":frozen["case_id"],"partition":frozen["partition"],"trajectory_group_id":frozen["trajectory_group_id"],"cutoff_t":frozen["cutoff_t"],"horizon":int(horizon),"target_id":target_id,"outcome":bool(payload[target["rf10_outcome_field"]]),"applicable":True if applicability is None else bool(payload[applicability]),"scores":dict(frozen["prediction_scores"][target_id]),"structure_interval":frozen["structure_intervals"][target_id],"applicability_coordinates":frozen["applicability"]})
    for partition in contract["input"]["allowed_partitions"]:
        for horizon in contract["evaluation"]["horizons"]:
            for target_id in sorted(contract["targets"]):
                selected=[r for r in rows if r["partition"]==partition and r["horizon"]==int(horizon) and r["target_id"]==target_id and r["scores"]["p2_structure_margin"] is not None]
                values=_permutation([r["scores"]["p2_structure_margin"] for r in selected],{"contract_version":contract["contract_version"],"partition":partition,"horizon":int(horizon),"target_id":target_id,"score_id":"p2_structure_margin_time_shuffled"})
                for row,value in zip(selected,values):row["scores"]["p2_structure_margin_time_shuffled"]=value
    return rows


def _metric_rows(samples:Sequence[Mapping[str,Any]],contract:Mapping[str,Any])->list[dict[str,Any]]:
    output=[];boot=contract["metrics"]["bootstrap"]
    for partition in contract["input"]["allowed_partitions"]:
      for horizon in contract["evaluation"]["horizons"]:
       for target_id in sorted(contract["targets"]):
        for score_id in contract["score_panels"]:
         chosen=[r for r in samples if r["partition"]==partition and r["horizon"]==int(horizon) and r["target_id"]==target_id and r.get("applicable",True) and r["scores"].get(score_id) is not None]
         scores=[float(r["scores"][score_id]) for r in chosen];outcomes=[bool(r["outcome"]) for r in chosen];groups=[str(r["trajectory_group_id"]) for r in chosen]
         point=_point(scores,outcomes)
         bootstrap=_bootstrap(scores,outcomes,groups,replicates=int(boot["replicates"]),confidence=float(boot["confidence"]),key={"contract_version":contract["contract_version"],"partition":partition,"horizon":int(horizon),"target_id":target_id,"score_id":score_id}) if scores else {"requested_replicates":int(boot["replicates"]),"trajectory_group_count":0,"roc_auc_valid_replicates":0,"average_precision_valid_replicates":0,"roc_auc_interval":None,"average_precision_interval":None}
         output.append({"partition":partition,"horizon":int(horizon),"target_id":target_id,"score_id":score_id,**point,"bootstrap":bootstrap})
    return output


def _support(samples:Sequence[Mapping[str,Any]],contract:Mapping[str,Any])->dict[str,Any]:
    test=[r for r in samples if r["partition"]=="test" and r.get("applicable",True)];cases=sorted({r["case_id"] for r in test});settings=contract["support_gates"];cells=[];all_ok=True
    for target_id in sorted(contract["targets"]):
      for horizon in contract["evaluation"]["horizons"]:
       chosen=[r for r in test if r["target_id"]==target_id and r["horizon"]==int(horizon)];positive=sum(r["outcome"] for r in chosen);negative=len(chosen)-positive
       ok=len(cases)>=int(settings["minimum_test_cases_for_accuracy_claim"]) and positive>=int(settings["minimum_positive_test_outcomes_per_target_horizon"]) and negative>=int(settings["minimum_negative_test_outcomes_per_target_horizon"]);all_ok=all_ok and ok
       cells.append({"target_id":target_id,"horizon":int(horizon),"sample_count":len(chosen),"positive_outcome_count":positive,"negative_outcome_count":negative,"supported":ok})
    return {"test_case_count":len(cases),"minimum_test_case_count":int(settings["minimum_test_cases_for_accuracy_claim"]),"all_target_horizon_cells_supported":all_ok,"cells":cells}


def _decision(metrics:Sequence[Mapping[str,Any]],support:Mapping[str,Any],contract:Mapping[str,Any])->dict[str,Any]:
    if not support["all_target_horizon_cells_supported"]:return {"status":"blocked_support_insufficient","supported_targets":[],"unsupported_targets":sorted(contract["targets"]),"performance_interpretation_allowed":False,"reason":"RF-10 support gates are not met for every target and horizon."}
    required=int(contract["support_gates"]["minimum_supported_horizons_for_target_precursor_signal"]);supported=[];audit=[]
    for target_id in sorted(contract["targets"]):
      qualifying=[]
      for row in metrics:
       if row["partition"]=="test" and row["target_id"]==target_id and row["score_id"]=="p2_structure_margin":
        ai=row["bootstrap"]["roc_auc_interval"];pi=row["bootstrap"]["average_precision_interval"];p=row["positive_prevalence"]
        if ai is not None and pi is not None and p is not None and ai[0]>.5 and pi[0]>p:qualifying.append(row["horizon"])
      ok=len(set(qualifying))>=required
      if ok:supported.append(target_id)
      audit.append({"target_id":target_id,"qualifying_horizons":sorted(set(qualifying)),"minimum_required_horizons":required,"precursor_signal_supported":ok})
    all_targets=sorted(contract["targets"]);status="eligible_for_full_phase3_model_comparison" if len(supported)==len(all_targets) else "eligible_for_partial_phase3_model_comparison" if supported else "blocked_no_supported_precursor_signal"
    return {"status":status,"supported_targets":supported,"unsupported_targets":[x for x in all_targets if x not in supported],"performance_interpretation_allowed":True,"target_audit":audit,"reason":"Decision uses the preregistered bootstrap lower-bound rule without fitting a predictor."}


def _equal(expected:Any,actual:Any,name:str)->None:
    if canonical_digest(expected)!=canonical_digest(actual):raise RelationFieldPredictionP2PrecursorAuditError(f"independent validator mismatch: {name}")


def validate_precursor_audit(audit_dir:str|Path,case_manifest_path:str|Path,*,contract:Mapping[str,Any])->dict[str,Any]:
    root=Path(audit_dir).resolve();verify_manifest(root)
    if load_json(root/contract["storage"]["contract_file"])!=dict(contract):raise RelationFieldPredictionP2PrecursorAuditError("stored P2-4 contract mismatch")
    raw,cases=resolve_case_manifest(case_manifest_path,contract)
    _equal(raw,load_json(root/contract["storage"]["frozen_case_manifest_file"]),"case manifest")
    snapshot=load_json(root/contract["storage"]["prediction_snapshot_file"]);futures=load_json(root/contract["storage"]["future_outcomes_file"])
    check=dict(snapshot);saved_hash=check.pop("prediction_snapshot_hash")
    if canonical_digest(check)!=saved_hash:raise RelationFieldPredictionP2PrecursorAuditError("prediction snapshot hash mismatch")
    by_case={str(row["case_id"]):row for row in snapshot["cases"]};future_by={str(row["case_id"]):row for row in futures["cases"]}
    for case in cases:
        frozen=by_case[str(case["case_id"])]
        if tree_hash(Path(case["p1_series_dir"]))!=frozen["p1_tree_hash"] or tree_hash(Path(case["p2_series_dir"]))!=frozen["p2_tree_hash"] or tree_hash(Path(case["prefix_trajectory_dir"]))!=frozen["prefix_trajectory_tree_hash"]:raise RelationFieldPredictionP2PrecursorAuditError("prediction source hash mismatch")
        if tree_hash(Path(case["full_trajectory_dir"]))!=future_by[str(case["case_id"])]["full_trajectory_tree_hash"]:raise RelationFieldPredictionP2PrecursorAuditError("future source hash mismatch")
    samples=_reconstruct_samples(snapshot,futures,contract);saved_samples=load_json(root/contract["storage"]["sample_ledger_file"])
    _equal(samples,saved_samples["rows"],"sample ledger")
    metrics=_metric_rows(samples,contract);saved_metrics=load_json(root/contract["storage"]["metrics_file"])
    _equal(metrics,saved_metrics["rows"],"metrics")
    support=_support(samples,contract);_equal(support,load_json(root/contract["storage"]["support_file"]),"support")
    decision=_decision(metrics,support,contract);saved_decision=load_json(root/contract["storage"]["decision_file"])
    for key,value in decision.items():
        if saved_decision.get(key)!=value:raise RelationFieldPredictionP2PrecursorAuditError(f"independent validator mismatch: decision.{key}")
    return {"p2_4_independent_validation_gate":"passed","case_count":len(cases),"sample_count":len(samples),"metric_row_count":len(metrics),"decision_status":decision["status"],"builder_metric_module_imported":False,"rf10_outcome_redefinition_performed":False}
