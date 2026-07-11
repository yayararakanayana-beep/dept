from __future__ import annotations

import argparse, json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .batch import rank_summaries, select_rank, validation_mean_js
from .contract import DEFAULT_CONTRACT, canonical_contract_text, load_contract, sha256_file, sha256_text


def _add(checks: dict[str,dict[str,Any]], name: str, passed: bool, **ev: Any) -> None:
    checks[name]={"passed":bool(passed), **ev}


def validate_selection(artifact_dir: str|Path, contract_path: str|Path=DEFAULT_CONTRACT, *, strict: bool=False, write_outputs: bool=True) -> dict[str,dict[str,Any]]:
    root=Path(artifact_dir); contract=load_contract(contract_path); checks={}
    required=["model_runs.csv","reconstruction_metrics.csv","component_matches.csv","rank_summary.csv","structure_summary.csv","selection_candidate.json","grouped_subset_diagnostics.csv","world_seed_diagnostics.csv","frobenius_sensitivity.csv"]
    missing=[p for p in required if not (root/p).is_file()]
    _add(checks,"required_output_files", not missing, missing=missing)
    if missing:
        if write_outputs: (root/"selection_audit.json").write_text(json.dumps(checks,indent=2)+"\n")
        if strict: raise SystemExit(1)
        return checks
    runs=pd.read_csv(root/"model_runs.csv"); metrics=pd.read_csv(root/"reconstruction_metrics.csv"); matches=pd.read_csv(root/"component_matches.csv"); stored_summary=pd.read_csv(root/"rank_summary.csv"); cand=json.loads((root/"selection_candidate.json").read_text())
    _add(checks,"holdout_not_accessed", cand.get("holdout_accessed") is False and not any("holdout" in str(p.relative_to(root)).lower() for p in root.rglob("*") if p.is_file()), value=cand.get("holdout_accessed"))
    _add(checks,"producer_did_not_create_lock", not (root/"selection_lock.json").exists() or json.loads((root/"selection_lock.json").read_text()).get("selection_lock_creator")=="independent_validator")
    expected=[]
    ranks=sorted(set(runs[runs["method"]=="nmf_kl"]["rank"].astype(int)))
    for r in ranks:
        expected.append(f"nmf_kl_rank{r:02d}_anchor"); expected += [f"nmf_kl_rank{r:02d}_seed{s}" for s in contract["primary_model"]["random_seeds"]]
    actual=runs[runs["method"]=="nmf_kl"]["run_id"].tolist()
    _add(checks,"rank_seed_coverage", actual==expected and all(runs[runs["method"]=="nmf_kl"].groupby("rank").size()==7), expected=expected, actual=actual)
    hash_bad=[]; shapes_bad=[]; copied=[]; seen={}
    for _,r in runs[runs["method"]=="nmf_kl"].iterrows():
        bp=root/str(r.basis_path); fp=root/str(r.fit_activation_path); vp=root/str(r.validation_activation_path)
        if not bp.is_file() or sha256_file(bp)!=r.basis_sha256 or sha256_file(fp)!=r.fit_activation_sha256 or sha256_file(vp)!=r.validation_activation_sha256: hash_bad.append(r.run_id); continue
        b=np.load(bp); fa=np.load(fp); va=np.load(vp)
        if b.shape[0]!=int(r["rank"]) or fa.shape[1]!=int(r["rank"]) or va.shape[1]!=int(r["rank"]) or not np.allclose(b.sum(axis=1),1,atol=1e-10): shapes_bad.append(r.run_id)
        sig=(r.basis_sha256,r.fit_activation_sha256,r.validation_activation_sha256)
        if sig in seen: copied.append((seen[sig], r.run_id))
        seen[sig]=r.run_id
    _add(checks,"model_hashes_and_shapes", not hash_bad and not shapes_bad, hash_bad=hash_bad, shapes_bad=shapes_bad)
    _add(checks,"no_copied_outputs_across_seeds", not copied, copied=copied)
    conv_bad=runs[(runs["method"]=="nmf_kl") & ((runs.n_iter<0) | (runs.n_iter>runs.max_iter) | ((runs.converged==True)&(runs.n_iter>=runs.max_iter)))]
    _add(checks,"convergence_evidence_valid", conv_bad.empty, bad_run_ids=conv_bad["run_id"].tolist())
    try:
        recomputed, structures, _=rank_summaries(root,runs,metrics,matches,np.ones(np.load(root/str(runs[runs["method"]=="nmf_kl"].iloc[0].fit_activation_path)).shape[0]),contract)
        cols=["rank","representative_run_id","converged_random_run_count","duplicate_structure_fraction","inactive_structure_fraction","admissible","rejection_reasons"]
        stored_cmp=stored_summary[cols].copy().reset_index(drop=True)
        recomputed_cmp=recomputed[cols].copy().reset_index(drop=True)
        merged=len(stored_cmp)==len(recomputed_cmp)
        for col in cols:
            if col in {"duplicate_structure_fraction","inactive_structure_fraction"}:
                merged = merged and np.allclose(stored_cmp[col].astype(float), recomputed_cmp[col].astype(float), rtol=1e-12, atol=1e-12)
            else:
                merged = merged and stored_cmp[col].fillna("").astype(str).tolist()==recomputed_cmp[col].fillna("").astype(str).tolist()
        _add(checks,"rank_summary_recomputed", merged, stored_rows=len(stored_summary), recomputed_rows=len(recomputed))
        expected_sel=select_rank(recomputed,runs,metrics)
        ok=all(cand.get(k)==expected_sel.get(k) for k in ("selection_status","selected_rank","selected_representative_run","best_error_rank"))
        _add(checks,"selection_recomputed", ok, expected=expected_sel, candidate={k:cand.get(k) for k in expected_sel})
    except Exception as exc:
        _add(checks,"rank_summary_recomputed", False, error=str(exc)); _add(checks,"selection_recomputed", False, error=str(exc))
    _add(checks,"contract_hash_valid", cand.get("contract_hash")==sha256_text(canonical_contract_text(contract_path)), value=cand.get("contract_hash"))
    subsets=pd.read_csv(root/"grouped_subset_diagnostics.csv"); worlds=pd.read_csv(root/"world_seed_diagnostics.csv"); frob=pd.read_csv(root/"frobenius_sensitivity.csv")
    _add(checks,"perturbation_diagnostics_present", len(subsets)==contract["matching_and_stability"]["grouped_subset"]["count"] and subsets["group_preserving"].astype(bool).all())
    _add(checks,"world_seed_diagnostics_do_not_alter_selection", set(worlds["world_seed"].astype(int))==set(contract["matching_and_stability"]["world_seed_sensitivity"]["fit_world_seeds"]) and worlds["selected_rank_unchanged"].astype(bool).all())
    _add(checks,"frobenius_not_primary_selection", len(frob)>0 and not frob["influenced_primary_selection"].astype(bool).any())
    failed=[k for k,v in checks.items() if not v["passed"]]
    audit={"checks":checks,"failed_checks":failed,"holdout_accessed":False,"independent_selection_audit":"passed" if not failed else "failed"}
    if write_outputs:
        (root/"selection_audit.json").write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n")
        if not failed:
            lock={"selected_rank":cand.get("selected_rank"),"selected_representative_run":cand.get("selected_representative_run"),"holdout_accessed":False,"independent_selection_audit":"passed","selection_lock_creator":"independent_validator","contract_hash":cand.get("contract_hash"),"candidate_hash":sha256_file(root/"selection_candidate.json")}
            (root/"selection_lock.json").write_text(json.dumps(lock,indent=2,sort_keys=True)+"\n")
            # manifest last
            files=[]
            for p in sorted(root.rglob("*")):
                if p.is_file() and p.name!="artifact_manifest.json": files.append({"path":str(p.relative_to(root)),"sha256":sha256_file(p),"size_bytes":p.stat().st_size})
            (root/"artifact_manifest.json").write_text(json.dumps({"files":files},indent=2,sort_keys=True)+"\n")
    if failed and strict: raise SystemExit(1)
    return checks


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--artifact-dir", required=True); ap.add_argument("--contract", default=str(DEFAULT_CONTRACT)); ap.add_argument("--strict", action="store_true"); args=ap.parse_args()
    c=validate_selection(args.artifact_dir,args.contract,strict=args.strict); print(json.dumps({"failed_checks":[k for k,v in c.items() if not v["passed"]],"check_count":len(c)},indent=2))
if __name__=="__main__": main()
