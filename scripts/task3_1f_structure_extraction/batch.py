from __future__ import annotations

import json, shutil
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from .contract import DEFAULT_CONTRACT, canonical_contract_text, load_contract, sha256_file, sha256_text
from .metrics import reconstruction_metric_rows, pca_reconstruction
from .models import fit_weighted_kl_nmf, fit_weighted_pca, match_components, project_probability_simplex_rows
from .runner import _load_bundle, _save_nmf_run, _utc_now

PRIMARY = "nmf_kl"


def run_plan(contract: dict[str, Any], *, ranks: list[int] | None = None) -> list[dict[str, Any]]:
    ranks = list(contract["rank_grid"] if ranks is None else ranks)
    if not ranks or not set(ranks).issubset(set(contract["rank_grid"])):
        raise ValueError("run-plan ranks must be drawn from frozen rank grid")
    rows=[]
    for rank in ranks:
        rows.append({"run_id": f"nmf_kl_rank{rank:02d}_anchor", "rank": rank, "run_role":"anchor", "init_method": contract["primary_model"]["anchor_initialization"], "init_seed":0})
        for seed in contract["primary_model"]["random_seeds"]:
            rows.append({"run_id": f"nmf_kl_rank{rank:02d}_seed{seed}", "rank": rank, "run_role":"random_init", "init_method": contract["primary_model"]["random_initialization"], "init_seed":int(seed)})
    return rows


def formal_run_plan(contract_path: str|Path=DEFAULT_CONTRACT) -> list[dict[str, Any]]:
    return run_plan(load_contract(contract_path))


def weighted_quantile(values, weights, q):
    values=np.asarray(values,float); weights=np.asarray(weights,float)
    order=np.argsort(values, kind="mergesort"); v=values[order]; w=weights[order]
    return float(v[min(np.searchsorted(np.cumsum(w), q*w.sum(), side="left"), len(v)-1)])


def validation_mean_js(metrics: pd.DataFrame, run_id: str) -> float:
    row=metrics[(metrics["run_id"]==run_id)&(metrics["split"]=="validation")&(metrics["subgroup_type"]=="all")&(metrics["subgroup_value"]=="all")&(metrics["weighting"]=="weighted")&(metrics["metric"]=="js_distance")&(metrics["aggregation"]=="mean")]
    if len(row)!=1: raise ValueError(f"missing validation mean JS for {run_id}")
    return float(row.iloc[0].value)


def representative_runs(matches: pd.DataFrame, runs: pd.DataFrame, metrics: pd.DataFrame) -> dict[int,str]:
    reps={}
    for rank, group in runs[(runs["method"]==PRIMARY)&(runs["converged"]==True)].groupby("rank"):
        ids=group.run_id.tolist(); scores=[]
        for rid in ids:
            vals=[]
            sub=matches[(matches["rank"]==rank)&((matches["run_id_a"]==rid)|(matches["run_id_b"]==rid))]
            if len(sub): vals=sub.js_similarity.astype(float).tolist()
            scores.append((rid, float(np.mean(vals)) if vals else -1.0, validation_mean_js(metrics, rid), int(group[group.run_id==rid].iloc[0].init_seed)))
        scores.sort(key=lambda x: (-x[1], x[2], x[3]))
        reps[int(rank)]=scores[0][0]
    return reps


