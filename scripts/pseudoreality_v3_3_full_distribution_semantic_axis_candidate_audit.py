"""Task 3.1d full-distribution semantic axis candidate audit.

Audits broad, reproducible semantic axis candidates computed from the real
PseudoReality v3.3/v3.2.2 full distribution path. This is decision support only:
no Core dimensions are selected, no fixed 5-axis Core is built, and PCA is not
used as the primary log basis.
"""
from __future__ import annotations

import argparse, sys
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0, str(REPO_ROOT))

from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322Config, DistributionTerrainV322World
from scripts.pseudoreality_v3_3_external_envelope_fixed_pca_audit import EXTERNAL_FACTORS, fit_external_scenarios, holdout_external_scenarios, zero_factors, FIT_SEEDS, HOLDOUT_SEEDS, STEPS

OUTPUT_DIR = Path("docs/task3_1d_full_distribution_semantic_axis_candidate_audit")
EPS = 1e-12
TERRAIN_FIELDS = ("short_payoff","medium_payoff","effective_medium_payoff","friction","viscosity","damage","rigidity","recovery_speed","route_support","operating_cost","cost_reduction_gain","viability_reserve","negative_viability_pressure","released_mass","release_reallocation_flow")
AUX_FIELDS = ("information_memory","exploration_option_value","exploration_net_expected_value","expected_value_advantage","short_gain_information_conversion","short_path_decline_information","exploration_experience_information","last_flow")

@dataclass(frozen=True)
class AxisDef:
    axis_id: str; axis_name: str; axis_family: str; definition: str; source_fields: str
    uses_distribution_mass: bool=True; uses_terrain: bool=False; uses_auxiliary_terrain: bool=False; uses_history: bool=False; uses_external_factor: bool=False; is_interaction_axis: bool=False

def _norm(x):
    x=np.asarray(x,float); r=float(np.max(x)-np.min(x)); return (x-float(np.min(x)))/(r+EPS)
def _corr(a,b):
    a=np.asarray(a,float); b=np.asarray(b,float)
    return 0.0 if len(a)<2 or np.std(a)<=EPS or np.std(b)<=EPS else float(np.corrcoef(a,b)[0,1])
def _q(a,p): return float(np.quantile(np.asarray(a,float),p)) if len(a) else 0.0

def _state(world):
    fields={k:getattr(world,k).reshape(-1).astype(float) for k in TERRAIN_FIELDS + AUX_FIELDS if hasattr(world,k)}
    mass=world.distribution.reshape(-1).astype(float)
    coords=np.indices(world.shape).reshape(len(world.shape),-1).astype(float)
    coords=np.vstack([_norm(c) for c in coords])
    return mass, fields, coords

