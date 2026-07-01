# Codex Task26: PseudoReality v2 Impl-A

## タスク名

Implement PseudoReality v2 asymmetric shrinking-equilibrium smoke world

## 対象リポジトリ

```text
yayararakanayana-beep/dept
```

## 対象ベースブランチ

```text
main
```

## 参照仕様書

先に以下を読んでください。

```text
docs/PseudoReality_v2_AsymmetricGameWorld_Design_RC1.md
```

ただし、今回は仕様書全体を一気に実装しないでください。

今回は **v2-Impl-A のみ** を実装します。

---

## 0. 今回やること

PseudoReality v2 の最小接続を追加してください。

v2は、可変型・非対称動的ゲーム疑似現実系です。
主ターゲットは縮小均衡です。

今回の範囲は以下のみです。

```text
v2 engineの最小接続
shrinking_equilibrium profile 1つ
entity_trace / relation_trace 既存互換
v2_hidden_trace 追加
matrix_v2_smoke 追加
既存smokeとv2_smokeの通過確認
```

以下は今回は実装しないでください。

```text
v2-Impl-B
追加profile
v2_game_trace
v2_resource_trace
v2_information_trace
v2_action_effect_trace
summary metrics拡張
performance validation
既存O_t/G_t/K_tの改造
```

---

## 1. 作業開始時に確認すること

```bash
pwd
git status --short --branch
git branch --show-current
git log --oneline -5
```

作業ディレクトリの想定:

```bash
cd localprep1/dept
```

まず確認すること:

```text
既存PseudoRealitySystemの実装場所
既存WorldAdapterの実装場所
既存world_profile読み込み処理
既存matrix runner
既存CSV出力処理
FullSpecRunnerConfigの定義場所
CycleArtifactsの定義場所
AuditLedgerModule.collect_outputsの構造
```

---

## 2. 実装範囲

### 2.1 FullSpecRunnerConfig に追加

`FullSpecRunnerConfig` に以下を追加してください。

```python
world_engine: str = "pseudo_reality_v1"
v2_world_profile: str = ""
v2_world_config: Dict[str, Any] = field(default_factory=dict)
```

注意:

```text
既存profileに world_engine がなくても落ちないこと。
既存profileはデフォルトで pseudo_reality_v1 として扱うこと。
```

---

### 2.2 AsymmetricGamePseudoRealitySystem を追加

推奨配置:

```text
localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py
```

追加する主クラス:

```python
AsymmetricGamePseudoRealitySystem
```

最低限必要な機能:

```text
__init__(seed, scenario, n_entities, action_coupling, noise_scale, drift_scale, profile_name, profile_config)
step(action_frame=None)
emit_trace()
```

`emit_trace()` は以下を返してください。

```python
{
  "entity_trace": entity_trace_df,
  "relation_trace": relation_trace_df,
  "v2_hidden_trace": v2_hidden_trace_df,
}
```

---

### 2.3 WorldAdapterで v1 / v2 切替

`WorldAdapter.__init__` で `cfg.world_engine` を見て切り替えてください。

擬似コード:

```python
if str(getattr(cfg, "world_engine", "pseudo_reality_v1")) == "asymmetric_game_v2":
    self.world = AsymmetricGamePseudoRealitySystem(...)
    self.baseline_world = AsymmetricGamePseudoRealitySystem(...)
else:
    self.world = PseudoRealitySystem(world_cfg)
    self.baseline_world = PseudoRealitySystem(world_cfg)
```

注意:

```text
既存v1のデフォルト挙動を変えないこと。
既存PseudoRealitySystemを削除しないこと。
```

---

### 2.4 trace schema

#### entity_trace 必須列

```text
entity_id
t
scenario
seed
activity
volatility
uncertainty
relation_lock
coupling
exploration
reversibility
entropy
```

#### relation_trace 必須列

```text
source
target
relation_strength
relation_rigidity
flow
t
scenario
seed
```

#### v2_hidden_trace 必須列

```text
entity_id
t
scenario
seed
latent_pressure
fatigue
private_resource
defensiveness
opportunism
cooperation_intent
information_quality
hidden_damage
```

重要:

```text
trace時刻列は step ではなく t です。
loop_step はrunner側の補助列として付く場合があります。
```

値域:

