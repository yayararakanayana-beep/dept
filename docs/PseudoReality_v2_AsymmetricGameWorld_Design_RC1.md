# PseudoReality v2 Asymmetric Game World Design RC1 Freeze

可変型・非対称動的ゲーム疑似現実系のRC1凍結仕様です。

この文書は、Codex実装前に設計境界・trace契約・repo互換条件を固定するための仕様書です。実装作業そのものは別文書 `Codex_Task26_PseudoReality_v2_Impl_A.md` の範囲に限定します。

---

## 1. 目的

PseudoReality v2 は、既存の `PseudoRealitySystem` を置き換えるものではなく、追加world engineとして実装する。

主対象は **縮小均衡** である。

縮小均衡とは、各主体の局所合理的な防御・抱え込み・探索撤退・情報秘匿が重なり、表面上は安定しているように見える一方で、内部では探索・信頼・可逆性・余白が失われていく状態である。

v2-RC1の目的は性能検証ではなく、以下の穴探しである。

- 表面安定と内部劣化をDEPT2/H-DEPTが区別できるか
- NO_OPが本当に安全か、劣化放置かを判定できるか
- ActionFrameによる作用が縮小均衡を悪化させないか
- boundary / rollback / commit gate が危険条件で止まるか
- 既存閉ループ境界を壊さずに新しい世界を接続できるか

---

## 2. 設計名

実装上の主クラス名は以下を推奨する。

```text
AsymmetricGamePseudoRealitySystem
```

推奨配置:

```text
localprep1/dept/
  DEPT2_ActionModule_ActuationPrimitives_RC1/
    pseudo_reality/
      system.py
      asymmetric_game_v2.py
```

理由:

- 既存 `PseudoRealitySystem` が `pseudo_reality/system.py` にあるため
- v2がDEPT2本体ではなく疑似現実側の追加であることが明確になるため
- WorldAdapterからimportしやすいため

---

## 3. 絶対境界

v2 world は **ActionFrameだけ** を受け取る。

禁止:

```text
ParameterBoxを直接読む
上位圧を直接読む
G_t / O_t / K_t を直接読む
探索sidecarを直接読む
DEPT2内部へ直接書き戻す
v2_hidden_traceをG_tへ直接混ぜる
```

正しい経路:

```text
DEPT2 / H-DEPT
  ↓
ParameterBox / ShadowBox / WindowBinder
  ↓
ActionFrame
  ↓
ActionModule
  ↓
WorldAdapter
  ↓
AsymmetricGamePseudoRealitySystem
  ↓
entity_trace / relation_trace / v2追加trace
```

世界状態は v2 world 内部が正本である。G_t / O_t / K_t は世界traceから派生するだけであり、世界状態へ直接書き戻さない。

---

## 4. 現行repo互換の必須条件

### 4.1 trace時刻列

既存traceの時刻列は `step` ではなく `t` である。v2でも必ず `t` を使う。

```text
正: t
誤: step
```

`loop_step` はrunner側の補助列として付いてよい。

### 4.2 entity_trace 必須列

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

### 4.3 relation_trace 必須列

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

### 4.4 v2追加trace

v2固有traceは既存traceの置換ではなく追加監査traceである。

v2-Impl-Aで必須:

```text
v2_hidden_trace
```

v2-Impl-B以降で追加候補:

```text
v2_game_trace
v2_resource_trace
v2_information_trace
v2_action_effect_trace
```

---

## 5. FullSpecRunnerConfig 追加フィールド

現行 `profile_loader.py` は、world profile の `config` だけを `FullSpecRunnerConfig` に混ぜる。また、`FullSpecRunnerConfig` に存在しないフィールドがあると落ちる。

したがって、v2用に以下を追加する。

```python
world_engine: str = "pseudo_reality_v1"
v2_world_profile: str = ""
v2_world_config: Dict[str, Any] = field(default_factory=dict)
```

既存profileに `world_engine` がない場合は、デフォルトで `pseudo_reality_v1` として扱う。

---

## 6. world_profile JSON構造

v2固有設定は top-level に置かない。必ず `config.v2_world_config` に入れる。

正しい構造:

```json
{
  "name": "pseudo_reality_v2_shrinking_equilibrium",
  "config": {
    "world_engine": "asymmetric_game_v2",
    "scenario": "v2_shrinking_equilibrium",
    "n_entities": 24,
    "v2_world_profile": "pseudo_reality_v2_shrinking_equilibrium",
    "v2_world_config": {
      "entity_mix": {},
      "payoff_weights": {},
      "information_settings": {},
      "resource_settings": {},
      "relation_settings": {},
      "side_effect_settings": {},
      "active_dynamics": {},
      "trace_settings": {}
    }
  }
}
```