def axis_catalog():
    axes=[]
    for name, weight in [("mass_concentration","sum(mass_i^2)"),("distribution_entropy","-sum(mass_i*log(mass_i))"),("center_dim0","sum(mass_i*x0_i)"),("center_dim1","sum(mass_i*x1_i)"),("center_dim2","sum(mass_i*x2_i)"),("center_dim3","sum(mass_i*x3_i)"),("center_dim4","sum(mass_i*x4_i)"),("spatial_spread","sum(mass_i*||x_i-center||^2)")]:
        axes.append(AxisDef(f"distribution_shape_{len(axes)+1:02d}",name,"distribution_shape",weight,"distribution,cell_coordinates"))
    for f in ("short_payoff","medium_payoff","effective_medium_payoff","friction","viscosity","rigidity","recovery_speed","route_support","operating_cost","cost_reduction_gain","viability_reserve"):
        axes.append(AxisDef(f"terrain_semantic_{f}",f"mass_weighted_{f}","terrain_semantic",f"sum_i mass_i(t) * normalized({f}_i(t))",f"distribution,{f}",True,True))
    for a,b in [("short_payoff","friction"),("medium_payoff","viscosity"),("effective_medium_payoff","operating_cost"),("route_support","cost_reduction_gain"),("viability_reserve","negative_viability_pressure"),("released_mass","release_reallocation_flow")]:
        axes.append(AxisDef(f"terrain_interaction_{a}_x_{b}",f"{a}_by_{b}","terrain_interaction",f"sum_i mass_i(t) * normalized({a}_i(t)) * normalized({b}_i(t))",f"distribution,{a},{b}",True,True,False,False,False,True))
    for f in ("information_memory","exploration_option_value","exploration_net_expected_value","expected_value_advantage","last_flow"):
        axes.append(AxisDef(f"temporal_response_{f}",f"history_weighted_{f}","temporal_response",f"sum_i mass_i(t) * normalized({f}_i(t)); velocity/curvature audited by scenario history",f"distribution,{f},scenario_history",True,False,True,True))
    for f in EXTERNAL_FACTORS:
        axes.append(AxisDef(f"external_response_{f}",f"mass_response_to_{f}","external_response",f"axis value is mass-weighted terrain stress multiplied by external factor {f}(t): sum_i mass_i(t)*normalized(friction_i+viscosity_i+damage_i)*{f}(t)",f"distribution,friction,viscosity,damage,{f}",True,True,False,False,True,True))
    for f in ("positive_residual_proxy","negative_residual_proxy","residual_energy_proxy"):
        axes.append(AxisDef(f"residual_response_{f}",f,"residual_response",f"full-distribution residual proxy from mass_i(t) minus scenario no-external baseline mean; {f}","distribution,scenario_history,no_external_baseline",True,False,False,True,False))
    return axes

def _axis_values(axes,mass,fields,coords,row,baseline):
    vals={}; center=np.array([np.sum(mass*c) for c in coords]); stress=_norm(fields.get('friction',0)+fields.get('viscosity',0)+fields.get('damage',0))
    resid=mass-baseline
    for ax in axes:
        n=ax.axis_name
        if n=="mass_concentration": v=np.sum(mass*mass)
        elif n=="distribution_entropy": v=-np.sum(mass*np.log(mass+EPS))
        elif n.startswith("center_dim"): v=center[int(n[-1])]
        elif n=="spatial_spread": v=np.sum(mass*np.sum((coords-center[:,None])**2,axis=0))
        elif ax.axis_family=="terrain_semantic": v=np.sum(mass*_norm(fields[n.replace('mass_weighted_','')]))
        elif ax.axis_family=="terrain_interaction": a,b=n.split('_by_'); v=np.sum(mass*_norm(fields[a])*_norm(fields[b]))
        elif ax.axis_family=="temporal_response": v=np.sum(mass*_norm(fields[n.replace('history_weighted_','')]))
        elif ax.axis_family=="external_response": v=np.sum(mass*stress)*float(row.get(n.replace('mass_response_to_',''),0.0))
        elif n=="positive_residual_proxy": v=np.sum(np.maximum(resid,0))
        elif n=="negative_residual_proxy": v=np.sum(np.maximum(-resid,0))
        else: v=np.sum(resid*resid)
        vals[ax.axis_id]=float(v)
    return vals

def build_corpus(steps=3):
    rows=[]; states=[]
    scenarios=fit_external_scenarios(steps)[:10]+holdout_external_scenarios(steps)[:5]
    for sc in scenarios:
      seeds=(FIT_SEEDS[:2] if sc.scenario_id.startswith('fit_') else HOLDOUT_SEEDS[:1])
      dataset='fit_external' if sc.scenario_id.startswith('fit_') else 'holdout_external'
      for seed in seeds:
        w=DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed,n_bins=3))
        for t in range(sc.steps+1):
          factors=zero_factors() if t==0 else sc.schedule(t-1)
          if t>0: w.set_external_factors(factors); w.step()
          mass,fields,coords=_state(w); row=dict(dataset=dataset,scenario_id=sc.scenario_id,scenario_group=sc.scenario_group,external_factor_name=sc.external_factor_name,external_factor_value=sc.external_factor_value,seed=seed,t=t,source_path='production_world_distribution_terrain_v3_2_2')
          row.update({f:float(factors.get(f,0.0)) for f in EXTERNAL_FACTORS}); rows.append(row); states.append((mass,fields,coords))
    baseline=np.mean([s[0] for r,s in zip(rows,states) if r['t']==0],axis=0)
    axes=axis_catalog(); val_rows=[]
    for row,state in zip(rows,states): val_rows.append(row|_axis_values(axes,*state,row,baseline))
    return axes,pd.DataFrame(val_rows)

