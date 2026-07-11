# Task 3.2-1 状態・ログ項目対応表

## 1. 既存v3.3から直接取得できる状態

`DistributionTerrainV322World`および継承元には、Task 2でスナップショット可能な次の全配列が存在する。

### 分布

- `distribution`

### 基本地形・応答状態

- `short_payoff`
- `medium_payoff`
- `friction`
- `viscosity`
- `damage`
- `rigidity`
- `recovery_speed`

### v3.2期待値・探索・保持状態

- `existing_path_expected_value`
- `exploration_cost`
- `exploration_option_value`
- `exploration_net_expected_value`
- `expected_value_advantage`
- `information_memory`
- `viability_reserve`
- `route_support`
- `maintenance_cost`
- `net_viability_value`
- `negative_viability_pressure`

### v3.2.2費用削減状態

- `effective_medium_payoff`
- `operating_cost`
- `cost_reduction_gain`
- `cost_reduction_preference`

これら23配列をTask 2の各`X_t`で必須保存する。

## 2. 既存v3.3から取得できる遷移記憶

次は直前の遷移や応答を表すため、現在状態本体と区別して保存できる。

### 配列

- `last_flow`
- `short_gain_information_conversion`
- `short_path_decline_information`
- `exploration_experience_information`
- `support_erosion`
- `released_mass`
- `release_reallocation_flow`

### スカラー

- `total_gain_delta_signal`
- `last_external_deformation_strength`
- `last_threshold_activation_strength`
- `last_distribution_weighted_threshold_activation_strength`

これらはTask 2初回では任意だが、保存する場合は履歴由来情報として明示する。

## 3. 既存の外部入力

次の6要因は現在時点で観測済みの入力として記録できる。

- `external_resource_supply`
- `external_demand`
- `external_competition_pressure`
- `external_information_noise`
- `external_shock`
- `external_constraint_pressure`

資源供給と需要は`[-1, 1]`、その他4要因はTask 3.1eと同じく`[0, 1]`を探索契約の範囲とする。

## 4. 既存traceで取得できる要約

現在の`emit_trace()`は次の要約表を返す。

- 分布要約
- 地形要約
- 流量要約
- 外部入力要約
- 補助状態要約

ただし、これらは平均、中心、広がり等の要約であり、全配列ではない。

## 5. Task 2で追加実装が必要なもの

現在の`emit_trace()`だけでは今回の目的を満たさない。Task 2では世界本体を改変せず、軌道生成側から各ステップの全配列をコピーして保存する。

追加が必要な記録:

- `trajectory_id`
- `scenario_id`
- `initial_state_id`
- `world_version`
- `config_version`
- `dataset_split`
- 各ステップの全状態配列参照
- 観測済みイベント
- 実施済み作用
- 観測済み応答
- 採点用の次状態参照
- 将来リスク結果
- 回復結果
- 不可逆性段階
- リスク深度候補
- 境界通過時刻

## 6. 初回Task 2でnullを許可するもの

作用試験や反実仮想複製をまだ行わない初回軌道では、次を未評価としてよい。

- `observed_action`
- `observed_response`
- `irreversibility_level`
- リスク深度候補
- `boundary_crossing_step`
- 回復作用結果

存在しない値を推測で埋めず、`null`または`not_evaluated`を使用する。

## 7. Task 2への実装指針

各軌道で次を行う。

1. reset直後を`step=0`の`X_0`として保存する。
2. 時点`t`で既知の外部入力とイベントを保存する。
3. `world.step()`を1回実行する。
4. 新しい状態を`X_{t+1}`として保存する。
5. `prediction_step=t`、`target_step=t+1`の正解参照を作る。
6. 軌道終了後に将来結果ラベルを更新する。
7. 契約検証器で軌道単位の完全性を確認する。

初回は少数seed・短い軌道で記録経路を確認し、大規模生成は行わない。
