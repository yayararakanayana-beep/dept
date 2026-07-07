# Task2-8j-24c-doc: 作用モジュール仮固定設計書 RC1

## 0. 文書の位置づけ

この文書は、Task2-8j-24 系列の検証結果をもとにした **作用モジュール仮固定設計書 RC1** である。

ここでいう「仮固定」とは、以下を意味する。

- 現時点の検証データから、作用モジュールが扱うべき対象・作用方向・強度・作用窓・除外条件をいったん固定する。
- ただし、本番展開、実ActionModule呼び出し、axis実行、canonical parameter write、deployment threshold freeze は行わない。
- 今後の実装・追加検証・引き継ぎの基準点として使う。

したがって、本書は「実行仕様」ではなく、**実行仕様を作るための仮固定設計契約**である。

---

## 1. 現在の到達点

Task2-8j-24b 系列では、作用候補をいきなり実行するのではなく、以下の順に検証した。

1. 地形から作用演算子候補を選ぶ。
2. 固定強度・単発作用で、NO_OP と比較する。
3. 複数シナリオ・複数seedで頑健性を確認する。
4. stress peak / stress concentration / large loss tail を監査する。
5. 作用強度を弱・中・強・段階的に変えて比較する。
6. 採用候補、追加検証候補、再設計候補を切り分ける。
7. 作用モジュールの仮固定設計データを作る。

この流れの結果、現時点では以下の3つだけを仮採用対象とする。

```text
relation_lock
oscillation
reversibility_loss
```

以下の2つは仮採用対象から外す。

```text
boundary_fragile
resource_pressure
```

---

## 2. 検証結果から得られた中心結論

### 2.1 強度について

Task24b5 の結果から、全体として最もバランスがよかったのは `fixed_medium` である。

整理すると以下になる。

```text
fixed_weak:
  安全寄りだが、主効果が弱い。

fixed_medium:
  主効果と副作用のバランスが最も良い。

fixed_strong:
  期待値は大きく伸びず、大負け率が増える。

gradual_ramp:
  安全側に寄る場合はあるが、初動が弱く、期待値は伸びにくい。

cautious_ramp_decay:
  さらに安全側だが、利得も落ちる。
```

したがって、今回の仮固定では **fixed_medium** を主強度として採用する。

### 2.2 作用窓について

Task24b 系列では、`wait 0-2` が主要な有効窓として残った。

```text
採用窓:
  wait 0-2

late window:
  wait 3-5 は原則としてNO_OPまたはreview寄り
```

理由は、作用が遅れると、地形の流れを変えるよりも副作用・遅延・rollback低下が目立ちやすくなるためである。

### 2.3 NO_OPについて

NO_OP は失敗ではなく、正式な作用選択肢として残す。

```text
NO_OPを選ぶ条件:
  情報不足
  採用対象外risk
  wait 0-2外
  runtime margin proxy不足
  rollback余地不足
  boundary guard不足
  未検証risk
  v2/validation情報がruntime側に混入しそうな場合
```

---

## 3. 仮固定する採用対象

### 3.1 relation_lock

```text
risk:
  relation_lock

operator family:
  lock_relief

operator:
  soft_resistance

intensity:
  fixed_medium

wait window:
  wait 0-2

status:
  provisional adoption policy対象
```

参考値:

```text
mean EV:
  0.256636

large loss rate:
  0.007407
```

設計上の意味:

relation_lock は、関係硬直が強まり、系が動きにくくなる状態を対象とする。ここでは強く壊すのではなく、中程度の抵抗緩和で硬直をほどく方向がよい。

採用理由:

- Task24b4で strong adoption candidate。
- Task24b5で fixed_medium が十分なEVを持つ。
- large loss tail が低い。
- NO_OPより明確に有利な範囲がある。

---

### 3.2 oscillation

```text
risk:
  oscillation

operator family:
  oscillation_damping

operator:
  damping

intensity:
  fixed_medium

wait window:
  wait 0-2

status:
  provisional adoption policy対象
```