def velocity_frame(values, axes):
    df=values.copy()
    for ax in axes:
        df[ax.axis_id+'_velocity']=0.0; df[ax.axis_id+'_curvature']=0.0
    for _,g in df.groupby(['dataset','scenario_id','seed'],sort=False):
        idx=g.index.to_numpy()
        for ax in axes:
            x=g[ax.axis_id].to_numpy(); v=np.r_[0,np.diff(x)]; c=np.r_[0,0,np.diff(x,2)] if len(x)>2 else np.zeros(len(x))
            df.loc[idx,ax.axis_id+'_velocity']=v; df.loc[idx,ax.axis_id+'_curvature']=c
    return df

def summarize(axes, values):
    vdf=velocity_frame(values, axes); ids=[a.axis_id for a in axes]
    catalog=pd.DataFrame([a.__dict__ for a in axes])
    val_summary=pd.DataFrame([{ 'axis_id':i,'value_mean':vdf[i].mean(),'value_std':vdf[i].std(),'value_min':vdf[i].min(),'value_max':vdf[i].max()} for i in ids])
    red=[]; cond=[]
    for n,i in enumerate(ids):
      for j in ids[n+1:]:
        gc=_corr(vdf[i],vdf[j]); vc=_corr(vdf[i+'_velocity'],vdf[j+'_velocity']); cc=_corr(vdf[i+'_curvature'],vdf[j+'_curvature'])
        rs=abs(_corr(vdf[i],vdf['residual_response_residual_energy_proxy'])-_corr(vdf[j],vdf['residual_response_residual_energy_proxy']))
        score=(abs(gc)+abs(vc)+abs(cc))/3*(1-rs)
        red.append(dict(axis_i=i,axis_j=j,global_correlation=gc,velocity_correlation=vc,curvature_correlation=cc,residual_relation_similarity=1-rs,redundancy_score=score))
        scen=[_corr(g[i],g[j]) for _,g in vdf.groupby('scenario_id')]
        er=abs(_corr(vdf[i],vdf[list(EXTERNAL_FACTORS)].abs().sum(axis=1))-_corr(vdf[j],vdf[list(EXTERNAL_FACTORS)].abs().sum(axis=1)))
        tr=abs(vdf[i+'_velocity'].mean()-vdf[j+'_velocity'].mean()); rr=rs; hs=abs(_corr(vdf[vdf.dataset=='holdout_external'][i],vdf[vdf.dataset=='holdout_external'][j])-gc)
        sep=min(1,er+abs(tr)+rr+hs); action='keep_separate' if sep>.25 else ('merge_candidate' if abs(gc)>.95 else 'needs_review')
        cond.append(dict(axis_i=i,axis_j=j,global_correlation=gc,scenario_correlation_min=min(scen),scenario_correlation_max=max(scen),external_response_difference=er,temporal_response_difference=tr,residual_response_difference=rr,holdout_separation_score=hs,conditional_separation_score=sep,recommended_pair_action=action))
    ext=[]
    for i in ids:
      for key,g in vdf.groupby(['external_factor_name','scenario_group']):
        fit=vdf[(vdf.dataset=='fit_external')&(vdf.external_factor_name==key[0])][i].mean(); hold=vdf[(vdf.dataset=='holdout_external')&(vdf.external_factor_name==key[0])][i].mean()
        x=g.sort_values('t')[i].to_numpy(); vel=np.diff(x) if len(x)>1 else [0]
        ext.append(dict(axis_id=i,external_factor_name=key[0],scenario_group=key[1],response_mean=float(np.mean(x)),response_peak=float(np.max(np.abs(x))),response_slope=float(x[-1]-x[0]),response_persistence=float(np.mean(np.abs(x)>_q(np.abs(x),.75))),fit_response_mean=float(fit) if pd.notna(fit) else 0,holdout_response_mean=float(hold) if pd.notna(hold) else 0,response_generalization_gap=float(abs((fit if pd.notna(fit) else 0)-(hold if pd.notna(hold) else 0)))))
    temp=[]
    for i in ids:
      for key,g in vdf.groupby(['scenario_id','seed','dataset']):
        x=g.sort_values('t')[i].to_numpy(); vel=np.r_[0,np.diff(x)]; acc=np.r_[0,0,np.diff(x,2)] if len(x)>2 else np.zeros(len(x))
        temp.append(dict(axis_id=i,scenario_id=key[0],seed=key[1],dataset=key[2],response_start=x[0],response_peak=float(np.max(np.abs(x))),response_end=x[-1],velocity_mean=float(np.mean(np.abs(vel))),velocity_peak=float(np.max(np.abs(vel))),acceleration_peak=float(np.max(np.abs(acc))),curvature_mean=float(np.mean(np.abs(acc))),curvature_peak=float(np.max(np.abs(acc))),reversal_score=float(np.mean(np.sign(vel[1:])!=np.sign(vel[:-1])) if len(vel)>1 else 0),recovery_score=float(abs(x[-1]-x[0])/(np.max(np.abs(x-x[0]))+EPS)),persistence_score=float(np.mean(np.abs(x)>_q(np.abs(x),.75))),oscillation_score=float(np.mean(np.diff(np.sign(vel))!=0) if len(vel)>1 else 0)))
    residual=[]
    re=vdf['residual_response_residual_energy_proxy']; rp=vdf['residual_response_positive_residual_proxy']; rn=vdf['residual_response_negative_residual_proxy']
    for i in ids:
      for ds,g in vdf.groupby('dataset'):
        residual.append(dict(axis_id=i,candidate_name=i,dataset=ds,correlation_with_positive_residual=_corr(g[i],g['residual_response_positive_residual_proxy']),correlation_with_negative_residual=_corr(g[i],g['residual_response_negative_residual_proxy']),correlation_with_residual_energy=_corr(g[i],g['residual_response_residual_energy_proxy']),residual_peak_alignment=float(np.argmax(vdf[i].to_numpy())==np.argmax(re.to_numpy())),residual_persistence_alignment=float(abs(_corr(vdf[i].abs()>_q(vdf[i].abs(),.75),re>_q(re,.75)))),holdout_residual_relation=_corr(vdf[vdf.dataset=='holdout_external'][i],vdf[vdf.dataset=='holdout_external']['residual_response_residual_energy_proxy']),residual_explanation_score=abs(_corr(vdf[i],re))))
    macro=[]; cls=[]
    for i in ids:
      vel=val_summary.loc[val_summary.axis_id==i,'value_std'].iloc[0]; rv=abs(_corr(vdf[i],re)); score=float(min(1, vel+rv+abs(_corr(vdf[i+'_velocity'],re))))
      macro.append(dict(axis_id=i,captures_velocity=abs(_corr(vdf[i+'_velocity'],re)),captures_acceleration=abs(_corr(vdf[i+'_curvature'],re)),captures_curvature=abs(_corr(vdf[i+'_curvature'],re)),captures_reversal=float(vdf[i+'_velocity'].lt(0).mean()),captures_recovery=float(vdf.groupby(['scenario_id','seed'])[i].apply(lambda x: abs(x.iloc[-1]-x.iloc[0])/(abs(x).max()+EPS)).mean()),captures_persistence=float((vdf[i].abs()>_q(vdf[i].abs(),.75)).mean()),captures_oscillation=float(vdf.groupby(['scenario_id','seed'])[i+'_velocity'].apply(lambda x: np.mean(np.diff(np.sign(x))!=0) if len(x)>1 else 0).mean()),captures_boundary_shift=abs(_corr(vdf[i],vdf['external_constraint_pressure'])),captures_concentration=abs(_corr(vdf[i],vdf['distribution_shape_01'])),captures_release=abs(_corr(vdf[i],vdf.get('terrain_semantic_released_mass',pd.Series(0,index=vdf.index)))),captures_reallocation=abs(_corr(vdf[i],vdf.get('terrain_semantic_release_reallocation_flow',pd.Series(0,index=vdf.index)))),macro_dynamics_preservation_score=score))
      classification='core_candidate' if score>.35 and rv>.2 else ('hold_candidate' if score>.15 else 'audit_only')
      cls.append(dict(axis_id=i,classification=classification,reason='Decision-support label from residual relation and macro-dynamics preservation; not final adoption.',redundancy_status='audited_not_dropped',conditional_separation_status='audited_keep_if_separable',residual_relevance_status='relevant' if rv>.2 else 'low_or_contextual',macro_dynamics_status='preserves_some_dynamics' if score>.15 else 'audit_context_only',recommended_next_action='review_with_full_distribution_before_any_core_selection'))
    return {"candidate_axis_catalog.csv":catalog,"axis_value_summary.csv":val_summary,"axis_redundancy_summary.csv":pd.DataFrame(red),"axis_conditional_separation_summary.csv":pd.DataFrame(cond),"axis_external_response_summary.csv":pd.DataFrame(ext),"axis_temporal_response_summary.csv":pd.DataFrame(temp),"axis_residual_relation_summary.csv":pd.DataFrame(residual),"axis_macro_dynamics_preservation_summary.csv":pd.DataFrame(macro),"axis_classification_summary.csv":pd.DataFrame(cls)}

