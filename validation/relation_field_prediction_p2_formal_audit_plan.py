from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from relation_field_prediction_p2_precursor_audit.common import canonical_digest, load_json, target_horizon_required

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "configs" / "relation_field_prediction_p2_formal_audit_dataset_v1.json"


class FormalAuditDatasetError(ValueError):
    """正式監査データ計画、生成結果または期待結果の不整合。"""


def load_plan(path: str | Path = DEFAULT_PLAN) -> dict[str, Any]:
    plan = load_json(Path(path))
    validate_plan(plan)
    return plan


def _tuple5(value: Sequence[Any], name: str) -> tuple[int, int, int, int, int]:
    if len(value) != 5:
        raise FormalAuditDatasetError(f"{name} must contain five integers")
    result = tuple(int(item) for item in value)
    if any(item < 0 or item > 4 for item in result):
        raise FormalAuditDatasetError(f"{name} is outside the fixed grid")
    return result  # type: ignore[return-value]


def _offset5(value: Sequence[Any], name: str) -> tuple[int, int, int, int, int]:
    if len(value) != 5:
        raise FormalAuditDatasetError(f"{name} must contain five integers")
    return tuple(int(item) for item in value)  # type: ignore[return-value]


def transform_index(
    index: Sequence[int],
    permutation: Sequence[int],
    mirror_mask: int,
) -> tuple[int, int, int, int, int]:
    source = _tuple5(index, "index")
    perm = tuple(int(value) for value in permutation)
    if sorted(perm) != [0, 1, 2, 3, 4]:
        raise FormalAuditDatasetError("permutation must be a 5-axis bijection")
    if mirror_mask < 0 or mirror_mask > 31:
        raise FormalAuditDatasetError("mirror_mask must be between 0 and 31")
    output = [source[perm[axis]] for axis in range(5)]
    for axis in range(5):
        if (mirror_mask >> axis) & 1:
            output[axis] = 4 - output[axis]
    return tuple(output)  # type: ignore[return-value]


def _base_broad_points(
    center: Sequence[int], offsets: Sequence[Sequence[int]]
) -> list[tuple[int, int, int, int, int]]:
    center_value = _tuple5(center, "broad center")
    points: list[tuple[int, int, int, int, int]] = []
    for index, raw_offset in enumerate(offsets):
        offset = _offset5(raw_offset, f"broad offset {index}")
        point = tuple(
            center_value[axis] + offset[axis] for axis in range(5)
        )
        if any(value < 0 or value > 4 for value in point):
            raise FormalAuditDatasetError(
                f"broad point outside grid: {point}"
            )
        points.append(point)  # type: ignore[arg-type]
    if len(set(points)) != len(points):
        raise FormalAuditDatasetError("broad offsets create duplicate points")
    return points


