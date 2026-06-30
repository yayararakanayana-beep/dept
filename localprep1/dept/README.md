# DEPT2 Task22C Rev1 LocalPrep-1

GitHub投入前のフル統合閉ループ実行パッケージです。

## 目的

Task22C-Rev1 RC1 Freezeコードを、GitHub / Codex環境で再現検証できるrepo構成に整理しています。

特徴:

```text
- world_profile で疑似現実系を切替
- action_profile で作用側設定を切替
- validation_profile で検証条件を切替
- smoke / q9 / matrix validation を実行可能
- validation_runs/latest に結果保存
```

## まず実行するコマンド

```bash
python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_q9_full_integration_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_basic.json
```

## profile構造

```text
configs/world_profiles/
configs/action_profiles/
configs/validation_profiles/
configs/matrices/
```

## 重要な境界

```text
ParameterBoxをActionModuleへ直接渡さない
上位圧をActionSurfaceへ直接足さない
ParameterBoxからworld/G/K/O_tへ書き戻さない
dry-run中はcanonical writeしない
commit gateなしでcanonical writeしない
rollback snapshotなしでcanonical writeしない
```

## 検証結果

最新の検証結果は以下に保存されます。

```text
validation_runs/latest/
```

ChatGPTに戻すときは、まず以下を渡してください。

```text
validation_runs/latest/summary.json
validation_runs/latest/matrix_summary.json
validation_runs/latest/matrix_metrics.csv
validation_runs/latest/boundary_violation_report.csv
```

## 注意

canonical stateは現時点ではin-memoryです。外部永続化は未実装です。
