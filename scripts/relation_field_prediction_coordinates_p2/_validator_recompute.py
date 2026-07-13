from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ._common import load_json, load_npz
from ._validator_math import Q, energy_checks, index_map, pathway_checks, q_abs, q_above, q_and, q_make, q_neg, q_one, q_or, recovery_checks, residual_checks, shape_checks, src_one, src_three, axis_checks, read_limits

def available(value: Q|None,reason: str|None=None) -> dict[str,Any]:
    return {"availability":"unavailable","reason":reason or "missing_source","value":None} if value is None else {"availability":"available","reason":None,"value":value}


def independent_formula(entry: Mapping[str,Any],ctx: Mapping[str,Any],done: Mapping[str,dict[str,Any]],prev_records: Mapping[str,dict[str,Any]]|None,prevprev_records: Mapping[str,dict[str,Any]]|None) -> dict[str,Any]:
    f=str(entry["formula"])
    if f=="reserved":return available(None,"reserved_not_implemented")
    if f in {"axis_signed_triplet","pathway_width_triplet","recovery_inward_triplet"}:return available(src_three(ctx,entry["source_feature_ids"]))
    if f in {"optional_source", "absolute_optional_source", "optional_triplet", "matrix_diagonal"}:
        keys=entry.get("source_feature_ids",[])
        if f == "optional_triplet": return available(src_three(ctx,keys))
        source=src_one(ctx,keys[0]) if keys else None
        if source is None: return available(None)
        if f == "absolute_optional_source": return available(q_abs(source))
        if f == "matrix_diagonal":
            if source[1].ndim != 2 or source[1].shape[0] != source[1].shape[1]: return available(None,"shape_mismatch")
            return available(q_make(np.diag(source[0]),np.diag(source[1]),np.diag(source[2])))
        return available(source)
    if f=="absolute_of":
        dep=done.get(entry["dependencies"][0]);return available(None,"missing_dependency") if not dep or dep["availability"]!="available" else available(q_abs(dep["value"]))
    if f in {"change_rate","change_acceleration"}:
        dep=entry["dependencies"][0]; cur=done.get(dep); old=None if prev_records is None else prev_records.get(dep)
        if not cur or cur["availability"]!="available" or not old or old["availability"]!="available":return available(None,"insufficient_history")
        dt=ctx["origin_t"]-ctx["previous"]["origin_t"]; x=cur["value"]; y=old["value"]
        if dt<=0 or x[1].shape!=y[1].shape:return available(None,"identity_mismatch")
        first=((x[0]-y[2])/dt,(x[1]-y[1])/dt,(x[2]-y[0])/dt)
        if f=="change_rate":return available(first)
        older=None if prevprev_records is None else prevprev_records.get(dep)
        if not older or older["availability"]!="available":return available(None,"insufficient_history")
        z=older["value"]; pdt=ctx["previous"]["origin_t"]-ctx["previous_previous"]["origin_t"]; gap=((ctx["origin_t"]+ctx["previous"]["origin_t"])-(ctx["previous"]["origin_t"]+ctx["previous_previous"]["origin_t"]))/2
        previous_first=((y[0]-z[2])/pdt,(y[1]-z[1])/pdt,(y[2]-z[0])/pdt)
        return available(((first[0]-previous_first[2])/gap,(first[1]-previous_first[1])/gap,(first[2]-previous_first[0])/gap))
    if f=="aggregate_candidate_width":
        widths=[float(np.max(r["value"][2]-r["value"][0])) for r in done.values() if r["availability"]=="available" and r.get("role")=="state"]
        return available(q_one(max(widths))) if widths else available(None)
    if f=="availability_ratio":return available(None,"deferred")
    if f=="identity_stability":
        if ctx.get("previous") is None:return available(None,"insufficient_history")
        a={k:v.get("comparability_id") for k,v in ctx["index"].items()};b={k:v.get("comparability_id") for k,v in ctx["previous"]["index"].items()};common=set(a)&set(b)
        return available(q_one(sum(a[k]==b[k] for k in common)/len(common))) if common else available(None)
    if f=="history_coverage":
        a=src_one(ctx,"rf8_history_conditioned_innovation__prior_transition_count");b=src_one(ctx,"rf8_history_conditioned_innovation__effective_support")
        if a is None or b is None:return available(None)
        l=ctx["limits"];return available(q_and(q_above(a,l["history_count"],max(l["history_count"],1)),q_above(b,l["history_support"],max(l["history_support"],1))))
    if f in {"residual_ratio","residual_dominance"}:return available(None) if ctx["residual"] is None else available(ctx["residual"][0 if f=="residual_ratio" else 1])
    if f.startswith("shape_"):return available(None) if ctx["shape"] is None else available(ctx["shape"][f[6:]])
    if f in {"pathway_narrowing","pathway_widening"}:return available(None,"insufficient_history") if ctx["pathway"] is None else available(ctx["pathway"][f.split("_")[-1]])
    if f.startswith("same_axis_"):
        key={"same_axis_amplification":"amplification","same_axis_decay":"decay","same_axis_stop":"stop","same_axis_reversal":"reversal"}[f]
        return available(None,"insufficient_history") if ctx["axis"] is None else available(ctx["axis"][key])
    if f in {"recovery_weakening","recovery_strengthening","return_suppression"}:
        key=f.removeprefix("recovery_");return available(None,"insufficient_history") if ctx["recovery"] is None else available(ctx["recovery"][key])
    if f in {"gradient_dominance","circulation_dominance"}:return available(None) if ctx["energy"] is None else available(ctx["energy"][0 if f=="gradient_dominance" else 1])
    dependency_map={
      "risk_overconvergence":["p2.condition.shape.convergence","p2.condition.pathway.narrowing","p2.condition.same_axis.amplification"],
      "risk_fixation":["p2.risk.overconvergence.structure_margin","p2.condition.recovery.return_suppression"],
      "risk_divergence":["p2.condition.shape.divergence","p2.condition.pathway.widening","SPECIAL_DECAY_STOP"],
      "risk_recovery_margin_reduction":["p2.condition.recovery.weakening","SPECIAL_NOT_STRENGTHENING"],
    }
    if f in dependency_map:
        values=[]
        for dep in dependency_map[f]:
            if dep=="SPECIAL_DECAY_STOP":
                x=done.get("p2.condition.same_axis.decay");y=done.get("p2.condition.same_axis.axis_stop")
                if not x or not y or x["availability"]!="available" or y["availability"]!="available":return available(None,"missing_dependency")
                values.append(q_or(x["value"],y["value"]));continue
            if dep=="SPECIAL_NOT_STRENGTHENING":
                x=done.get("p2.condition.recovery.strengthening")
                if not x or x["availability"]!="available":return available(None,"missing_dependency")
                values.append(q_neg(x["value"]));continue
            x=done.get(dep)
            if not x or x["availability"]!="available":return available(None,"missing_dependency")
            values.append(x["value"])
        return available(q_and(*values))
    return available(None,"unsupported_formula")