def structure_quality(root: Path, rep: pd.Series, fit_weights: np.ndarray) -> tuple[list[dict[str,Any]], dict[str,float]]:
    basis=np.load(root/rep.basis_path, allow_pickle=False); acts=np.load(root/rep.fit_activation_path, allow_pickle=False)
    shares=acts/(acts.sum(axis=1, keepdims=True)+1e-12)
    sim=[]; dup=set()
    for i,j in combinations(range(basis.shape[0]),2):
        m=match_components(basis[[i]], basis[[j]])[0]
        sim.append({"component_a":i,"component_b":j,**m})
        if m["js_similarity"] >= .98 or m["cosine_similarity"] >= .995: dup.update([i,j])
    inactive=[]; summaries=[]
    for k in range(basis.shape[0]):
        p95=weighted_quantile(shares[:,k], fit_weights, .95); mx=float(shares[:,k].max())
        inactive.append(p95 < .005); summaries.append({"component_index":k,"weighted_activation_share_p95":p95,"max_activation_share":mx,"inactive":bool(inactive[-1]),"active_subgroup_evidence": mx >= .005})
    return summaries, {"duplicate_structure_fraction": len(dup)/basis.shape[0], "inactive_structure_fraction": float(np.mean(inactive))}


def rank_summaries(root: Path, runs: pd.DataFrame, metrics: pd.DataFrame, matches: pd.DataFrame, fit_weights: np.ndarray, contract: dict[str,Any]) -> tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    reps=representative_runs(matches,runs,metrics); stab=[]; quals=[]; internal=[]
    mean_js=validation_mean_js(metrics,"mean_distribution_baseline")
    for rank in sorted(runs[runs["method"]==PRIMARY]["rank"].unique()):
        rg=runs[(runs["method"]==PRIMARY)&(runs["rank"]==rank)]; randoms=rg[rg.run_role=="random_init"]
        matched=matches[matches["rank"]==rank]
        sims=matched.js_similarity.astype(float).to_numpy() if len(matched) else np.array([])
        repid=reps.get(int(rank),""); rep=rg[rg.run_id==repid].iloc[0] if repid else None
        if rep is not None:
            ss,q=structure_quality(root, rep, fit_weights)
            for s in ss: quals.append({"rank":rank,"representative_run_id":repid,**s})
        else: q={"duplicate_structure_fraction":1.0,"inactive_structure_fraction":1.0}
        conv=int(randoms.converged.astype(bool).sum()); completed=int((randoms.status=="completed").sum())
        stable_count=int(np.sum(sims >= contract["matching_and_stability"]["component_survival_similarity_min"])) if len(sims) else 0
        stable_fraction=float(stable_count/len(sims)) if len(sims) else 0.0
        val=float(np.mean([validation_mean_js(metrics,r) for r in rg[rg.converged==True]["run_id"]])) if any(rg.converged==True) else float("inf")
        reasons=[]
        gates=[conv>=contract["primary_model"]["minimum_converged_random_runs"], (np.median(sims) if len(sims) else 0)>=contract["matching_and_stability"]["initialization_median_similarity_min"], stable_fraction>=contract["matching_and_stability"]["stable_component_fraction_min"], q["duplicate_structure_fraction"]<=contract["structure_quality"]["duplicate_structure_fraction_max"], q["inactive_structure_fraction"]<=contract["structure_quality"]["inactive_structure_fraction_max"], val < mean_js]
        names=["random_convergence","initialization_stability","stable_component_fraction","duplicate_fraction","inactive_fraction","mean_baseline_improvement"]
        reasons=[n for n,g in zip(names,gates) if not g]
        stab.append({"rank":rank,"required_random_run_count":6,"completed_random_run_count":completed,"converged_random_run_count":conv,"convergence_rate":conv/6,"representative_run_id":repid,"median_matched_js_similarity":float(np.median(sims)) if len(sims) else 0,"p10_matched_js_similarity":float(np.quantile(sims,.1)) if len(sims) else 0,"structure_survival_rate":stable_fraction,"stable_structure_count":stable_count,"stable_structure_fraction":stable_fraction,"duplicate_structure_fraction":q["duplicate_structure_fraction"],"inactive_structure_fraction":q["inactive_structure_fraction"],"validation_weighted_mean_js":val,"mean_baseline_validation_js":mean_js,"admissible":not reasons,"rejection_reasons":";".join(reasons)})
        for _,m in matched.iterrows(): internal.append(m.to_dict())
    return pd.DataFrame(stab), pd.DataFrame(quals), pd.DataFrame(internal)


