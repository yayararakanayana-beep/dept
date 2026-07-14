# 固定5軸上位観測翻訳層 RC1 — 接続タスク4 単体科学検証と校正固定

## 1. 目的

Task 4では、Task 1で固定した契約、Task 2のbuilder、Task 3の独立validatorを変更せず、次を行う。

1. 校正用・検証用・最終確認用データの完全分離
2. 校正用データだけを使った凍結校正成果物の生成
3. 固定5軸の単体合成シナリオによる科学仮説検証
4. 検証用データと最終確認用データへの同一基準の適用
5. 校正成果物・検証結果・最終判定の再現可能な凍結

## 2. 事前登録

実行前に次を `configs/fixed5axis_hdept_task4_scientific_validation_rc1.json` へ固定した。

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

| 分割 | seed | 軌道数 | 用途 |
|---|---:|---:|---|
| 校正 | 1100–1103 | 44 | 特徴ごとの中央値・尺度だけをfit |
| 検証 | 2200–2202 | 33 | 事前登録仮説の第一検証 |
| 最終確認 | 3300–3302 | 33 | 未使用seedによる再確認 |

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

予約特徴・非採点特徴には校正値を与えない。検証・最終確認・未来接尾部をfitへ使わず、実行中の再fitも禁止する。

## 6. 事前登録仮説

1. 固定化を安全な安定と誤認しない
2. 構造化探索を固定化から分離する
3. 構造化探索をノイズ拡張から分離する
4. 振動を滑らかな移動から分離する
5. 境界発散を広い安定分布から分離する
6. 緩慢な固定化を検出する
7. 生の戻り距離を順序づけつつ、正式なRecoverabilityは利用不能のまま保つ
8. 利用可能H11軸が一律0.5へ崩壊しない

## 7. 実行結果

Task 2 builderとTask 3独立validatorは、検証33軌道・最終確認33軌道の全66軌道で通過した。校正の再現性、分割非重複、校正用データ限定、予約軸の利用不能も通過した。

一方、科学仮説は検証・最終確認とも **8件中6件通過** であり、次の2件が同じ方向で再現して失敗した。

### H2 構造化探索の分離失敗

構造化探索は狭い固定化より、生のentropy、effective_rank、participation_ratioでは高かった。しかし、最終H11では次となった。

```text
Exploration(structured) - Exploration(locked) ≈ -0.006
StructuralDiversity(structured) - StructuralDiversity(locked) ≈ +0.033
```

事前登録基準の+0.08を満たさない。特にmode_countとcluster_balanceが全検証ケースで定数となり、構造化された複数分布を識別できていない。

### H5 境界発散のCoherence誤読

境界発散はtail_massが大きく、Stabilityも広い安定分布より低くなったため、発散運動自体は検出した。しかしCoherenceは逆方向となった。

```text
Coherence(stable broad) - Coherence(boundary divergence) ≈ -0.44
```

境界へ集中した分布のcompactness等が、境界質量と不安定性の証拠を上回り、境界発散を高Coherenceとして読んでいる。

## 8. 校正の判定

校正成果物は機械的には再現可能で、Task 2・Task 3契約から読み込める。しかし科学的な本番校正としては固定しない。

理由は次のとおり。

- active_axis_count、mode_count、cluster_balance等が校正・検証で退化
- 複数特徴が校正後の±4へ高頻度で飽和
- H2とH5の失敗が最終確認でも再現

したがって最終判定は次とする。

```text
freeze_reproducibility_only_not_scientifically_approved
```

## 9. 凍結成果物

全ケースを含む完全な検証bundleはGitHub Actionsで毎回再生成し、Actions artifactとして保持する。

Git管理上は、次の小型凍結成果物を `artifacts/fixed5axis_hdept_task4_compact_freeze_rc1/` に保存する。

```text
fixed5axis_hdept_task4_calibration_rc1.json
task4_diagnostic_findings.json
task4_freeze_decision.json
task4_freeze_manifest.json
```

小型凍結成果物は、完全bundleから決定論的に再生成し、checked-inファイルとバイト単位で照合する。

## 10. 主張限界と次工程

Task 4の工学的検証器は成立したが、科学ゲートは不合格である。次は未検証または未承認である。

- 実データ妥当性
- 本番校正
- Predictability下位契約
- Recoverability下位契約
- 上位圧の安全性
- Parameter Boxとの接続
- 作用実行
- 閉ループ効果

Task 5への診断接続は進めない。先に別の修理タスクとして、固定グリッドのモード識別、Explorationの構成と校正飽和、Coherenceの境界集中誤読を改修し、新しい事前登録検証を行う必要がある。
