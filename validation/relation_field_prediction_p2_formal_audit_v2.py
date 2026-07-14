from __future__ import annotations

import argparse
import copy
import itertools
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT / "validation") not in sys.path:
    sys.path.insert(0, str(ROOT / "validation"))

from generic_relation_field_g2 import build_fixed5_structure_artifact
from relation_field_grid_rc1 import build_grid_artifact, cell_id_from_indices
from relation_field_prediction_coordinates_p2 import (
    build_relation_field_prediction_coordinates,
    validate_relation_field_prediction_coordinates,
)
from relation_field_prediction_p2_precursor_audit import (
    DEFAULT_CONTRACT,
    build_relation_field_prediction_p2_precursor_audit,
    load_contract,
    validate_relation_field_prediction_p2_precursor_audit,
)
from relation_field_prediction_p2_precursor_audit.common import (
    canonical_digest,
    dump_json,
    load_json,
    target_horizon_required,
)
from relation_field_prediction_state_p1 import (
    build_prediction_state_series,
    validate_prediction_state_series,
)
from relation_field_prediction_p2_formal_audit_helpers import (
    OUTCOME_FIELDS,
    _primary_metric_summary,
    _scientific_status,
    _verify_expected_outcomes,
    _verify_primary_score_availability,
    _write_trajectory,
)

DEFAULT_PLAN = (
    ROOT
    / "configs"
    / "relation_field_prediction_p2_formal_audit_dataset_v1.json"
)

EXPECTED_PLAN_SHA256 = "ce23c17576007eb3eab394feeb4fe716b8d9215c25cbfb8f5b074fee5c2052f7"

PREFIX_PATTERNS = {'concentration_persistent': [['wide', 'wide', 'wide', 'wide', 'wide', 'wide', 'broad'], ['wide', 'wide', 'wide', 'wide', 'wide', 'broad', 'broad'], ['broad', 'wide', 'broad', 'wide', 'wide', 'wide', 'broad'], ['wide', 'broad', 'wide', 'broad', 'wide', 'wide', 'broad']], 'concentration_transient': [['wide', 'wide', 'wide', 'wide', 'wide', 'wide', 'broad'], ['wide', 'wide', 'broad', 'wide', 'wide', 'broad', 'broad'], ['broad', 'wide', 'wide', 'broad', 'wide', 'wide', 'broad'], ['narrow', 'broad', 'wide', 'wide', 'wide', 'wide', 'broad']], 'concentration_late': [['wide', 'wide', 'broad', 'broad', 'wide', 'broad', 'broad'], ['broad', 'wide', 'broad', 'wide', 'broad', 'broad', 'broad'], ['wide', 'broad', 'wide', 'broad', 'broad', 'broad', 'broad'], ['broad', 'broad', 'wide', 'wide', 'broad', 'broad', 'broad']], 'stable_broad': [['broad', 'broad', 'broad', 'broad', 'broad', 'broad', 'broad'], ['wide', 'broad', 'wide', 'broad', 'wide', 'broad', 'broad']], 'recovery_fast': [['wide', 'wide', 'broad', 'boundary', 'wide', 'wide', 'broad'], ['broad', 'wide', 'boundary', 'wide', 'broad', 'wide', 'broad']], 'recovery_late': [['wide', 'boundary', 'wide', 'boundary', 'wide', 'wide', 'broad'], ['boundary', 'wide', 'boundary', 'wide', 'boundary', 'wide', 'broad']], 'dispersion_persistent': [['point', 'point', 'point', 'point', 'point', 'point', 'narrow'], ['point', 'point', 'point', 'point', 'point', 'narrow', 'narrow'], ['narrow', 'point', 'narrow', 'point', 'point', 'point', 'narrow'], ['point', 'narrow', 'point', 'narrow', 'point', 'point', 'narrow'], ['point', 'point', 'narrow', 'point', 'narrow', 'point', 'narrow'], ['narrow', 'narrow', 'point', 'point', 'point', 'point', 'narrow']], 'dispersion_transient': [['point', 'point', 'point', 'point', 'point', 'point', 'narrow'], ['point', 'point', 'narrow', 'point', 'point', 'point', 'narrow'], ['narrow', 'point', 'point', 'narrow', 'point', 'point', 'narrow'], ['point', 'narrow', 'point', 'point', 'narrow', 'point', 'narrow']], 'dispersion_late': [['point', 'point', 'point', 'narrow', 'point', 'narrow', 'narrow'], ['narrow', 'point', 'narrow', 'point', 'narrow', 'narrow', 'narrow'], ['point', 'narrow', 'point', 'narrow', 'narrow', 'narrow', 'narrow'], ['narrow', 'narrow', 'point', 'point', 'narrow', 'narrow', 'narrow']], 'stable_point': [['point', 'point', 'point', 'point', 'point', 'point', 'point'], ['narrow', 'point', 'narrow', 'point', 'narrow', 'point', 'point'], ['point', 'narrow', 'point', 'narrow', 'point', 'point', 'point'], ['narrow', 'narrow', 'point', 'point', 'point', 'point', 'point']]}