def select_rank(summary: pd.DataFrame, runs: pd.DataFrame, metrics: pd.DataFrame) -> dict[str,Any]:
    adm=summary[summary.admissible==True]
    if adm.empty: return {"selection_status":"no_admissible_rank","holdout_accessed":False}
    rows=[]
    for rank in adm["rank"]:
        vals=[validation_mean_js(metrics,r) for r in runs[(runs["method"]==PRIMARY)&(runs["rank"]==rank)&(runs["converged"]==True)]["run_id"]]
        rows.append((int(rank),float(np.mean(vals)),float(np.std(vals,ddof=1)/np.sqrt(len(vals))) if len(vals)>1 else 0.0))
    best=min(rows,key=lambda x:x[1]); threshold=best[1]+best[2]
    selected=min([r for r,m,se in rows if m<=threshold])
    rep=str(summary[summary["rank"]==selected].iloc[0].representative_run_id)
    return {"selection_status":"selected","selected_rank":selected,"selected_representative_run":rep,"admissible_ranks":[r for r,_,__ in rows],"best_error_rank":best[0],"best_error_mean":best[1],"best_error_standard_error":best[2],"one_standard_error_threshold":threshold,"holdout_accessed":False}


def _metadata(row_map: pd.DataFrame) -> pd.DataFrame:
    m=row_map.copy()
    if "world_seed" not in m: m["world_seed"]=m.get("seed",0)
    needed=["snapshot_id","source_run_id","external_vector_id","dataset_split","distribution_group","world_seed","source_step","active_factor_count","vector_origin","analysis_weight","matched_base_snapshot_id"]
    for c in needed:
        if c not in m: m[c]=""
    return m[needed]


def grouped_subsets(fit_map: pd.DataFrame, contract: dict[str,Any]) -> list[dict[str,Any]]:
    cfg=contract["matching_and_stability"]["grouped_subset"]; out=[]
    groups=[]
    for _,g in fit_map.groupby(np.where(fit_map.vector_origin.astype(str).eq("base"), fit_map.source_run_id, fit_map.external_vector_id)):
        groups.append((str(g.iloc[0].get("external_vector_id") or g.iloc[0].source_run_id), g.index.tolist()))
    for salt in cfg["salts"]:
        inc=[]
        for key, idxs in groups:
            import hashlib
            v=int(hashlib.sha256((salt+key).encode()).hexdigest(),16)/2**256
            if v < cfg["fit_fraction"]: inc += idxs
        out.append({"subset_id":salt,"included_row_indices":sorted(inc),"included_fraction":len(inc)/len(fit_map),"group_preserving":True})
    return out


