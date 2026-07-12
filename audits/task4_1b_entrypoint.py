"""Task 4.1-compatible entrypoint for the Task 4.1b audit.

Task 4.1 stores ``current_risk`` and ``current_value`` as the mean initial
metrics of its noisy branch replicates, not as raw snapshot metrics.  The core
Task 4.1b audit verifies regenerated source states against those stored values.
This entrypoint supplies the same replicate-mean semantics only when that
verification reads an NPZ snapshot.  Normal branch-world metric evaluation is
left unchanged.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT, ROOT / "scripts", ROOT / "audits"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import task3_2_4_1_structural_risk as t41  # noqa: E402
import task4_1b_lightweight_audit as audit  # noqa: E402


def _install_formal_initial_metric_adapter(
    corpus_dir: str | Path,
    audit_config: Mapping[str, Any],
) -> None:
    base_config = t41.load_config(ROOT / str(audit_config["base_task_config"]))
    index = t41.CorpusIndex(corpus_dir, base_config)
    entries = {
        entry.path.resolve(): entry
        for split in ("fit", "validation")
        for entry in index.entries_for(split)
    }
    records = {
        entry.path.resolve(): {
            int(record["step"]): record for record in t41.snapshot_records(entry, base_config)
        }
        for entry in entries.values()
    }
    replicate_count = int(base_config["branch_probe"]["replicate_count"])
    original = t41._metrics_from_arrays

    def compatible_metrics(bundle: Mapping[str, Any]) -> dict[str, float]:
        if isinstance(bundle, np.lib.npyio.NpzFile):
            source_path = Path(bundle.fid.name).resolve()
            trajectory_path = source_path.parent.parent
            entry = entries.get(trajectory_path)
            if entry is not None:
                step = int(source_path.stem.rsplit("_", 1)[-1])
                record = records[trajectory_path].get(step)
                if record is not None:
                    replicate_metrics = []
                    for replicate in range(replicate_count):
                        world = t41._restore_world(entry, record, replicate, base_config)
                        replicate_metrics.append(t41._metrics_from_world(world))
                    return {
                        key: float(np.mean([row[key] for row in replicate_metrics]))
                        for key in replicate_metrics[0]
                    }
        return original(bundle)

    t41._metrics_from_arrays = compatible_metrics


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--corpus", required=True)
    execute.add_argument("--formal-artifact", required=True)
    execute.add_argument("--output", required=True)
    execute.add_argument("--config", default=str(audit.DEFAULT_CONFIG))
    check = sub.add_parser("validate")
    check.add_argument("--input", required=True)
    check.add_argument("--config", default=str(audit.DEFAULT_CONFIG))
    args = parser.parse_args(argv)

    if args.command == "run":
        config = audit.load_config(args.config)
        _install_formal_initial_metric_adapter(args.corpus, config)
        result = audit.run(args.corpus, args.formal_artifact, args.output, args.config)
    else:
        result = audit.validate_output(args.input, args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
