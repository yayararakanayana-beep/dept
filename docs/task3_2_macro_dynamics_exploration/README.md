# Task 3.2 マクロ力学探索フェーズ

## 目的

生のPseudoReality v3.3状態と履歴ログから、高リスク構造への移行を早期に検出し、不可逆性、リスクの深さ、作用可能な時間幅の判断に使えるマクロ力学表現が存在するかを探索する。

このフェーズは正式な動的関係場を完成させる段階ではない。粗い試作とフィードバック修正によって、研究線そのものの有望性を確認する。

## 固定した6タスク

1. 生状態・履歴ログ・高リスク評価基盤の定義
2. 連続軌道データの生成
3. 単純予測・早期警戒基準の構築
4. マクロ力学抽出の最小試作
5. 高リスク判断への接続
6. 反復修正と研究線の有望性判定

タスク数と順序は固定する。ただし、各タスク内部の手法、履歴幅、抽出法、リスク閾値、力学要素は検証結果に応じて修正できる。

## Task 3.2-1の完了状態

Task 3.2-1では次を実装した。

- `X_t + L_t`を正式な予測入力境界として固定
- 生ログを正本とし、派生特徴を再計算可能にする規則
- モデル入力、採点用正解、再現用情報の分離
- 未来情報の入力混入を拒否する検証器
- PseudoReality v3.3の全状態配列を保存する最小契約
- 高リスク、回復、不可逆性、リスク深度の暫定採点欄
- 軌道単位のデータ分割規則
- Task 2が使用する実行可能な契約検証コードとテスト

## Task 3.2-2の完了状態

Task 3.2-2では次を実装した。

- 6種類の連続軌道シナリオ
- smoke / exploratoryプロファイル
- 各時点の23必須状態配列保存
- 遷移記憶・外部入力・イベント・応答ログ
- 次状態正解
- 軌道単位split
- 同一条件再現性
- 異seed・異シナリオ差
- 状態bundle検証
- SVG可視化とmanifest
- 同一seed通常軌道による暫定結果補正

正式スモークでは、12軌道・384遷移・396状態を生成し、19テストと全データ検証を通過した。

補正後の暫定結果:

```text
stable: 2
persistent_deterioration: 6
fixation_candidate: 2
collapse_or_divergence_candidate: 2
```

## 非固定事項

次はまだ固定していない。

- 地形、流れ、循環、粘性、拡散、外力等の最終分解
- 履歴幅
- 高リスクの正式な数値閾値
- 不可逆性の最終数式
- リスク深度の最終数式
- 使用するDMD、Koopman、HAVOK等の手法
- 固定5軸上の正式なG_t・K_t
- ゲーム構造

## 正本ファイル

### Task 3.2-1

- `TASK3_2_1_SCOPE_FREEZE.md`
- `task3_2_1_state_log_inventory.md`
- `../../configs/task3_2_1_macro_dynamics_contract.json`
- `../../scripts/task3_2_1_macro_dynamics_contract.py`

### Task 3.2-2

- `TASK3_2_2_SCOPE.md`
- `task3_2_2_results.md`
- `task3_2_2_completion.md`
- `../../configs/task3_2_2_continuous_trajectory.json`
- `../../configs/task3_2_2_reference_calibration.json`
- `../../scripts/task3_2_2_continuous_trajectory.py`
- `../../scripts/task3_2_2_reference_calibration.py`
