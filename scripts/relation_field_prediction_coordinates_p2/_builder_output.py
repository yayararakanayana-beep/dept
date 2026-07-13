from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ._common import (
    RelationFieldPredictionCoordinatesP2Error,
    canonical_digest,
    coordinate_arrays_from_records,
    dump_json,
    load_json,
    load_npz,
    p1_origin_paths,
    tree_hash,
    write_deterministic_npz,
    write_manifest,
)
from ._builder_math import _I, _record, _single
from ._builder_formulas import _coordinate_value, _energy, _pathway, _recovery, _residual, _same_axis, _shape, _thresholds

def _metadata_record(row: Mapping[str,Any]) -> dict[str,Any]:
    value={k:v for k,v in row.items() if k not in {"value","lower","center","upper"}}
    if row["availability"]=="available":
        cid=row["coordinate_id"]
        value["array_keys"]={part:f"{cid}__{part}" for part in ("lower","center","upper")}
        value["shape"]=list(row["value"].center.shape)
        if row["coordinate_role"] in {"condition_margin","structure_margin","modifier"}:
            v=row["value"]
            value["outside_distance_center_maximum"]=float(np.max(np.maximum(0.0,-v.center)))
            value["inside_depth_center_maximum"]=float(np.max(np.maximum(0.0,v.center)))
    return value


def _compute_origin(entry_list: Sequence[Mapping[str,Any]], origin_t: int, origin: Path, state: Path, p1_contract: Mapping[str,Any], previous_ctx: dict[str,Any]|None, previous_previous_ctx: dict[str,Any]|None, previous_records: Mapping[str,dict[str,Any]]|None, previous_previous_records: Mapping[str,dict[str,Any]]|None) -> tuple[dict[str,Any],dict[str,dict[str,Any]]]:
    arrays=load_npz(state/str(p1_contract["storage"]["base_state_file"])); base_index=load_json(state/str(p1_contract["storage"]["base_state_index_file"])); index={str(r["array_key"]):r for r in base_index["arrays"]}
    ctx={"origin_t":origin_t,"origin":origin,"arrays":arrays,"index":index,"thresholds":_thresholds(origin,p1_contract),"previous":previous_ctx,"previous_previous":previous_previous_ctx}
    ctx["shape"]=_shape(ctx); ctx["pathway"]=_pathway(ctx); ctx["same_axis"]=_same_axis(ctx); ctx["recovery"]=_recovery(ctx,ctx["pathway"],ctx["same_axis"],ctx["shape"]); ctx["residual"]=_residual(ctx); ctx["energy"]=_energy(ctx)
    computed:dict[str,dict[str,Any]]={}
    for entry in entry_list:
        value,reason=_coordinate_value(entry,ctx,computed,previous_records,previous_previous_records)
        row=_record(entry,value,reason)
        row["value"]=value
        computed[str(entry["coordinate_id"])]=row
    aid="p2.applicability.coordinate_availability_ratio"; row=computed[aid]
    considered=[r for cid,r in computed.items() if cid!=aid and r["registration_status"]=="required"]
    ratio=sum(r["availability"]=="available" for r in considered)/len(considered)
    val=_single(ratio); computed[aid]=_record(next(e for e in entry_list if e["coordinate_id"]==aid),val,None); computed[aid]["value"]=val
    ctx["risk_state"]=load_json(state/str(p1_contract["storage"]["risk_state_file"]))
    return ctx,computed


