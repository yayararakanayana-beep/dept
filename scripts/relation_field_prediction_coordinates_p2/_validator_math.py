from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ._common import RelationFieldPredictionCoordinatesP2Error, load_json

# All coordinate mathematics below is a second implementation used only for validation.

Q = tuple[np.ndarray, np.ndarray, np.ndarray]


def q_make(lo: Any, ce: Any, hi: Any) -> Q:
    a,b,c=np.broadcast_arrays(np.asarray(lo,dtype=float),np.asarray(ce,dtype=float),np.asarray(hi,dtype=float))
    low=np.minimum.reduce([a,b,c]); high=np.maximum.reduce([a,b,c])
    if np.any(~np.isfinite(low)) or np.any(~np.isfinite(b)) or np.any(~np.isfinite(high)):
        raise RelationFieldPredictionCoordinatesP2Error("independent interval nonfinite")
    return np.ascontiguousarray(low),np.ascontiguousarray(b),np.ascontiguousarray(high)


def q_one(x: Any) -> Q:
    a=np.asarray(x,dtype=float); return q_make(a,a,a)


def q_neg(x: Q) -> Q: return -x[2],-x[1],-x[0]

def q_sub(x: Q,y: Q) -> Q: return x[0]-y[2],x[1]-y[1],x[2]-y[0]

def q_abs(x: Q) -> Q:
    lo=np.where((x[0]<=0)&(x[2]>=0),0,np.minimum(np.abs(x[0]),np.abs(x[2])))
    return lo,np.abs(x[1]),np.maximum(np.abs(x[0]),np.abs(x[2]))

def q_mul(x: Q,y: Q) -> Q:
    candidates=np.stack([x[0]*y[0],x[0]*y[2],x[2]*y[0],x[2]*y[2]])
    return np.min(candidates,axis=0),x[1]*y[1],np.max(candidates,axis=0)

def q_reduce(values: list[np.ndarray], use_minimum: bool) -> np.ndarray:
    broadcast=np.broadcast_arrays(*values);result=broadcast[0]
    for value in broadcast[1:]:result=np.minimum(result,value) if use_minimum else np.maximum(result,value)
    return result

def q_and(*xs: Q) -> Q: return q_reduce([x[0] for x in xs],True),q_reduce([x[1] for x in xs],True),q_reduce([x[2] for x in xs],True)

def q_or(*xs: Q) -> Q: return q_reduce([x[0] for x in xs],False),q_reduce([x[1] for x in xs],False),q_reduce([x[2] for x in xs],False)

def q_above(x: Q,b: float,s: float) -> Q:
    d=max(abs(float(s)),1e-12); return (x[0]-b)/d,(x[1]-b)/d,(x[2]-b)/d

def q_below(x: Q,b: float,s: float) -> Q:
    d=max(abs(float(s)),1e-12); return (b-x[2])/d,(b-x[1])/d,(b-x[0])/d

def q_any(x: Q) -> Q:
    if x[1].ndim==0:return q_make(x[0],x[1],x[2])
    axes=tuple(range(x[1].ndim)); return q_make(np.max(x[0],axis=axes),np.max(x[1],axis=axes),np.max(x[2],axis=axes))


def index_map(payload: Mapping[str,Any]) -> dict[str,Mapping[str,Any]]:
    return {str(r["array_key"]):r for r in payload["arrays"]}


def src(ctx: Mapping[str,Any],key: str) -> np.ndarray|None:
    if key not in ctx["arrays"] or key not in ctx["index"]: return None
    a=np.asarray(ctx["arrays"][key])
    if a.dtype.kind not in "fiu" or a.size==0 or np.any(~np.isfinite(a)): return None
    return np.asarray(a,dtype=float)


def src_one(ctx: Mapping[str,Any],key: str) -> Q|None:
    a=src(ctx,key); return None if a is None else q_one(a)


def src_three(ctx: Mapping[str,Any],keys: Sequence[str]) -> Q|None:
    values=[src(ctx,k) for k in keys]
    if any(v is None for v in values): return None
    return q_make(values[0],values[1],values[2])


