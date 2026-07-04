# Task 2-8a: 地形改変作用 設計仕様 RC1

## 0. 位置づけ

Task 2-7c-light の結果から、現在の6作用は「状態作用」としては一定のリスク低下を出せるが、リスクトレンドの反転または明確な緩和には届かないことが分かった。

したがって、次の段階では、危険状態そのものを押すのではなく、危険を増幅している地形・力学・ルールを変える作用を設計する。

本仕様では、これを **地形改変作用** と呼ぶ。

---

## 1. 基本方針

地形改変作用は、以下を目的にする。

```text
リスク水準を一時的に下げること
ではなく、
リスクが上がりにくい地形、
ピークが低くなる地形、
危険後に戻りやすい地形を作る。
```

金融バブルで言えば、価格を直接下げるのではなく、過熱時に「買いが入っても価格が上がりにくくなる」ルールを入れることに近い。

---

## 2. 状態作用との違い

### 2.1 状態作用

状態作用は、現在の状態値に対して働く。

```text
現在リスクが高い
↓
リスクを少し下げる
揺れを少し抑える
余裕枠を少し増やす
```

Task 2-7までの6作用は主に状態作用である。

### 2.2 地形改変作用

地形改変作用は、状態値ではなく、状態の変化規則に働く。

```text
危険入力がリスクに変換される係数
リスク上昇が次のリスク上昇を呼ぶ自己増幅
高リスク時のピーク高さ
危険状態から戻る回復勾配
```

を変える。

---

## 3. 最小3作用

RC1では、地形改変作用を3つに限定する。

### 3.1 入力感度低下作用

危険方向の入力が来ても、リスクが上がりにくくする。

対象となる力学:

```text
入力 → リスク上昇
```

金融バブル例:

```text
買いが入っても価格が跳ねにくくする。
```

期待される効果:

```text
リスク上昇傾きの低下
リスクピークの低下
副作用は中程度
短期利得は少し下がる可能性あり
```

### 3.2 自己増幅遮断作用

リスク上昇が、さらなるリスク上昇を呼ぶループを弱める。

対象となる力学:

```text
リスク上昇 → 不安定化 → さらにリスク上昇
```

金融バブル例:

```text
価格上昇が期待を呼び、期待がさらに買いを呼ぶループを弱める。
```

期待される効果:

```text
リスク加速度の低下
振動・再帰的悪化の抑制
ピーク到達の遅延または低下
副作用は局所構造に依存
```

### 3.3 回復谷形成作用

危険状態に入っても戻りやすい地形を作る。

対象となる力学:

```text
高リスク状態 → 回復方向への勾配
```

金融バブル例:

```text
過熱後に一気に崩壊するのではなく、段階的に冷える戻り道を作る。
```

期待される効果:

```text
回復時間の短縮
不可逆化リスクの低下
崩壊後の復帰失敗の減少
短期的には保守寄りになる可能性あり
```

---

## 4. 入力情報

地形改変作用は、単一情報から出してはいけない。

RC1では、以下を統合した整理済み入力を使う。

```text
下位リスク情報
+ v8局所観測証拠
+ 上位圧による発動制度調整
+ 探索モジュールによる効率候補
```

---

## 5. 下位リスク情報

下位レイヤーは、マクロな危険度・トレンド・回復余地を出す。

必要な代表項目:

```text
risk_level
risk_slope
risk_acceleration
input_sensitivity_score
amplification_score
peak_risk_estimate
recovery_margin
irreversibility_risk
local_uncertainty
```

役割:

```text
いつ危ないか
どれくらい危ないか
リスクが水準問題か、傾き問題か、加速度問題か
回復余地があるか
```

を判断する。

---

## 6. v8局所観測証拠

v8局所観測は、危険の局所的な原因を読む。

下位リスク情報だけでは、危険の量は分かるが、どの力学を変えるべきかは曖昧になる。

v8局所観測は以下を与える。

```text
local_pattern_type
local_confidence
local_uncertainty
local_counter_evidence
recommended_terrain_target
requires_micro_audit
```

想定する local_pattern_type:

```text
boundary_instability
input_overreaction
recursive_amplification
oscillation
recurrence
recovery_failure
regime_switch
split_merge_return_failure
unresolved_noise_cluster
```

---

## 7. 下位リスク × v8局所観測の対応

### 7.1 入力感度低下作用を示唆する条件

下位リスク情報:

```text
input_sensitivity_score が高い
risk_slope が正
boundary risk が高い
小さい入力でrisk_levelが大きく動く
```

v8局所観測:

