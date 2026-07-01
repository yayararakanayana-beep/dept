# PR23 Validation Instructions

## 位置づけ

この文書は PR #23 `Add Task22C diagnostic matrix exports` の検証手順です。

PR #23 の目的は、Task22C Rev1 LocalPrep-1 のフル統合閉ループ検証フェーズに向けて、再利用可能なmatrixと探索診断CSV出力を追加することです。

## Codexタスク設定

タスク種別:
  新しいCodexタスク

対象リポジトリ:
  yayararakanayana-beep/dept

対象PR:
  PR #23

対象ブランチ:
  head branch: task23-diagnostic-export-matrices
  base branch: main

GitHub反映の要否:
  検証のみ
  push不要
  PR作成不要
  コメント投稿不要
  コード修正不要

## 重要ルール

- このタスクでは修正しない。
- commitしない。
- pushしない。
- 別ブランチ・別PRを勝手に作らない。
- GitHubに反映できていない作業を、反映済みのように報告しない。
- Codex環境から対象ブランチをcheckoutできない場合は、作業を止めて報告する。
- 対象が PR #23 / head branch `task23-diagnostic-export-matrices` であることを確認してから実行する。

## 最初に確認

```bash
pwd
git status --short --branch
git branch --show-current
git log -1 --oneline
```

## 作業ディレクトリ

```bash
cd localprep1/dept
```

## 実行コマンド

```bash
python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_basic.json --output-dir validation_runs/matrix_basic
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_extended_probe.json --output-dir validation_runs/matrix_extended_probe
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_slow_drift_projection_diagnostic.json --output-dir validation_runs/slow_drift_projection_diagnostic
```

## 確認コマンド

```bash
cat validation_runs/matrix_basic/matrix_summary.json
cat validation_runs/matrix_extended_probe/matrix_summary.json
cat validation_runs/slow_drift_projection_diagnostic/matrix_summary.json
```

## 重点確認項目

- `matrix_basic` の `overall_pass`
- `matrix_extended_probe` の `overall_pass`
- `matrix_slow_drift_projection_diagnostic` の `overall_pass`
- `boundary_violation_total`
- `dry_run_write_violation_count`
- `forbidden_write_count`
- `projection_min`
- `action_frame_min`
- per-run配下に探索診断CSVが出力されるか

## 探索診断CSVの確認対象

各matrixの `validation_runs/<matrix_name>/runs/<label>/` 配下で、以下を確認する。

- `exploration_candidates.csv`
- `exploration_sandbox.csv`
- `exploration_decision.csv`
- `exploration_sidecar.csv`
- `exploration_projection.csv`
- `coactivation_gate.csv`
- `action_surface_planning_audit.csv`
- `action_frame.csv`
- `action_execution_audit.csv`

存在しないCSVがある場合は `not exported` として報告する。推測で「出力された」と報告しない。

## cleanup

```bash
rm -rf validation_runs
find . -type d \( -name "__pycache__" -o -name "pycache" \) -prune -exec rm -rf {} +
```

## 最後に報告する内容

1. 新しいCodexタスクとして実行したか
2. 対象PRが PR #23 だったか
3. head branch が `task23-diagnostic-export-matrices` だったか
4. base branch が `main` だったか
5. `git log -1 --oneline`
6. `compileall` の結果
7. `smoke` の結果
8. `matrix_basic` の結果
9. `matrix_extended_probe` の結果
10. `matrix_slow_drift_projection_diagnostic` の結果
11. 探索診断CSVの出力状況
12. cleanup後の `git status --short`
