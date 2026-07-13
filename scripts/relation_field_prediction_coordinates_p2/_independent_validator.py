from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ._common import (
    RelationFieldPredictionCoordinatesP2Error,
    arrays_close,
    canonical_digest,
    load_json,
    load_npz,
    p1_origin_paths,
    tree_hash,
    verify_manifest,
)
from ._validator_recompute import expected_arrays, expected_differences, recompute_origin

# This module and its validator-only helpers do not import builder code.

def validate_coordinate_series(p2_series_dir:str|Path,p1_series_dir:str|Path,*,contract:Mapping[str,Any],registry:Mapping[str,Any]) -> dict[str,Any]:
    p2=Path(p2_series_dir).resolve();p1=Path(p1_series_dir).resolve();p1_before=tree_hash(p1)
    verify_manifest(p2)
    if load_json(p2/"contract.json")!=dict(contract):raise RelationFieldPredictionCoordinatesP2Error("P2 stored contract mismatch")
    if load_json(p2/"coordinate_registry.json")!=dict(registry):raise RelationFieldPredictionCoordinatesP2Error("P2 stored registry mismatch")
    p1_contract,origins=p1_origin_paths(p1);storage=contract["storage"];history=[]
    for origin_t,origin,state in origins:
        previous=history[-1] if history else None;older=history[-2] if len(history)>1 else None
        ctx,records=recompute_origin(registry["entries"],origin_t,origin,state,p1_contract,None if previous is None else previous[1],None if older is None else older[1],None if previous is None else previous[2],None if older is None else older[2])
        out=p2/str(storage["origin_container_dir"])/str(storage["origin_name_format"]).format(origin_t=origin_t);verify_manifest(out)
        arrays_close(expected_arrays(records),load_npz(out/str(storage["coordinate_file"])),"independent coordinate")
        first,second=expected_differences(origin_t,records,None if previous is None else previous[0],None if previous is None else previous[2],None if older is None else older[0],None if older is None else older[2])
        arrays_close(first,load_npz(out/str(storage["first_difference_file"])),"independent first difference");arrays_close(second,load_npz(out/str(storage["second_difference_file"])),"independent second difference")
        saved_index=load_json(out/str(storage["coordinate_index_file"]));by_id={str(r["coordinate_id"]):r for r in saved_index["records"]}
        if set(by_id)!=set(records):raise RelationFieldPredictionCoordinatesP2Error("coordinate index ID mismatch")
        for cid,row in records.items():
            if by_id[cid].get("availability")!=row["availability"]:raise RelationFieldPredictionCoordinatesP2Error(f"coordinate availability mismatch: {cid}")
            expected_reason=[] if row["availability"]=="available" else [row["reason"]]
            if by_id[cid].get("unavailable_reasons")!=expected_reason:raise RelationFieldPredictionCoordinatesP2Error(f"coordinate unavailability reason mismatch: {cid}")
        risk=load_json(out/str(storage["risk_structure_file"]));p1risk={str(r["risk_structure_id"]):bool(r["current_candidate"]) for r in load_json(state/str(p1_contract["storage"]["risk_state_file"]))["records"]}
        mapping={"overconvergence":"p2.risk.overconvergence.structure_margin","fixation":"p2.risk.fixation.structure_margin","divergence":"p2.risk.divergence.structure_margin","recovery_margin_reduction":"p2.risk.recovery_margin_reduction.structure_margin"}
        for rr in risk["records"]:
            rid=rr["risk_structure_id"];row=records[mapping[rid]];inside=None if row["availability"]!="available" else bool(np.all(row["value"][1]>0))
            if rr.get("continuous_center_inside")!=inside or rr.get("p1_current_candidate")!=p1risk.get(rid):raise RelationFieldPredictionCoordinatesP2Error(f"risk structure record mismatch: {rid}")
            if inside is not None and rr.get("p1_boolean_consistent")!=(inside==p1risk[rid]):raise RelationFieldPredictionCoordinatesP2Error(f"risk consistency record mismatch: {rid}")
        history.append((origin_t,ctx,records))
    if tree_hash(p1)!=p1_before:raise RelationFieldPredictionCoordinatesP2Error("parent P1 source was modified during independent validation")
    validation=load_json(p2/str(storage["series_validation_file"]))
    if validation.get("formula_paths_are_distinct") is not True or validation.get("precursor_validity_evaluated") is not False:raise RelationFieldPredictionCoordinatesP2Error("P2 validation claim boundary mismatch")
    return {"p2_series_gate":"passed","origin_count":len(origins),"coordinate_count":len(registry["entries"]),"independent_formula_recomputation":True,"builder_formula_module_imported":False,"precursor_validity_evaluated":False,"prediction_accuracy_evaluated":False}
