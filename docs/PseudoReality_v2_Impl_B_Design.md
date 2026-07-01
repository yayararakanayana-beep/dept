# PseudoReality v2 Impl-B Design

## 0. 位置づけ

この文書は、PseudoReality v2 Impl-A 完了後に進む v2-Impl-B の設計文書である。

v2-Impl-A では、以下が完了している。

```text
- AsymmetricGamePseudoRealitySystem の最小接続
- world_engine による v1 / v2 切替
- pseudo_reality_v2_shrinking_equilibrium profile
- matrix_v2_smoke
- entity_trace / relation_trace / v2_hidden_trace の出力
- 既存smoke PASS
- v2_smoke overall_pass true
- boundary / dry_run_write / forbidden_write 0
```

v2-Impl-B の目的は、v2 world を「ただ動く世界」から「読める世界・診断できる世界」へ拡張することである。

ただし、v2-Impl-B もまだ性能検証ではない。目的は、観測・診断・副作用監査の解像度を上げることである。

---

## 1. v2-Impl-B の主目的

v2-Impl-B の主目的は以下である。

```text
1. v2追加traceを拡張する
2. v2 profileを増やす
3. profile_config の反映を強める
4. matrix_v2_probe を追加する
5. 既存v1とImpl-A smokeを壊さない
```

v2-Impl-Bで追加するtraceは以下。

```text
v2_game_trace
v2_resource_trace
v2_information_trace
v2_action_effect_trace
```

v2-Impl-Bで追加するprofileは以下。

```text
pseudo_reality_v2_trust_collapse
pseudo_reality_v2_public_stability_hidden_decay
```

v2-Impl-Bで追加するmatrixは以下。

```text
matrix_v2_probe
```

---

## 2. v2-Impl-B でやらないこと

v2-Impl-Bでは以下を行わない。

```text
- 既存PseudoRealitySystemの置換
- 既存v1 profileの変更
- 既存matrixの変更
- acceptance条件の緩和
- O_t / G_t / K_t の大改造
- ActionModuleの大改造
- H-DEPT圧変換の大改造
- performance superiority claim
- v2_hidden_trace や v2追加trace を G_t へ直接混ぜること
```

v2追加traceは、まず監査・診断用である。G/K/O_t の入力を勝手に拡張しない。

---

## 3. 追加trace設計

### 3.1 共通trace契約

すべてのv2追加traceは、以下の列を持つ。

```text
t
scenario
seed
```

entity単位traceでは、さらに以下を持つ。

```text
entity_id
```

値域は原則として `0.0〜1.0` にclipする。ただし、標準偏差や件数など明らかに異なる意味を持つ列は、非負値でよい。

禁止:

```text
NaN
inf
None混入
object列への数値混入
```

---

### 3.2 v2_game_trace

目的:

```text
各主体が、縮小均衡の中でどのような局所反応傾向を持ったかを読む。
```

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

意味:

```text
cooperate_tendency:
  協力方向への局所傾向

defend_tendency:
  防御・固定・抱え込み方向への局所傾向

explore_tendency:
  探索方向への局所傾向

extract_tendency:
  抽出・利用方向への局所傾向

connect_tendency:
  橋渡し・関係修復方向への局所傾向

amplify_tendency:
  ノイズ・不信・反応増幅方向への局所傾向

hoard_tendency:
  資源抱え込み方向への局所傾向

share_tendency:
  資源共有方向への局所傾向

local_payoff:
  そのstepにおける局所利得

short_term_payoff:
  短期利得

long_term_health_proxy:
  長期健全性のproxy
```

期待する読み方:

```text
縮小均衡では、短期利得や防御傾向が上がる一方、長期健全性・協力・探索が落ちる。
```

---

### 3.3 v2_resource_trace

目的:

```text
共有資源・私的資源・資源偏りを読む。
```

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

意味:

```text
shared_resource:
  全体で共有される資源量

commons_health:
  共有基盤の健全性

resource_pressure:
  資源不足・競争圧

resource_inequality:
  資源偏り

private_resource_mean/std/min/max:
  主体ごとの私的資源の集約値
```

期待する読み方:

```text
縮小均衡では、共有資源やcommons_healthが下がり、resource_inequalityやresource_pressureが上がる。
```

---

### 3.4 v2_information_trace

目的:

```text
情報遅延・歪み・隠れ状態の見えにくさ・誤読確率を読む。
```

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

意味:

```text
information_delay_mean:
  情報伝達の平均遅延

information_distortion_mean:
  情報歪みの平均

hidden_state_visibility:
  隠れ状態がどの程度表面に見えるか

private_information_rate:
  私有情報比率

misread_probability_mean:
  誤読確率平均

information_quality_mean:
  情報品質平均

information_flow_mean:
  情報流量平均

coordination_lag_mean:
  調整遅れ平均
```

期待する読み方:

