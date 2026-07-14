# 固定5軸上位観測翻訳層 RC1 — 接続タスク4 単体科学検証と校正固定

## 1. 目的

Task 4では、Task 1で固定した契約、Task 2のbuilder、Task 3の独立validatorを変更せず、次を行う。

1. 校正用・検証用・最終確認用データの完全分離
2. 校正用データだけを使った凍結校正成果物の生成
3. 固定5軸の単体合成シナリオによる科学仮説検証
4. 検証用データと最終確認用データへの同一基準の適用
5. 校正成果物・検証結果・最終判定の再現可能な凍結

## 2. 事前登録

実行前に次を
`configs/fixed5axis_hdept_task4_scientific_validation_rc1.json`
へ固定する。

- シナリオ群
- seed範囲
- 校正・検証・最終確認の分割
- 校正方法
- 8つの検証仮説
- 各仮説の数値閾値
- 凍結判定条件
- 主張限界

結果を見てから閾値や分割を変更しない。

## 3. データ分割

| 分割 | seed | 用途 |
|---|---:|---|
| 校正 | 1100–1103 | 特徴ごとの中央値・尺度だけをfit |
| 検証 | 2200–2202 | 事前登録仮説の第一検証 |
| 最終確認 | 3300–3302 | 同じ閾値による未使用seed確認 |

軌道識別子は分割間で重複しない。

## 4. シナリオ

- 広い安定分布
- 狭い固定化
- 滑らかな適応移動
- 構造化探索
- ノイズ的拡張
- 振動
- 境界への発散
- 緩慢な固定化
- 衝撃後の完全回復
- 衝撃後の部分回復
- 衝撃後の非回復

すべて固定5軸の3,125セル完全分布として生成し、正本G/K形式へ書き出す。

## 5. 校正

特徴ごとの校正は、校正分割の最終時点だけから作る。

```text
center = median
primary scale = 1.4826 × MAD
fallback = sample standard deviation
minimum scale = 1e-9
clip = [-4, 4]
```

予約特徴・非採点特徴には校正値を与えない。

validation・final confirmation・未来接尾部をfitへ使わない。実行中の再fitも禁止する。

## 6. 科学仮説

### H1 偽安定の分離

狭い固定化は低運動のためStabilityが高くなり得る。しかし、広い安定分布よりExplorationとStructuralDiversityが低くなければならない。

Stability単独を安全性へ読み替えない。

### H2 構造化探索

構造化探索は固定化よりExplorationとStructuralDiversityが高いこと。

### H3 ノイズ拡張の抑制

構造化探索はノイズ的拡張よりCoherenceが高く、ノイズ側は境界質量が大きいこと。

### H4 振動検出

振動シナリオは滑らかな適応移動より、oscillation_indexとmotion_angleが高く、TrajectoryDynamicsも識別可能な差を持つこと。

### H5 境界発散

境界発散は広い安定分布よりtail_massが高く、CoherenceとStabilityが低いこと。

### H6 緩慢な固定化

緩慢な固定化は広い安定分布よりExplorationとStructuralDiversityが低いこと。

### H7 回復契約の限界

完全・部分・非回復の生の戻り距離は順序づけられるが、正式なRecoverability軸は下位契約未固定のため利用不能のままであること。

### H8 単一batch 0.5崩壊の防止

各ケースで十分なH11軸が利用可能であり、利用可能軸が一律0.5へ潰れず、シナリオ間分散を持つこと。

## 7. 独立検証

検証・最終確認の全ケースで、Task 2 builderの成果物をTask 3 validatorへ通す。

科学仮説の評価以前に、次が全件通過していなければTask 4は不合格とする。

- G_t/K_t同一性
- 47特徴の独立再計算
- H11全11軸の独立再計算
- 未来漏洩禁止
- 欠測・信頼度契約
- 正本非変更

## 8. 凍結成果物

最終的に次を
`artifacts/fixed5axis_hdept_task4_rc1/`
へ固定する。

```text
fixed5axis_hdept_task4_calibration_rc1.json
task4_calibration_audit.json
task4_validation_report.json
task4_final_confirmation_report.json
task4_freeze_decision.json
task4_manifest.json
```

GitHub Actionsで同じ成果物を再生成し、checked-in成果物とバイト単位で一致させる。

## 9. 主張限界

Task 4が通過しても、主張は次に限定する。

```text
B_limited_synthetic_fixed5_only
```

確認対象は固定5軸上の合成シナリオだけである。

次は未検証である。

- 実データでの妥当性
- 外部結果を含む適応成功
- Predictability下位契約
- Recoverability下位契約
- 上位圧の安全性
- Parameter Boxとの接続
- 作用実行
- 閉ループ効果

Task 4の合格は、Task 5の診断接続へ進める条件であり、実運用可能性の証明ではない。