def recompute_origin(entries: Sequence[Mapping[str,Any]],origin_t:int,origin:Path,state:Path,p1:Mapping[str,Any],previous_ctx:dict[str,Any]|None,previous_previous_ctx:dict[str,Any]|None,previous_records:Mapping[str,dict[str,Any]]|None,previous_previous_records:Mapping[str,dict[str,Any]]|None) -> tuple[dict[str,Any],dict[str,dict[str,Any]]]:
    arrays=load_npz(state/str(p1["storage"]["base_state_file"]));idx=index_map(load_json(state/str(p1["storage"]["base_state_index_file"])));ctx={"origin_t":origin_t,"origin":origin,"arrays":arrays,"index":idx,"limits":read_limits(origin,p1),"previous":previous_ctx,"previous_previous":previous_previous_ctx}
    ctx["shape"]=shape_checks(ctx);ctx["pathway"]=pathway_checks(ctx);ctx["axis"]=axis_checks(ctx);ctx["recovery"]=recovery_checks(ctx,ctx["pathway"],ctx["axis"],ctx["shape"]);ctx["residual"]=residual_checks(ctx);ctx["energy"]=energy_checks(ctx)
    done={}
    for entry in entries:
        result=independent_formula(entry,ctx,done,previous_records,previous_previous_records);result["role"]=entry["coordinate_role"];done[str(entry["coordinate_id"])]=result
    key="p2.applicability.coordinate_availability_ratio";required=[r for cid,r in done.items() if cid!=key and next(e for e in entries if e["coordinate_id"]==cid)["registration_status"]=="required"]
    done[key]={"availability":"available","reason":None,"value":q_one(sum(r["availability"]=="available" for r in required)/len(required)),"role":"applicability"}
    return ctx,done


def expected_arrays(records: Mapping[str,dict[str,Any]]) -> dict[str,np.ndarray]:
    result={}
    for cid,row in records.items():
        if row["availability"]!="available":continue
        for part,value in zip(("lower","center","upper"),row["value"]):result[f"{cid}__{part}"]=np.asarray(value,dtype=float)
    return result


def expected_differences(t:int,records:Mapping[str,dict[str,Any]],pt:int|None,prior:Mapping[str,dict[str,Any]]|None,ppt:int|None,older:Mapping[str,dict[str,Any]]|None) -> tuple[dict[str,np.ndarray],dict[str,np.ndarray]]:
    one={};two={}
    if prior is None or pt is None:return one,two
    for cid,row in records.items():
        old=prior.get(cid)
        if row["availability"]!="available" or not old or old["availability"]!="available" or row["value"][1].shape!=old["value"][1].shape:continue
        dt=t-pt;x=row["value"];y=old["value"]
        first=((x[0]-y[2])/dt,(x[1]-y[1])/dt,(x[2]-y[0])/dt)
        for part,val in zip(("lower","center","upper"),first):one[f"{cid}__{part}"]=val
        if older is None or ppt is None:continue
        z=older.get(cid)
        if not z or z["availability"]!="available" or y[1].shape!=z["value"][1].shape:continue
        pdt=pt-ppt;gap=((t+pt)-(pt+ppt))/2;previous=((y[0]-z["value"][2])/pdt,(y[1]-z["value"][1])/pdt,(y[2]-z["value"][0])/pdt)
        second=((first[0]-previous[2])/gap,(first[1]-previous[1])/gap,(first[2]-previous[0])/gap)
        for part,val in zip(("lower","center","upper"),second):two[f"{cid}__{part}"]=val
    return one,two

