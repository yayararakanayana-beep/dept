# Task 3.2-2 スモーク軌道生成結果

## 1. 実行情報

- GitHub Actions run: `29168450056`
- head commit: `ff5165bafd89f7397e739ff58141277eb237d13d`
- workflow: `Task 3.2-2 Continuous Trajectories`
- 結果: `success`

## 2. テスト

対象テストは合計19件で、すべて通過した。

```text
19 passed in 26.99s
```

主な検査:

- Task 3.2-1データ契約
- 未来情報漏洩拒否
- 履歴時刻整合
- 23状態配列の保存
- 外部入力範囲
- 軌道単位split
- 同一seed・同一条件の再現性
- 異seedの軌道差
- 異シナリオの軌道差
- 分布改ざん拒否
- 同一seed通常軌道による基準補正

## 3. 正式スモークArtifact

- Artifact ID: `8252843059`
- 名前: `task3-2-2-continuous-trajectories-smoke`
- ZIPサイズ: `98,506,079` bytes
- GitHub digest: `sha256:92e6a0468b376b592590af1ec1c19285fa8d252d81c0cbed44391bdd54c66c89`
- 有効期限: 2026-08-10

Artifact内部:

- ファイル数: 484
- 非圧縮合計: `100,898,089` bytes
- 軌道数: 12
- シナリオ数: 6
- seed数: 2
- 1軌道あたり: 32遷移、33状態
- 全遷移数: 384
- 全状態数: 396

## 4. 検証結果

コーパス検証はすべて通過した。

```json
{
  "trajectory_count": 12,
  "scenario_count": 6,
  "seed_count": 2,
  "trajectory_split_check": "passed",
  "seed_difference_check": "passed",
  "scenario_difference_check": "passed",
  "stable_reference_calibration": "passed",
  "stable_reference_seed_count": 2,
  "status": "valid"
}
```

各軌道についても次を通過した。

- 33状態ファイル
- 32遷移正解
- 未来情報漏洩なし
- 23必須状態配列
- 5×5×5×5×5形状
- 有限値
- 分布非負
- 分布質量合計1

## 5. 通常軌道による基準補正

初回実行では、外部入力ゼロの通常軌道にも自然なリスク点数の上昇があり、全軌道が「持続悪化」と判定された。

これは軌道生成の失敗ではなく、初期状態だけを安全基準にした暫定採点の問題だった。

修正後は、各軌道を同じseedの`stable_continuation`軌道と比較する。

```text
対象軌道
−
同一seedの通常軌道
=
外部条件に由来する相対変化
```

シナリオ名は正解として使用していない。

## 6. 補正後の暫定結果

| 入力シナリオ | seed数 | 実測結果 |
|---|---:|---|
| stable_continuation | 2 | stable |
| natural_recovery | 2 | persistent_deterioration |
| delayed_recovery | 2 | persistent_deterioration |
| persistent_deterioration | 2 | persistent_deterioration |
| fixation_candidate | 2 | fixation_candidate |
| collapse_candidate | 2 | collapse_or_divergence_candidate |

結果数:

```text
stable: 2
persistent_deterioration: 6
fixation_candidate: 2
collapse_or_divergence_candidate: 2
```

## 7. 重要な観測

### 通常軌道

同一seedの通常軌道との差は0として正しく整理された。

### 自然回復候補

32遷移の範囲では、外乱解除後も通常軌道へ戻らなかった。

相対末尾リスク差は約`0.0621`だった。

したがって、シナリオ名に反して実測結果は「持続悪化」となった。これはシナリオ名を正解へコピーしていないことの確認でもある。

### 遅延回復候補

32遷移の範囲では回復せず、相対末尾リスク差は約`0.1775`だった。

現行v3.3では、設定した外乱が想定より長く状態へ残る可能性がある。

### 持続悪化候補

相対末尾リスク差は約`0.0764`だった。

### 固定化候補

- 相対末尾リスク差: 約`0.1384`
- 通常軌道に対する末尾集中度比: 約`1.119`
- 通常軌道に対する末尾移動量比: 約`0.609`
- 通常軌道に対する剛性差: 約`0.324`

集中増加、移動量低下、剛性上昇が同時に確認された。

### 崩壊候補

- 相対末尾リスク差: 約`0.2669`
- 通常軌道に対する末尾集中度比: 約`1.320`
- 通常軌道に対する末尾移動量比: 約`0.378`
- 通常軌道に対する剛性差: 約`0.379`

今回の6条件の中で最も深い高リスク軌道になった。

## 8. 結果の境界

この結果は次を意味しない。

- 正式な高リスク閾値が確定した
- 不可逆性が証明された
- ゲーム構造が分類された
- 固定化や崩壊の正式定義が完成した
- 作用判断が可能になった

現在のラベルは、Task 3で基準予測を試すための暫定的な軌道整理である。

## 9. Task 3への引き渡し

Task 3では、このコーパスを用いて次を比較する。

1. 現在状態維持
2. 直近変化の延長
3. 単純な履歴特徴による高リスク早期警戒

Task 3の中心評価は、全状態の完全予測ではなく次とする。

- 高リスクを何ステップ前に検出できるか
- 通常軌道と高リスク軌道を区別できるか
- リスク深度の順位を再現できるか
- 見逃しと誤警報