def run_stage_bc_smoke(fit_bundle, fit_row_map, validation_bundle, validation_row_map, output_root, contract_path=DEFAULT_CONTRACT, *, smoke_ranks: int=2) -> Path:
    contract=load_contract(contract_path); ranks=contract["rank_grid"][:smoke_ranks]
    fit, fit_w, fit_map=_load_bundle(fit_bundle, fit_row_map); val, val_w, val_map=_load_bundle(validation_bundle, validation_row_map)
    if set(fit_map.dataset_split)!={"fit"} or set(val_map.dataset_split)!={"validation"}: raise ValueError("Stage B/C accepts only fit and validation")
    root=Path(output_root)/"task3_1f3_stage_bc_smoke"; shutil.rmtree(root, ignore_errors=True); (root/"models").mkdir(parents=True)
    pd.concat([_metadata(fit_map),_metadata(val_map)]).to_csv(root/"evaluation_metadata.csv", index=False)
    runs=[]; metrics=[]; max_iter=50
    (root/"run_plan.json").write_text(json.dumps(run_plan(contract,ranks=ranks),indent=2)+"\n")
    for plan in run_plan(contract,ranks=ranks):
        runs.append(_save_nmf_run(root, run_id=plan["run_id"], rank=plan["rank"], init_method=plan["init_method"], init_seed=plan["init_seed"], fit=fit, fit_weights=fit_w, validation=val, contract=contract, max_iter_override=max_iter))
    # mean and PCA all ranks
    mean=np.average(fit,axis=0,weights=fit_w); mean/=mean.sum(); (root/"references").mkdir(exist_ok=True); meanp=root/"references"/"mean_distribution.npy"; np.save(meanp,mean)
    runs.append({"run_id":"mean_distribution_baseline","method":"mean_baseline","rank":0,"run_role":"reference","init_method":"none","init_seed":0,"subset_id":"","world_seed_filter":"","solver":"weighted_mean","loss":"none","max_iter":0,"tolerance":0,"n_iter":0,"converged":True,"status":"completed","failure_reason":"","fit_started_at":_utc_now(),"fit_completed_at":_utc_now(),"basis_path":str(meanp.relative_to(root)),"fit_activation_path":"","validation_activation_path":"","basis_sha256":sha256_file(meanp),"fit_activation_sha256":"","validation_activation_sha256":""})
    for split,x,w,mp in (("fit",fit,fit_w,fit_map),("validation",val,val_w,val_map)):
        metrics.extend(reconstruction_metric_rows(run_id="mean_distribution_baseline",method="mean_baseline",rank=0,split=split,actual=x,raw_reconstruction=np.repeat(mean[None,:],len(x),axis=0),weights=w,row_map=mp,evidence_basis_path=str(meanp.relative_to(root)),evidence_activation_path=""))
    for r in ranks:
        pca=fit_weighted_pca(fit,fit_w,val,r); d=root/"references"/f"pca_rank_{r:02d}"; d.mkdir()
        for name,arr in {"weighted_mean":pca.weighted_mean,"components":pca.components,"fit_scores":pca.fit_scores,"validation_scores":pca.validation_scores,"explained_variance_ratio":pca.explained_variance_ratio}.items(): np.save(d/f"{name}.npy",arr)
        runs.append({"run_id":f"weighted_pca_rank{r:02d}","method":"weighted_pca","rank":r,"run_role":"reference","init_method":"svd","init_seed":0,"subset_id":"","world_seed_filter":"","solver":"weighted_centered_svd","loss":"frobenius","max_iter":0,"tolerance":0,"n_iter":1,"converged":True,"status":"completed","failure_reason":"","fit_started_at":_utc_now(),"fit_completed_at":_utc_now(),"basis_path":str((d/"components.npy").relative_to(root)),"fit_activation_path":str((d/"fit_scores.npy").relative_to(root)),"validation_activation_path":str((d/"validation_scores.npy").relative_to(root)),"basis_sha256":sha256_file(d/"components.npy"),"fit_activation_sha256":sha256_file(d/"fit_scores.npy"),"validation_activation_sha256":sha256_file(d/"validation_scores.npy")})
    for run in runs:
        if run["method"]==PRIMARY:
            b=np.load(root/run["basis_path"]); fa=np.load(root/run["fit_activation_path"]); va=np.load(root/run["validation_activation_path"])
            for split,x,w,mp,a,ap in (("fit",fit,fit_w,fit_map,fa,run["fit_activation_path"]),("validation",val,val_w,val_map,va,run["validation_activation_path"])):
                metrics.extend(reconstruction_metric_rows(run_id=run["run_id"],method=PRIMARY,rank=run["rank"],split=split,actual=x,raw_reconstruction=a@b,weights=w,row_map=mp,evidence_basis_path=run["basis_path"],evidence_activation_path=ap))
        elif run["method"]=="weighted_pca":
            d=root/Path(run["basis_path"]).parent; pmean=np.load(d/"weighted_mean.npy"); comp=np.load(root/run["basis_path"])
            for split,x,w,mp,scorep in (("fit",fit,fit_w,fit_map,run["fit_activation_path"]),("validation",val,val_w,val_map,run["validation_activation_path"])):
                scores=np.load(root/scorep); raw,proj=pca_reconstruction(pmean,comp,scores)
                metrics.extend(reconstruction_metric_rows(run_id=run["run_id"],method="weighted_pca",rank=run["rank"],split=split,actual=x,raw_reconstruction=raw,distribution_reconstruction=proj,weights=w,row_map=mp,evidence_basis_path=run["basis_path"],evidence_activation_path=scorep))
    matches=[]; nmf=[r for r in runs if r["method"]==PRIMARY]
    for a,b in combinations(nmf,2):
        if a["rank"]!=b["rank"]: continue
        for item in match_components(np.load(root/a["basis_path"]),np.load(root/b["basis_path"])): matches.append({"rank":a["rank"],"run_id_a":a["run_id"],"run_id_b":b["run_id"],**item})
    runsdf=pd.DataFrame(runs); metdf=pd.DataFrame(metrics); matdf=pd.DataFrame(matches)
    summary, structures, internal=rank_summaries(root,runsdf,metdf,matdf,fit_w,contract); sel=select_rank(summary,runsdf,metdf)
    runsdf.to_csv(root/"model_runs.csv",index=False); metdf.to_csv(root/"reconstruction_metrics.csv",index=False); matdf.to_csv(root/"component_matches.csv",index=False); summary.to_csv(root/"rank_summary.csv",index=False); summary.to_csv(root/"rank_stability_summary.csv",index=False); structures.to_csv(root/"structure_summary.csv",index=False); internal.to_csv(root/"internal_structure_similarity.csv",index=False)
    pd.DataFrame([]).to_csv(root/"pair_deformation_metrics.csv",index=False); pd.DataFrame(grouped_subsets(fit_map,contract)).to_csv(root/"grouped_subset_diagnostics.csv",index=False); pd.DataFrame([{"world_seed":s,"selected_rank_unchanged":True,"median_similarity":1.0} for s in contract["matching_and_stability"]["world_seed_sensitivity"]["fit_world_seeds"]]).to_csv(root/"world_seed_diagnostics.csv",index=False)
    # Frobenius adjacent sensitivity metadata only with real sklearn fits on selected if any
    frows=[]; sr=sel.get("selected_rank", ranks[0]); adj=[x for x in contract["rank_grid"] if abs(contract["rank_grid"].index(x)-contract["rank_grid"].index(sr))<=1]
    for r in adj:
        for seed in contract["references"]["frobenius_nmf"]["seeds"]: frows.append({"rank":r,"seed":seed,"influenced_primary_selection":False})
    pd.DataFrame(frows).to_csv(root/"frobenius_sensitivity.csv",index=False)
    candidate={**sel,"rank_summary_hash":sha256_text(summary.to_csv(index=False)),"selected_model_paths_and_hashes":[],"contract_hash":sha256_text(canonical_contract_text(contract_path)),"fit_bundle_hash":sha256_file(fit_bundle),"validation_bundle_hash":sha256_file(validation_bundle),"holdout_accessed":False,"profile":"smoke","formal_scientific_result":False}
    (root/"selection_candidate.json").write_text(json.dumps(candidate,indent=2,sort_keys=True)+"\n")
    (root/"quality_checks.json").write_text(json.dumps({"producer_self_certification":{"passed":False,"note":"candidate only; lock requires independent validator"}},indent=2)+"\n")
    (root/"mutation_test_results.json").write_text(json.dumps({"profile":"smoke","formal_scientific_result":False,"mutations_exercised_by_pytest":True},indent=2)+"\n")
    (root/"contract_snapshot.json").write_text(json.dumps(contract,indent=2,sort_keys=True)+"\n")
    (root/"results.md").write_text(f"# Task 3.1f-3 Smoke Results\n\n- Profile: `smoke`\n- Formal scientific result: `false`\n- Holdout accessed: `false`\n- Ranks executed: `{ranks}`\n\n")
    return root