---

## 7. 主体タイプ

v2-RC1の主体タイプは5種類に固定する。

```text
stabilizer: 安定維持型
explorer: 探索型
extractor: 抽出型
connector: 橋渡し型
amplifier: 増幅型
```

主体は以下を持つ。

```text
entity_id
primary_type
type_weights
public_state
hidden_state
private_resource
information_state
payoff_weights
```

主体タイプは完全固定ではなく、混合重み `type_weights` を持ってよい。

---

## 8. 公開状態

公開状態は既存8状態量を維持する。

```text
activity
volatility
uncertainty
relation_lock
coupling
exploration
reversibility
entropy
```

値域:

```text
0.0〜1.0
NaN禁止
inf禁止
負値禁止
1.0超過禁止
最後にclipする
```

---

## 9. 隠れ状態

v2の隠れ状態は以下。

```text
latent_pressure
fatigue
private_resource
defensiveness
opportunism
cooperation_intent
information_quality
hidden_damage
```

これらは `entity_trace` に直接混ぜない。出力先は `v2_hidden_trace` とする。

ただし、時間遅れで公開状態に滲み出ることは許可する。

例:

```text
hidden_damage 上昇 → 数step後に reversibility 低下
fatigue 上昇 → 数step後に exploration 低下
```

---

## 10. 関係状態

v2内部の関係状態は以下。

```text
trust
dependency
asymmetry
information_flow
resource_flow
extraction_flow
coordination_lag
relation_rigidity
```

公開 `relation_trace` へは以下に射影する。

```text
relation_strength
relation_rigidity
flow
```

---

## 11. 資源状態・情報状態

資源状態:

```text
shared_resource
commons_health
resource_pressure
resource_inequality
private_resource
```

情報状態:

```text
information_delay
information_distortion
private_information
hidden_state_visibility
misread_probability
information_quality
```

v2-Impl-Aでは内部に簡易的に持たせてもよい。詳細trace化はv2-Impl-B以降とする。

---

## 12. v2中核力学

v2-RC1の中核力学候補:

```text
trust_decay
defensive_hoarding
exploration_cost_rise
opportunistic_extraction
explorer_fatigue
connector_overload
resource_inequality_growth
public_stability_mask
delayed_reversibility_loss
hidden_damage_growth
coordination_mismatch
commons_depletion
stabilization_lockin
buffer_overprotection
no_op_decay
```

v2-Impl-Aでは、最小実装として以下だけでもよい。

```text
trust_decay
defensive_hoarding
exploration_cost_rise
resource_inequality_growth
public_stability_mask
delayed_reversibility_loss
hidden_damage_growth
no_op_decay
```

残りはv2-Impl-B以降で拡張する。

---

## 13. v2-Impl-A profile

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

## 14. v2-Impl-A matrix

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

## 15. 実装段階分割

### v2-Impl-A

目的:

```text
v2 engineの最小接続
shrinking_equilibrium profile
entity_trace / relation_trace 既存互換
v2_hidden_trace 追加
matrix_v2_smoke
```

### v2-Impl-B

目的:

```text
追加profile
追加trace
summary metrics
matrix_v2_probe
```

追加候補:

```text
pseudo_reality_v2_trust_collapse
pseudo_reality_v2_public_stability_hidden_decay
v2_game_trace
v2_resource_trace
v2_information_trace
v2_action_effect_trace
```

---

## 16. RC1凍結結論

PseudoReality v2 RC1では以下を凍結する。

```text
PseudoReality v2 は可変型・非対称動的ゲーム疑似現実系である。
主対象は縮小均衡である。
v2は既存v1の置き換えではなく追加world engineである。
既存v1 profileに world_engine がない場合は pseudo_reality_v1 として扱う。
v2固有設定は world_profile の config.v2_world_config に入れる。
FullSpecRunnerConfig に world_engine / v2_world_profile / v2_world_config を追加する。
trace時刻列は step ではなく t を使う。
entity_trace / relation_trace は既存schema完全互換にする。
v2-Impl-Aでは v2_hidden_trace のみ必須追加traceとする。
v2 world は ActionFrame だけを受け取る。
v2 world は ParameterBox / 上位圧 / G_t / O_t / K_t を直接読まない。
v2_hidden_trace は G_t に直接混ぜない。
Codex実装は v2-Impl-A / v2-Impl-B の2段階に分ける。
```