```text
0.0〜1.0
NaN禁止
inf禁止
clip必須
```

---

### 2.5 CycleArtifacts に v2_hidden_trace を追加

`CycleArtifacts` に以下を追加してください。

```python
v2_hidden_trace: pd.DataFrame = field(default_factory=pd.DataFrame)
```

---

### 2.6 run_cycle で v2_hidden_trace を取り出す

`world_trace_after` を得た後、trace dictに `v2_hidden_trace` がある場合だけ取り出してください。

擬似コード:

```python
artifacts.world_trace_after = self.action_execution_module.apply(self.world_adapter, artifacts.action_frame)

if isinstance(artifacts.world_trace_after, dict):
    artifacts.v2_hidden_trace = self._tag(
        artifacts.world_trace_after.get("v2_hidden_trace", pd.DataFrame()),
        step,
    )
```

v1では空DataFrameのままにしてください。

---

### 2.7 AuditLedgerModule.collect_outputs に追加

`AuditLedgerModule.collect_outputs(cycles)` が `CycleArtifacts` から各DataFrameを集約する構造なら、`v2_hidden_trace` も出力対象に追加してください。

出力キー:

```text
v2_hidden_trace
```

v2-Impl-Aでは、他のv2 traceは追加しないでください。

---

### 2.8 run_matrix_validation.py に追加

`PER_RUN_EXPORTS` に以下を追加してください。

```python
"v2_hidden_trace",
```

v2-Impl-Aでは、以下は追加しないでください。

```python
"v2_game_trace",
"v2_resource_trace",
"v2_information_trace",
"v2_action_effect_trace",
```

---

### 2.9 world profileを追加

追加ファイル:

```text
configs/world_profiles/pseudo_reality_v2_shrinking_equilibrium.json
```

内容:

```json
{
  "name": "pseudo_reality_v2_shrinking_equilibrium",
  "config": {
    "world_engine": "asymmetric_game_v2",
    "scenario": "v2_shrinking_equilibrium",
    "n_entities": 24,
    "v2_world_profile": "pseudo_reality_v2_shrinking_equilibrium",
    "v2_world_config": {
      "entity_mix": {
        "stabilizer": 0.30,
        "explorer": 0.20,
        "extractor": 0.20,
        "connector": 0.20,
        "amplifier": 0.10
      },
      "payoff_weights": {
        "short_term_gain_weight": 0.65,
        "long_term_health_weight": 0.35,
        "risk_avoidance_weight": 0.70,
        "trust_preference_weight": 0.40,
        "exploration_preference_weight": 0.45,
        "extraction_reward_weight": 0.55
      },
      "information_settings": {
        "information_delay_steps": 2,
        "information_distortion_scale": 0.06,
        "hidden_state_visibility": 0.22,
        "private_information_rate": 0.30,
        "misread_probability": 0.10
      },
      "resource_settings": {
        "initial_shared_resource": 0.72,
        "resource_recovery_rate": 0.018,
        "resource_depletion_rate": 0.035,
        "commons_dependency": 0.55,
        "resource_inequality_growth": 0.03
      },
      "relation_settings": {
        "initial_trust": 0.55,
        "trust_decay_rate": 0.028,
        "relation_lock_growth_rate": 0.025,
        "relation_unlock_cost": 0.035,
        "dependency_strength": 0.50,
        "fragmentation_rate": 0.018
      },
      "side_effect_settings": {
        "exploration_exploitation_risk": 0.24,
        "stabilization_lockin_side_effect": 0.22,
        "buffer_overprotection_effect": 0.16,
        "relation_unlock_fragmentation_risk": 0.16,
        "no_op_decay_rate": 0.025
      },
      "active_dynamics": {
        "trust_decay": {"enabled": true, "intensity": 0.04},
        "defensive_hoarding": {"enabled": true, "intensity": 0.05},
        "exploration_cost_rise": {"enabled": true, "intensity": 0.04},
        "resource_inequality_growth": {"enabled": true, "intensity": 0.04},
        "public_stability_mask": {"enabled": true, "intensity": 0.05},
        "delayed_reversibility_loss": {"enabled": true, "intensity": 0.035},
        "hidden_damage_growth": {"enabled": true, "intensity": 0.04},
        "no_op_decay": {"enabled": true, "intensity": 0.03}
      },
      "trace_settings": {
        "emit_entity_trace": true,
        "emit_relation_trace": true,
        "emit_v2_hidden_trace": true
      }
    }
  }
}
```

