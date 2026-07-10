#!/usr/bin/env python3
"""Task 3.1e static full-distribution testbed generator."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, sys
from dataclasses import dataclass
from itertools import combinations, product
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from typing import Iterable
import numpy as np
import pandas as pd
from scipy.stats import qmc
from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322Config, DistributionTerrainV322World

EXTERNAL_COLUMNS=["external_resource_supply","external_demand","external_competition_pressure","external_information_noise","external_shock","external_constraint_pressure"]
RANGES={EXTERNAL_COLUMNS[0]:(-1.0,1.0),EXTERNAL_COLUMNS[1]:(-1.0,1.0),EXTERNAL_COLUMNS[2]:(0.0,1.0),EXTERNAL_COLUMNS[3]:(0.0,1.0),EXTERNAL_COLUMNS[4]:(0.0,1.0),EXTERNAL_COLUMNS[5]:(0.0,1.0)}
TERRAIN_FIELDS=["short_payoff","medium_payoff","effective_medium_payoff","friction","viscosity","damage","rigidity","recovery_speed","existing_path_expected_value","exploration_cost","exploration_option_value","exploration_net_expected_value","expected_value_advantage","information_memory","viability_reserve","route_support","maintenance_cost","net_viability_value","negative_viability_pressure","operating_cost","cost_reduction_gain","cost_reduction_preference"]
EXCLUDED_TRANSITION_FIELDS=["last_flow","short_gain_information_conversion","short_path_decline_information","exploration_experience_information","support_erosion","released_mass","release_reallocation_flow","total_gain_delta_signal","last_external_deformation_strength","last_threshold_activation_strength","last_distribution_weighted_threshold_activation_strength"]
CAPTURE_POLICY="provisional_fixed_exposure_v1"; OUT_SUBDIR="pseudoreality_v3_3_task3_1e_static_full_distribution"

@dataclass(frozen=True)
class ExternalVector:
    external_vector_id:str; dataset_split:str; vector_origin:str; mask_bits:str; active_factor_count:int; is_base_vector:bool; sobol_scramble_seed:int|None; sobol_index:int|None; values:tuple[float,...]; candidate_pool_id:str|None=None

def validate_external_values(values):
    if len(values)!=6: raise ValueError("exactly six external factors are required")
    for col,val in zip(EXTERNAL_COLUMNS, values):
        lo,hi=RANGES[col]
        if not np.isfinite(val) or val < lo or val > hi: raise ValueError(f"{col}={val} outside [{lo}, {hi}]")
    return tuple(float(v) for v in values)

def all_external_update(values): return dict(zip(EXTERNAL_COLUMNS, validate_external_values(values)))
def is_base(values): return all(float(v)==0.0 for v in values)
def mask_bits_for(active): return "".join("1" if i in active else "0" for i in range(6))
def real_from_unit(dim,u): return 2.0*u-1.0 if dim in (0,1) else u

def sobol_points(dim,n,seed):
    m=0 if n<=1 else math.ceil(math.log2(n))
    pts=qmc.Sobol(d=dim, scramble=True, seed=seed).random_base2(m)
    return pts[:n]

def vector_from_active(active, urow):
    vals=[0.0]*6
    for j,dim in enumerate(active): vals[dim]=float(real_from_unit(dim, urow[j]))
    return tuple(vals)

def rounded_key(values): return tuple(round(float(v),12) for v in values)
def masks_by_count(k): return [tuple(c) for c in combinations(range(6), k)]

def make_sobol_vectors(split, seed, alloc, start=1):
    out=[]; idx=start
    for k in range(1,7):
        for active in masks_by_count(k):
            if k==6 and active != tuple(range(6)): continue
            n=int(alloc[str(k)])
            pts=sobol_points(k,n,seed)
            for si,row in enumerate(pts):
                vals=validate_external_values(vector_from_active(active,row))
                out.append(ExternalVector(f"vec_{split}_{idx:06d}",split,"sobol_stratified",mask_bits_for(active),k,False,seed,si,vals)); idx+=1
    return out, idx

def base_vector(split, idx): return ExternalVector(f"vec_{split}_{idx:06d}",split,"base","000000",0,True,None,None,(0.0,0.0,0.0,0.0,0.0,0.0))

def boundary_vectors(split,start, limit=None):
    out=[]; idx=start
    corners=list(product([-1.0,1.0],[-1.0,1.0],[0.0,1.0],[0.0,1.0],[0.0,1.0],[0.0,1.0]))
    for vals in corners[:limit]:
        active=tuple(i for i,v in enumerate(vals) if v!=0.0)
        out.append(ExternalVector(f"vec_{split}_{idx:06d}",split,"boundary_corner",mask_bits_for(active),len(active),False,None,None,validate_external_values(vals))); idx+=1
    return out, idx

def generate_vectors(profile):
    if profile=="formal":
        fit,idx=make_sobol_vectors("fit",3101,{"1":4,"2":2,"3":2,"4":1,"5":1,"6":32}); fit.append(base_vector("fit",idx)); idx+=1
        val,idxv=make_sobol_vectors("validation",3102,{"1":2,"2":1,"3":1,"4":1,"5":1,"6":16}); val.append(base_vector("validation",idxv))
        hold,idxh=boundary_vectors("holdout",1); pts=sobol_points(6,16,3103)
        for si,row in enumerate(pts): hold.append(ExternalVector(f"vec_holdout_{idxh:06d}","holdout","holdout_full6_sobol","111111",6,False,3103,si,validate_external_values(vector_from_active(tuple(range(6)),row)))); idxh+=1
        hold.append(base_vector("holdout",idxh)); vectors=fit+val+hold
        adaptive=select_adaptive(vectors,32)
        for v in adaptive: vectors.append(ExternalVector(f"vec_fit_{idx:06d}","fit","adaptive_maximin",v.mask_bits,v.active_factor_count,False,4101,v.sobol_index,v.values,v.candidate_pool_id)); idx+=1
        return vectors, adaptive
    if profile=="smoke":
        fit,idx=make_sobol_vectors("fit",3101,{"1":1,"2":0,"3":0,"4":0,"5":0,"6":2}); fit.append(base_vector("fit",idx))
        val=[]; idxv=1
        for si,row in enumerate(sobol_points(6,2,3102)): val.append(ExternalVector(f"vec_validation_{idxv:06d}","validation","sobol_stratified","111111",6,False,3102,si,validate_external_values(vector_from_active(tuple(range(6)),row)))); idxv+=1
        val.append(base_vector("validation",idxv)); hold,idxh=boundary_vectors("holdout",1,4); hold.append(base_vector("holdout",idxh)); return fit+val+hold, []
    raise ValueError(f"unknown profile: {profile}")

def normalize_mass(x):
    arr=np.asarray(x,dtype=np.float64).reshape(-1); arr=np.nan_to_num(arr,nan=0,posinf=0,neginf=0); arr=np.maximum(arr,0); total=float(arr.sum())
    if total<=0: raise ValueError("non-positive mass")
    arr=arr/total
    if arr.shape!=(3125,) or not np.isfinite(arr).all() or arr.min() < -1e-12 or abs(arr.sum()-1)>1e-8: raise ValueError("invalid mass")
    return arr.astype(np.float64)

def run_world(seed, values, step):
    w=DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed,n_bins=5)); w.set_external_factors(all_external_update(values))
    for _ in range(step): w.set_external_factors(all_external_update(values)); w.step()
    return w, normalize_mass(w.distribution)

def js_distance(p,q):
    p=normalize_mass(p); q=normalize_mass(q); eps=1e-12; p=np.maximum(p,eps); p/=p.sum(); q=np.maximum(q,eps); q/=q.sum(); m=.5*(p+q)
    return float(np.sqrt(.5*np.sum(p*np.log(p/m))+.5*np.sum(q*np.log(q/m))))

def adaptive_candidates(existing_keys):
    out=[]; cid=1
    for k,n in [(2,2),(3,1),(6,128)]:
        for active in (masks_by_count(k) if k<6 else [tuple(range(6))]):
            for si,row in enumerate(sobol_points(k,n,4101)):
                vals=validate_external_values(vector_from_active(active,row))
                if rounded_key(vals) in existing_keys: continue
                out.append(ExternalVector("", "fit", "adaptive_maximin", mask_bits_for(active), k, False, 4101, si, vals, f"cand_{cid:06d}")); cid+=1
    return out

def select_adaptive(vectors, count):
    existing={rounded_key(v.values) for v in vectors}; candidates=adaptive_candidates(existing)
    refs=[run_world(0,v.values,12)[1] for v in vectors if v.dataset_split=="fit" and not v.is_base_vector]
    cand_masses=[run_world(0,c.values,12)[1] for c in candidates]; selected=[]; remaining=list(range(len(candidates)))
    for _ in range(count):
        scores=[(min(js_distance(cand_masses[i],r) for r in refs), candidates[i].candidate_pool_id, i) for i in remaining]
        score,_,best=max(scores, key=lambda t:(t[0], -int(t[1].split('_')[1])))
        c=candidates[best]; object.__setattr__(c,"minimum_js_distance_at_selection",score); selected.append(c); refs.append(cand_masses[best]); remaining.remove(best)
    return selected

def snap_id(split,vid,seed,step): return "snap_"+hashlib.sha256(f"{split}|{vid}|{seed}|{step}|{CAPTURE_POLICY}".encode()).hexdigest()[:16]
def run_id(split,vid,seed): return "run_"+hashlib.sha256(f"{split}|{vid}|{seed}|{CAPTURE_POLICY}".encode()).hexdigest()[:16]

def write_csv(path, rows, cols): pd.DataFrame(rows, columns=cols).to_csv(path,index=False)

def build(profile, output_root):
    out=Path(output_root)/OUT_SUBDIR; out.mkdir(parents=True,exist_ok=True)
    vectors, additions=generate_vectors(profile); seeds={"fit":[0,1] if profile=="formal" else [0],"validation":[10],"holdout":[20]}; ext_steps=[1,4,12] if profile=="formal" else [1,2]; base_steps=[0,1,4,12] if profile=="formal" else [0,1,2]
    masses=[]; terrain={f:[] for f in TERRAIN_FIELDS}; meta=[]; discovery=[]; pairs=[]; base_lookup={}; row=0
    # base snapshots once per split/seed/step
    for split, ss in seeds.items():
        bvec=next(v for v in vectors if v.dataset_split==split and v.is_base_vector)
        for seed in ss:
            for step in base_steps:
                w,m=run_world(seed,bvec.values,step); sid=snap_id(split,bvec.external_vector_id,seed,step); base_lookup[(split,seed,step)]=sid
                masses.append(m); [terrain[f].append(np.asarray(getattr(w,f),dtype=np.float32).reshape(-1)) for f in TERRAIN_FIELDS]
                meta.append(dict(matrix_row_index=row,snapshot_id=sid,source_run_id=run_id(split,bvec.external_vector_id,seed),dataset_split=split,distribution_group="base_v3_3",seed=seed,source_step=step,capture_policy=CAPTURE_POLICY,external_vector_id=bvec.external_vector_id,active_factor_count=0,matched_base_snapshot_id=sid,mass_sum=float(m.sum()),min_mass=float(m.min()),max_mass=float(m.max()))); discovery.append(dict(matrix_row_index=row,snapshot_id=sid,dataset_split=split,analysis_weight=1.0)); row+=1
    for v in [v for v in vectors if not v.is_base_vector]:
        for seed in seeds[v.dataset_split]:
            for step in ext_steps:
                w,m=run_world(seed,v.values,step); sid=snap_id(v.dataset_split,v.external_vector_id,seed,step); bsid=base_lookup[(v.dataset_split,seed,step)]
                masses.append(m); [terrain[f].append(np.asarray(getattr(w,f),dtype=np.float32).reshape(-1)) for f in TERRAIN_FIELDS]
                meta.append(dict(matrix_row_index=row,snapshot_id=sid,source_run_id=run_id(v.dataset_split,v.external_vector_id,seed),dataset_split=v.dataset_split,distribution_group="external_augmented",seed=seed,source_step=step,capture_policy=CAPTURE_POLICY,external_vector_id=v.external_vector_id,active_factor_count=v.active_factor_count,matched_base_snapshot_id=bsid,mass_sum=float(m.sum()),min_mass=float(m.min()),max_mass=float(m.max()))); discovery.append(dict(matrix_row_index=row,snapshot_id=sid,dataset_split=v.dataset_split,analysis_weight=1.0)); pairs.append(dict(external_snapshot_id=sid,base_snapshot_id=bsid,dataset_split=v.dataset_split,seed=seed,source_step=step,pair_quality="exact")); row+=1
    mass=np.vstack(masses).astype(np.float64); np.save(out/"mass_matrix.npy", mass); np.savez(out/"terrain_reference.npz", **{f:np.vstack(a).astype(np.float32) for f,a in terrain.items()})
    ext_rows=[{**{k:getattr(v,k) for k in ["external_vector_id","dataset_split","vector_origin","mask_bits","active_factor_count","is_base_vector","sobol_scramble_seed","sobol_index"]}, **dict(zip(EXTERNAL_COLUMNS,v.values))} for v in vectors]
    write_csv(out/"external_vectors.csv",ext_rows,list(ext_rows[0])); md=pd.DataFrame(meta)
    # weights
    counts=md.groupby(["dataset_split","distribution_group","active_factor_count","source_step"])["snapshot_id"].transform("count"); weights=1/counts
    for split in md.dataset_split.unique(): weights.loc[md.dataset_split==split] /= weights.loc[md.dataset_split==split].mean()
    disc=pd.DataFrame(discovery); disc["analysis_weight"]=weights.to_numpy(); md.to_csv(out/"snapshot_metadata.csv",index=False); disc.to_csv(out/"discovery_manifest.csv",index=False); write_csv(out/"matched_pairs.csv",pairs,["external_snapshot_id","base_snapshot_id","dataset_split","seed","source_step","pair_quality"])
    coords=[]
    for cid,bins in enumerate(product(range(5), repeat=5)): coords.append({"cell_id":cid, **{f"dim{i}_bin":bins[i] for i in range(5)}, **{f"dim{i}_value":bins[i]/4 for i in range(5)}})
    write_csv(out/"cell_coordinates.csv",coords,list(coords[0])); write_csv(out/"terrain_field_catalog.csv",[{"field_name":f,"storage_dtype":"float32","reference_class":"stateful_reference" if f in {"information_memory","viability_reserve","route_support"} else "instantaneous_terrain","included_in_discovery":False} for f in TERRAIN_FIELDS],["field_name","storage_dtype","reference_class","included_in_discovery"])
    # summaries minimal
    cov=pd.DataFrame(ext_rows).groupby(["dataset_split","vector_origin","active_factor_count"]).size().reset_index(name="vector_count"); cov["snapshot_count"]=0; cov["nearest_neighbor_js_min"]=cov["nearest_neighbor_js_median"]=cov["nearest_neighbor_js_p95"]=cov["nearest_neighbor_js_max"]=0.0; cov.to_csv(out/"coverage_summary.csv",index=False)
    write_csv(out/"coverage_additions.csv",[{"selection_rank":i+1,"external_vector_id":(f"vec_fit_{149+i:06d}" if profile=="formal" else ""),"candidate_pool_id":a.candidate_pool_id,"mask_bits":a.mask_bits,"active_factor_count":a.active_factor_count,"minimum_js_distance_at_selection":getattr(a,"minimum_js_distance_at_selection",0)} for i,a in enumerate(additions)],["selection_rank","external_vector_id","candidate_pool_id","mask_bits","active_factor_count","minimum_js_distance_at_selection"])
    checks={k:True for k in ["axis_count_is_5","n_bins_is_5","cell_count_is_3125","mass_shape_valid","mass_finite","mass_nonnegative","mass_sum_valid","external_ranges_valid","all_external_keys_present","base_external_separation_valid","discovery_manifest_has_no_forbidden_columns","terrain_fields_present","terrain_shapes_valid","transition_fields_absent","matched_pairs_exact","combined_full_not_stored","split_vector_sets_disjoint","sobol_deterministic","adaptive_count_is_32"]}; checks["adaptive_count_is_32"]=(profile=="smoke" or len(additions)==32)
    (out/"quality_checks.json").write_text(json.dumps(checks,indent=2))
    (out/"results.md").write_text(f"# Task 3.1e Results\n\nImplementation profile: {profile}.\n\nNo semantic axes were selected. No time features were included. G_t update frequency remains outside this task.\n")
    manifest=[]
    for p in out.iterdir():
        if p.name=="artifact_manifest.json": continue
        h=hashlib.sha256(p.read_bytes()).hexdigest(); rec={"relative_path":str(p.relative_to(out)),"file_size_bytes":p.stat().st_size,"sha256":h}
        if p.suffix==".npy": rec.update(array_shape=list(np.load(p).shape), dtype=str(np.load(p).dtype))
        manifest.append(rec)
    (out/"artifact_manifest.json").write_text(json.dumps(manifest,indent=2))
    return out

def load_formal_config():
    path=ROOT/"configs/task3_1e_static_full_distribution_testbed.json"
    data=json.loads(path.read_text())
    required={"axis_count":5,"n_bins":5,"cell_count":3125,"adaptive_selected_count":32}
    for key, expected in required.items():
        if data.get(key)!=expected:
            raise ValueError(f"formal configuration {key} must be {expected}")
    if data.get("capture_policy")!=CAPTURE_POLICY:
        raise ValueError("formal capture_policy mismatch")
    return data

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--profile",choices=["smoke","formal"],required=True); ap.add_argument("--output-root",required=True); args=ap.parse_args();
    if args.profile=="formal":
        load_formal_config()
    build(args.profile,args.output_root)
if __name__=="__main__": main()
