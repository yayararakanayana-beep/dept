"""Run IntegratedDiagnosticClosedLoop RC1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.integrated_diagnostic_closed_loop import (
    IntegratedDiagnosticConfig,
    run_many,
    write_outputs,
)


def run(
    out_dir: str | Path = "results",
    steps: int = 8,
    seeds: list[int] | None = None,
    scenarios: list[str] | None = None,
) -> dict:
    seeds = seeds or [42]
    scenarios = scenarios or ["normal", "exploration_loss", "relation_lock", "shock"]
    cfg = IntegratedDiagnosticConfig(steps=steps)
    outputs = run_many(seeds=seeds, scenarios=scenarios, cfg=cfg)
    summary = write_outputs(outputs, Path(out_dir), cfg)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results")
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--seeds", default="42")
    ap.add_argument("--scenarios", default="normal,exploration_loss,relation_lock,shock")
    args = ap.parse_args()

    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    scenarios = [x.strip() for x in args.scenarios.split(",") if x.strip()]
    run(out_dir=args.out, steps=args.steps, seeds=seeds, scenarios=scenarios)


if __name__ == "__main__":
    main()