参考値:

```text
mean EV:
  0.236809

large loss rate:
  0.008889
```

設計上の意味:

oscillation は、振動・往復・過反応が増えている状態を対象とする。強い抑制ではなく、中程度の減衰で揺れを抑える。

採用理由:

- Task24b4で strong adoption candidate。
- Task24b5で fixed_medium が安定。
- fixed_strong にすると副作用側が悪化しやすい。
- 初期窓での介入が有効。

---

### 3.3 reversibility_loss

```text
risk:
  reversibility_loss

operator family:
  return_path_support

operator:
  reversibility_support

intensity:
  fixed_medium

wait window:
  wait 0-2

status:
  provisional adoption policy対象
```

参考値:

```text
mean EV:
  0.271696

large loss rate:
  0.001481
```

設計上の意味:

reversibility_loss は、戻り道が細くなり、不可逆化が進む状態を対象とする。ここでは戻り道を補助し、rollback余地を保つことを狙う。

採用理由:

- Task24b4で strong adoption candidate。
- Task24b5で fixed_medium が高いEVを持つ。
- large loss tail が非常に低い。
- ただし stress concentration は副次監査として継続する。

---

## 4. 仮採用から外す対象

### 4.1 boundary_fragile

```text
risk:
  boundary_fragile

status:
  guarded review

interim action:
  fixed_medium または fixed_weak を review only で保持

next validation:
  boundary_fragile baseline separation and guard condition audit
```

採用しない理由:

- large loss tail は低い。
- しかし randomized baseline との分離が弱い。
- つまり、「この演算子である必然性」がまだ十分に強くない。

現時点の扱い:

```text
採用:
  しない

review:
  継続

NO_OP:
  defaultとして保持
```

---

### 4.2 resource_pressure

```text
risk:
  resource_pressure

status:
  operator redesign required

interim action:
  fixed_weak monitor only または NO_OP default

next validation:
  resource_pressure operator redesign with alternative targets and tail risk audit
```

採用しない理由:

- fixed_medium では large loss tail が高い。
- fixed_strong はさらに悪化する。
- gradual schedule でも十分に救えない。
- fixed_weak は安全寄りだが利得が弱く、採用には足りない。

現時点の扱い:

```text
採用:
  禁止

再設計:
  必須

NO_OP:
  default
```

---

## 5. 作用モジュールの入力境界

作用モジュールが見てよい情報は、すでに作用モジュール向けに準備された情報だけである。

### 5.1 許可される入力

```text
risk_name
selected_operator_name
operator_family
wait_step
prepared_action_material
runtime margin proxy
rollback proxy
boundary proxy
作用モジュールに渡された観測地形由来の要約情報
```

### 5.2 禁止される入力

```text
v2 future
NO_OP future
observed outcome
action outcome
negative control outcome
validation score
hidden truth
DEPT/H-DEPT内部状態への直接アクセス
```

重要なのは、v2側の情報は採点専用であり、runtime側の判断に使わないことである。

```text
runtime policy view:
  作用モジュールが使ってよい情報

validation scoring view:
  v2 / NO_OP / negative control による後評価
```

この2つは必ず分離する。

---

## 6. Admission gate

仮固定設計では、以下の順番でgateを通す。

```text
1. scope gate
   risk_name が relation_lock / oscillation / reversibility_loss のいずれかか

2. exclusion gate
   boundary_fragile / resource_pressure なら採用せず、review/redesignへ送る

3. timing gate
   wait_step が 0-2 か

4. late wait gate
   wait_step >= 3 なら NO_OP または review

5. intensity gate
   fixed_medium か

6. runtime information gate
   v2 future / validation score がruntime側に入っていないか

7. margin gate
   rollback proxy / boundary proxy が不足していないか

8. fallback gate
   必要情報が欠ける場合は NO_OP
```

このgateは、まだ本番閾値ではない。あくまで仮固定設計上の構造である。

