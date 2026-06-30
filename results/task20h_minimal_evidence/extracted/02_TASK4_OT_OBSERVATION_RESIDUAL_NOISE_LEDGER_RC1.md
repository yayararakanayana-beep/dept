# Task4: O_t Observation Module + Residual Noise Ledger RC1

## 位置づけ

Task4は、Task2で置いたO_tの最小箱を、実際の閉ループ監査に耐える局所観測面へ強化するタスクです。

Task3までで、疑似現実状態からG/Kを毎周回生成し、G/Kがworld traceへ書き戻さないことを確認しました。Task4では、その横にある下位局所観測面 `O_t` を明示化し、未分類ノイズを保存する台帳を作りました。

## 入力

```text
world trace
G_t
K_t
lower graph objects
```

## 出力

```text
O_t_native
O_t_action_view
O_t_exploration_view
ot_observation_audit
residual_noise_log
residual_noise_ledger_audit
```

## O_tの意味

`O_t` は、G/Kとは別の下位局所観測面です。

```text
G/K = 全体の分布・履歴の幾何状態
O_t = 局所的にどこで何が起きているかを見る観測面
```

ただし、O_tは正式な上位圧入力ではありません。
上位圧は引き続きG/Kのみから作ります。

## O_tの4つの出力

### 1. O_t_native

局所観測単位の本体です。

主な列です。

```text
ot_id
ot_identity_key
ot_source_trace_fingerprint
ot_residual_score
ot_noise_score
ot_unresolved_score
ot_ambiguity_score
ot_boundary_instability_score
ot_macro_micro_mismatch_score
ot_action_relevance_score
ot_exploration_gap_score
ot_local_observation_need_score
ot_explanation_status
```

### 2. O_t_action_view

作用候補生成側が読むビューです。

ただし、ActionModuleへ直接渡してはいけません。

### 3. O_t_exploration_view

探索候補生成側が後続Taskで読むビューです。

Task4時点では探索モジュールはplaceholderなので、未検証探索軸はまだ作用側へ流れません。

### 4. residual_noise_log

未分類ノイズを捨てない台帳です。

残す対象は以下です。

```text
残差
未解決信号
曖昧性
macro/micro mismatch
boundary instability
低信号ノイズ
```

## 境界契約

Task4では以下を境界guardで検査します。

```text
O_tはG/K生成器ではない
O_tは上位圧formal inputではない
O_tはActionModule直接入力ではない
O_tはworldへ書き戻さない
residual_noise_logは全O_t行を保持する
未分類ノイズはdiscardしない
residual_noise_logはG/Kやworldへ書き戻さない
```

## 実行結果

確認実行:

```bash
python runner/run_fullspec_integrated_closed_loop_runner_rc1.py --steps 3 --seed 42 --scenario normal --out results
```

結果:

```text
cycle_rows: 3
action_frame_rows: 440
ot_native_rows: 54
ot_action_view_rows: 54
ot_exploration_view_rows: 54
ot_observation_audit_rows: 3
residual_noise_rows: 54
residual_noise_ledger_audit_rows: 3
boundary_violation_count: 0
all_noise_retained: true
all_sanity_checks_passed: true
```

## テスト

```text
10 passed
```

追加テスト:

```text
O_t views and noise ledger emitted
O_t is not G/K generator or formal input
residual noise retains low and unclassified noise
O_t action view flows to planning but not ActionModule directly
```

## Scope Limit

Task4はO_tとノイズ台帳の強化までです。
探索候補生成、sandbox、探索v8監査、本格的な探索橋は後続Taskで扱います。
