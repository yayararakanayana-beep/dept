from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ._common import load_json
from ._builder_math import _I, _abs, _any_axis, _gt, _lt, _maximum, _minimum, _mul, _neg, _single, _source_single, _source_triplet, _sub

def _thresholds(origin: Path, p1_contract: Mapping[str, Any]) -> dict[str, float]:
    storage = p1_contract["storage"]
    parents = origin / str(storage["parent_artifact_dir"])
    rf7 = load_json(parents / str(storage["parent_stage_dirs"]["RF-7"]) / "contract.json")
    rf8 = load_json(parents / str(storage["parent_stage_dirs"]["RF-8"]) / "contract.json")
    rf9 = load_json(parents / str(storage["parent_stage_dirs"]["RF-9"]) / "contract.json")
    return {
        "shape_tol": float(rf7["transition_shape_metrics"]["shape_scalar_tolerance"]),
        "support_tol": float(rf7["transition_shape_metrics"]["effective_support_tolerance"]),
        "channel_tol": float(rf7["flow_channel_metrics"]["channel_change_tolerance"]),
        "persistence": float(rf9["risk_structure"]["boundary_persistence_threshold"]),
        "recovery_tol": float(rf9["risk_structure"]["boundary_recovery_change_tolerance"]),
        "sticking_inward": float(rf7["boundary_dynamics"]["maximum_inward_flow_for_sticking"]),
        "axis_tol": float(rf8["same_axis_dynamics"]["magnitude_tolerance"]),
        "energy_tol": float(rf9["risk_structure"]["energy_dominance_tolerance"]),
        "residual_fraction": float(rf9["unresolved_residual"]["dominance_fraction"]),
        "residual_floor": float(rf9["unresolved_residual"]["absolute_floor"]),
        "history_count": float(rf8["history_conditioned_innovation"]["minimum_prior_transition_count_for_label"]),
        "history_support": float(rf8["history_conditioned_innovation"]["minimum_effective_support_for_label"]),
    }


def _shape(ctx: Mapping[str, Any]) -> dict[str, _I] | None:
    p="rf7_transition_shape_metrics__"
    names=["total_variance_delta","entropy_delta","effective_support_delta","participation_delta","l2_concentration_delta","peak_mass_delta","major_component_count_delta","component_mass_entropy_delta"]
    vals={n:_source_single(ctx,p+n) for n in names}
    if any(v is None for v in vals.values()): return None
    t=ctx["thresholds"]; st=t["shape_tol"]; et=t["support_tol"]
    contraction=_minimum(_lt(vals["total_variance_delta"],-st,st),_lt(vals["entropy_delta"],-st,st),_lt(vals["effective_support_delta"],-et,et),_lt(vals["participation_delta"],-et,et))
    concentration=_minimum(_lt(vals["entropy_delta"],-st,st),_gt(vals["l2_concentration_delta"],st,st),_gt(vals["peak_mass_delta"],st,st))
    coalescence=_maximum(_lt(vals["major_component_count_delta"],0.0,1.0),_lt(vals["component_mass_entropy_delta"],-st,st))
    expansion=_minimum(_gt(vals["total_variance_delta"],st,st),_gt(vals["entropy_delta"],st,st),_gt(vals["effective_support_delta"],et,et),_gt(vals["participation_delta"],et,et))
    dispersion=_minimum(_gt(vals["entropy_delta"],st,st),_lt(vals["l2_concentration_delta"],-st,st),_lt(vals["peak_mass_delta"],-st,st))
    fragmentation=_maximum(_gt(vals["major_component_count_delta"],0.0,1.0),_gt(vals["component_mass_entropy_delta"],st,st))
    return {"contraction":contraction,"concentration":concentration,"coalescence":coalescence,"convergence":_maximum(contraction,concentration,coalescence),"expansion":expansion,"dispersion":dispersion,"fragmentation":fragmentation,"divergence":_maximum(expansion,dispersion,fragmentation)}


