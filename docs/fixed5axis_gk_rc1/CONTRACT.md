# 固定5軸 G_t・K_t 基盤契約 RC1

## 1. 目的

固定5軸空間上の完全分布を現在状態 `G_t` として保存し、`G_0` から `G_t` までの完全な順序付き履歴を `K_t` として保持する。

この基盤は、後続のマクロ力学抽出、関係場、ゲーム構造、リスク構造予測に使用する。ただし本タスクでは、関係場の推定、ゲーム構造の分類、リスク予測、作用接続は行わない。

## 2. 固定5軸

軸順は変更しない。

1. 資源余裕 `resource_slack`
2. 情報品質 `information_quality`
3. 圧力 `pressure`
4. 探索余地 `exploration_room`
5. 可逆性 `reversibility`

各軸は `[0.00, 0.25, 0.50, 0.75, 1.00]` の5区分とする。

```text
5 × 5 × 5 × 5 × 5 = 3,125セル
```

固定5軸は基準座標であり、PCA軸、NMF構造、意味軸候補、関係場の方向、探索軸で置き換えない。

## 3. G_t契約

`G_t` は時点 `t` の遷移前における固定5軸上の確率質量分布である。

- 正本形状: `(5, 5, 5, 5, 5)`
- 正本型: `float64`
- 全値有限
- 負の質量なし
- 総質量 `1.0 ± 1e-10`
- 不正値の自動切捨て禁止
- 不正値の自動再正規化禁止

RC1の数値入力は、PseudoReality v3.3の状態ファイル内の `distribution` 配列だけである。

地形、流れ、外部入力、seed、シナリオ名、データ分割、将来正解を、G_tの数値構成に使用してはならない。

## 4. K_t契約

`K_t` は次の完全履歴である。

```text
K_t = {G_0, G_1, ..., G_t}
```

K_tを傾き、平均、速度、変化量だけへ置き換えてはならない。正本は、保存された全G_tへの順序付き参照台帳である。

履歴台帳は以下を保持する。

- `trajectory_id`
- `source_trajectory_id`
- `t`
- `phase`
- `gt_row_index`
- `gt_hash`
- `previous_gt_hash`
- `history_chain_hash`
- `delta_t`
- `continuity_status`
- `admissible_for_research`
- `source_state_ref`
- `source_state_hash`

正本履歴は追記専用とし、過去の上書き、削除、時点の再割当てを禁止する。

## 5. 履歴異常の扱い

履歴異常を黙って削除したり、正常な履歴へ見せかけたりしてはならない。

`continuity_status`は以下を使用する。

- `initial`
- `continuous`
- `gap`
- `duplicate`
- `out_of_order`
- `source_mismatch`

異常なG_tも正本配列と台帳へ残す。ただし、`initial`と`continuous`以外は`admissible_for_research = false`とし、正式な関係場・予測検証には使用しない。

これにより、観測欠落や時点異常そのものを失わず、正常履歴と混同もしない。

## 6. 三層構造

### 第1層: 正本

全G_tとK_t履歴台帳。変更不可。

### 第2層: 変化情報

G_t間の距離、重心変化、広がり変化など。削除・再計算可能であり、正本ではない。

初期窓口として以下を実装する。

- Jensen–Shannon距離
- Hellinger距離
- エントロピー変化
- 集中度変化
- 各固定軸の重心変化
- 各固定軸の広がり変化

異常履歴からは第2層を生成しない。

### 第3層: 履歴窓

- 全履歴
- 直近N時点
- 開始時点から終了時点

を読み出せる。

短期・中期・長期の具体的な窓長は、予測フェーズの結果を待って決める。

## 7. 入力境界

読み取る正本入力:

- `metadata.json`
- `steps.jsonl`
- 各`state_ref`の`distribution`

数値入力として使用禁止:

- `truth.jsonl`
- `summary.json`
- `metrics.jsonl`
- 将来状態
- 将来外部入力
- 将来イベント
- 将来作用
- リスク正解
- 回復正解
- 地形正解
- 流れ正解

seed、シナリオ名、データ分割、世界版は出典情報としてのみ保存する。

## 8. 別ログ

G_t・K_tとは分離して以下を保存する。

- 観測済み外部入力
- 観測済み作用
- 観測済みイベント

正解地形、正解流れ、将来リスクなどの検証専用情報は、正本出力へコピーしない。

## 9. 保存形式

```text
<output>/
  contract.json
  dataset_manifest.json
  validation.json
  manifest.json
  trajectories/
    <trajectory_id>/
      gt_mass.npy
      history_ledger.csv
      provenance.json
      observed_external_input.jsonl
      observed_action.jsonl
      observed_event.jsonl
      validation.json
      manifest.json
      derived/
        derivation_registry.json
```

`gt_mass.npy`の形状は次とする。

```text
(T, 5, 5, 5, 5, 5)
```

`derived/`以下は正本マニフェストから除外し、いつでも削除・再生成できる。

## 10. ハッシュ

各G_tは、契約版、軌道ID、時点、固定軸定義、固定区分、G_tバイト列、出典状態ハッシュからSHA-256を生成する。

履歴連鎖ハッシュは、前回の連鎖ハッシュ、現在G_tハッシュ、時点から生成し、過去履歴の差替えを検出する。

## 11. 採用判定

### 11.1 成果物整合判定

単一成果物検証で確認する。

- 軸順、区分、形状、型
- 有限、非負、総質量1
- G_tハッシュ
- 履歴連鎖ハッシュ
- 履歴異常の正確な記録
- 将来正解の隔離
- 観測ログの行数整合
- 世界状態への書戻しなし

これを`artifact_integrity_gate`とする。

### 11.2 表現基盤の硬い判定

以下は単一成果物検証だけでは完了しない。

- 決定論的再構築
- 軌道群単位のデータ分割整合
- 全正式軌道の履歴連続性

したがって、実装直後は成果物整合が通過しても、`representation_hard_gate = partial`とする。

### 11.3 後続研究判定

- 外部要因応答が通常揺らぎから分離できるか
- K_tが現在G_t単独より動力学情報を追加するか
- validation・holdoutで安定するか

### 11.4 判定区分

- A: 表現基盤と全研究判定を通過
- B: 成果物基盤は成立しているが、表現判定または研究判定が未完・限定的
- C: 成果物整合失敗、正式履歴異常、または外部応答と履歴価値の双方が失敗

未実施の検証を通過扱いにしてはならない。本実装直後の判定はBであり、A採用は主張しない。

## 12. 実行例

単一軌道:

```bash
python scripts/fixed5axis_gk_rc1.py build-trajectory \
  --source artifacts/task3_2_2/trajectories/<trajectory_id> \
  --output-root artifacts/fixed5axis_gk_rc1
```

軌道群:

```bash
python scripts/fixed5axis_gk_rc1.py build-corpus \
  --source-corpus artifacts/task3_2_2 \
  --output artifacts/fixed5axis_gk_rc1
```

検証:

```bash
python scripts/fixed5axis_gk_rc1.py validate-trajectory \
  --trajectory artifacts/fixed5axis_gk_rc1/trajectories/<trajectory_id>
```

派生変化情報:

```bash
python scripts/fixed5axis_gk_rc1.py derive-transition-metrics \
  --trajectory artifacts/fixed5axis_gk_rc1/trajectories/<trajectory_id> \
  --write
```
