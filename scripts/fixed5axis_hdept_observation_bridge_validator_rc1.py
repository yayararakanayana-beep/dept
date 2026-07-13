"""固定5軸上位観測翻訳層 Task 3 validator CLI。"""
from fixed5axis_hdept_bridge_task3.validator import (
    Fixed5AxisHDEPTValidationError,
    main,
    validate_observation,
)

__all__ = ["Fixed5AxisHDEPTValidationError", "validate_observation", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
