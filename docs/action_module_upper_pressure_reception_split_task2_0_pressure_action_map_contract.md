# 作用モジュール 上位圧受容分離 RC1 / Task 2-0

日本語名: **圧-作用対応表の設計と検証方針**

## 0. 位置づけ

この文書は、`PressureIntentBundle` に含まれる意味を持った圧成分群を、どの作用候補へ接続するかを決める前段の契約である。

Task 2-0では、実行時の作用方針をまだ作らない。初期対応表もまだ作らない。単独Action検証もまだ実装しない。

Task 2-0で固定するのは次の3点である。

1. 圧-作用対応表が何を表すか
2. その対応表をどう検証・校正するか
3. どの情報を監査列として残すか

## 1. 既存構造との整合

上位圧から作用モジュールまでは、すでに複数の翻訳層を持つ。

```text
formal G/K
↓
上位圧
↓
H11局所受容
↓
PressureIntentBundle
↓
作用面計画
↓
作用候補
↓
同時発火門
↓
ActionFrame
↓
作用モジュール / 疑似現実
```

したがって、Task 2以降で新しい曖昧な意味翻訳層を追加してはならない。

`PressureIntentBundle` は、すでに次の情報を保持している。

- `pressure_component`
- `component_direction`
- `component_signed_value`
- `component_magnitude`
- `h11_received_signed_pressure`
- `h11_received_abs_pressure`
- `control_domain`
- `semantic_effect`
- `intent_family`
- `suggested_control_route`
- action channel relevance flags

Task 2以降の部品は、この意味を作り直すのではなく、保持したまま作用候補へ接続する。

## 2. 圧-作用対応表の定義

圧-作用対応表は、次のような手作りの直接変換表ではない。

```text
b圧 → Action A
c圧 → Action B
```

正しくは、各Actionが実際にどの圧成分方向へどれだけ効いたかを表す、検証由来の対応表である。

```text
Action A → b圧方向 0.60 / c圧方向 0.25 / 副作用 0.15
Action B → b圧方向 0.10 / c圧方向 0.70 / 副作用 0.20
```

そのため、対応表の主キーは少なくとも次を持つ。

```text
action_channel
action_primitive
scenario_or_state_band
pressure_component
component_direction
```

対応表の値は少なくとも次を持つ。

```text
estimated_pressure_alignment
estimated_side_effect_burden
estimated_reversibility_effect
estimated_exploration_effect
estimated_public_effect
estimated_hidden_effect
calibration_status
mapping_source
sample_count
confidence
```

## 3. なぜAction→結果→圧対応で作るか

本上位圧の意味を保つには、圧からActionを直接手で決めるよりも、まずActionの実際の反応を測る必要がある。

```text
Actionを単独で打つ
↓
世界trace / v2 action-effect trace / G/K / O_t を読む
↓
そのActionがどの圧成分方向にどれだけ寄与したかを推定する
↓
圧-作用対応表を作る
↓
PressureIntentBundleから作用候補を選ぶときに参照する
```

これにより、初期仮説と検証済み対応を区別できる。

## 4. 既存の材料

現状の既存実装には、利用できる材料がすでにある。

### 4.1 PressureIntentBundle側

`pressure_intent.py` は、圧成分、方向、強度、意味、意図族、提案経路を保持している。これは圧側の意味情報であり、Task 2で再翻訳してはならない。

### 4.2 Action側

作用チャネルは少なくとも次の集合を持つ。

```text
exploration_injection
coupling_relief
volatility_damping
uncertainty_probe
relation_unlock
buffer_increase
no_op
```

また、既存のActionPlannerには、各チャネルに対応する関連フラグと、疑似現実向け作用primitiveが存在する。

### 4.3 v1 / v2疑似現実側

v1疑似現実では、各Action channelが public state features に直接作用する。

v2疑似現実では、各Action channelが public state と hidden state の両方に作用し、`v2_action_effect_trace` として副作用や隠れ影響も出る。

### 4.4 既存検証地図

既存の `phase2g19b1_channel_level_action_response_map.md` は、チャネル別反応地図を記録している。ただしこれは runtime policy input ではなく、review evidence である。

Task 2-2では、この既存地図を参考にしつつ、圧成分単位の対応表へ拡張する。

## 5. Task 2-1 の範囲

Task 2-1では、初期仮説版の対応表を作る。

ただし、これは校正済みではない。

必ず次を明示する。

```text
mapping_source = initial_hypothesis
calibration_status = uncalibrated
confidence = low_or_medium
```

初期仮説は、`PressureIntentBundle` の relevance flags と既存Action channelを使って作る。新しい意味ラベルは作らない。

## 6. Task 2-2 の範囲

Task 2-2では、単独Action検証で対応表を校正する。

最低限の検証単位は次である。

```text
action_channel × action_strength × scenario_or_state_band × seed
```

各検証では、同条件の `no_op` baseline と比較する。

測定対象は少なくとも次である。

```text
public state delta
hidden state delta
v2_action_effect_trace
G/K-derived geometry delta
O_t action/evaluation signal delta
side effect burden
```

この結果から、各Actionがどの圧成分方向にどれだけ合っていたかを推定する。

## 7. Task 2-3 の範囲

Task 2-3では、対応表を使って `PressureIntentBundle` から作用候補を作る。

ここでの部品は、新しい意味翻訳器ではない。

役割は次である。

```text
PressureIntentBundle
↓
圧-作用対応表を参照
↓
候補Actionを選ぶ
↓
pre-gate action candidateとして出す
```

出力候補には必ず次を残す。

```text
pressure_component
component_direction
component_magnitude
h11_received_abs_pressure
semantic_effect
intent_family
suggested_control_route
action_channel
action_primitive
action_strength
mapping_source
calibration_status
mapping_confidence
pressure_action_map_version
```

## 8. 禁止事項

Task 2以降では、次を禁止する。

```text
PressureIntentBundleの意味を作り直す
semantic_effectを別の中間意味へ翻訳する
診断用policyを呼ぶ
RepairedDiagnosticActionPolicyをFullSpec本経路で使う
未校正対応を校正済みとして扱う
v2 action-effect traceをruntime policy inputとして直接戻す
副作用を無視してActionを選ぶ
```

## 9. 完了条件

Task 2-0は、次が固定されたら完了とする。

```text
1. 圧-作用対応表の役割が固定されている
2. 圧からActionを手で直結しない方針が固定されている
3. Action→結果→圧対応を検証で推定する方針が固定されている
4. 初期仮説と校正済み対応を区別する列が固定されている
5. Task 2-1 / 2-2 / 2-3 の境界が固定されている
```

## 10. Task 2-0 結論

Task 2-0の結論は次である。

```text
必要なのは、新しい意味翻訳層ではない。
必要なのは、Actionが各圧成分方向へどれだけ効くかを検証で作る圧-作用対応表である。
```

この対応表を作るまでは、本上位圧用の作用候補生成は、未校正または仮説扱いにしなければならない。
