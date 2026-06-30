# Task17: Stress / Scenario Validation RC1

## 目的

Task17 は、Task16 までで統合された FullSpec Integrated Closed Loop Runner を、複数の疑似現実ストレス条件で実行し、境界違反・観測保持・探索・同時発火門・shadow-only更新が壊れないかを確認する。

このタスクは性能優位性の主張ではない。目的は、次の Task18 ablation validation に渡す watch 項目を明示することである。

## 実行したstress matrix

- S00 baseline normal
- S01 high noise / residual growth
- S02 exploration loss / overconvergence
- S03 relation lock pressure
- S04 dense same-step coactivation pressure
- S05 shock recovery window
- S06 exploration off high-noise regression

## 固定した検査観点

- boundary violation がないこと
- canonical parameter write がないこと
- world/G/K/O_t への不正書き戻しがないこと
- G/K formal input に O_t / v8 / exploration / action が混入しないこと
- O_t / residual noise ledger がノイズを捨てないこと
- 探索候補が sandbox/local audit を経ずに projection 化されないこと
- exploration sidecar が非圧縮で保持されること
- coactivation gate が ActionFrame 前に必ず通ること
- ActionModule が ActionFrame だけを受け取ること

## 結果要約

7ケースすべてで boundary violation は 0。canonical write / world write / G/K writeback も 0。
全ケースは `pass_with_watch` で、失敗ではなく watch 付き通過として扱う。

主な watch は `coactivation_dampen_zone`。これは同時発火門が中程度の同時発火を検知し、ActionFrame強度を弱めていることを意味する。
Shockケースでは `residual_noise_high` も出たため、Task18で noise ledger / exploration / gate の寄与分解を行う。

## 重要な非claim

Task17 は以下を主張しない。

- 現実投入可能
- 安全性証明済み
- deployment-ready
- combined interference solved
- 本パラメーター更新可能
- canonical write可能

Task17 の許される主張は、限定的な疑似現実 stress matrix において、統合runnerが境界違反なしに動作し、watch項目を監査可能にした、という範囲に限る。

## 次タスク

次は Task18: ablation validation。

Task18では、以下を外して寄与を確認する。

- O_tなし
- noise ledgerなし
- explorationなし
- sandboxなし
- local auditなし
- exploration bridgeなし
- coactivation gateなし
- parameter shadowなし
- ActionModule boundary guardなし