def expanded_prefix_signature(
    plan: Mapping[str, Any], case: Mapping[str, Any]
) -> str:
    family = plan["families"][str(case["family_id"])]
    permutation = case["permutation"]
    mirror_mask = int(case["mirror_mask"])
    centers = plan["geometry"]["base_centers"]
    if family["prefix_kind"] == "point":
        frames = [
            [transform_index(center, permutation, mirror_mask)]
            for center in centers
        ]
    elif family["prefix_kind"] == "broad":
        frames = [
            sorted(
                transform_index(point, permutation, mirror_mask)
                for point in _base_broad_points(
                    center, plan["geometry"]["broad_offsets"]
                )
            )
            for center in centers
        ]
    else:
        raise FormalAuditDatasetError(
            f"unsupported prefix kind: {family['prefix_kind']}"
        )
    return canonical_digest(frames)


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
        != "relation_field_prediction_p2_formal_audit_dataset_v1"
    ):
        raise FormalAuditDatasetError("unsupported formal dataset plan")
    if plan.get("scientific_scope") != (
        "synthetic_preregistered_independent_trajectory_audit_only"
    ):
        raise FormalAuditDatasetError("formal plan scientific scope changed")
    if int(plan.get("cutoff_t", -1)) != 6:
        raise FormalAuditDatasetError("formal plan cutoff must remain six")
    if [int(value) for value in plan.get("origins", [])] != [4, 5, 6]:
        raise FormalAuditDatasetError("formal plan origins changed")
    if [int(value) for value in plan.get("horizons", [])] != [1, 2, 4]:
        raise FormalAuditDatasetError("formal plan horizons changed")

    independence = plan.get("independence", {})
    for key in (
        "one_case_per_trajectory_group",
        "shared_prediction_prefix_between_cases",
        "score_driven_case_selection_forbidden",
        "future_pattern_fixed_before_p1_or_p2_build",
        "all_cases_test_partition",
    ):
        if key not in independence:
            raise FormalAuditDatasetError(
                f"formal plan independence field missing: {key}"
            )
    if independence["one_case_per_trajectory_group"] is not True:
        raise FormalAuditDatasetError(
            "formal plan must use one case per trajectory group"
        )
    if independence["shared_prediction_prefix_between_cases"] is not False:
        raise FormalAuditDatasetError(
            "formal plan must not share prediction prefixes"
        )
    if independence["score_driven_case_selection_forbidden"] is not True:
        raise FormalAuditDatasetError(
            "formal plan must forbid score-driven selection"
        )
    if (
        independence["future_pattern_fixed_before_p1_or_p2_build"]
        is not True
    ):
        raise FormalAuditDatasetError(
            "formal future pattern must be fixed before P1/P2"
        )
    if independence["all_cases_test_partition"] is not True:
        raise FormalAuditDatasetError(
            "formal plan must use only the test partition"
        )

    cases = plan.get("cases")
    if not isinstance(cases, list):
        raise FormalAuditDatasetError("formal plan cases must be a list")
    if len(cases) != int(plan.get("required_case_count", -1)):
        raise FormalAuditDatasetError("formal plan case count mismatch")
    if len(cases) < 30:
        raise FormalAuditDatasetError(
            "formal plan must contain at least thirty cases"
        )

    families = plan.get("families")
    if not isinstance(families, dict) or not families:
        raise FormalAuditDatasetError("formal plan families missing")
    identifiers: set[str] = set()
    groups: set[str] = set()
    transforms: set[tuple[tuple[int, ...], int]] = set()
    signatures: set[str] = set()
    observed_counts: Counter[str] = Counter()

    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise FormalAuditDatasetError(
                f"formal case {index} must be an object"
            )
        case_id = str(case.get("case_id", ""))
        group_id = str(case.get("trajectory_group_id", ""))
        family_id = str(case.get("family_id", ""))
        if not case_id or case_id in identifiers:
            raise FormalAuditDatasetError(
                "formal case identifiers must be unique"
            )
        if not group_id or group_id in groups:
            raise FormalAuditDatasetError(
                "formal trajectory groups must be unique"
            )
        if case.get("partition") != "test":
            raise FormalAuditDatasetError(
                "formal cases must all be in test"
            )
        if family_id not in families:
            raise FormalAuditDatasetError(
                f"unknown formal family: {family_id}"
            )
        permutation = tuple(int(value) for value in case["permutation"])
        mirror_mask = int(case["mirror_mask"])
        if sorted(permutation) != [0, 1, 2, 3, 4]:
            raise FormalAuditDatasetError(
                f"invalid formal permutation: {case_id}"
            )
        if not 0 <= mirror_mask <= 31:
            raise FormalAuditDatasetError(
                f"invalid formal mirror mask: {case_id}"
            )
        transform = (permutation, mirror_mask)
        if transform in transforms:
            raise FormalAuditDatasetError(
                "formal transforms must be unique"
            )
        signature = expanded_prefix_signature(plan, case)
        if signature in signatures:
            raise FormalAuditDatasetError(
                "formal prediction prefixes must be unique"
            )
        identifiers.add(case_id)
        groups.add(group_id)
        transforms.add(transform)
        signatures.add(signature)
        observed_counts[family_id] += 1

    required_counts = {
        str(key): int(value)
        for key, value in plan.get("required_family_counts", {}).items()
    }
    if dict(sorted(observed_counts.items())) != dict(
        sorted(required_counts.items())
    ):
        raise FormalAuditDatasetError(
            "formal family counts do not match the frozen plan"
        )

    for family_id, family in families.items():
        if family.get("prefix_kind") not in {"point", "broad"}:
            raise FormalAuditDatasetError(
                f"invalid prefix kind: {family_id}"
            )
        future_pattern = family.get("future_pattern")
        if (
            not isinstance(future_pattern, list)
            or len(future_pattern) != 4
            or any(
                value
                not in {
                    "point_anchor",
                    "broad_anchor",
                    "boundary_corner",
                }
                for value in future_pattern
            )
        ):
            raise FormalAuditDatasetError(
                f"invalid future pattern: {family_id}"
            )
        expected = family.get("expected_rf10_outcomes")
        if set(expected or {}) != {"1", "2", "4"}:
            raise FormalAuditDatasetError(
                f"expected outcomes missing: {family_id}"
            )
        for horizon in ("1", "2", "4"):
            if set(expected[horizon]) != set(OUTCOME_FIELDS):
                raise FormalAuditDatasetError(
                    f"expected outcome fields changed: {family_id}/{horizon}"
                )

    if contract is not None:
        if len(cases) < int(
            contract["support_gates"][
                "minimum_test_cases_for_accuracy_claim"
            ]
        ):
            raise FormalAuditDatasetError(
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
                    raise FormalAuditDatasetError(
                        f"formal plan positive support too small: "
                        f"{target_id}/{horizon}"
                    )
                if int(record["negative_count"]) < minimum_negative:
                    raise FormalAuditDatasetError(
                        f"formal plan negative support too small: "
                        f"{target_id}/{horizon}"
                    )