CUTOFF_FRAME_KINDS = {'concentration_persistent': 'broad', 'concentration_transient': 'broad', 'concentration_late': 'broad', 'stable_broad': 'broad', 'recovery_fast': 'broad', 'recovery_late': 'broad', 'dispersion_persistent': 'narrow', 'dispersion_transient': 'narrow', 'dispersion_late': 'narrow', 'stable_point': 'point'}


class FormalAuditDatasetV2Error(ValueError):
    """P2-4正式監査v2のデータ計画または生成成果物の不整合。"""


def _tuple5(
    value: Sequence[Any], name: str
) -> tuple[int, int, int, int, int]:
    if len(value) != 5:
        raise FormalAuditDatasetV2Error(
            f"{name} must contain five integers"
        )
    result = tuple(int(item) for item in value)
    if any(item < 0 or item > 4 for item in result):
        raise FormalAuditDatasetV2Error(
            f"{name} is outside the fixed grid"
        )
    return result  # type: ignore[return-value]


def _offset5(
    value: Sequence[Any], name: str
) -> tuple[int, int, int, int, int]:
    if len(value) != 5:
        raise FormalAuditDatasetV2Error(
            f"{name} must contain five integers"
        )
    return tuple(int(item) for item in value)  # type: ignore[return-value]


def transform_index(
    index: Sequence[int],
    permutation: Sequence[int],
    mirror_mask: int,
) -> tuple[int, int, int, int, int]:
    source = _tuple5(index, "index")
    perm = tuple(int(value) for value in permutation)
    if sorted(perm) != [0, 1, 2, 3, 4]:
        raise FormalAuditDatasetV2Error(
            "permutation must be a 5-axis bijection"
        )
    if mirror_mask < 0 or mirror_mask > 31:
        raise FormalAuditDatasetV2Error(
            "mirror_mask must be between 0 and 31"
        )
    output = [source[perm[axis]] for axis in range(5)]
    for axis in range(5):
        if (mirror_mask >> axis) & 1:
            output[axis] = 4 - output[axis]
    return tuple(output)  # type: ignore[return-value]


def _frame_points(
    plan: Mapping[str, Any],
    center: Sequence[int],
    frame_kind: str,
) -> list[tuple[int, int, int, int, int]]:
    geometry = plan["geometry"]
    if frame_kind == "boundary":
        return [_tuple5(geometry["boundary_corner"], "boundary corner")]

    offsets = geometry["frame_offsets"].get(frame_kind)
    if not isinstance(offsets, list) or not offsets:
        raise FormalAuditDatasetV2Error(
            f"unsupported frame kind: {frame_kind}"
        )
    center_value = _tuple5(center, f"{frame_kind} center")
    points: list[tuple[int, int, int, int, int]] = []
    for index, raw_offset in enumerate(offsets):
        offset = _offset5(
            raw_offset, f"{frame_kind} offset {index}"
        )
        point = tuple(
            center_value[axis] + offset[axis]
            for axis in range(5)
        )
        if any(value < 0 or value > 4 for value in point):
            raise FormalAuditDatasetV2Error(
                f"{frame_kind} point outside grid: {point}"
            )
        points.append(point)  # type: ignore[arg-type]
    if len(points) != len(set(points)):
        raise FormalAuditDatasetV2Error(
            f"{frame_kind} offsets create duplicate points"
        )
    return sorted(points)


def _distribution(
    points: Sequence[tuple[int, int, int, int, int]],
) -> np.ndarray:
    if not points:
        raise FormalAuditDatasetV2Error(
            "distribution points must not be empty"
        )
    flat = np.zeros(5**5, dtype=np.float64)
    for point in points:
        flat[cell_id_from_indices(point)] += 1.0 / len(points)
    return flat.reshape((5, 5, 5, 5, 5))


