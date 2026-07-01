# Codex Task31: PseudoReality v2 Impl-B

## タスク名

Implement PseudoReality v2 diagnostic traces and probe matrix

## 対象リポジトリ

```text
yayararakanayana-beep/dept
```

## 対象ベースブランチ

```text
main
```

## 作業ブランチ名

```text
task31-pseudoreality-v2-impl-b-diagnostic-traces
```

## 参照docs

先に以下を読んでください。

```text
docs/PseudoReality_v2_Impl_A_Freeze.md
docs/PseudoReality_v2_Impl_B_Design.md
docs/PseudoReality_v2_AsymmetricGameWorld_Design_RC1.md
```

今回は **v2-Impl-Bのみ** を実装してください。

---

## 0. 今回の目的

PR #28で PseudoReality v2 Impl-A が main に入っています。
Impl-Aでは、v2 world engineの最小接続、shrinking_equilibrium profile、matrix_v2_smoke、v2_hidden_trace が成立しています。

今回の v2-Impl-B では、以下を追加してください。

```text
1. v2_game_trace
2. v2_resource_trace
3. v2_information_trace
4. v2_action_effect_trace
5. profile_config 反映強化
6. pseudo_reality_v2_trust_collapse profile
7. pseudo_reality_v2_public_stability_hidden_decay profile
8. matrix_v2_probe
```

目的は性能検証ではありません。

目的は、v2 world の観測・診断・副作用監査の解像度を上げることです。

---

## 1. 今回やらないこと

以下は実装しないでください。

```text
既存PseudoRealitySystemの置換
既存v1 profileの変更
既存matrixの変更
acceptance条件の緩和
O_t / G_t / K_t の大改造
ActionModuleの大改造
H-DEPT圧変換の大改造
performance superiority claim
v2追加traceをG_tへ直接混ぜること
```

v2追加traceは、まず監査・診断用です。G/K/O_tの入力を勝手に拡張しないでください。

---

## 2. 実装対象

### 2.1 asymmetric_game_v2.py の拡張

対象:

```text
localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py
```

追加・強化するもの:

```text
v2_game_trace
v2_resource_trace
v2_information_trace
v2_action_effect_trace
profile_config反映強化
```

既存の `entity_trace` / `relation_trace` / `v2_hidden_trace` は壊さないでください。

---

### 2.2 v2_game_trace

必須列:

```text
entity_id
t
scenario
seed
primary_type
cooperate_tendency
defend_tendency
explore_tendency
extract_tendency
connect_tendency
amplify_tendency
hoard_tendency
share_tendency
local_payoff
short_term_payoff
long_term_health_proxy
```

entity単位で出してください。

---

### 2.3 v2_resource_trace

必須列:

```text
t
scenario
seed
shared_resource
commons_health
resource_pressure
resource_inequality
private_resource_mean
private_resource_std
private_resource_min
private_resource_max
```

step単位で1行出してください。

---

### 2.4 v2_information_trace

必須列:

```text
t
scenario
seed
information_delay_mean
information_distortion_mean
hidden_state_visibility
private_information_rate
misread_probability_mean
information_quality_mean
information_flow_mean
coordination_lag_mean
```

step単位で1行出してください。

---

### 2.5 v2_action_effect_trace

必須列:

```text
t
scenario
seed
action_channel
action_intensity
target_count
direct_effect_score
side_effect_score
net_public_effect_score
net_hidden_effect_score
exploitation_risk_delta
trust_delta
fatigue_delta
hidden_damage_delta
resource_inequality_delta
reversibility_delta
exploration_delta
```

ActionFrameが空の場合でも、`no_action` または `no_op` 行を1行出してよいです。

---

## 3. trace値の基本ルール

```text
NaN禁止
inf禁止
None禁止
原則0.0〜1.0にclip
件数や標準偏差などは非負値でよい
時刻列は step ではなく t
scenario / seed を必ず入れる
```

---

## 4. profile_config反映強化

v2-Impl-Aでは、profile_configを受け取っていても、内部係数の多くは直書きでした。

v2-Impl-Bでは、profile_configの反映を強めてください。

推奨ヘルパー:

```python
_cfg(section, key, default)
_dynamic_intensity(name, default)
_dynamic_enabled(name, default=True)
```