---

### 2.10 matrixを追加

追加ファイル:

```text
configs/matrices/matrix_v2_smoke.json
```

内容:

```json
{
  "name": "matrix_v2_smoke",
  "description": "Minimal smoke matrix for PseudoReality v2 asymmetric shrinking equilibrium world.",
  "runs": [
    {
      "label": "v2_shrinking_equilibrium_default_smoke",
      "world_profile": "pseudo_reality_v2_shrinking_equilibrium",
      "action_profile": "action_default",
      "validation_profile": "stress_medium",
      "overrides": {"seed": 501, "steps": 12}
    },
    {
      "label": "v2_shrinking_equilibrium_conservative_smoke",
      "world_profile": "pseudo_reality_v2_shrinking_equilibrium",
      "action_profile": "action_conservative",
      "validation_profile": "stress_medium",
      "overrides": {"seed": 502, "steps": 12}
    },
    {
      "label": "v2_shrinking_equilibrium_buffered_smoke",
      "world_profile": "pseudo_reality_v2_shrinking_equilibrium",
      "action_profile": "action_buffered",
      "validation_profile": "stress_medium",
      "overrides": {"seed": 503, "steps": 12}
    }
  ]
}
```

---

## 3. 禁止事項

```text
既存PseudoRealitySystemを削除しない
既存v1 profileを変更しない
既存matrixを変更しない
既存runnerのデフォルト挙動を変えない
acceptance条件を緩めない
ActionModuleを大改造しない
O_t / G_t / K_t を改造しない
v2_hidden_traceをG_tへ直接混ぜない
ParameterBoxをv2 worldへ渡さない
上位圧をv2 worldへ直接渡さない
G_t / O_t / K_t をv2 worldへ渡さない
v2-Impl-B範囲を今回実装しない
```

---

## 4. 検証コマンド

```bash
cd localprep1/dept

python -m compileall .

python scripts/run_smoke_validation.py

python scripts/run_matrix_validation.py \
  --matrix configs/matrices/matrix_v2_smoke.json \
  --output-dir validation_runs/v2_smoke
```

---

## 5. 確認すること

```text
compileall PASS
既存 smoke PASS
v2 smoke overall_pass true
boundary_violation_total 0
dry_run_write_violation_count 0
forbidden_write_count 0
action_frame_min > 0
```

全runで以下が存在すること:

```text
entity_trace.csv
relation_trace.csv
v2_hidden_trace.csv
```

v2挙動確認:

```text
public_state が大きく壊れないこと
hidden_damage / latent_pressure / fatigue が一定程度動くこと
NaN / inf が出ないこと
値域が0.0〜1.0に収まること
```

---

## 6. cleanup

検証後、以下を実行してください。

```bash
rm -rf validation_runs
find . -type d \( -name "__pycache__" -o -name "pycache" \) -prune -exec rm -rf {} +

git status --short
```

---

## 7. PR作成

検証が通った場合、新しいブランチでcommitし、PRを作成してください。

推奨ブランチ名:

```text
task26-pseudoreality-v2-shrinking-smoke
```

推奨commit message:

```text
Add PseudoReality v2 shrinking-equilibrium smoke world
```

推奨PR title:

```text
Add PseudoReality v2 shrinking-equilibrium smoke world
```

PR本文に含めること:

```text
目的
追加したv2 world engine
追加したworld profile
追加したmatrix
追加したtrace CSV
既存v1 smokeが通ったこと
v2 smokeの結果
boundary/write/forbidden writeが0であること
v2_hidden_traceが全runで出力されたこと
既存v1を壊していないこと
```

PR作成できない場合は、以下を報告してください。

```text
理由
git diff --stat
git diff
検証結果
作成したファイル一覧
```

---

## 8. 最終報告

以下を報告してください。

```text
対象ブランチ
git log --oneline -5
追加ファイル一覧
compileall結果
existing smoke結果
v2 smoke結果
出力CSV確認結果
cleanup後のgit status
commitしたか
pushしたか
PRを作成したか
PR番号とURL、または作成不能理由
```