def _profile_frames(
    plan: Mapping[str, Any],
    profile: Mapping[str, Any],
    *,
    permutation: Sequence[int] | None = None,
    mirror_mask: int = 0,
) -> list[list[tuple[int, int, int, int, int]]]:
    centers = profile["centers"]
    kinds = profile["frame_kinds"]
    frames: list[list[tuple[int, int, int, int, int]]] = []
    for center, kind in zip(centers, kinds):
        points = _frame_points(plan, center, str(kind))
        if permutation is not None:
            points = sorted(
                transform_index(point, permutation, mirror_mask)
                for point in points
            )
        frames.append(points)
    return frames


def expanded_prefix_signature(
    plan: Mapping[str, Any],
    case: Mapping[str, Any],
    *,
    recent_only: bool = False,
    transformed: bool = True,
) -> str:
    profile = plan["prefix_profiles"][
        str(case["prefix_profile_id"])
    ]
    frames = _profile_frames(
        plan,
        profile,
        permutation=case["permutation"] if transformed else None,
        mirror_mask=int(case["mirror_mask"]) if transformed else 0,
    )
    if recent_only:
        frames = frames[-4:]
    return canonical_digest(frames)


def _selected_recent_center_paths() -> list[list[tuple[int, int]]]:
    points = list(itertools.product(range(5), repeat=2))
    candidates: list[tuple[int, list[tuple[int, int]]]] = []
    for p3 in points:
        for p4 in points:
            for p5 in points:
                sequence = [p3, p4, p5, (3, 3)]
                valid = all(
                    max(
                        abs(sequence[index + 1][0] - sequence[index][0]),
                        abs(sequence[index + 1][1] - sequence[index][1]),
                    )
                    <= 2
                    and sequence[index + 1] != sequence[index]
                    for index in range(3)
                )
                if not valid:
                    continue
                movement = sum(
                    abs(sequence[index + 1][0] - sequence[index][0])
                    + abs(sequence[index + 1][1] - sequence[index][1])
                    for index in range(3)
                )
                candidates.append((movement, sequence))
    candidates.sort(key=lambda row: (row[0], row[1]))

    selected: list[list[tuple[int, int]]] = []
    used: set[tuple[tuple[int, int], ...]] = set()
    for position in range(36):
        index = round(position * (len(candidates) - 1) / 35)
        while tuple(candidates[index][1]) in used:
            index = (index + 1) % len(candidates)
        sequence = candidates[index][1]
        used.add(tuple(sequence))
        selected.append(sequence)
    return selected


