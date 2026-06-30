# Task22A External Validation Environment

Use this document only if the Codex environment cannot install Python packages from the configured package index.

## Environment

- Python: use the same major/minor version reported in `environment_recovery_summary.json` under `python_version` where possible.
- Dependencies: install this repository's `requirements.txt`, including `pandas>=2.0`.

## Commands

```bash
python -m pip install -r requirements.txt
python validation/task22a_existing_runner_execution_environment_recovery_rc1.py
pytest -q
```

## Expected output fields

The Task22A summary must include archive, extraction, dependency manifest, pip install, pandas runtime, and runner smoke fields. The key fields for recovery are:

- `pip_install_exit_code: 0`
- `pandas_importable: true`
- `existing_runner_smoke_attempted: true`
- `existing_runner_executed: true`
- `synthetic_metrics_used: false`
- `parallel_runner_created: false`
- `bounded_update_hook_connected: false`

## Passed/failed criteria

Task22A passes only when the frozen RC1 runner executes for one step with installed dependencies. If install, import, extraction, or smoke execution fails, keep `passed: false` and preserve the blocker details.

## Task22B condition

Task22B may begin only after Task22A records `existing_runner_executed == true`. Task22B must not begin from synthetic, mock, stub, trace, or fixed-value substitutes.