def _difference_payload(current_t:int,current:Mapping[str,dict[str,Any]],previous_t:int|None,previous:Mapping[str,dict[str,Any]]|None,previous_previous_t:int|None,previous_previous:Mapping[str,dict[str,Any]]|None) -> tuple[dict[str,np.ndarray],dict[str,np.ndarray],dict[str,Any]]:
    first={}; second={}; rows=[]
    for cid,row in current.items():
        rec={"coordinate_id":cid,"first_status":"unavailable","first_reason":"no_previous_origin","second_status":"unavailable","second_reason":"insufficient_previous_origins"}
        if row["availability"]=="available" and previous is not None and previous_t is not None and cid in previous and previous[cid]["availability"]=="available" and row["value"].center.shape==previous[cid]["value"].center.shape:
            dt=current_t-previous_t; a=row["value"]; b=previous[cid]["value"]
            for part,x,y in (("lower",a.lower,b.upper),("center",a.center,b.center),("upper",a.upper,b.lower)): first[f"{cid}__{part}"]=(x-y)/dt
            rec.update(first_status="available",first_reason=None)
            if previous_previous is not None and previous_previous_t is not None and cid in previous_previous and previous_previous[cid]["availability"]=="available" and b.center.shape==previous_previous[cid]["value"].center.shape:
                c=previous_previous[cid]["value"]; pdt=previous_t-previous_previous_t; gap=((current_t+previous_t)-(previous_t+previous_previous_t))/2.0
                p={"lower":(b.lower-c.upper)/pdt,"center":(b.center-c.center)/pdt,"upper":(b.upper-c.lower)/pdt}
                q={part:first[f"{cid}__{part}"] for part in ("lower","center","upper")}
                second[f"{cid}__lower"]=(q["lower"]-p["upper"])/gap; second[f"{cid}__center"]=(q["center"]-p["center"])/gap; second[f"{cid}__upper"]=(q["upper"]-p["lower"])/gap
                rec.update(second_status="available",second_reason=None)
        rows.append(rec)
    return first,second,{"difference_index_version":"relation_field_prediction_coordinates_p2_differences","origin_t":current_t,"first_difference_count":len(first)//3,"second_difference_count":len(second)//3,"zero_fill_performed":False,"records":rows}


def build_coordinate_series(p1_series_dir:str|Path,output:str|Path,*,contract:Mapping[str,Any],registry:Mapping[str,Any]) -> Path:
    p1_root=Path(p1_series_dir).resolve(); target=Path(output)
    if target.exists(): raise RelationFieldPredictionCoordinatesP2Error(f"output already exists: {target}")
    p1_before=tree_hash(p1_root); p1_contract,origins=p1_origin_paths(p1_root)
    target.parent.mkdir(parents=True,exist_ok=True); tmp=Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-",dir=target.parent))
    try:
        dump_json(tmp/"contract.json",dict(contract)); dump_json(tmp/"coordinate_registry.json",dict(registry))
        history=[]; series_rows=[]
        for origin_t,origin,state in origins:
            previous=history[-1] if history else None; previous_previous=history[-2] if len(history)>1 else None
            ctx,records=_compute_origin(registry["entries"],origin_t,origin,state,p1_contract,None if previous is None else previous[1],None if previous_previous is None else previous_previous[1],None if previous is None else previous[2],None if previous_previous is None else previous_previous[2])
            first,second,diff=_difference_payload(origin_t,records,None if previous is None else previous[0],None if previous is None else previous[2],None if previous_previous is None else previous_previous[0],None if previous_previous is None else previous_previous[2])
            out=tmp/contract["storage"]["origin_container_dir"]/str(contract["storage"]["origin_name_format"]).format(origin_t=origin_t); out.mkdir(parents=True)
            coord_arrays=coordinate_arrays_from_records({**r,"lower":r["value"].lower,"center":r["value"].center,"upper":r["value"].upper} for r in records.values() if r["availability"]=="available")
            write_deterministic_npz(out/contract["storage"]["coordinate_file"],coord_arrays); write_deterministic_npz(out/contract["storage"]["first_difference_file"],first); write_deterministic_npz(out/contract["storage"]["second_difference_file"],second)
            metadata=[_metadata_record(r) for r in records.values()]; dump_json(out/contract["storage"]["coordinate_index_file"],{"coordinate_index_version":"relation_field_prediction_coordinates_p2_index","origin_t":origin_t,"registry_version":registry["registry_version"],"coordinate_count":len(metadata),"available_count":sum(r["availability"]=="available" for r in metadata),"records":metadata})
            p1_risks={str(r["risk_structure_id"]):bool(r["current_candidate"]) for r in ctx["risk_state"]["records"]}
            mapping={"overconvergence":"p2.risk.overconvergence.structure_margin","fixation":"p2.risk.fixation.structure_margin","divergence":"p2.risk.divergence.structure_margin","recovery_margin_reduction":"p2.risk.recovery_margin_reduction.structure_margin"}
            risk_records=[]
            for rid,cid in mapping.items():
                rr=records[cid]; predicted=None if rr["availability"]!="available" else bool(np.all(rr["value"].center>0))
                risk_records.append({"risk_structure_id":rid,"coordinate_id":cid,"availability":rr["availability"],"continuous_center_inside":predicted,"p1_current_candidate":p1_risks.get(rid),"p1_boolean_consistent":None if predicted is None or rid not in p1_risks else predicted==p1_risks[rid]})
            dump_json(out/contract["storage"]["risk_structure_file"],{"risk_structure_margin_version":"relation_field_prediction_coordinates_p2_risk_margins","single_scalar_risk_score_produced":False,"records":risk_records})
            dump_json(out/contract["storage"]["difference_index_file"],diff)
            dump_json(out/contract["storage"]["origin_identity_file"],{"artifact_version":"relation_field_prediction_coordinates_p2_origin","origin_t":origin_t,"parent_p1_origin_manifest_sha256":canonical_digest(load_json(origin/"manifest.json")),"coordinate_registry_hash":canonical_digest(registry),"coordinate_count":len(records)})
            dump_json(out/contract["storage"]["origin_validation_file"],{"p2_origin_gate":"passed","future_payload_read":False,"precursor_validity_evaluated":False,"single_scalar_risk_score_produced":False,"parent_writeback_performed":False})
            write_manifest(out,"relation_field_prediction_coordinates_p2_origin")
            series_rows.append({"origin_t":origin_t,"available_coordinate_count":sum(r["availability"]=="available" for r in records.values()),"coordinate_count":len(records),"origin_manifest_sha256":canonical_digest(load_json(out/"manifest.json"))})
            history.append((origin_t,ctx,records))
        dump_json(tmp/contract["storage"]["series_identity_file"],{"artifact_version":"relation_field_prediction_coordinates_p2_series","parent_p1_tree_hash":p1_before,"parent_p1_contract_version":"relation_field_prediction_state_p1","contract_hash":canonical_digest(contract),"registry_hash":canonical_digest(registry),"origin_count":len(series_rows)})
        dump_json(tmp/contract["storage"]["series_index_file"],{"series_index_version":"relation_field_prediction_coordinates_p2_series_index","rows":series_rows})
        dump_json(tmp/contract["storage"]["series_validation_file"],{"p2_series_gate":"passed","builder_formula_path":"relation_field_prediction_coordinates_p2._builder","independent_validator_formula_path":"relation_field_prediction_coordinates_p2._independent_validator","formula_paths_are_distinct":True,"precursor_validity_evaluated":False,"prediction_accuracy_evaluated":False,"parent_writeback_performed":False})
        write_manifest(tmp,"relation_field_prediction_coordinates_p2_series")
        if tree_hash(p1_root)!=p1_before: raise RelationFieldPredictionCoordinatesP2Error("parent P1 source was modified")
        tmp.rename(target); return target
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True); raise
