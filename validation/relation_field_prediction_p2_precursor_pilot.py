from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Sequence

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/"scripts") not in sys.path:sys.path.insert(0,str(ROOT/"scripts"))

from fixed5axis_gk_rc1 import AXIS_BINS,AXIS_NAMES,GENESIS_HASH,compute_gt_hash,compute_history_chain_hash
from generic_relation_field_g2 import build_fixed5_structure_artifact
from relation_field_grid_rc1 import build_grid_artifact,cell_id_from_indices
from relation_field_prediction_coordinates_p2 import build_relation_field_prediction_coordinates,validate_relation_field_prediction_coordinates
from relation_field_prediction_p2_precursor_audit import build_relation_field_prediction_p2_precursor_audit,validate_relation_field_prediction_p2_precursor_audit
from relation_field_prediction_state_p1 import build_prediction_state_series,validate_prediction_state_series


def _distribution(points:Sequence[tuple[tuple[int,int,int,int,int],float]])->np.ndarray:
    flat=np.zeros(5**5,dtype=np.float64)
    for indices,mass in points:flat[cell_id_from_indices(indices)]+=float(mass)
    flat/=np.sum(flat)
    return flat.reshape((5,5,5,5,5))


def _point(indices:tuple[int,int,int,int,int])->np.ndarray:return _distribution([(indices,1.0)])

def _mix(indices:Sequence[tuple[int,int,int,int,int]])->np.ndarray:return _distribution([(value,1/len(indices)) for value in indices])


