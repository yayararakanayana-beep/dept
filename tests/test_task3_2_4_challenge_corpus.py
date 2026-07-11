from __future__ import annotations

import json

import pytest

import task3_2_4_challenge_runner as module


def test_all_challenge_conditions_are_deterministic_and_contiguous() -> None:
    config = module.load_config()
    hashes = set()
    for condition in config["challenge"]["condition_groups"]:
        first, first_parameters = module.build_scenario(condition, 10, config)
        second, second_parameters = module.build_scenario(condition, 10, config)
        assert first == second
        assert first_parameters == second_parameters
        segments = first["segments"]
        assert segments[0]["start"] == 0
        assert segments[-1]["end"] is None
        for left, right in zip(segments, segments[1:]):
            assert left["end"] == right["start"]
        hashes.add(first_parameters["schedule_hash"])
    assert len(hashes) == len(config["challenge"]["condition_groups"])


def test_seed_changes_schedule_parameters() -> None:
    config = module.load_config()
    schedules = []
    for seed in [10, 11, 12, 13, 14]:
        _, parameters = module.build_scenario("temporary_disturbance", seed, config)
        schedules.append(parameters["schedule_hash"])
    assert len(set(schedules)) == 5


def test_external_inputs_remain_inside_task2_contract() -> None:
    config = module.load_config()
    for condition in config["challenge"]["condition_groups"]:
        scenario, _ = module.build_scenario(condition, 14, config)
        for segment in scenario["segments"]:
            for name in module._core.EXTERNAL_FIELDS:
                value = float(segment[name])
                low, high = (-1.0, 1.0) if name in module._core.EXTERNAL_FIELDS[:2] else (0.0, 1.0)
                assert low <= value <= high


def test_unknown_condition_is_rejected() -> None:
    config = module.load_config()
    with pytest.raises(module.ChallengeError, match="unknown condition"):
        module.build_scenario("not_a_condition", 10, config)
