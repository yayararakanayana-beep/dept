# 固定5軸 G_t・K_t 基盤契約 RC1

## 目的

固定5軸空間上の完全分布を現在状態 `G_t` として保存し、`G_0` から `G_t` までの完全な順序付き履歴を `K_t` として保持する。

この基盤は、後続のマクロ力学抽出、関係場、ゲーム構造、リスク構造予測に使用する。ただし本タスクでは、それらの推定・分類・予測・作用接続は行わない。

## 固定5軸

軸順は変更しない。

1. 資源余裕 `resource_slack`
2. 情報品質 `information_quality`
3. 圧力 `pressure`
4. 探索余地 `exploration_room`
5. 可逆性 `reversibility`

各軸は `[0.00, 0.25, 0.50, 0.75, 1.00]` の5区分とし、分布は `5 × 5 × 5 × 5 × 5 = 3,125` セルで構成する。

## G_t

`G_t` は時点 `t` の遷移前における固定5軸上の確率質量分布である。

- 正本形状: `(5, 5, 5, 5, 5)`
- 正本型: `float64`
- 全値有限
- 負の質量なし
- 総質量 `1.0 ± 1e-10`
- 不正値の自動切捨て・自動再正規化は禁止

RC1の数値入力は、PseudoReality v3.3状態ファイル内の `distribution` 配列だけである。地形、流れ、外部入力、seed、シナリオ名、将来正解はG_tの数値構成に使用しない。

## K_t

`K_t` は次の完全履歴である。

```text
K_t = {G_0, G_1, ..., G_t}
```

K_tを傾き、速度、平均、変化量だけへ置換してはならない。正本は全G_tへの順序付き参照台帳である。

各履歴行は以下を含む。

- `trajectory_id`
- `t`
- `phase`
- `gt_row_index`
- `gt_hash`
- `previous_gt_hash`
- `history_chain_hash`
- `delta_t`
- `continuity_status`
- `source_state_ref`
- `source_state_hash`

正式履歴は追記専用とし、過去の上書き、削除、再割当てを禁止する。

## 三層構造

### 第1層: 正本

全G_tとK_t履歴台帳。変更不可。

### 第2層: 変化情報

G_t間の距離、重心変化、分散変化など。削除・再計算可能であり、正本ではない。

初期窓口として以下を実装する。

- Jensen–Shannon距離
- Hellinger距離
- エントロピー変化
- 集中度変化
- 各固定軸の重心変化
- 各固定軸の広がり変化

内容は予測フェーズの結果に応じて変更できる。

### 第3層: 履歴窓

- 全履歴
- `last_n`
- `start_t`から`end_t`

を読み出せる。短期・中期・長期の具体的な長さは本タスクでは固定しない。

## 入力境界

読み取る正本入力:

- `metadata.json`
- `steps.jsonl`
- 各 `state_ref` の `distribution`

数値入力として禁止:

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

seed、シナリオ名、データ分割名、世界版は出典情報としてのみ保存する。

## 別ログ

G_t・K_tとは別に以下を保存する。

- 観測済み外部入力
- 観測済み作用
- 観測済みイベント

正解地形、正解流れ、将来リスクなどの検証専用情報は、正本出力へコピーしない。

## 保存形式

```text
<output>/
  contract.json
  dataset_manifest.json
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

`gt_mass.npy` の形状は `(T, 5, 5, 5, 5, 5)` である。

`derived/` 以下は正本マニフェストから除外し、いつでも削除・再生成できる。

## ハッシュ

各G_tは、契約版、軌道ID、時点、固定軸定義、固定区分、G_tバイト列、出典状態ハッシュからSHA-256を生成する。

履歴連鎖ハッシュは前回の連鎖ハッシュ、現在G_tハッシュ、時点から生成し、過去履歴の差替えを検出する。

## 採用判定

### 表現基盤の硬い判定

以下をすべて通過しなければならない。

- 軸順・区分・形状・型の一致
- 有限・非負・総質量1
- 同一入力から同一結果
- 保存・再読込の一致
- 時点の一意性と連続性
- 欠落・重複・逆順の検出
- 将来情報不使用
- 出典情報を数値入力に不使用
- 軌道単位のデータ分割
- 検証正解の隔離
- 世界状態への書戻しなし
- 正本履歴の上書きなし

### 後続研究判定

- 外部要因応答が通常揺らぎから分離できるか
- K_tが現在G_t単独より動力学情報を追加するか
- validation・holdoutで安定するか

### 判定区分

- A: 表現基盤と全研究判定を通過
- B: 表現基盤は通過、研究判定が未完または限定的
- C: 表現基盤失敗、または外部応答と履歴価値の双方が失敗

本実装直後の自動判定は、表現基盤が通過しても研究判定未実施のためBとする。A判定を自動的に主張しない。

## 実行例

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
