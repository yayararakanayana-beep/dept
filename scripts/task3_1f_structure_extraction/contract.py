from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "configs" / "task3_1f_structure_extraction_contract.json"
OUTPUT_SUBDIR = "task3_1f_stable_structure_extraction"
SMOKE_SPLIT_ROWS = {"fit": 23, "validation": 7, "holdout": 11}
REQUIRED_INPUT_FILES = [
    "mass_matrix.npy",
    "snapshot_metadata.csv",
    "discovery_manifest.csv",
    "external_vectors.csv",
    "matched_pairs.csv",
    "generation_metadata.json",
]


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract_path = Path(path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != "task3.1f-1-rc1":
        raise ValueError("unexpected Task 3.1f contract version")
    if contract.get("status") != "frozen":
        raise ValueError("Task 3.1f contract is not frozen")
    if contract.get("rank_grid") != [5, 8, 10, 12, 15, 20, 25]:
        raise ValueError("Task 3.1f rank grid differs from the frozen contract")
    model = contract.get("primary_model", {})
    expected = {
        "family": "nmf",
        "solver": "multiplicative_update",
        "beta_loss": "kullback-leibler",
        "max_iter": 2000,
        "tolerance": 1e-5,
        "anchor_initialization": "nndsvda",
        "random_initialization": "random",
    }
    for key, value in expected.items():
        if model.get(key) != value:
            raise ValueError(f"primary_model.{key} differs from the frozen contract")
    if model.get("random_seeds") != [31011, 31012, 31013, 31014, 31015, 31016]:
        raise ValueError("primary-model random seeds differ from the frozen contract")
    if not contract.get("change_control", {}).get("requires_explicit_user_approval"):
        raise ValueError("change-control guard is not enabled")
    return contract


def canonical_contract_text(path: str | Path = DEFAULT_CONTRACT) -> str:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
