# P3-1 接続確認

## 状態

P3-1の目的は、予測式を実装する前に、P3試作機が読む正本情報と既存関係場成果物の接続点を確定することである。

この段階では予測、入力翻訳、未来分布生成、精度検証を行わない。

## 最上位境界

P3の正式入力は次に限定する。

- 正本`G_t`
- `cutoff_t`までの因果的な`K_t`接頭部
- `G_t/K_t`だけから`cutoff_t`までに生成された関係場成果物
- 固定5軸格子の識別子・座標・隣接関係

次は予測入力にしない。

- 疑似現実系の内部配列
- 外部入力・作用・イベントの将来予定
- シナリオ名、seed、split
- 未来状態
- truth・outcome・RF-10

疑似現実系の生状態は、未来の正本`G_{t+1}`生成と入口変換監査に限ってP3外部で利用する。

## 確認した正本G/K接続

実装：`scripts/fixed5axis_gk_rc1.py`

既存の公開接続点：

```python
build_trajectory(source_trajectory_dir, output_root)
validate_trajectory_artifact(trajectory_dir)
```

P3が読む実ファイル：

```text
<gk trajectory>/
  gt_mass.npy
  history_ledger.csv
  provenance.json
  manifest.json
  validation.json
```

`gt_mass.npy`は`(time, 5, 5, 5, 5, 5)`の`float64`配列である。

`history_ledger.csv`は時点、G_t行番号、G_tハッシュ、直前G_tハッシュ、履歴鎖ハッシュ、連続性、研究利用可否を保持する。

P3は`cutoff_t`と`cutoff_t-1`の行を、履歴台帳の因果的接頭部から選ぶ。未来接尾部を予測入力に含めない。

## 確認したRF-3接続

実装：`scripts/relation_field_single_transition_rc1.py`

既存の公開接続点：

```python
build_transition_field(
    trajectory_dir,
    grid_artifact_dir,
    output,
    from_t=cutoff_t - 1,
    to_t=cutoff_t,
)
```

P3-1で直接検証するRF-3成果物：

```text
<rf3>/trajectories/<trajectory_id>/fields/t_<cutoff_t>/
  identity.json
  local_flow_edges.csv
  local_flow.npz
  reconstruction.json
  unresolved_residual.npz
  uncertainty.json
  manifest.json
```

主な数値接続は次である。

- `local_flow.npz/net_flow`
- `local_flow.npz/observed_delta`
- `unresolved_residual.npz/residual`
- `local_flow_edges.csv/canonical_edge_id`
- `local_flow_edges.csv/direction`
- `local_flow_edges.csv/flow_amount`

`identity.json`の`source_gt_hash_from/to`をG/K履歴台帳の該当ハッシュと一致させる。

`max_source_t_read`は必ず`cutoff_t`でなければならない。

RF-3は観測済み遷移の逆算であり、予測結果ではない。

## 流れ識別子に関する決定

### 固定位置の同一有向辺

同じ格子位置の流れ比較には次を使用できる。

```text
canonical_edge_id + direction
```

### 使用してはいけないもの

- `directed_flow_id`：単一RF-3成果物内の行番号であり、時系列同一性を持たない
- `relation_field_id`：遷移成果物全体の識別子であり、流れ個体の識別子ではない

### 平行移動する流れ型

固定辺番号だけでは、分布とともに移動する同じ流れ型を追跡できない。

RF-5では候補流れを平行移動非依存の31次元記述へ変換し、K_t上で時間候補経路を保持している。

したがってP3-2では、次を分けて翻訳する。

- 固定位置の有向辺：`canonical_edge_id + direction`
- 移動する流れ型：RF-5の相対記述・候補経路・共通構造

P3-1では流れ系譜の新しい固定規則を作らない。

## RF-4〜RF-9の接続役割

### RF-4

RF-3の再構成、最小作用、非一意性、solver感度、局所性を監査する。

P3の主要数値入力にはせず、RF-3を採用する際の監査証拠として扱う。

### RF-5

P3-2の主要入力候補である。

主な成果物：

- `candidate_flows.npz`
- `candidate_index.json`
- `temporal_paths.json`
- `representative_flow.npz`
- `common_structure.npz`
- `temporal_diagnostics.json`
- `uncertainty.json`

候補経路、共通流れ、軸流量区間、加速度、反転、場の変化候補を保持する。

### RF-6

勾配・循環・調和・分解残差を候補幅ごとに保持する。

P3-2では局所結合や循環の補助情報として採否を決める。初回必須入力とはまだ固定しない。

### RF-7

分布の重心、形状、収縮・拡張、集中・分散、流路細化・拡幅、境界動態を保持する。

P3-2では分布形状と流れ予測の補助情報として採否を決める。

### RF-8

軸間結合、同方向増強・減衰、方向反転、履歴条件付き新規駆動候補、未解決輸送残差を保持する。

P3-2では結合補正・新規駆動・残差情報の候補となる。

### RF-9

RF-6〜RF-8を組み合わせた並列の構造リスク候補である。

未来予測でも正解ラベルでもない。P3の主要流れ入力にはせず、後段へ渡す文脈候補として扱う。

## P3-1実装

追加した接続確認器：

```text
scripts/relation_field_prediction_p3_connection_check.py
```

実行例：

```bash
python scripts/relation_field_prediction_p3_connection_check.py \
  --gk-trajectory <gk trajectory dir> \
  --rf3-artifact <rf3 artifact dir> \
  --cutoff-t 8 \
  --output work/p3_1_connection.json
```

確認内容：

- 既存G/K検証器を通過している
- `cutoff_t-1 → cutoff_t`が連続している
- G_t行番号とハッシュが有効である
- RF-3の親G_tハッシュが一致する
- RF-3が`cutoff_t`より先を読んでいない
- RF-3流れ・分布差・残差の配列形状が有効である
- 固定位置の有向辺キーを生成できる
- 生状態・未来・正解情報を予測入力に使っていない
- 正本へ書き戻していない

## P3-1完了範囲

完了：

- P3用ブランチ作成
- G/Kの実接続点確定
- RF-3の実接続点確定
- RF-4〜RF-9の役割と主要成果物の棚卸し
- 時系列流れ識別の境界確定
- 因果カットオフ接続確認器
- 接続境界の否定試験

未実施：

- 共通ミクロ流れ情報への翻訳
- RF-5〜RF-9の数値統合
- 未来流れ予測
- 未来G生成
- 精度・バランス検証

これらはP3-2以降の範囲である。
