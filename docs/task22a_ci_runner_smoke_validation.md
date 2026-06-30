# Task22A CI Runner Smoke Validation

Task22A-CI adds a GitHub Actions workflow for running the existing frozen RC1 runner smoke diagnostic in an external CI environment. The CI path is intentionally limited to environment recovery and smoke validation for Task22A.

## Workflow

The workflow is defined in `.github/workflows/task22a_runner_smoke.yml` and runs on:

- manual `workflow_dispatch`;
- `pull_request`;
- `push` to `main`.

It uses `ubuntu-latest`, Python 3.12, `actions/checkout`, and the repository `requirements.txt` dependency manifest.

## CI Commands

The workflow performs these commands in order:

1. `python -m pip install --upgrade pip`
2. `python -m pip install -r requirements.txt`
3. `python -m pip install pytest`
4. `python validation/task22a_existing_runner_execution_environment_recovery_rc1.py`
5. `pytest -q`

Task22A result Markdown and JSON files are printed to the GitHub Actions logs when present, and `results/task22a_existing_runner_execution_environment_recovery_rc1/` is uploaded as an artifact when available.

## Pass and Fail Criteria

The workflow fails if dependency installation fails, if `pandas_importable` is not `true`, if `existing_runner_executed` is not `true`, or if the Task22A summary has `passed` other than `true`.

Failure is allowed as a diagnostic outcome, but the logs must identify the failing stage through the install output, Task22A summary fields, pytest output, or the final pass-criteria enforcement step.

## Boundaries

This CI workflow does not modify the runner, remove the `pandas` dependency, synthesize or mock success, advance to Task22B, connect a bounded canonical ParameterBox update hook, add G/K writeback, add world direct writes, connect ActionModule internals, or generate ActionFrames directly.