def _pathway(ctx: Mapping[str, Any]) -> dict[str, _I] | None:
    if ctx.get("previous") is None: return None
    keys=["rf7_flow_channel_metrics__effective_edge_support_minimum","rf7_flow_channel_metrics__effective_edge_support_mean","rf7_flow_channel_metrics__effective_edge_support_maximum"]
    conc=["rf7_flow_channel_metrics__maximum_edge_fraction_minimum","rf7_flow_channel_metrics__maximum_edge_fraction_mean","rf7_flow_channel_metrics__maximum_edge_fraction_maximum"]
    now=_source_triplet(ctx,keys); old=_source_triplet(ctx["previous"],keys); cn=_source_triplet(ctx,conc); co=_source_triplet(ctx["previous"],conc)
    if any(x is None for x in (now,old,cn,co)): return None
    dw=_sub(now,old); dc=_sub(cn,co); tol=ctx["thresholds"]["channel_tol"]
    return {"narrowing":_minimum(_lt(dw,-tol,tol),_gt(dc,tol,tol)),"widening":_minimum(_gt(dw,tol,tol),_lt(dc,-tol,tol)),"width_delta":dw}


def _same_axis(ctx: Mapping[str, Any]) -> dict[str, _I] | None:
    if ctx.get("previous") is None: return None
    keys=["rf8_axis_flow_family__axis_signed_flow_minimum","rf8_axis_flow_family__axis_signed_flow_mean","rf8_axis_flow_family__axis_signed_flow_maximum"]
    now=_source_triplet(ctx,keys); old=_source_triplet(ctx["previous"],keys)
    if now is None or old is None: return None
    tol=ctx["thresholds"]["axis_tol"]
    product=_mul(now,old); same=_gt(product,0.0,tol*tol)
    mag_delta=_sub(_abs(now),_abs(old))
    amplification=_minimum(same,_gt(mag_delta,tol,tol))
    decay=_minimum(same,_lt(mag_delta,-tol,tol))
    reversal=_lt(product,0.0,tol*tol)
    old_active=_gt(_abs(old),tol,tol); now_stopped=_lt(_abs(now),tol,tol)
    stop=_minimum(old_active,now_stopped)
    return {"amplification":_any_axis(amplification),"decay":_any_axis(decay),"reversal":_any_axis(reversal),"stop":_any_axis(stop)}


def _recovery(ctx: Mapping[str, Any], pathway: Mapping[str,_I] | None, same: Mapping[str,_I] | None, shape: Mapping[str,_I] | None) -> dict[str,_I] | None:
    if ctx.get("previous") is None or pathway is None or same is None or shape is None: return None
    persistence=_source_single(ctx,"rf7_boundary_dynamics__boundary_mass_persistence")
    inward=_source_single(ctx,"rf7_boundary_dynamics__mass_weighted_inward_flow_mean")
    old=_source_single(ctx["previous"],"rf7_boundary_dynamics__mass_weighted_inward_flow_mean")
    if persistence is None or inward is None or old is None: return None
    t=ctx["thresholds"]
    sticking=_minimum(_gt(persistence,t["persistence"],max(t["persistence"],1e-12)),_lt(inward,t["sticking_inward"],max(t["sticking_inward"],1e-9)))
    change=_sub(inward,old)
    declining=_minimum(_gt(persistence,t["persistence"],max(t["persistence"],1e-12)),_lt(change,-t["recovery_tol"],t["recovery_tol"]))
    weakening=_maximum(sticking,declining)
    strengthening=_maximum(_gt(change,t["recovery_tol"],t["recovery_tol"]),pathway["widening"],same["reversal"],shape["expansion"],shape["dispersion"])
    return {"weakening":weakening,"strengthening":strengthening,"return_suppression":_minimum(weakening,_neg(strengthening))}


def _residual(ctx: Mapping[str, Any]) -> tuple[_I,_I] | None:
    keys=["rf8_unresolved_residual_ledger__residual_l1_minimum","rf8_unresolved_residual_ledger__residual_l1_mean","rf8_unresolved_residual_ledger__residual_l1_maximum"]
    residual=_source_triplet(ctx,keys); tvd=_source_single(ctx,"rf7_transition_shape_metrics__total_variation_distance")
    if residual is None or tvd is None: return None
    floor=ctx["thresholds"]["residual_floor"]; observed=2.0*tvd.center
    denominator=np.maximum(observed,floor)
    ratio=_I(residual.lower/denominator,residual.center/denominator,residual.upper/denominator)
    dominance=_minimum(_gt(residual,floor,floor),_gt(ratio,ctx["thresholds"]["residual_fraction"],ctx["thresholds"]["residual_fraction"]))
    return ratio,dominance