def build_plan_v2(base_plan: Mapping[str, Any]) -> dict[str, Any]:
    plan = copy.deepcopy(dict(base_plan))
    if (
        plan.get("plan_version")
        != "relation_field_prediction_p2_formal_audit_dataset_v1"
    ):
        raise FormalAuditDatasetV2Error(
            "v2 plan source must be the frozen v1 dataset plan"
        )

    plan["plan_version"] = (
        "relation_field_prediction_p2_formal_audit_dataset_v2"
    )
    plan["purpose"] = (
        "Generate 36 preregistered, score-blind synthetic test "
        "trajectories with 36 distinct untransformed recent-dynamics "
        "prefixes for the P2-4 formal precursor audit."
    )
    plan["scientific_scope"] = (
        "synthetic_preregistered_distinct_prefix_dynamics_audit_only"
    )
    plan["independence"] = {
        "all_cases_test_partition": True,
        "axis_transform_alone_counts_as_independent": False,
        "future_only_counterfactual_pairs_excluded_from_primary_audit": True,
        "future_pattern_fixed_before_p1_or_p2_build": True,
        "minimum_distinct_recent_dynamics": 30,
        "one_case_per_trajectory_group": True,
        "score_driven_case_selection_forbidden": True,
        "shared_prediction_prefix_between_cases": False,
        "unique_untransformed_prefix_profile_per_case": True,
    }
    plan["geometry"] = {
        "axis_size": 5,
        "boundary_corner": [4, 4, 4, 4, 4],
        "frame_offsets": {
            "point": [[0, 0, 0, 0, 0]],
            "narrow": [
                [0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1],
            ],
            "broad": [
                [0, 0, 0, -1, 0],
                [0, 0, 0, 0, -1],
                [0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1],
            ],
            "wide": [
                [0, 0, -1, -1, 0],
                [0, 0, -1, 0, 0],
                [0, 0, 0, -1, -1],
                [0, 0, 0, -1, 0],
                [0, 0, 0, 0, -1],
                [0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1],
                [0, 0, 0, 1, 0],
            ],
        },
        "transform_definition": (
            "output_axis_i_reads_input_axis_permutation_i_then_"
            "optional_i_mirror"
        ),
    }

    for family_id, family in plan["families"].items():
        family["cutoff_frame_kind"] = CUTOFF_FRAME_KINDS[family_id]
        family.pop("prefix_kind", None)

    recent_paths = _selected_recent_center_paths()
    family_positions: Counter[str] = Counter()
    profiles: dict[str, dict[str, Any]] = {}
    for position, case in enumerate(plan["cases"]):
        family_id = str(case["family_id"])
        family_position = family_positions[family_id]
        family_positions[family_id] += 1
        frame_kinds = PREFIX_PATTERNS[family_id][family_position]

        p3, p4, p5, p6 = recent_paths[position]
        p0 = (max(0, p3[0] - 2), max(0, p3[1] - 2))
        p1 = (max(0, p3[0] - 1), max(0, p3[1] - 1))
        p2 = (p3[0], max(0, p3[1] - 1))
        centers = [
            [x, y, 2, 2, 2]
            for x, y in [p0, p1, p2, p3, p4, p5, p6]
        ]
        profile_id = f"profile-{position + 1:03d}"
        profiles[profile_id] = {
            "centers": centers,
            "frame_kinds": list(frame_kinds),
        }
        case["prefix_profile_id"] = profile_id

    plan["prefix_profiles"] = profiles
    for case in plan["cases"]:
        case["untransformed_prefix_sha256"] = (
            expanded_prefix_signature(
                plan,
                case,
                transformed=False,
            )
        )

    actual_hash = canonical_digest(plan)
    if actual_hash != EXPECTED_PLAN_SHA256:
        raise FormalAuditDatasetV2Error(
            "generated v2 plan hash mismatch: "
            f"{actual_hash}"
        )
    return plan


def _anchor_frame(
    plan: Mapping[str, Any],
    center: Sequence[int],
    frame_kind: str,
    permutation: Sequence[int],
    mirror_mask: int,
) -> np.ndarray:
    points = [
        transform_index(point, permutation, mirror_mask)
        for point in _frame_points(plan, center, frame_kind)
    ]
    return _distribution(sorted(points))


