"""Public runner for Task 3.2-3 simple early-warning baselines."""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

import _task3_2_3_core as _core
from _task3_2_3_core import *  # noqa: F401,F403

ROOT = _core.ROOT
EXTERNAL_FIELDS = _core.EXTERNAL_FIELDS
CorpusEntry = _core.CorpusEntry


def _apply_alarm(
    frame: pd.DataFrame,
    probability: np.ndarray,
    threshold: float,
    persistence: int,
) -> np.ndarray:
    """Apply a consecutive-threshold alarm without namedtuple field rewriting."""
    result = np.zeros(len(frame), dtype=np.int64)
    working = frame[["trajectory_id", "step"]].copy()
    working["position"] = np.arange(len(frame), dtype=np.int64)
    working["probability_value"] = np.asarray(probability, dtype=np.float64)
    for _, group in working.groupby("trajectory_id", sort=False):
        run = 0
        for row in group.sort_values("step").to_dict(orient="records"):
            run = run + 1 if float(row["probability_value"]) >= threshold else 0
            if run >= persistence:
                result[int(row["position"])] = 1
    return result


_core._apply_alarm = _apply_alarm


def main(argv: Sequence[str] | None = None) -> int:
    return _core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = list(_core.__all__) + ["CorpusEntry", "EXTERNAL_FIELDS", "ROOT", "main"]
