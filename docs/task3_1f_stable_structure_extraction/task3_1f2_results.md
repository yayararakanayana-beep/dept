# Task 3.1f-2 検証結果

## ローカル検証

- 正常系・数理部品テスト：8件
- 破壊系テスト：8件
- 合計：16件合格

確認済み項目：

- 入力bundle分離
- 固定seedのKL-NMF経路
- 基底総和1
- 非負活性度
- 固定基底transform
- 構造順序に依存しない対応付け
- holdout未使用
- 指標の独立再計算
- 負基底、NaN活性度、固定0指標、偽造対応表、holdout使用フラグ、run欠落、NaN入力、split漏洩の検出

## 正式性の境界

本結果はTask 3.1f-2の実装smokeであり、正式な構造数選択結果ではない。

- 正式rank grid：未実行
- 正式2,000反復：未実行
- selection lock：未作成
- holdout：未使用
- Task 3.1gへ渡す構造：未選択

GitHub Actions上のTask 3.1e実データsmoke結果はPR検証時に追記する。
