# Task 3.2-2 範囲
## 小規模連続軌道データ生成

## 1. タスク種別

- 新規タスク: Task 3.2-2
- 親フェーズ: Task 3.2 マクロ力学探索
- 依存: Task 3.2-1
- 性質: 小規模連続軌道の生成・保存・検証

## 2. 目的

PseudoReality v3.3から、Task 3以降がそのまま使用できる連続軌道を生成する。

中心出力は次である。

```text
X_t
+
時点tまでの履歴ログL_t
+
実際のX_{t+1}
+
実測軌道から作る暫定的な高リスク結果
```

Task 3.2-2では予測器やマクロ力学抽出器を作らない。

## 3. 実装方針

- 既存の`DistributionTerrainV322World`を変更しない。
- 外側の軌道生成器から各時点の全状態をコピーする。
- Task 3.2-1で定めた23状態配列を必須保存する。
- 取得可能な遷移記憶配列・スカラーも保存する。
- 外部入力予定表全体をmodel inputへ渡さない。
- シナリオ名を結果ラベルとして使用しない。
- 暫定結果は実測軌道のリスク、集中、移動量、剛性等から計算する。
- 未評価の不可逆性や作用強度は推測で埋めない。

## 4. シナリオ

初回は次の6種類を使用する。

1. 通常・安定継続
2. 外乱後に自然回復する候補
3. 遅延して回復する候補
4. 一方向に悪化する候補
5. 固定化・関係ロック候補
6. 崩壊・不可逆境界候補

これらは入力条件の名称であり、正解ラベルではない。

## 5. プロファイル

### smoke

- 6シナリオ
- 2 seed
- 32遷移
- 合計12軌道、384遷移
- splitは`exploratory`

### exploratory

- 6シナリオ
- 5 seed
- 64遷移
- 合計30軌道、1,920遷移
- seed単位でfit / validation / holdoutを分離

数値は探索実行用の設定であり、研究上の普遍的な固定値ではない。

## 6. 保存形式

各軌道は次を持つ。

```text
trajectory_<ID>/
├── metadata.json
├── steps.jsonl
├── truth.jsonl
├── metrics.jsonl
├── states/
│   └── step_XXXXXX.npz
├── summary.json
├── trajectory.svg
└── validation.json
```

コーパス全体は次を持つ。

- `corpus_summary.json`
- `scenario_comparison.csv`
- `trajectory_overview.svg`
- `validation.json`
- `manifest.json`

## 7. 暫定結果

結果分類は次を使用する。

- `stable`
- `natural_recovery`
- `delayed_recovery`
- `persistent_deterioration`
- `fixation_candidate`
- `collapse_or_divergence_candidate`

この分類はTask 2の整理用であり、正式なゲーム構造名ではない。

リスク点数と分類規則は、データ生成結果を確認するための暫定診断である。後続の予測モデルへそのまま正解として固定することを意味しない。

## 8. 検証

- Task 3.2-1契約検証
- 23状態配列の存在
- 5×5×5×5×5形状
- 有限値
- 分布非負性・質量合計
- 時刻連続性
- 未来情報漏洩防止
- 軌道単位split
- 同条件再実行の一致
- 異seedの軌道差
- 異シナリオの軌道差
- manifestハッシュ

## 9. 範囲外

- 予測モデル
- DMD / Koopman / HAVOK / VAMP
- マクロ力学要素の固定
- 高リスク閾値の正式固定
- 不可逆性の正式数式
- 正式G_t・K_t
- ゲーム構造
- 作用モジュール接続
- 研究線の有望性判定
