# Task22A Existing Runner Execution Environment Recovery RC1

Task22A is an environment recovery and smoke-run diagnostic for the frozen RC1 closed-loop runner. It does **not** validate the bounded canonical ParameterBox update, does **not** connect the update hook, and does **not** use synthetic, mock, stub, or fixed metrics as a substitute for executing the existing runner.

The diagnostic checks:

1. archive existence and zip integrity;
2. required runner files inside the frozen archive;
3. temporary extraction only, without committing expanded archive contents;
4. `requirements.txt` and `pandas` declaration;
5. `python -m pip install -r requirements.txt` in the active environment;
6. runtime `pandas` importability;
7. one-step smoke execution of `FullSpecIntegratedClosedLoopRunner` only when dependencies import.

Task22A passes only when the existing frozen runner executes for one step with dependencies installed. If package-index/network restrictions or any other dependency/runtime blocker prevents execution, Task22A records `passed: false` and a `blocker_stage`.

Task22B may start only after `existing_runner_executed == true` in Task22A results.
