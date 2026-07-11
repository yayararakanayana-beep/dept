from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from task3_1f_fixture import build_smoke_task3_1e_artifact
from task3_1f_structure_extraction import freeze_input, run_smoke, validate_smoke
from task3_1f_structure_extraction.contract import DEFAULT_CONTRACT


@pytest.fixture(scope="session")
def valid_pipeline(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("task3_1f2_shared")
    input_artifact = build_smoke_task3_1e_artifact(root / "input")
    frozen = freeze_input(input_artifact, root / "frozen", "smoke", DEFAULT_CONTRACT)
    bundles = frozen / "bundles"
    output = run_smoke(
        bundles / "fit_bundle.npz",
        bundles / "fit_row_map.csv",
        bundles / "validation_bundle.npz",
        bundles / "validation_row_map.csv",
        root / "run",
        DEFAULT_CONTRACT,
    )
    checks = validate_smoke(
        output,
        bundles / "fit_bundle.npz",
        bundles / "fit_row_map.csv",
        bundles / "validation_bundle.npz",
        bundles / "validation_row_map.csv",
        DEFAULT_CONTRACT,
        write_outputs=True,
    )
    assert all(result["passed"] for result in checks.values()), checks
    return {"root": root, "input": input_artifact, "frozen": frozen, "bundles": bundles, "output": output}