---

## 7. NO_OP fallback設計

NO_OP fallback は以下の条件で発動する。

```text
prepared_action_material が不足
runtime proxy が不足
wait 0-2外
boundary_fragile / resource_pressure が入力された
risk_name が未検証
rollback proxy が不足
boundary proxy が不足
v2 future / validation score の混入疑い
```

NO_OPは「何もしない」ではなく、作用モジュールの正式な安全側出力である。

---

## 8. 現時点で固定するもの

```text
採用対象:
  relation_lock
  oscillation
  reversibility_loss

operator:
  soft_resistance
  damping
  reversibility_support

強度:
  fixed_medium

作用窓:
  wait 0-2

fallback:
  NO_OP

除外:
  boundary_fragile
  resource_pressure
```

---

## 9. 現時点で固定しないもの

```text
本番閾値:
  未凍結

release / rollback / audit の最終条件:
  未固定

実ActionModule呼び出し:
  未実行

axis実行:
  未実行

canonical parameter write:
  未実行

現実系への適用:
  未実行

長期運用での累積利得:
  未検証
```

---

## 10. 主要な未検証課題

### 10.1 長期ストレス分散

現時点では、短期・中期の局所検証が中心である。

今後必要なもの:

```text
stress concentration persistence
stress peak half-life
delayed side-effect tail
long-run NO_OP gap
local failure tail
```

### 10.2 boundary_fragileの追加検証

boundary_fragile は、低リスクではあるが、randomized baseline との差が弱い。

今後必要なもの:

```text
operator-specific baseline separation
boundary guard condition audit
false-positive action audit
```

### 10.3 resource_pressureの再設計

resource_pressure は、強度調整では救えなかった。

今後必要なもの:

```text
alternative target design
tail risk audit
weak monitor-only route
pressure_diffusion redesign
```

### 10.4 release / rollback / audit 条件

今回の設計は作用方針の仮固定であり、release / rollback / audit の正式条件はまだない。

次に必要なもの:

```text
release condition draft
rollback trigger draft
audit ledger condition draft
NO_OP escalation condition
```

---

## 11. 引き継ぎ時の注意

次のチャットまたは次の実装者は、以下を守ること。

```text
1. Task24c設計は本番固定ではない。
2. 採用対象は3riskだけ。
3. boundary_fragileを勝手に採用対象へ戻さない。
4. resource_pressureを現行pressure_diffusionのまま採用しない。
5. v2 future / NO_OP future / validation score をruntime側へ入れない。
6. NO_OPを正式fallbackとして残す。
7. fixed_medium / wait 0-2 を基本設計として扱う。
8. release / rollback / audit は次段階で別途設計する。
```

---

## 12. 次に進むべき作業

推奨される次作業は以下である。

```text
Task24c-policy:
  作用モジュール仮固定policy skeleton

目的:
  本書で固定した設計を、実装可能なpolicy skeletonへ落とす。

ただし:
  まだ実ActionModule呼び出しはしない。
  まだcanonical writeはしない。
  まだdeployment-readyとは言わない。
```

その次に、以下を分岐で進める。

```text
Task24d:
  release / rollback / audit 条件草稿

Task24e:
  boundary_fragile baseline separation追加検証

Task24f:
  resource_pressure operator redesign
```

---

## 13. 最終要約

```text
作用モジュール仮固定設計 RC1:

採用:
  relation_lock -> soft_resistance -> fixed_medium -> wait 0-2
  oscillation -> damping -> fixed_medium -> wait 0-2
  reversibility_loss -> reversibility_support -> fixed_medium -> wait 0-2

除外:
  boundary_fragile -> guarded review
  resource_pressure -> operator redesign

fallback:
  NO_OP正式保持

禁止:
  v2 future runtime入力
  validation score runtime入力
  real ActionModule call
  axis execution
  canonical write
  deployment-ready claim

次:
  policy skeleton化
```