反映対象:

```text
information_settings
resource_settings
relation_settings
side_effect_settings
active_dynamics
```

条件:

```text
未指定の場合はImpl-Aと近いデフォルトになる
キー欠けで落ちない
enabled=false のdynamicは効かない
intensity が反映される
```

---

## 5. 追加profile

### 5.1 trust_collapse

追加ファイル:

```text
localprep1/dept/configs/world_profiles/pseudo_reality_v2_trust_collapse.json
```

目的:

```text
信頼低下・情報歪み・調整遅れによる崩壊を再現する。
```

期待挙動:

```text
information_quality が下がる
misread_probability が上がる
coordination_lag が上がる
information_flow が下がる
hidden_damage が上がる
```

---

### 5.2 public_stability_hidden_decay

追加ファイル:

```text
localprep1/dept/configs/world_profiles/pseudo_reality_v2_public_stability_hidden_decay.json
```

目的:

```text
表面安定と内部劣化の分離を強く出す。
```

期待挙動:

```text
volatility / uncertainty は安定または低下
activity は維持
hidden_damage / latent_pressure / fatigue は上昇
reversibility / exploration は低下
```

---

## 6. matrix_v2_probe

追加ファイル:

```text
localprep1/dept/configs/matrices/matrix_v2_probe.json
```

構成:

```text
3 profiles × 3 action profiles = 9 runs
```

profiles:

```text
pseudo_reality_v2_shrinking_equilibrium
pseudo_reality_v2_trust_collapse
pseudo_reality_v2_public_stability_hidden_decay
```

action profiles:

```text
action_default
action_conservative
action_buffered
```

steps:

```text
18
```

---

## 7. runner / audit / export接続

以下に追加traceを通してください。

```text
CycleArtifacts
fullspec_integrated_closed_loop_runner.py
AuditLedgerModule.collect_outputs
scripts/run_matrix_validation.py PER_RUN_EXPORTS
```

追加する出力キー:

```text
v2_game_trace
v2_resource_trace
v2_information_trace
v2_action_effect_trace
```

既存の `v2_hidden_trace` は維持してください。

---

## 8. 検証コマンド

```bash
cd localprep1/dept

python -m compileall .

python scripts/run_smoke_validation.py

python scripts/run_matrix_validation.py \
  --matrix configs/matrices/matrix_v2_smoke.json \
  --output-dir validation_runs/v2_smoke

python scripts/run_matrix_validation.py \
  --matrix configs/matrices/matrix_v2_probe.json \
  --output-dir validation_runs/v2_probe
```

---

## 9. 確認すること

```text
compileall PASS
既存 smoke PASS
matrix_v2_smoke overall_pass true
matrix_v2_probe overall_pass true
boundary_violation_total 0
dry_run_write_violation_count 0
forbidden_write_count 0
action_frame_min > 0
```

全runで以下CSVが出ること:

```text
entity_trace.csv
relation_trace.csv
v2_hidden_trace.csv
v2_game_trace.csv
v2_resource_trace.csv
v2_information_trace.csv
v2_action_effect_trace.csv
```

数値確認:

```text
NaNなし
infなし
主要列が0.0〜1.0に収まる
```

---

## 10. cleanup

検証後に以下を実行してください。

```bash
rm -rf validation_runs
find . -type d \( -name "__pycache__" -o -name "pycache" \) -prune -exec rm -rf {} +

git status --short --branch
```

---

## 11. PR作成

検証が通った場合、PRを作成してください。

PR title:

```text
Add PseudoReality v2 diagnostic traces and probe matrix
```

PR本文に含めること:

```text
- 目的
- 追加したv2 trace
- 追加したprofile
- 追加したmatrix
- 既存smoke結果
- matrix_v2_smoke結果
- matrix_v2_probe結果
- boundary/write/forbidden writeが0であること
- 全runで追加CSVが出たこと
- 既存v1を壊していないこと
```

---

## 12. 最終報告

以下を報告してください。

```text
対象ブランチ
git log --oneline -5
追加・変更ファイル一覧
compileall結果
existing smoke結果
v2_smoke結果
v2_probe結果
出力CSV確認結果
cleanup後のgit status
commitしたか
pushしたか
PRを作成したか
PR番号とURL、または作成不能理由
```