def _energy(ctx: Mapping[str, Any]) -> tuple[_I,_I] | None:
    gmin=_source_single(ctx,"rf7_flow_channel_metrics__gradient_energy_minimum"); gmax=_source_single(ctx,"rf7_flow_channel_metrics__gradient_energy_maximum")
    cmin=_source_single(ctx,"rf7_flow_channel_metrics__circulation_energy_minimum"); cmax=_source_single(ctx,"rf7_flow_channel_metrics__circulation_energy_maximum")
    if any(x is None for x in (gmin,gmax,cmin,cmax)): return None
    tol=ctx["thresholds"]["energy_tol"]
    return _gt(_sub(gmin,cmax),tol,max(tol,1e-12)),_gt(_sub(cmin,gmax),tol,max(tol,1e-12))


def _coordinate_value(entry: Mapping[str,Any], ctx: dict[str,Any], computed: Mapping[str,dict[str,Any]], previous_records: Mapping[str,dict[str,Any]] | None, previous_previous_records: Mapping[str,dict[str,Any]] | None) -> tuple[_I|None,str|None]:
    formula=str(entry["formula"]); cid=str(entry["coordinate_id"])
    if formula=="reserved": return None,"reserved_not_implemented"
    if formula=="axis_signed_triplet": return _source_triplet(ctx,entry["source_feature_ids"]),"missing_source"
    if formula in {"pathway_width_triplet","recovery_inward_triplet"}: return _source_triplet(ctx,entry["source_feature_ids"]),"missing_source"
    if formula in {"optional_source", "absolute_optional_source", "optional_triplet", "matrix_diagonal"}:
        keys=list(entry.get("source_feature_ids",[]))
        if formula == "optional_triplet":
            return _source_triplet(ctx, keys), "missing_source"
        source = _source_single(ctx, keys[0]) if keys else None
        if source is None:
            return None, "missing_source"
        if formula == "absolute_optional_source":
            return _abs(source), None
        if formula == "matrix_diagonal":
            if source.center.ndim != 2 or source.center.shape[0] != source.center.shape[1]:
                return None, "shape_mismatch"
            return _I(np.diag(source.lower), np.diag(source.center), np.diag(source.upper)), None
        return source, None
    if formula=="absolute_of":
        dep=computed.get(entry["dependencies"][0]); return (None,"missing_dependency") if not dep or dep["availability"]!="available" else (_abs(dep["value"]),None)
    if formula in {"change_rate","change_acceleration"}:
        dep=entry["dependencies"][0]
        cur=computed.get(dep); prev=None if previous_records is None else previous_records.get(dep)
        if not cur or cur["availability"]!="available" or not prev or prev["availability"]!="available": return None,"insufficient_history"
        dt=float(ctx["origin_t"]-ctx["previous"]["origin_t"])
        if dt<=0 or cur["value"].center.shape!=prev["value"].center.shape: return None,"identity_mismatch"
        first=_I((cur["value"].lower-prev["value"].upper)/dt,(cur["value"].center-prev["value"].center)/dt,(cur["value"].upper-prev["value"].lower)/dt)
        if formula=="change_rate": return first,None
        prevprev=None if previous_previous_records is None else previous_previous_records.get(dep)
        if not prevprev or prevprev["availability"]!="available": return None,"insufficient_history"
        pdt=float(ctx["previous"]["origin_t"]-ctx["previous_previous"]["origin_t"])
        if pdt<=0 or prev["value"].center.shape!=prevprev["value"].center.shape: return None,"identity_mismatch"
        pfirst=_I((prev["value"].lower-prevprev["value"].upper)/pdt,(prev["value"].center-prevprev["value"].center)/pdt,(prev["value"].upper-prevprev["value"].lower)/pdt)
        gap=((ctx["origin_t"]+ctx["previous"]["origin_t"])-(ctx["previous"]["origin_t"]+ctx["previous_previous"]["origin_t"]))/2.0
        return _I((first.lower-pfirst.upper)/gap,(first.center-pfirst.center)/gap,(first.upper-pfirst.lower)/gap),None
    if formula=="aggregate_candidate_width":
        widths=[r["value"].upper-r["value"].lower for r in computed.values() if r["availability"]=="available" and r["coordinate_role"]=="state"]
        if not widths: return None,"missing_source"
        vals=np.asarray([float(np.max(w)) for w in widths]); return _single(float(np.max(vals))),None
    if formula=="availability_ratio": return None,"deferred"
    if formula=="identity_stability":
        if ctx.get("previous") is None: return None,"insufficient_history"
        cur={k:v.get("comparability_id") for k,v in ctx["index"].items()}; old={k:v.get("comparability_id") for k,v in ctx["previous"]["index"].items()}
        common=set(cur)&set(old)
        return (_single(sum(cur[k]==old[k] for k in common)/len(common)),None) if common else (None,"missing_source")
    if formula=="history_coverage":
        count=_source_single(ctx,"rf8_history_conditioned_innovation__prior_transition_count"); support=_source_single(ctx,"rf8_history_conditioned_innovation__effective_support")
        if count is None or support is None: return None,"missing_source"
        t=ctx["thresholds"]; return _minimum(_gt(count,t["history_count"],max(t["history_count"],1.0)),_gt(support,t["history_support"],max(t["history_support"],1.0))),None
    if formula in {"residual_ratio","residual_dominance"}:
        value=ctx["residual"]; return (None,"missing_source") if value is None else (value[0 if formula=="residual_ratio" else 1],None)
    shape=ctx["shape"]
    if formula.startswith("shape_"):
        key=formula.removeprefix("shape_"); return (None,"missing_source") if shape is None else (shape[key],None)
    pathway=ctx["pathway"]
    if formula in {"pathway_narrowing","pathway_widening"}: return (None,"insufficient_history") if pathway is None else (pathway[formula.split("_")[-1]],None)
    same=ctx["same_axis"]
    if formula.startswith("same_axis_"):
        key={"same_axis_amplification":"amplification","same_axis_decay":"decay","same_axis_stop":"stop","same_axis_reversal":"reversal"}[formula]
        return (None,"insufficient_history") if same is None else (same[key],None)
    recovery=ctx["recovery"]
    if formula in {"recovery_weakening","recovery_strengthening","return_suppression"}:
        key=formula.removeprefix("recovery_")
        return (None,"insufficient_history") if recovery is None else (recovery[key],None)
    if formula=="gradient_dominance" or formula=="circulation_dominance":
        value=ctx["energy"]; return (None,"missing_source") if value is None else (value[0 if formula=="gradient_dominance" else 1],None)
    risks={
      "risk_overconvergence":("p2.condition.shape.convergence","p2.condition.pathway.narrowing","p2.condition.same_axis.amplification"),
      "risk_fixation":("p2.risk.overconvergence.structure_margin","p2.condition.recovery.return_suppression"),
      "risk_divergence":("p2.condition.shape.divergence","p2.condition.pathway.widening","__decay_or_stop__"),
      "risk_recovery_margin_reduction":("p2.condition.recovery.weakening","__not_strengthening__"),
    }
    if formula in risks:
        vals=[]
        for dep in risks[formula]:
            if dep=="__decay_or_stop__":
                a=computed.get("p2.condition.same_axis.decay"); b=computed.get("p2.condition.same_axis.axis_stop")
                if not a or not b or a["availability"]!="available" or b["availability"]!="available": return None,"missing_dependency"
                vals.append(_maximum(a["value"],b["value"])); continue
            if dep=="__not_strengthening__":
                a=computed.get("p2.condition.recovery.strengthening")
                if not a or a["availability"]!="available": return None,"missing_dependency"
                vals.append(_neg(a["value"])); continue
            row=computed.get(dep)
            if not row or row["availability"]!="available": return None,"missing_dependency"
            vals.append(row["value"])
        return _minimum(*vals),None
    return None,"unsupported_formula"