```text
trust_collapse profileでは、misread_probability / coordination_lag / distortion が上がり、information_quality / information_flow が下がる。
```

---

### 3.5 v2_action_effect_trace

目的:

```text
ActionFrameの直接効果と副作用を読む。
```

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

方針:

```text
ActionFrameが空の場合でも、no_action または no_op 行を1行出してよい。
ただし、既存ActionFrame処理を壊さない。
```

期待する読み方:

```text
volatility_damping は表面を安定させるが、profileによっては hidden_damage / lockin を増やす。
exploration_injection は探索を上げるが、extractor条件では exploitation_risk を上げる。
buffer_increase は可逆性を上げるが、過保護で探索を下げる可能性がある。
```

---

## 4. profile_config 反映強化

v2-Impl-Aでは、`profile_config` を受け取るが、内部係数の多くは直書きである。

v2-Impl-Bでは、profile_configの反映を強める。

推奨方針:

```text
- 既存の値を大きく変えすぎない
- 未指定の場合はImpl-Aと同等のデフォルトに戻る
- profile_configのキーが欠けていても落ちない
- active_dynamicsの enabled / intensity を反映する
```

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

---

## 5. 追加profile設計

### 5.1 pseudo_reality_v2_trust_collapse

目的:

```text
信頼低下・情報歪み・調整遅れによる崩壊を再現する。
```

想定力学:

```text
trust_decay 強め
information_distortion 強め
coordination_mismatch 強め
connector_overload 強め
amplifier_noise_spread 中程度
hidden_damage_growth 中程度
```

期待挙動:

```text
trust proxy が下がる
information_quality が下がる
misread_probability が上がる
coordination_lag が上がる
connector系の負荷が上がる
```

このprofileでは、悪意ある主体がいなくても、情報遅延と誤読で協力が壊れることを検証する。

---

### 5.2 pseudo_reality_v2_public_stability_hidden_decay

目的:

```text
表面安定と内部劣化の分離を強く出す。
```

想定力学:

```text
public_stability_mask 強め
stabilization_lockin 強め
hidden_damage_growth 強め
delayed_reversibility_loss 強め
buffer_overprotection 中程度
no_op_decay 強め
```

期待挙動:

```text
volatility / uncertainty は下がる、または安定する
activity は維持される
hidden_damage / latent_pressure / fatigue は上がる
reversibility / exploration は下がる
```

このprofileでは、上位観測が単純に「揺らぎ低下＝良い」と誤読しないかを確認する。

---

## 6. matrix_v2_probe 設計

追加ファイル候補:

```text
configs/matrices/matrix_v2_probe.json
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
18 または 24
```

推奨は最初 18 steps。重ければ12でもよいが、hidden decayを見るなら18以上が望ましい。

matrix acceptance:

```text
overall_pass true
boundary_violation_total 0
dry_run_write_violation_count 0
forbidden_write_count 0
action_frame_min > 0
```

CSV確認:

```text
entity_trace.csv
relation_trace.csv
v2_hidden_trace.csv
v2_game_trace.csv
v2_resource_trace.csv
v2_information_trace.csv
v2_action_effect_trace.csv
```

---

## 7. 実装影響範囲

v2-Impl-Bで変更してよい範囲:

```text
DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py
configs/world_profiles/pseudo_reality_v2_trust_collapse.json
configs/world_profiles/pseudo_reality_v2_public_stability_hidden_decay.json
configs/matrices/matrix_v2_probe.json
dept2_fullspec_runner_rc1/contracts/cycle_state.py
dept2_fullspec_runner_rc1/runner/fullspec_integrated_closed_loop_runner.py
dept2_fullspec_runner_rc1/modules/audit_ledger_module.py
scripts/run_matrix_validation.py
```

変更しない方がよい範囲:

```text
既存PseudoRealitySystem
既存v1 world_profiles
既存matrices
O_t / G_t / K_t modules
ActionModule core
acceptance_pass 条件
```

---

## 8. v2-Impl-B 成功条件

v2-Impl-Bの成功条件は以下。

```text
compileall PASS
既存 smoke PASS
matrix_v2_smoke PASS
matrix_v2_probe PASS
boundary_violation_total 0
dry_run_write_violation_count 0
forbidden_write_count 0
v2追加trace CSV が全runで出る
v1 default挙動が壊れていない
```

---

## 9. v2-Impl-B後に残す課題

v2-Impl-B後も、以下は未完了として残す。

```text
- v2追加traceをO_t/G_t/K_tへどう接続するか
- v2 metricsの正式採用
- long-run v2 validation
- stress/ablation for v2 profiles
- extractor_contamination / coordination_failure / commons_depletion profiles
- profile_config の完全体系化
- pseudo-reality v2 RC1 freeze
```

v2-Impl-Bは、あくまで「観測・診断traceの拡張」と「probe matrix」の段階である。