```text
input_overreaction
boundary_instability
local transition が過敏
counter evidence が弱い
```

### 7.2 自己増幅遮断作用を示唆する条件

下位リスク情報:

```text
risk_acceleration が正
amplification_score が高い
risk_slope が加速している
peak_risk_estimate が高い
```

v8局所観測:

```text
recursive_amplification
oscillation
recurrence
feedback-like local loop
```

### 7.3 回復谷形成作用を示唆する条件

下位リスク情報:

```text
recovery_margin が低い
irreversibility_risk が高い
risk_level が下がりにくい
```

v8局所観測:

```text
recovery_failure
regime_switch
split_merge_return_failure
post-shock return failure
```

---

## 8. 上位圧の役割

上位圧は、地形改変作用を直接選ばない。

上位圧は以下を調整する。

```text
発動閾値
強度上限
採用ハードル
診断深度
サンドボックス投入率
冷却期間
監査要求
```

例:

```text
rollback_sensitivity increase
  → 回復谷形成作用の発動閾値を下げる

pressure_cap decrease
  → 地形改変作用の強度上限を下げる

diagnostic_depth increase
  → v8局所観測またはmicro監査要求を強める

exploration_frequency increase
  → 改変候補をサンドボックスで多めに試す

adoption_threshold increase
  → 地形改変候補の採用ハードルを上げる
```

これにより、圧は保持されるが、圧が恣意的に作用を直接指定することは避ける。

---

## 9. 探索モジュールの役割

探索モジュールは、地形改変作用の効率を上げる。

担当する内容:

```text
どの地形パラメーターを変えると効くか
どの改変方向が副作用少ないか
どの局所にだけ作用すべきか
どの改変がリスクピークを下げるか
どの改変が利得AUCを改善するか
```

探索モジュールは直接作用しない。

出力は、地形改変候補としてサンドボックスへ渡す。

---

## 10. 作用モジュール境界

作用モジュールは、生の下位レイヤー情報やv8内部状態を直接読まない。

作用モジュールに渡してよいのは、整理済みの候補だけである。

許可される入力例:

```text
terrain_reshaping_candidate
terrain_target
expected_trend_effect
expected_peak_effect
expected_recovery_effect
side_effect_estimate
local_evidence_summary
upper_pressure_modulation_summary
sandbox_validation_summary
```

禁止:

```text
G_t 直接参照
K_t 直接参照
O_t / v8 内部への直接アクセス
探索モジュールの未検証候補を本作用化
上位圧だけで地形改変作用を決定
```

---

## 11. サンドボックス検証条件

地形改変作用は、原則としてサンドボックス検証を通す。

最低限見る指標:

```text
risk_peak_reduction
risk_slope_delta
risk_acceleration_delta
risk_auc_reduction
gain_auc_delta
side_effect_auc
recovery_time_delta
irreversibility_risk_delta
post_action_persistence
```

重要なのは、作用中だけの改善ではなく、作用を止めた後も地形改善が残るかである。

```text
post_action_persistence > 0
```

を地形改変作用の重要指標とする。

---

## 12. 検証設計

次の検証では、以下を比較する。

```text
A. no_op
B. 状態作用のみ
C. 地形改変作用のみ
D. 状態作用 + 地形改変作用
```

評価指標:

```text
リスクピーク
リスク傾き
リスク加速度
リスクAUC
利得AUC
副作用AUC
回復時間
崩壊/不可逆化率
長期正味利益
作用停止後の改善持続
```

---

## 13. RC1でまだやらないこと

```text
本物のH-DEPT上位圧との完全接続
ActionFrame生成
作用モジュール呼び出し
世界runtime呼び出し
canonical parameter 書き戻し
実データ適用
```

---

## 14. 成功条件

地形改変作用は、以下を満たすと有望とする。

```text
状態作用のみより risk_peak が低い
状態作用のみより risk_auc が低い
状態作用のみより risk_slope または risk_acceleration が改善する
副作用AUC込みでも long_term_net_benefit が改善する
作用停止後も一部改善が残る
v8局所観測が改変対象の根拠として保存されている
上位圧は閾値・強度・採用条件調整として使われている
```

---

## 15. 次タスク案

```text
Task 2-8b:
  地形改変作用 最小検証 RC1

内容:
  - v2危険状態を使う
  - 下位リスク情報を生成
  - v8局所観測証拠を模擬生成
  - 3地形改変作用を候補化
  - no_op / 状態作用 / 地形改変作用 / 併用 を比較
  - 40step〜100stepで長期指標を見る
```
