"""exploration_module: Task7 integrated exploration candidate + sandbox pipeline.

Task7 replaces the earlier placeholder with a bounded, non-actuating exploration
module.  It reads G/K, O_t_exploration_view, residual_noise_log, and shadow
parameter state, then emits candidate axes, sandbox screening rows, and decision
rows.  It never emits pressure, never updates parameters, never writes to
world/G/K/O_t, and never sends unverified candidates to the action side.

Scope boundary:
  - Candidate generation is heuristic and local to the pseudo-reality RC1 loop.
  - Sandbox is counterfactual screening only, not closed-loop validation.
  - Exploration local v8 audit remains a later Task8 strengthening.
  - Exploration bridge projection remains Task10; Task7 only proves the
    exploration module has real candidate/sandbox/decision outputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import hashlib
import numpy as np
import pandas as pd


@dataclass
class ExplorationThresholds:
    candidate_budget: int = 6
    sandbox_entry_threshold: float = 0.34
    pass_threshold: float = 0.50
    watch_threshold: float = 0.34
    max_noise_risk: float = 0.72
    max_topology_break_risk: float = 0.72


def _safe_mean(df: pd.DataFrame | None, col: str, default: float = 0.0) -> float:
    if df is None or df.empty or col not in df.columns:
        return float(default)
    return float(pd.to_numeric(df[col], errors="coerce").fillna(default).mean())


def _clip(x: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return float(max(lo, min(hi, float(x))))
    except Exception:
        return float(lo)


def _fingerprint(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


class ExplorationModule:
    name = "exploration_module"

    def __init__(self, enabled: bool = True, thresholds: ExplorationThresholds | None = None):
        self.enabled = bool(enabled)
        self.thresholds = thresholds or ExplorationThresholds()

    def _resolve_thresholds(self, parameter_windows: dict | None = None) -> ExplorationThresholds:
        if not parameter_windows:
            return self.thresholds
        return ExplorationThresholds(
            candidate_budget=int(parameter_windows.get("candidate_budget", self.thresholds.candidate_budget)),
            sandbox_entry_threshold=float(parameter_windows.get("sandbox_entry_threshold", self.thresholds.sandbox_entry_threshold)),
            pass_threshold=float(parameter_windows.get("pass_threshold", self.thresholds.pass_threshold)),
            watch_threshold=float(parameter_windows.get("watch_threshold", self.thresholds.watch_threshold)),
            max_noise_risk=float(parameter_windows.get("max_noise_risk", self.thresholds.max_noise_risk)),
            max_topology_break_risk=float(parameter_windows.get("max_topology_break_risk", self.thresholds.max_topology_break_risk)),
        )

    def run(
        self,
        gt: pd.DataFrame,
        kt: pd.DataFrame,
        ot_exploration_view: pd.DataFrame,
        residual_noise_log: pd.DataFrame,
        shadow_params: pd.DataFrame,
        parameter_windows: dict | None = None,
    ) -> dict[str, pd.DataFrame]:
        thresholds = self._resolve_thresholds(parameter_windows)
        t = int(gt["t"].iloc[0]) if gt is not None and not gt.empty and "t" in gt.columns else -1
        seed = int(gt["seed"].iloc[0]) if gt is not None and not gt.empty and "seed" in gt.columns else -1
        scenario = str(gt["scenario"].iloc[0]) if gt is not None and not gt.empty and "scenario" in gt.columns else "unknown"

        if not self.enabled:
            decision = self._summary_decision(seed, scenario, t, "skipped_disabled", 0, 0, 0, 0, 0)
            return {
                "exploration_candidates": pd.DataFrame(),
                "exploration_sandbox": pd.DataFrame(),
                "exploration_decision": decision,
            }

        candidates = self._generate_candidates(seed, scenario, t, gt, kt, ot_exploration_view, residual_noise_log, shadow_params, thresholds)
        sandbox = self._run_sandbox(candidates, gt, ot_exploration_view, residual_noise_log, thresholds)
        decision = self._decide(seed, scenario, t, candidates, sandbox)
        return {
            "exploration_candidates": candidates,
            "exploration_sandbox": sandbox,
            "exploration_decision": decision,
        }

    def _generate_candidates(
        self,
        seed: int,
        scenario: str,
        t: int,
        gt: pd.DataFrame,
        kt: pd.DataFrame,
        ot: pd.DataFrame,
        noise: pd.DataFrame,
        shadow_params: pd.DataFrame,
        thresholds: ExplorationThresholds | None = None,
    ) -> pd.DataFrame:
        thresholds = thresholds or self.thresholds
        if ot is None or ot.empty:
            return pd.DataFrame()

        work = ot.copy()
        for col in [
            "exploration_gap_proxy", "residual_gap_score", "novelty_pressure_proxy",
            "ot_unresolved_score", "ot_ambiguity_score", "ot_macro_micro_mismatch_score",
            "risk", "relation_lock", "exploration", "reversibility", "entropy",
        ]:
            if col not in work.columns:
                work[col] = 0.0
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

        # Merge retained noise state by entity, but do not discard low or unclassified noise.
        noise_by_entity = pd.DataFrame()
        if noise is not None and not noise.empty and "entity_id" in noise.columns:
            n = noise.copy()
            for col in ["ot_noise_score", "noise_delta", "residual_delta", "persistent_noise"]:
                if col not in n.columns:
                    n[col] = 0.0
            n["persistent_noise"] = n["persistent_noise"].astype(bool)
            noise_by_entity = n.groupby("entity_id", as_index=False).agg({
                "ot_noise_score": "max",
                "noise_delta": "mean",
                "residual_delta": "mean",
                "persistent_noise": "max",
            })
        if not noise_by_entity.empty and "entity_id" in work.columns:
            work = work.merge(noise_by_entity, on="entity_id", how="left", suffixes=("", "_ledger"))
        for col in ["ot_noise_score", "noise_delta", "residual_delta"]:
            if col not in work.columns:
                work[col] = 0.0
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)
        if "persistent_noise" not in work.columns:
            work["persistent_noise"] = False
        work["persistent_noise"] = work["persistent_noise"].fillna(False).astype(bool)

        shadow_abs_delta = 0.0
        if shadow_params is not None and not shadow_params.empty and "shadow_theta_delta_from_previous" in shadow_params.columns:
            shadow_abs_delta = float(pd.to_numeric(shadow_params["shadow_theta_delta_from_previous"], errors="coerce").fillna(0.0).abs().sum())
        gt_over = float(gt.get("gt_overconvergence", pd.Series([0.0])).iloc[0]) if gt is not None and not gt.empty else 0.0
        kt_exploration_slope = float(kt.get("kt_exploration_slope", pd.Series([0.0])).iloc[0]) if kt is not None and not kt.empty else 0.0

        work["candidate_signal_score"] = (
            0.22 * work["exploration_gap_proxy"]
            + 0.20 * work["residual_gap_score"]
            + 0.18 * work["novelty_pressure_proxy"]
            + 0.15 * work["ot_unresolved_score"]
            + 0.10 * work["ot_ambiguity_score"]
            + 0.08 * work["ot_noise_score"]
            + 0.04 * gt_over
            + 0.03 * max(0.0, -kt_exploration_slope)
        ).clip(0.0, 1.0)
        work["candidate_noise_risk"] = (
            0.35 * work["ot_noise_score"]
            + 0.25 * work["risk"]
            + 0.20 * work["ot_ambiguity_score"]
            + 0.20 * work["ot_unresolved_score"]
        ).clip(0.0, 1.0)
        work["candidate_topology_break_risk"] = (
            0.40 * work["relation_lock"]
            + 0.25 * work["risk"]
            + 0.20 * (1.0 - work["reversibility"])
            + 0.15 * work["ot_macro_micro_mismatch_score"]
        ).clip(0.0, 1.0)
        work["candidate_pre_sandbox_score"] = (
            work["candidate_signal_score"]
            + 0.08 * (1.0 - work["candidate_noise_risk"])
            + 0.05 * (1.0 - work["candidate_topology_break_risk"])
            + 0.04 * min(shadow_abs_delta, 1.0)
        ).clip(0.0, 1.0)

        selected = work.sort_values("candidate_pre_sandbox_score", ascending=False).head(thresholds.candidate_budget)
        rows = []
        for rank, (_, r) in enumerate(selected.iterrows(), start=1):
            entity_id = str(r.get("entity_id", f"entity_{rank}"))
            signal = float(r["candidate_signal_score"])
            noise_risk = float(r["candidate_noise_risk"])
            topology_risk = float(r["candidate_topology_break_risk"])
            pre_score = float(r["candidate_pre_sandbox_score"])
            if float(r.get("residual_gap_score", 0.0)) >= max(float(r.get("exploration_gap_proxy", 0.0)), float(r.get("novelty_pressure_proxy", 0.0))):
                axis_type = "residual_gap_axis"
                generated_from = "residual_noise_ledger"
            elif float(r.get("novelty_pressure_proxy", 0.0)) >= float(r.get("exploration_gap_proxy", 0.0)):
                axis_type = "novelty_counter_bias_axis"
                generated_from = "novel_combination"
            else:
                axis_type = "coverage_gap_axis"
                generated_from = "ot_exploration_gap"
            status = "ready_for_sandbox" if pre_score >= thresholds.sandbox_entry_threshold else "monitor_only"
            cid = f"EXP_t{t}_{entity_id}_{rank:02d}_{_fingerprint([str(seed), scenario, str(t), entity_id, axis_type])[:6]}"
            rows.append({
                "seed": seed,
                "scenario": scenario,
                "t": t,
                "candidate_axis_id": cid,
                "candidate_rank": rank,
                "entity_id": entity_id,
                "ot_id": str(r.get("ot_id", "")),
                "axis_type": axis_type,
                "generated_from": generated_from,
                "source_signal_strength": round(signal, 6),
                "confidence": round(_clip(0.58 + 0.35 * signal - 0.20 * noise_risk), 6),
                "ambiguity": round(float(r.get("ot_ambiguity_score", 0.0)), 6),
                "noise_risk": round(noise_risk, 6),
                "topology_break_risk_prior": round(topology_risk, 6),
                "pre_sandbox_score": round(pre_score, 6),
                "candidate_status": status,
                "sandbox_required": status == "ready_for_sandbox",
                "verified_by_sandbox": False,
                "passed_to_action_projection": False,
                "unverified_candidate_can_pass": False,
                "uses_gk_summary": True,
                "uses_ot_exploration_view": True,
                "uses_residual_noise_log": True,
                "uses_shadow_parameter_state": True,
                "exploration_generates_pressure": False,
                "exploration_updates_parameter_box": False,
                "exploration_writes_world": False,
                "exploration_writes_gk": False,
                "exploration_writes_ot": False,
                "expected_effect": "candidate-only: test whether a local exploration axis could reduce residual/unresolved tension without breaking topology",
                "evidence_basis": f"O_t exploration view + retained noise ledger; entity={entity_id}; signal={signal:.3f}; noise={noise_risk:.3f}; topology={topology_risk:.3f}",
                "exploration_contract": "Task7_exploration_candidate_generation__candidate_only_no_pressure_no_action_no_parameter_update__RC1",
            })
        return pd.DataFrame(rows)

    def _run_sandbox(self, candidates: pd.DataFrame, gt: pd.DataFrame, ot: pd.DataFrame, noise: pd.DataFrame, thresholds: ExplorationThresholds | None = None) -> pd.DataFrame:
        thresholds = thresholds or self.thresholds
        if candidates is None or candidates.empty:
            return pd.DataFrame()
        rows = []
        baseline_residual = _safe_mean(ot, "residual_gap_score", _safe_mean(noise, "ot_residual_score", 0.0))
        baseline_unresolved = _safe_mean(ot, "ot_unresolved_score", 0.0)
        baseline_ambiguity = _safe_mean(ot, "ot_ambiguity_score", 0.0)
        baseline_entropy = float(gt.get("gt_entropy", pd.Series([0.0])).iloc[0]) if gt is not None and not gt.empty else 0.0
        baseline_variance = float(gt.get("gt_volatility", pd.Series([0.0])).iloc[0]) if gt is not None and not gt.empty else 0.0
        for _, c in candidates.iterrows():
            if str(c.get("candidate_status")) != "ready_for_sandbox":
                status = "monitor_only"
                verified = False
            else:
                verified = True
                quality = _clip(
                    0.30 * float(c.get("pre_sandbox_score", 0.0))
                    + 0.25 * float(c.get("source_signal_strength", 0.0))
                    + 0.20 * (1.0 - float(c.get("noise_risk", 0.0)))
                    + 0.25 * (1.0 - float(c.get("topology_break_risk_prior", 0.0)))
                )
                if float(c.get("noise_risk", 0.0)) > thresholds.max_noise_risk or float(c.get("topology_break_risk_prior", 0.0)) > thresholds.max_topology_break_risk:
                    status = "block"
                elif quality >= thresholds.pass_threshold:
                    status = "pass"
                elif quality >= thresholds.watch_threshold:
                    status = "watch"
                else:
                    status = "block"
            # Counterfactual sandbox projection. No world/action/parameter writeback.
            signal = float(c.get("source_signal_strength", 0.0))
            noise_risk = float(c.get("noise_risk", 0.0))
            topology_risk = float(c.get("topology_break_risk_prior", 0.0))
            residual_delta = -0.08 * signal + 0.05 * noise_risk
            unresolved_delta = -0.05 * signal + 0.04 * noise_risk
            ambiguity_delta = -0.035 * signal + 0.05 * noise_risk
            topology_break_risk = _clip(0.60 * topology_risk + 0.20 * noise_risk)
            rows.append({
                "seed": int(c.get("seed", -1)),
                "scenario": str(c.get("scenario", "unknown")),
                "t": int(c.get("t", -1)),
                "candidate_axis_id": str(c.get("candidate_axis_id")),
                "sandbox_verified": bool(verified),
                "sandbox_status": status,
                "dispersion_gain": round(_clip(0.35 * signal + 0.10 * baseline_variance), 6),
                "residual_reduction": round(_clip(-residual_delta), 6),
                "information_gain": round(_clip(0.30 * signal + 0.10 * baseline_entropy), 6),
                "stability_cost": round(_clip(topology_risk * 0.45 + noise_risk * 0.20), 6),
                "noise_risk": round(noise_risk, 6),
                "adoption_risk": round(_clip(0.45 * topology_risk + 0.35 * noise_risk + 0.20 * (1.0 - signal)), 6),
                "baseline_entropy": round(baseline_entropy, 6),
                "projected_entropy": round(_clip(baseline_entropy + 0.05 * signal - 0.02 * noise_risk), 6),
                "baseline_variance": round(baseline_variance, 6),
                "projected_variance": round(_clip(baseline_variance + 0.04 * signal), 6),
                "baseline_residual": round(baseline_residual, 6),
                "projected_residual": round(_clip(baseline_residual + residual_delta), 6),
                "residual_delta": round(float(residual_delta), 6),
                "baseline_ambiguity": round(baseline_ambiguity, 6),
                "projected_ambiguity": round(_clip(baseline_ambiguity + ambiguity_delta), 6),
                "ambiguity_delta_sandbox": round(float(ambiguity_delta), 6),
                "baseline_unresolved": round(baseline_unresolved, 6),
                "projected_unresolved": round(_clip(baseline_unresolved + unresolved_delta), 6),
                "unresolved_delta_sandbox": round(float(unresolved_delta), 6),
                "topology_preservation_score": round(_clip(1.0 - topology_break_risk), 6),
                "topology_break_risk": round(topology_break_risk, 6),
                "sandbox_projection_contract": "Task7_counterfactual_exploration_sandbox__no_world_writeback_no_action_no_parameter_update__RC1",
                "world_writeback_performed": False,
                "gk_writeback_performed": False,
                "ot_writeback_performed": False,
                "parameter_update_performed": False,
                "action_performed": False,
            })
        return pd.DataFrame(rows)

    def _decide(self, seed: int, scenario: str, t: int, candidates: pd.DataFrame, sandbox: pd.DataFrame) -> pd.DataFrame:
        if candidates is None or candidates.empty:
            return self._summary_decision(seed, scenario, t, "no_candidates", 0, 0, 0, 0, 0)
        sb = sandbox.copy() if sandbox is not None else pd.DataFrame()
        cand = candidates.copy()
        if not sb.empty:
            cand = cand.merge(sb[["candidate_axis_id", "sandbox_verified", "sandbox_status", "residual_reduction", "information_gain", "topology_break_risk"]], on="candidate_axis_id", how="left")
        else:
            cand["sandbox_verified"] = False
            cand["sandbox_status"] = "not_run"
            cand["residual_reduction"] = 0.0
            cand["information_gain"] = 0.0
            cand["topology_break_risk"] = cand.get("topology_break_risk_prior", 0.0)
        cand["sandbox_verified"] = cand["sandbox_verified"].fillna(False).astype(bool)
        cand["sandbox_status"] = cand["sandbox_status"].fillna("not_run")
        cand["decision_score"] = (
            0.40 * pd.to_numeric(cand.get("pre_sandbox_score", 0.0), errors="coerce").fillna(0.0)
            + 0.20 * pd.to_numeric(cand.get("residual_reduction", 0.0), errors="coerce").fillna(0.0)
            + 0.20 * pd.to_numeric(cand.get("information_gain", 0.0), errors="coerce").fillna(0.0)
            + 0.20 * (1.0 - pd.to_numeric(cand.get("topology_break_risk", 0.0), errors="coerce").fillna(0.0))
        ).clip(0.0, 1.0)
        cand["decision_status"] = "monitor_only"
        cand.loc[cand["sandbox_status"].eq("block"), "decision_status"] = "block"
        cand.loc[cand["sandbox_status"].eq("watch"), "decision_status"] = "watch"
        cand.loc[cand["sandbox_status"].eq("pass") & cand["sandbox_verified"], "decision_status"] = "sandbox_pass"
        cand["passed_to_action_projection"] = False  # Task10 bridge decides projection; Task7 does not.
        cand["unverified_candidate_can_pass"] = False

        passed = int(cand["decision_status"].eq("sandbox_pass").sum())
        watch = int(cand["decision_status"].isin(["watch", "monitor_only"]).sum())
        blocked = int(cand["decision_status"].eq("block").sum())
        status = "task7_integrated_candidate_sandbox_decision"
        rows = []
        for _, r in cand.iterrows():
            rows.append({
                "seed": seed,
                "scenario": scenario,
                "t": t,
                "candidate_axis_id": str(r.get("candidate_axis_id")),
                "decision_status": str(r.get("decision_status")),
                "decision_score": round(float(r.get("decision_score", 0.0)), 6),
                "decision_reason": self._decision_reason(str(r.get("decision_status")), bool(r.get("sandbox_verified", False))),
                "sandbox_status": str(r.get("sandbox_status")),
                "sandbox_verified": bool(r.get("sandbox_verified", False)),
                "candidate_count": int(len(cand)),
                "sandbox_count": int(len(sb)) if sb is not None else 0,
                "passed_count": passed,
                "watch_count": watch,
                "blocked_count": blocked,
                "all_passed_candidates_verified": bool((cand.loc[cand["decision_status"].eq("sandbox_pass"), "sandbox_verified"].astype(bool).all()) if passed else True),
                "unverified_candidate_can_pass": False,
                "exploration_task2_status": status,
                "exploration_task7_status": status,
                "exploration_generates_pressure": False,
                "exploration_updates_parameter_box": False,
                "exploration_executes_action": False,
                "exploration_writes_world": False,
                "exploration_writes_gk": False,
                "exploration_writes_ot": False,
                "exploration_decision_contract": "Task7_decision_gate_only__verified_sandbox_pass_allowed__no_action_projection_until_Task10__RC1",
            })
        return pd.DataFrame(rows)

    def _summary_decision(self, seed: int, scenario: str, t: int, status: str, candidate_count: int, sandbox_count: int, passed: int, watch: int, blocked: int) -> pd.DataFrame:
        return pd.DataFrame([{
            "seed": seed,
            "scenario": scenario,
            "t": t,
            "candidate_axis_id": "none",
            "decision_status": status,
            "decision_score": 0.0,
            "decision_reason": status,
            "sandbox_status": "not_run",
            "sandbox_verified": False,
            "candidate_count": candidate_count,
            "sandbox_count": sandbox_count,
            "passed_count": passed,
            "watch_count": watch,
            "blocked_count": blocked,
            "all_passed_candidates_verified": True,
            "unverified_candidate_can_pass": False,
            "exploration_task2_status": status,
            "exploration_task7_status": status,
            "exploration_generates_pressure": False,
            "exploration_updates_parameter_box": False,
            "exploration_executes_action": False,
            "exploration_writes_world": False,
            "exploration_writes_gk": False,
            "exploration_writes_ot": False,
            "exploration_decision_contract": "Task7_decision_gate_only__no_unverified_exploration_pass__RC1",
        }])

    def _decision_reason(self, status: str, verified: bool) -> str:
        if status == "sandbox_pass":
            return "sandbox_verified_candidate_passed_screening__bridge_projection_deferred_to_Task10" if verified else "invalid_unverified_pass_blocked"
        if status == "watch":
            return "candidate_requires_monitoring_before_bridge_projection"
        if status == "block":
            return "sandbox_blocked_candidate_due_to_noise_or_topology_risk"
        return "monitor_only_candidate_below_sandbox_pass_threshold"