def _write_trajectory(root:Path,frames:Sequence[np.ndarray],trajectory_id:str)->Path:
    root.mkdir(parents=True,exist_ok=False);np.save(root/"gt_mass.npy",np.stack(frames),allow_pickle=False)
    fields=["trajectory_id","source_trajectory_id","t","phase","gt_row_index","gt_hash","previous_gt_hash","history_chain_hash","delta_t","continuity_status","admissible_for_research","source_state_ref","source_state_hash"]
    rows=[];previous="";chain=GENESIS_HASH
    for t,frame in enumerate(frames):
        distribution_hash=hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest();source_hash=hashlib.sha256(f"p2-4-source-{t}-{distribution_hash}".encode()).hexdigest()
        gt_hash=compute_gt_hash(contract_version="fixed5axis_gk_rc1",trajectory_id=trajectory_id,t=t,distribution=frame,source_state_hash=source_hash);chain=compute_history_chain_hash(chain,gt_hash,t)
        rows.append({"trajectory_id":trajectory_id,"source_trajectory_id":trajectory_id,"t":t,"phase":"pre_transition","gt_row_index":t,"gt_hash":gt_hash,"previous_gt_hash":previous,"history_chain_hash":chain,"delta_t":0 if t==0 else 1,"continuity_status":"initial" if t==0 else "continuous","admissible_for_research":True,"source_state_ref":f"states/step_{t:06d}.npz","source_state_hash":source_hash});previous=gt_hash
    with (root/"history_ledger.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,lineterminator="\n");writer.writeheader();writer.writerows(rows)
    (root/"provenance.json").write_text(json.dumps({"contract_version":"fixed5axis_gk_rc1","axis_order":list(AXIS_NAMES),"axis_bins":list(AXIS_BINS),"gt_shape":[5,5,5,5,5],"gt_dtype":"float64","gt_phase":"pre_transition","source_mode":"reference_full","trajectory_id":trajectory_id,"total_gt_frames":len(frames),"forbidden_source_files_read":[],"source_writeback_performed":False,"canonical_history_is_complete_gt_sequence":True},ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return root


def _prefix_a()->list[np.ndarray]:
    return [_point((2,2,2,2,2)),_point((2,2,2,2,3)),_mix([(2,2,2,2,2),(2,2,2,2,3)]),_mix([(2,2,2,2,1),(2,2,2,2,2),(2,2,2,2,3)]),_mix([(2,2,2,2,1),(2,2,2,2,2),(2,2,2,2,3),(2,2,2,2,4)]),_mix([(2,2,2,2,1),(2,2,2,2,2),(2,2,2,2,3),(2,2,2,2,4)]),_mix([(2,2,2,2,1),(2,2,2,2,2),(2,2,2,2,3),(2,2,2,2,4)])]

def _prefix_b()->list[np.ndarray]:
    return [_point((1,2,2,2,2)),_point((2,2,2,2,2)),_point((2,3,2,2,2)),_point((2,3,3,2,2)),_point((2,3,3,3,2)),_point((2,3,3,3,3)),_point((2,3,3,3,3))]

def _prefix_c()->list[np.ndarray]:
    return [_point((2,1,2,2,2)),_point((2,2,2,2,2)),_mix([(2,2,2,2,2),(2,2,2,2,3)]),_mix([(2,2,2,2,1),(2,2,2,2,2),(2,2,2,2,3)]),_mix([(2,2,2,2,1),(2,2,2,2,2),(2,2,2,2,3),(2,2,2,2,4)]),_mix([(2,2,2,2,1),(2,2,2,2,2),(2,2,2,2,3),(2,2,2,2,4)]),_mix([(2,2,2,2,1),(2,2,2,2,2),(2,2,2,2,3),(2,2,2,2,4)])]


def _cases()->list[tuple[str,str,list[np.ndarray],list[list[np.ndarray]]]]:
    spread4=_mix([(2,2,2,2,1),(2,2,2,2,2),(2,2,2,2,3),(2,2,2,2,4)])
    spread2=_mix([(2,2,2,2,2),(2,2,2,2,3)])
    point=_point((2,3,3,3,3))
    spread_b=_mix([(2,3,3,3,2),(2,3,3,3,3),(2,3,3,4,2),(2,3,3,4,3)])
    boundary=_point((4,4,4,4,4))
    recovered=_mix([(2,2,2,2,1),(2,2,2,2,2),(2,2,2,2,3),(2,2,2,2,4)])
    return [
      ("group-a","development",_prefix_a(),[[spread2,_point((2,2,2,2,2)),_point((2,2,2,2,2)),_point((2,2,2,2,2))],[spread4,spread4,spread4,spread4]]),
      ("group-b","validation",_prefix_b(),[[spread2,spread_b,spread_b,spread_b],[point,point,point,point]]),
      ("group-c","test",_prefix_c(),[[boundary,boundary,boundary,boundary],[boundary,recovered,recovered,recovered]]),
    ]


def run(work_dir:Path)->dict[str,object]:
    if work_dir.exists():shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)
    grid=build_grid_artifact(work_dir/"grid");structure=build_fixed5_structure_artifact(grid,work_dir/"structure")
    manifest={"manifest_version":"relation_field_prediction_p2_precursor_case_manifest_v1","cases":[]}
    for group_id,partition,prefix_frames,futures in _cases():
        trajectory_id=f"p2_4_pilot_{group_id}";prefix=_write_trajectory(work_dir/group_id/"prefix",prefix_frames,trajectory_id)
        p1=build_prediction_state_series(prefix,grid,structure,work_dir/group_id/"p1",origins=[4,5,6]);validate_prediction_state_series(p1,prefix,grid,structure)
        p2=build_relation_field_prediction_coordinates(p1,work_dir/group_id/"p2");validate_relation_field_prediction_coordinates(p2,p1)
        for index,suffix in enumerate(futures):
            full=_write_trajectory(work_dir/group_id/f"future-{index}",prefix_frames+suffix,trajectory_id)
            manifest["cases"].append({"case_id":f"{group_id}-future-{index}","partition":partition,"trajectory_group_id":group_id,"prefix_trajectory_dir":str(prefix.relative_to(work_dir)),"full_trajectory_dir":str(full.relative_to(work_dir)),"grid_artifact_dir":str(grid.relative_to(work_dir)),"p1_series_dir":str(p1.relative_to(work_dir)),"p2_series_dir":str(p2.relative_to(work_dir)),"cutoff_t":6})
    manifest_path=work_dir/"case_manifest.json";manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    audit=build_relation_field_prediction_p2_precursor_audit(manifest_path,work_dir/"audit")
    validation=validate_relation_field_prediction_p2_precursor_audit(audit,manifest_path)
    decision=json.loads((audit/"decision.json").read_text())
    if decision["status"]!="blocked_support_insufficient":raise RuntimeError(f"pilot must remain support-blocked: {decision}")
    summary={"pilot_status":"passed","case_count":len(manifest["cases"]),"trajectory_group_count":3,"decision_status":decision["status"],"independent_validation":validation}
    (work_dir/"pilot_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return summary


def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--work-dir",type=Path,default=ROOT/"results"/"p2_4_precursor_pilot");args=parser.parse_args();print(json.dumps(run(args.work_dir),ensure_ascii=False,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
