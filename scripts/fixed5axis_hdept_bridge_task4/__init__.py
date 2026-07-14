"""固定5軸上位観測翻訳層 Task 4。"""
from .runner import generate_task4_bundle, main as legacy_main
from .scenarios import SCENARIOS, generate_trajectory
from .whole_system import CaseSpec, generate_case_frames, generate_task4_3_bundle, main
from .whole_system_validator import validate_task4_3_bundle

__all__ = [
    "SCENARIOS",
    "CaseSpec",
    "generate_trajectory",
    "generate_case_frames",
    "generate_task4_bundle",
    "generate_task4_3_bundle",
    "validate_task4_3_bundle",
    "legacy_main",
    "main",
]