def read_limits(origin: Path,p1: Mapping[str,Any]) -> dict[str,float]:
    s=p1["storage"]; root=origin/str(s["parent_artifact_dir"])
    seven=load_json(root/str(s["parent_stage_dirs"]["RF-7"])/"contract.json")
    eight=load_json(root/str(s["parent_stage_dirs"]["RF-8"])/"contract.json")
    nine=load_json(root/str(s["parent_stage_dirs"]["RF-9"])/"contract.json")
    return {
      "shape":float(seven["transition_shape_metrics"]["shape_scalar_tolerance"]),
      "support":float(seven["transition_shape_metrics"]["effective_support_tolerance"]),
      "channel":float(seven["flow_channel_metrics"]["channel_change_tolerance"]),
      "persist":float(nine["risk_structure"]["boundary_persistence_threshold"]),
      "recover":float(nine["risk_structure"]["boundary_recovery_change_tolerance"]),
      "stick":float(seven["boundary_dynamics"]["maximum_inward_flow_for_sticking"]),
      "axis":float(eight["same_axis_dynamics"]["magnitude_tolerance"]),
      "energy":float(nine["risk_structure"]["energy_dominance_tolerance"]),
      "fraction":float(nine["unresolved_residual"]["dominance_fraction"]),
      "floor":float(nine["unresolved_residual"]["absolute_floor"]),
      "history_count":float(eight["history_conditioned_innovation"]["minimum_prior_transition_count_for_label"]),
      "history_support":float(eight["history_conditioned_innovation"]["minimum_effective_support_for_label"]),
    }


def shape_checks(ctx: Mapping[str,Any]) -> dict[str,Q]|None:
    pre="rf7_transition_shape_metrics__"
    required=["total_variance_delta","entropy_delta","effective_support_delta","participation_delta","l2_concentration_delta","peak_mass_delta","major_component_count_delta","component_mass_entropy_delta"]
    v={name:src_one(ctx,pre+name) for name in required}
    if any(item is None for item in v.values()): return None
    a=ctx["limits"]["shape"]; e=ctx["limits"]["support"]
    contract=q_and(q_below(v["total_variance_delta"],-a,a),q_below(v["entropy_delta"],-a,a),q_below(v["effective_support_delta"],-e,e),q_below(v["participation_delta"],-e,e))
    concentrate=q_and(q_below(v["entropy_delta"],-a,a),q_above(v["l2_concentration_delta"],a,a),q_above(v["peak_mass_delta"],a,a))
    merge=q_or(q_below(v["major_component_count_delta"],0,1),q_below(v["component_mass_entropy_delta"],-a,a))
    expand=q_and(q_above(v["total_variance_delta"],a,a),q_above(v["entropy_delta"],a,a),q_above(v["effective_support_delta"],e,e),q_above(v["participation_delta"],e,e))
    disperse=q_and(q_above(v["entropy_delta"],a,a),q_below(v["l2_concentration_delta"],-a,a),q_below(v["peak_mass_delta"],-a,a))
    fragment=q_or(q_above(v["major_component_count_delta"],0,1),q_above(v["component_mass_entropy_delta"],a,a))
    return {"contraction":contract,"concentration":concentrate,"coalescence":merge,"convergence":q_or(contract,concentrate,merge),"expansion":expand,"dispersion":disperse,"fragmentation":fragment,"divergence":q_or(expand,disperse,fragment)}


def pathway_checks(ctx: Mapping[str,Any]) -> dict[str,Q]|None:
    old=ctx.get("previous")
    if old is None:return None
    support=[f"rf7_flow_channel_metrics__effective_edge_support_{x}" for x in ("minimum","mean","maximum")]
    concentration=[f"rf7_flow_channel_metrics__maximum_edge_fraction_{x}" for x in ("minimum","mean","maximum")]
    a=src_three(ctx,support); b=src_three(old,support); c=src_three(ctx,concentration); d=src_three(old,concentration)
    if any(x is None for x in (a,b,c,d)):return None
    dw=q_sub(a,b); dc=q_sub(c,d); tol=ctx["limits"]["channel"]
    return {"narrowing":q_and(q_below(dw,-tol,tol),q_above(dc,tol,tol)),"widening":q_and(q_above(dw,tol,tol),q_below(dc,-tol,tol)),"width_delta":dw}


