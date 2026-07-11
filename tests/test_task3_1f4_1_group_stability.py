from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from task3_1f4_1_group_stability import (
    _assert_no_holdout,
    _native_signature_similarity,
    best_group_match,
    native_signature_tables,
)


def _factorized_distribution(axis_probabilities: list[np.ndarray]) -> np.ndarray:
    tensor = axis_probabilities[0]
    for probabilities in axis_probabilities[1:]:
        tensor = np.multiply.outer(tensor, probabilities)
    values = tensor.reshape(-1)
    return values / values.sum()


def test_group_match_recovers_two_component_split() -> None:
    rng = np.random.default_rng(7)
    left = np.zeros(3125, dtype=float)
    right = np.zeros(3125, dtype=float)
    left[:1500] = rng.random(1500)
    right[1500:3000] = rng.random(1500)
    distractor = np.zeros(3125, dtype=float)
    distractor[3000:] = rng.random(125)
    target = np.vstack([left / left.sum(), right / right.sum(), distractor / distractor.sum()])
    source = 0.65 * target[0] + 0.35 * target[1]
    match = best_group_match(source, target, max_group_size=4, beam_width=16)
    assert match.target_indices == (0, 1)
    assert match.js_similarity > 0.999
    assert match.classification in {"group_preserved", "group_rescued"}
    assert np.allclose(match.weights, (0.65, 0.35), atol=0.03)


def test_native_signature_preserves_five_axis_marginals() -> None:
    axes = [
        np.asarray([0.05, 0.10, 0.15, 0.25, 0.45]),
        np.asarray([0.40, 0.25, 0.15, 0.10, 0.10]),
        np.asarray([0.10, 0.10, 0.20, 0.25, 0.35]),
        np.asarray([0.30, 0.25, 0.20, 0.15, 0.10]),
        np.asarray([0.15, 0.15, 0.20, 0.20, 0.30]),
    ]
    distribution = _factorized_distribution(axes)
    marginal, contribution, joint, relation = native_signature_tables(
        rank=1,
        run_id="synthetic",
        basis=distribution[None, :],
        global_distribution=np.full(3125, 1.0 / 3125.0),
        n_bins=5,
    )
    assert len(marginal) == 25
    assert len(contribution) == 5
    assert len(joint) == 250
    assert len(relation) == 10
    for axis_index, expected in enumerate(axes):
        actual = marginal[marginal["axis_index"] == axis_index].sort_values("bin_index")["probability"].to_numpy()
        assert np.allclose(actual, expected)
    assert np.isclose(contribution["native_axis_contribution_share"].sum(), 1.0)
    assert np.allclose(relation["mutual_information"].to_numpy(), 0.0, atol=1e-10)


def test_native_signature_similarity_detects_identical_relation() -> None:
    axes = [np.asarray([0.1, 0.2, 0.4, 0.2, 0.1])] * 5
    distribution = _factorized_distribution(axes)
    marginal_similarity, pair_similarity = _native_signature_similarity(distribution, distribution, 5)
    assert marginal_similarity == pytest.approx(1.0)
    assert pair_similarity == pytest.approx(1.0)


def test_holdout_named_material_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "safe.csv").write_text("ok\n", encoding="utf-8")
    _assert_no_holdout(tmp_path)
    (tmp_path / "sealed_holdout_bundle.npz").write_bytes(b"forbidden")
    with pytest.raises(ValueError, match="holdout material is forbidden"):
        _assert_no_holdout(tmp_path)
