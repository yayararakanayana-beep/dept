# Task 3.1f-2 検証結果

## ローカル検証

- 正常系・数理部品・数値境界テスト：9件
- 破壊系テスト：8件
- 合計：17件合格

確認済み項目：

- 入力bundle分離
- 固定seedのKL-NMF経路
- 基底総和1
- 非負活性度
- 固定基底transform
- 構造順序に依存しない対応付け
- holdout未使用
- 指標の独立再計算
- 重み付き中央値の浮動小数点境界
- 負基底、NaN活性度、固定0指標、偽造対応表、holdout使用フラグ、run欠落、NaN入力、split漏洩の検出

## GitHub Actions実データsmoke

- Workflow run ID：`29132331139`
- 検証head：`38dc4e1d7c813bb954eb32094c41fa54b23154c7`
- Task 3.1e実データsmoke生成：成功
- Task 3.1e独立厳格検証：成功
- Task 3.1f入力固定：成功
- 重み付きKL-NMF：7 run実行
- 重み付き主成分分析参照：成功
- 重み付き平均分布基準：成功
- 独立検証：8 / 8合格
- 再計算した指標：8,712件
- 再計算した構造対応：105件
- 指標最大再計算誤差：`9.882502802205373e-17`
- 構造対応最大再計算誤差：`3.3306690738754696e-16`
- holdout使用：なし

### GitHub Actions成果物

- Artifact ID：`8242425517`
- Artifact名：`task3-1f2-minimal-extraction-smoke`
- Archive digest：`sha256:a7c2020230a27dd355e740897a1d990bbae9545e80b4d5b0b0ec526bfce0234e`
- 保存期限：2026-07-25

## smokeの収束状態

7本のKL-NMF runは、smoke専用の反復上限50へ到達しており、正式な意味での収束判定には使用しない。

これは想定された実装確認境界であり、各runの`converged=false`を実測証拠として保存している。正式判定では固定契約どおり最大2,000反復を使用する。

## 正式性の境界

本結果はTask 3.1f-2の実装smokeであり、正式な構造数選択結果ではない。

- 正式rank grid：未実行
- 正式2,000反復：未実行
- selection lock：未作成
- holdout：未使用
- Task 3.1gへ渡す構造：未選択