def _write_results(root):
    text='''# Task 3.1d Full-Distribution Semantic Axis Candidate Audit

This report does not select final Core dimensions.
This report does not compress the full distribution into a fixed 5-axis Core.
This report does not use PCA as the primary log basis.
This report only audits semantic axis candidates extracted from the full distribution.
Axis classifications are decision-support labels, not final adoption decisions.
The goal is to preserve information needed for later macro-dynamics extraction.

このレポートは最終Core次元を確定しない。
このレポートはフル分布を固定5軸Coreへ圧縮しない。
このレポートはPCAを主ログ基盤として採用しない。
このレポートはフル分布から抽出した意味論軸候補を監査するだけである。
軸分類は判断材料であり、最終採用判断ではない。
目的は、後段のマクロ力学抽出に必要な情報を保存することである。

## Artifact provenance

- Generation command: `python scripts/pseudoreality_v3_3_full_distribution_semantic_axis_candidate_audit.py`
- Source data path: production PseudoReality path using `DistributionTerrainV322World`, `DistributionTerrainV322Config`, `world.set_external_factors(...)`, `world.step()`, and full `world.distribution` mass snapshots.
- Full distribution source: yes
- PCA used as primary log basis: no
- Fixed 5-axis Core selected: no
- Final Core dimensions selected: no
- Axis classifications are final decisions: no
- Detailed logs written by default: no
'''
    (root/'results.md').write_text(text)

def run_audit(output_root=OUTPUT_DIR, steps=3, write_detailed=False):
    root=Path(output_root); root.mkdir(parents=True,exist_ok=True)
    axes, values=build_corpus(steps); tables=summarize(axes,values)
    for name,df in tables.items(): df.to_csv(root/name,index=False)
    if write_detailed: values.to_csv(root/'detailed_axis_timeseries.csv',index=False)
    _write_results(root); return tables

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output-root',default=str(OUTPUT_DIR)); p.add_argument('--steps',type=int,default=3); p.add_argument('--write-detailed',action='store_true')
    a=p.parse_args(); run_audit(a.output_root,a.steps,a.write_detailed)
if __name__=='__main__': main()