def _transformed_geometry(
    plan: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    profile = plan["prefix_profiles"][
        str(case["prefix_profile_id"])
    ]
    permutation = case["permutation"]
    mirror_mask = int(case["mirror_mask"])
    point_sets = _profile_frames(
        plan,
        profile,
        permutation=permutation,
        mirror_mask=mirror_mask,
    )
    prefix_frames = [_distribution(points) for points in point_sets]
    final_center = profile["centers"][-1]
    return {
        "prefix_frames": prefix_frames,
        "point_anchor": _anchor_frame(
            plan, final_center, "point", permutation, mirror_mask
        ),
        "narrow_anchor": _anchor_frame(
            plan, final_center, "narrow", permutation, mirror_mask
        ),
        "broad_anchor": _anchor_frame(
            plan, final_center, "broad", permutation, mirror_mask
        ),
        "wide_anchor": _anchor_frame(
            plan, final_center, "wide", permutation, mirror_mask
        ),
        "boundary_corner": _anchor_frame(
            plan, final_center, "boundary", permutation, mirror_mask
        ),
    }


def expected_support_counts(
    plan: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, dict[str, dict[str, int | bool]]]:
    output: dict[str, dict[str, dict[str, int | bool]]] = {}
    for target_id, target in contract["targets"].items():
        output[target_id] = {}
        outcome_field = str(target["rf10_outcome_field"])
        applicability_field = target.get("rf10_applicability_field")
        for raw_horizon in contract["evaluation"]["horizons"]:
            horizon = int(raw_horizon)
            required = target_horizon_required(
                contract, target_id, horizon
            )
            positive = 0
            negative = 0
            applicable_count = 0
            if required:
                for case in plan["cases"]:
                    family = plan["families"][case["family_id"]]
                    expected = family["expected_rf10_outcomes"][
                        str(horizon)
                    ]
                    applicable = (
                        True
                        if applicability_field is None
                        else bool(expected[applicability_field])
                    )
                    if not applicable:
                        continue
                    applicable_count += 1
                    if bool(expected[outcome_field]):
                        positive += 1
                    else:
                        negative += 1
            output[target_id][str(horizon)] = {
                "required": required,
                "applicable_count": applicable_count,
                "positive_count": positive,
                "negative_count": negative,
            }
    return output


def validate_plan(
    plan: Mapping[str, Any],
    contract: Mapping[str, Any] | None = None,
) -> None:
    if (
        plan.get("plan_version")
        != "relation_field_prediction_p2_formal_audit_dataset_v2"
    ):
        raise FormalAuditDatasetV2Error(
            "unsupported formal dataset plan"
        )
    if plan.get("scientific_scope") != (
        "synthetic_preregistered_distinct_prefix_dynamics_audit_only"
    ):
        raise FormalAuditDatasetV2Error(
            "formal plan scientific scope changed"
        )
    if int(plan.get("cutoff_t", -1)) != 6:
        raise FormalAuditDatasetV2Error(
            "formal plan cutoff must remain six"
        )
    if [int(value) for value in plan.get("origins", [])] != [4, 5, 6]:
        raise FormalAuditDatasetV2Error(
            "formal plan origins changed"
        )
    if [int(value) for value in plan.get("horizons", [])] != [1, 2, 4]:
        raise FormalAuditDatasetV2Error(
            "formal plan horizons changed"
        )

    independence = plan.get("independence", {})
    expected_independence = {
        "all_cases_test_partition": True,
        "axis_transform_alone_counts_as_independent": False,
        "future_only_counterfactual_pairs_excluded_from_primary_audit": True,
        "one_case_per_trajectory_group": True,
        "score_driven_case_selection_forbidden": True,
        "shared_prediction_prefix_between_cases": False,
        "unique_untransformed_prefix_profile_per_case": True,
        "future_pattern_fixed_before_p1_or_p2_build": True,
    }
    for key, expected in expected_independence.items():
        if independence.get(key) is not expected:
            raise FormalAuditDatasetV2Error(
                f"formal plan independence mismatch: {key}"
            )
    minimum_recent = int(
        independence.get("minimum_distinct_recent_dynamics", 0)
    )
    if minimum_recent < 30:
        raise FormalAuditDatasetV2Error(
            "formal plan requires at least thirty recent dynamics"
        )

    cases = plan.get("cases")
    profiles = plan.get("prefix_profiles")
    families = plan.get("families")
    if not isinstance(cases, list):
        raise FormalAuditDatasetV2Error(
            "formal plan cases must be a list"
        )
    if not isinstance(profiles, dict) or not profiles:
        raise FormalAuditDatasetV2Error(
            "formal prefix profiles missing"
        )
    if not isinstance(families, dict) or not families:
        raise FormalAuditDatasetV2Error(
            "formal families missing"
        )
    if len(cases) != int(plan.get("required_case_count", -1)):
        raise FormalAuditDatasetV2Error(
            "formal plan case count mismatch"
        )
    if len(cases) < 30:
        raise FormalAuditDatasetV2Error(
            "formal plan must contain at least thirty cases"
        )
    if len(profiles) != len(cases):
        raise FormalAuditDatasetV2Error(
            "each formal case must have its own prefix profile"
        )

    valid_future_frames = {
        "point_anchor",
        "narrow_anchor",
        "broad_anchor",
        "wide_anchor",
        "boundary_corner",
    }
    valid_frame_kinds = {
        "point",
        "narrow",
        "broad",
        "wide",
        "boundary",
    }

    identifiers: set[str] = set()
    groups: set[str] = set()
    profile_ids: set[str] = set()
    transforms: set[tuple[tuple[int, ...], int]] = set()
    transformed_signatures: set[str] = set()
    untransformed_signatures: set[str] = set()
    recent_signatures: set[str] = set()
    observed_counts: Counter[str] = Counter()

    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise FormalAuditDatasetV2Error(
                f"formal case {index} must be an object"
            )
        case_id = str(case.get("case_id", ""))
        group_id = str(case.get("trajectory_group_id", ""))
        family_id = str(case.get("family_id", ""))
        profile_id = str(case.get("prefix_profile_id", ""))
        if not case_id or case_id in identifiers:
            raise FormalAuditDatasetV2Error(
                "formal case identifiers must be unique"
            )
        if not group_id or group_id in groups:
            raise FormalAuditDatasetV2Error(
                "formal trajectory groups must be unique"
            )
        if not profile_id or profile_id in profile_ids:
            raise FormalAuditDatasetV2Error(
                "formal prefix profile references must be unique"
            )
        if profile_id not in profiles:
            raise FormalAuditDatasetV2Error(
                f"unknown formal prefix profile: {profile_id}"
            )
        if family_id not in families:
            raise FormalAuditDatasetV2Error(
                f"unknown formal family: {family_id}"
            )
        if case.get("partition") != "test":
            raise FormalAuditDatasetV2Error(
                "formal cases must all be in test"
            )

        permutation = tuple(int(value) for value in case["permutation"])
        mirror_mask = int(case["mirror_mask"])
        if sorted(permutation) != [0, 1, 2, 3, 4]:
            raise FormalAuditDatasetV2Error(
                f"invalid formal permutation: {case_id}"
            )
        if not 0 <= mirror_mask <= 31:
            raise FormalAuditDatasetV2Error(
                f"invalid formal mirror mask: {case_id}"
            )
        transform = (permutation, mirror_mask)
        if transform in transforms:
            raise FormalAuditDatasetV2Error(
                "formal transforms must be unique"
            )

        profile = profiles[profile_id]
        centers = profile.get("centers")
        kinds = profile.get("frame_kinds")
        if (
            not isinstance(centers, list)
            or not isinstance(kinds, list)
            or len(centers) != 7
            or len(kinds) != 7
        ):
            raise FormalAuditDatasetV2Error(
                f"formal prefix profile must contain seven frames: "
                f"{profile_id}"
            )
        if any(str(kind) not in valid_frame_kinds for kind in kinds):
            raise FormalAuditDatasetV2Error(
                f"invalid frame kind in profile: {profile_id}"
            )
        for center, kind in zip(centers, kinds):
            _frame_points(plan, center, str(kind))

        cutoff_kind = str(
            families[family_id]["cutoff_frame_kind"]
        )
        if str(kinds[-1]) != cutoff_kind:
            raise FormalAuditDatasetV2Error(
                f"cutoff frame kind mismatch: {case_id}"
            )

        untransformed = expanded_prefix_signature(
            plan, case, transformed=False
        )
        declared = str(case.get("untransformed_prefix_sha256", ""))
        if declared != untransformed:
            raise FormalAuditDatasetV2Error(
                f"untransformed prefix digest mismatch: {case_id}"
            )
        transformed = expanded_prefix_signature(plan, case)
        recent = expanded_prefix_signature(
            plan, case, recent_only=True, transformed=False
        )
        if untransformed in untransformed_signatures:
            raise FormalAuditDatasetV2Error(
                "axis transform alone must not create an independent case"
            )
        if transformed in transformed_signatures:
            raise FormalAuditDatasetV2Error(
                "formal prediction prefixes must be unique"
            )

        identifiers.add(case_id)
        groups.add(group_id)
        profile_ids.add(profile_id)
        transforms.add(transform)
        untransformed_signatures.add(untransformed)
        transformed_signatures.add(transformed)
        recent_signatures.add(recent)
        observed_counts[family_id] += 1

    if len(recent_signatures) < minimum_recent:
        raise FormalAuditDatasetV2Error(
            "formal recent-dynamics diversity is too small"
        )

    required_counts = {
        str(key): int(value)
        for key, value in plan.get(
            "required_family_counts", {}
        ).items()
    }
    if dict(sorted(observed_counts.items())) != dict(
        sorted(required_counts.items())
    ):
        raise FormalAuditDatasetV2Error(
            "formal family counts do not match the frozen plan"
        )

    for family_id, family in families.items():
        cutoff_kind = str(family.get("cutoff_frame_kind", ""))
        if cutoff_kind not in {"point", "narrow", "broad", "wide"}:
            raise FormalAuditDatasetV2Error(
                f"invalid cutoff frame kind: {family_id}"
            )
        future_pattern = family.get("future_pattern")
        if (
            not isinstance(future_pattern, list)
            or len(future_pattern) != 4
            or any(
                value not in valid_future_frames
                for value in future_pattern
            )
        ):
            raise FormalAuditDatasetV2Error(
                f"invalid future pattern: {family_id}"
            )
        expected = family.get("expected_rf10_outcomes")
        if set(expected or {}) != {"1", "2", "4"}:
            raise FormalAuditDatasetV2Error(
                f"expected outcomes missing: {family_id}"
            )
        for horizon in ("1", "2", "4"):
            if set(expected[horizon]) != set(OUTCOME_FIELDS):
                raise FormalAuditDatasetV2Error(
                    f"expected outcome fields changed: "
                    f"{family_id}/{horizon}"
                )

    if contract is not None:
        independence_contract = contract.get("data_independence", {})
        for key, expected in expected_independence.items():
            if independence_contract.get(key) is not expected:
                raise FormalAuditDatasetV2Error(
                    f"contract independence mismatch: {key}"
                )
        if int(
            independence_contract.get(
                "minimum_distinct_recent_dynamics", 0
            )
        ) != minimum_recent:
            raise FormalAuditDatasetV2Error(
                "contract/plan recent-dynamics minimum mismatch"
            )

        if len(cases) < int(
            contract["support_gates"][
                "minimum_test_cases_for_accuracy_claim"
            ]
        ):
            raise FormalAuditDatasetV2Error(
                "formal plan does not meet the test-case support gate"
            )
        counts = expected_support_counts(plan, contract)
        minimum_positive = int(
            contract["support_gates"][
                "minimum_positive_test_outcomes_per_target_horizon"
            ]
        )
        minimum_negative = int(
            contract["support_gates"][
                "minimum_negative_test_outcomes_per_target_horizon"
            ]
        )
        for target_id, horizons in counts.items():
            for horizon, record in horizons.items():
                if not record["required"]:
                    continue
                if int(record["positive_count"]) < minimum_positive:
                    raise FormalAuditDatasetV2Error(
                        f"formal plan positive support too small: "
                        f"{target_id}/{horizon}"
                    )
                if int(record["negative_count"]) < minimum_negative:
                    raise FormalAuditDatasetV2Error(
                        f"formal plan negative support too small: "
                        f"{target_id}/{horizon}"
                    )


def load_plan(
    path: str | Path = DEFAULT_PLAN,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base_plan = load_json(Path(path))
    plan = build_plan_v2(base_plan)
    validate_plan(plan, contract)
    return plan


def run(
    work_dir: Path,
    *,
    plan_path: Path = DEFAULT_PLAN,
    contract_path: Path = DEFAULT_CONTRACT,
) -> dict[str, Any]:
    work_dir = work_dir.resolve()
    contract = load_contract(contract_path)
    plan = load_plan(plan_path, contract)

    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    frozen_plan = {
        "plan": plan,
        "plan_sha256": canonical_digest(plan),
        "contract_version": contract["contract_version"],
        "contract_sha256": canonical_digest(contract),
        "frozen_before_p1_or_p2_build": True,
        "score_driven_selection_performed": False,
    }
    dump_json(work_dir / "dataset_plan_frozen.json", frozen_plan)
    expected_counts = expected_support_counts(plan, contract)
    dump_json(
        work_dir / "expected_support_preflight.json",
        expected_counts,
    )

    grid = build_grid_artifact(work_dir / "grid")
    structure = build_fixed5_structure_artifact(
        grid, work_dir / "structure"
    )
    case_manifest: dict[str, Any] = {
        "manifest_version": contract["input"][
            "case_manifest_version"
        ],
        "cases": [],
    }

    for position, case in enumerate(plan["cases"], start=1):
        case_id = str(case["case_id"])
        family = plan["families"][case["family_id"]]
        geometry = _transformed_geometry(plan, case)
        prefix_frames = geometry["prefix_frames"]
        future_frames = [
            geometry[name] for name in family["future_pattern"]
        ]
        case_root = work_dir / "cases" / case_id
        trajectory_id = f"p2_4_formal_v2_{case_id}"
        print(
            f"[{position:02d}/{len(plan['cases'])}] "
            f"build {case_id} family={case['family_id']} "
            f"profile={case['prefix_profile_id']}",
            flush=True,
        )

        prefix = _write_trajectory(
            case_root / "prefix",
            prefix_frames,
            trajectory_id,
        )
        p1 = build_prediction_state_series(
            prefix,
            grid,
            structure,
            case_root / "p1",
            origins=[int(value) for value in plan["origins"]],
        )
        validate_prediction_state_series(
            p1, prefix, grid, structure
        )
        p2 = build_relation_field_prediction_coordinates(
            p1, case_root / "p2"
        )
        validate_relation_field_prediction_coordinates(p2, p1)

        full = _write_trajectory(
            case_root / "full",
            list(prefix_frames) + list(future_frames),
            trajectory_id,
        )
        case_manifest["cases"].append(
            {
                "case_id": case_id,
                "partition": "test",
                "trajectory_group_id": case[
                    "trajectory_group_id"
                ],
                "prefix_trajectory_dir": str(
                    prefix.relative_to(work_dir)
                ),
                "full_trajectory_dir": str(
                    full.relative_to(work_dir)
                ),
                "grid_artifact_dir": str(
                    grid.relative_to(work_dir)
                ),
                "p1_series_dir": str(p1.relative_to(work_dir)),
                "p2_series_dir": str(p2.relative_to(work_dir)),
                "cutoff_t": int(plan["cutoff_t"]),
            }
        )

    manifest_path = work_dir / "case_manifest.json"
    dump_json(manifest_path, case_manifest)

    audit = build_relation_field_prediction_p2_precursor_audit(
        manifest_path,
        work_dir / "audit",
        contract_path=contract_path,
    )
    independent_validation = (
        validate_relation_field_prediction_p2_precursor_audit(
            audit,
            manifest_path,
            contract_path=contract_path,
        )
    )
    expected_gate = _verify_expected_outcomes(plan, audit)
    availability_gate = _verify_primary_score_availability(
        audit, contract
    )

    support = load_json(audit / "support_audit.json")
    if not support["all_target_horizon_cells_supported"]:
        raise FormalAuditDatasetV2Error(
            f"formal support gate failed: {support}"
        )

    recovery_horizon_one = next(
        row
        for row in support["cells"]
        if row["target_id"] == "recovery_margin_reduction"
        and int(row["horizon"]) == 1
    )
    if (
        recovery_horizon_one["status"]
        != "not_applicable_by_contract"
        or recovery_horizon_one["required_for_support"] is not False
    ):
        raise FormalAuditDatasetV2Error(
            "recovery horizon one applicability correction failed"
        )

    decision = load_json(audit / "decision.json")
    scientific_status = _scientific_status(
        str(decision["status"])
    )
    primary_metrics = _primary_metric_summary(audit, contract)
    distinct_recent = len(
        {
            expanded_prefix_signature(
                plan,
                case,
                recent_only=True,
                transformed=False,
            )
            for case in plan["cases"]
        }
    )

    summary = {
        "formal_audit_status": "completed",
        "dataset_plan_version": plan["plan_version"],
        "dataset_scope": plan["scientific_scope"],
        "test_case_count": len(plan["cases"]),
        "trajectory_group_count": len(
            {
                case["trajectory_group_id"]
                for case in plan["cases"]
            }
        ),
        "distinct_untransformed_prefix_profile_count": len(
            plan["prefix_profiles"]
        ),
        "distinct_recent_dynamics_count": distinct_recent,
        "axis_transform_alone_counted_as_independent": False,
        "future_only_counterfactual_pairs_in_primary_audit": False,
        "shared_prediction_prefix_between_cases": False,
        "support_gate": support,
        "decision": decision,
        "scientific_status": scientific_status,
        "primary_metrics": primary_metrics,
        "expected_outcome_gate": expected_gate,
        "primary_score_availability_gate": availability_gate,
        "independent_validation": independent_validation,
        "p3_predictor_fitted": False,
        "real_world_generalization_claim": False,
        "unknown_trajectory_family_generalization_claim": False,
        "causal_prediction_claim": False,
        "true_irreversibility_claim": False,
        "action_recommendation_claim": False,
    }
    dump_json(work_dir / "formal_audit_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=ROOT / "results" / "p2_4_formal_audit_v2",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN,
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
    )
    args = parser.parse_args()

    if args.preflight_only:
        contract = load_contract(args.contract)
        plan = load_plan(args.plan, contract)
        payload = {
            "plan_version": plan["plan_version"],
            "case_count": len(plan["cases"]),
            "profile_count": len(plan["prefix_profiles"]),
            "expected_support": expected_support_counts(
                plan, contract
            ),
        }
    else:
        payload = run(
            args.work_dir,
            plan_path=args.plan,
            contract_path=args.contract,
        )
    print(json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
