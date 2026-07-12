# 固定5軸 関係場 RF-3 — 観測済み単一遷移の局所流れ逆算

## 1. 目的

Task RF-3は、正本の固定5軸分布に含まれる一つの連続した観測済み遷移、

```text
G_from_t → G_to_t
```

を、RF-2の局所格子上の有向流れとして逆算する。

これは未来予測ではない。`to_t`までに実際に観測された分布差分を、局所的な質量移動で説明するための代表解である。

本タスクでは、時間整合した関係場、勾配・循環分解、リスク構造、作用判断はまだ扱わない。

---

## 2. 入力境界

必須入力は次だけである。

- 正本`gt_mass.npy`
- 正本`history_ledger.csv`
- RF-2格子成果物

遷移は、

```text
to_t = from_t + 1
```

でなければならない。

`from_t`と`to_t`は研究利用可能であり、`to_t`の連続性状態は`continuous`でなければならない。履歴ハッシュ連鎖と選択したG_tハッシュも再検証する。

### 因果境界

時点`to_t`の成果物は、次だけを読む。

- `G_from_t`
- `G_to_t`
- `to_t`までの履歴台帳接頭部

次を読まない。

- `G_after_to_t`
- 観測済み外部入力ログ
- 作用ログ
- イベントログ
- シナリオ名やseedを数値入力として利用すること
- 地形、流れ、リスクなどの正解情報

将来接尾部が異なっても、同じ観測済み遷移からは同じRF-3成果物を生成しなければならない。

---

## 3. 逆算問題

RF-2の基準辺数を`E=12,500`、セル数を`V=3,125`、接続演算子を`B`とする。

各基準辺について、正方向と逆方向に別々の非負流量を置く。

```text
f_forward >= 0
f_reverse >= 0
```

符号付き正味流量は、

```text
f_net = f_forward - f_reverse
```

で得る。

観測差分は、

```text
delta_G = G_to_t - G_from_t
```

である。

残差を正負の非負変数へ分ける。

```text
r = r_positive - r_negative
```

制約式は、

```text
B f_forward - B f_reverse + r_positive - r_negative = delta_G
```

とする。

---

## 4. 目的関数

代表解は線形計画法で求める。

```text
最小化:
  0.25 × sum(f_forward + f_reverse)
  + 5.25 × sum(r_positive + r_negative)
```

- 一辺の固定5軸座標距離：`0.25`
- 格子の最大最短経路費用：`5.0`
- 残差費用：`5.25`

残差費用を格子内の最大経路費用より高くすることで、正規化分布間のゼロ和変化は、可能な限り局所格子流れで説明する。それでも残る量は削除せず、未解決残差として保存する。

solverはSciPy HiGHSの`highs-ds`を使用する。

---

## 5. 解の意味

RF-3が生成するのは、最小輸送費用を満たす代表解である。

固定5軸格子には循環経路が多数あるため、同じ観測差分を同じ最小費用で説明する別解が存在し得る。

したがって、次を主張しない。

- 真の流れを一意に復元した
- 世界の内部力学を確定した
- 外部要因を特定した
- 流れの信頼度を校正した

代替解と正則化感度の監査はRF-4へ送る。

---

## 6. 出力

```text
<output>/
  contract.json
  validation.json
  manifest.json
  trajectories/
    <trajectory_id>/
      relation_field_manifest.json
      provenance.json
      fields/
        t_<to_t:06d>/
          identity.json
          local_flow_edges.csv
          local_flow.npz
          reconstruction.json
          unresolved_residual.npz
          uncertainty.json
          manifest.json
```

### local_flow_edges.csv

閾値を超えた有向流れだけを行として保存する。

- 基準辺番号
- 移動元セル
- 移動先セル
- 移動軸
- 基準方向に対する正負
- 流量
- 距離
- 信頼度欄
- 信頼度状態

RF-3では信頼度を校正しないため、`confidence`は空欄、`confidence_status`は`not_calibrated_rf3`とする。

### local_flow.npz

全基準辺と全セルについて、次を保存する。

- `forward_flow`
- `reverse_flow`
- `net_flow`
- `observed_delta`
- `reconstructed_delta`

G_tそのものは複製しない。

### unresolved_residual.npz

- `residual`
- `positive_residual`
- `negative_residual`

残差を外部要因とは命名しない。

### uncertainty.json

少なくとも次を分離する。

- 識別不確実性
- 証拠不足
- 時間安定性未評価
- 範囲外未評価
- solver数値残差

---

## 7. 保存と再現性

- G_t・K_t正本を書き換えない
- G_t・K_t正本を関係場成果物へ複製しない
- 既存出力を上書きしない
- 一時領域から原子的に確定する
- NPZは固定ZIP時刻と固定キー順で保存する
- 全ファイルをSHA-256マニフェストで監査する
- 同じ入力・契約・solver版から同一成果物を生成する

---

## 8. 実行例

RF-2格子成果物を生成する。

```bash
python scripts/relation_field_grid_rc1.py build \
  --output artifacts/relation_field_grid_rc1
```

単一遷移を逆算する。

```bash
python scripts/relation_field_single_transition_rc1.py build \
  --trajectory artifacts/fixed5axis_gk_rc1/trajectories/<trajectory_id> \
  --grid-artifact artifacts/relation_field_grid_rc1 \
  --output artifacts/relation_field_single_transition_rc1 \
  --from-t 0 \
  --to-t 1
```

検証する。

```bash
python scripts/relation_field_single_transition_rc1.py validate \
  --input artifacts/relation_field_single_transition_rc1 \
  --grid-artifact artifacts/relation_field_grid_rc1
```

---

## 9. RF-3の合格条件

- 連続した研究利用可能遷移だけを受け付ける
- 履歴ハッシュ連鎖と選択G_tハッシュが一致する
- 有向流量が非負
- 観測差分を許容誤差内で再構成する
- 総質量保存または質量不整合を残差として明示する
- 未解決残差を保存する
- 必須4種類の不確実性を持つ
- `to_t`より後を利用しない
- 同じ入力から決定論的に同じ成果物を作る
- 入力G_t・K_tを変更しない
- マニフェスト検証を通過する

---

## 10. RF-4への引き渡し

RF-4では次を独立に監査する。

- 同じ最小費用を持つ代替流れ
- solver方式と正則化への感度
- 流れの疎性と経路分散
- 最小作用の成立
- 数値許容誤差
- 残差費用への感度
- 局所性を弱めた場合との比較
- 多経路格子での識別不確実性

RF-3単独では、代表解の科学的な一意性を採用判定しない。