def axis_checks(ctx: Mapping[str,Any]) -> dict[str,Q]|None:
    old=ctx.get("previous")
    if old is None:return None
    keys=[f"rf8_axis_flow_family__axis_signed_flow_{x}" for x in ("minimum","mean","maximum")]
    a=src_three(ctx,keys); b=src_three(old,keys)
    if a is None or b is None:return None
    tol=ctx["limits"]["axis"]; product=q_mul(a,b); same=q_above(product,0,tol*tol); delta=q_sub(q_abs(a),q_abs(b))
    return {"amplification":q_any(q_and(same,q_above(delta,tol,tol))),"decay":q_any(q_and(same,q_below(delta,-tol,tol))),"reversal":q_any(q_below(product,0,tol*tol)),"stop":q_any(q_and(q_above(q_abs(b),tol,tol),q_below(q_abs(a),tol,tol)))}


def recovery_checks(ctx: Mapping[str,Any],path: Mapping[str,Q]|None,axis: Mapping[str,Q]|None,shape: Mapping[str,Q]|None) -> dict[str,Q]|None:
    old=ctx.get("previous")
    if old is None or path is None or axis is None or shape is None:return None
    persist=src_one(ctx,"rf7_boundary_dynamics__boundary_mass_persistence"); inward=src_one(ctx,"rf7_boundary_dynamics__mass_weighted_inward_flow_mean"); prior=src_one(old,"rf7_boundary_dynamics__mass_weighted_inward_flow_mean")
    if persist is None or inward is None or prior is None:return None
    lim=ctx["limits"]; change=q_sub(inward,prior)
    sticking=q_and(q_above(persist,lim["persist"],max(lim["persist"],1e-12)),q_below(inward,lim["stick"],max(lim["stick"],1e-9)))
    decline=q_and(q_above(persist,lim["persist"],max(lim["persist"],1e-12)),q_below(change,-lim["recover"],lim["recover"]))
    weak=q_or(sticking,decline)
    strong=q_or(q_above(change,lim["recover"],lim["recover"]),path["widening"],axis["reversal"],shape["expansion"],shape["dispersion"])
    return {"weakening":weak,"strengthening":strong,"return_suppression":q_and(weak,q_neg(strong))}


def residual_checks(ctx: Mapping[str,Any]) -> tuple[Q,Q]|None:
    keys=[f"rf8_unresolved_residual_ledger__residual_l1_{x}" for x in ("minimum","mean","maximum")]
    r=src_three(ctx,keys); tv=src_one(ctx,"rf7_transition_shape_metrics__total_variation_distance")
    if r is None or tv is None:return None
    floor=ctx["limits"]["floor"]; denom=np.maximum(2*tv[1],floor); ratio=(r[0]/denom,r[1]/denom,r[2]/denom)
    dominance=q_and(q_above(r,floor,floor),q_above(ratio,ctx["limits"]["fraction"],ctx["limits"]["fraction"]))
    return ratio,dominance


def energy_checks(ctx: Mapping[str,Any]) -> tuple[Q,Q]|None:
    gm=src_one(ctx,"rf7_flow_channel_metrics__gradient_energy_minimum"); gx=src_one(ctx,"rf7_flow_channel_metrics__gradient_energy_maximum"); cm=src_one(ctx,"rf7_flow_channel_metrics__circulation_energy_minimum"); cx=src_one(ctx,"rf7_flow_channel_metrics__circulation_energy_maximum")
    if any(x is None for x in (gm,gx,cm,cx)):return None
    tol=ctx["limits"]["energy"]
    return q_above(q_sub(gm,cx),tol,max(tol,1e-12)),q_above(q_sub(cm,gx),tol,max(tol,1e-12))

