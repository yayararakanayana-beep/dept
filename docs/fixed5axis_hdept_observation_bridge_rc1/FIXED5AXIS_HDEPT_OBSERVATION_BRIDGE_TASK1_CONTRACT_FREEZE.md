# 固定5軸上位観測翻訳層 RC1 — 接続タスク1 契約凍結

## 0. 状態

- タスク: 接続タスク1「接続契約の固定」
- 契約版: `fixed5axis_hdept_observation_bridge_rc1`
- 状態: `frozen_for_builder_implementation`
- 科学的位置づけ: `B_limited_contract_only_no_bridge_performance_claim`
- このタスクでは翻訳builder、実行時validator、否定試験、校正、上位圧生成は実装しない。

本書は、固定5軸の正本 `G_t/K_t` を H-DEPT の `H11_STRUCTURED` 上位観測状態 `M_t` へ接続するための境界・特徴・証拠・校正・出力契約を固定する。

---

## 1. 目的

正式な接続経路は次とする。

```text
固定5軸 正本 G_t / 因果的 K_t 接頭部
    ↓
固定5軸特徴生成
    ↓
利用可能性・信頼度判定
    ↓
固定校正
    ↓
H11_STRUCTURED M_t
    ↓
将来の compute_from_m()
```

今回の翻訳層は、旧上位層を動かすために `gt_activity` や `gt_relation_lock` 等の旧列を恣意的に埋める互換器ではない。

`G_t → M_t` の観測意味を保った正式な翻訳層とする。

---

## 2. 固定する境界

### 2.1 正式入力

正式入力は次だけである。

1. 現在時点の固定5軸正本 `G_t`
2. 現在時点で終わる因果的な固定5軸 `K_t` 接頭部
3. 固定5軸の軸・格子・履歴・出所情報
4. 凍結済み校正成果物
5. 固定格子の座標と隣接関係

固定5軸の軸順は変更しない。

1. `resource_slack`
2. `information_quality`
3. `pressure`
4. `exploration_room`
5. `reversibility`

各軸は `[0.0, 0.25, 0.5, 0.75, 1.0]` の5区分、`G_t` は `(5,5,5,5,5)`、3,125セル、`float64`、`pre_transition` とする。

### 2.2 履歴選択

builder が使用できる履歴は、現在時点 `current_t` で終わる **連続した因果的接尾部**だけである。

- 未来接尾部を読まない。
- 現在行は `initial` または `continuous` で、`admissible_for_research=true` を必須とする。
- 過去にgap等が存在しても保存するが、その境界を越えて連続量を計算しない。
- 初期1フレームは有効入力だが、履歴特徴は利用不能とし、全体状態を `INSUFFICIENT_HISTORY` 以下に制限する。

### 2.3 正式入力から除外するもの

次は数値証拠として使用禁止とする。

- 未来の `G_t/K_t`
- 正解、リスク正解、回復正解、最終結果
- RF-10の未来結果・予測対象側成果物
- P1の未来ラベル・予測対象
- 外部入力、行動、事象ログ
- `O_t`
- v8局所監査
- 探索モジュール出力
- 作用面、作用結果
- 上位圧、承認圧
- Parameter Box
- validation/holdoutの結果

外部入力・行動・事象は出所監査として別記録できるが、H11の正式な数値証拠にはしない。

---

## 3. Phase 1の47特徴の扱い

H-DEPT Phase 1の47特徴は、合成検証で使われた意味‐幾何特徴語彙であり、固定5軸正本からの抽出方法まで検証済みという意味ではない。

そのため47特徴を次の種類に分ける。

| 種類 | 扱い |
|---|---|
| `exact_current` | 現在の正本 `G_t` から厳密に計算 |
| `exact_history` | 因果的な連続 `K_t` から厳密に計算 |
| `adapted_fixed_grid_proxy` | 固定格子向け代理量。代理であることを明示し信頼度上限を持つ |
| `structural_constant` | 契約上一定。状態証拠として使わない |
| `reserved_prediction_subcontract` | 予測契約が固定されるまで利用不能 |
| `reserved_recovery_subcontract` | 変形・回復事象契約が固定されるまで利用不能 |

全47特徴の式・必要履歴・信頼度上限・主張限界は
`configs/fixed5axis_hdept_feature_registry_rc1.json`
に固定する。

### 3.1 重要な非対応

以下は Task 1 では値を捏造しない。

- `prediction_error`
- `residual_variance`
- `residual_acceleration`
- `target_distance`
- `forecast_instability`
- `recovery_half_life`
- `post_shock_shape_deviation`
- `post_shock_entropy_deviation`
- `return_distance`
- `deformation_persistence`

これらは未来正解や外部事象ラベルで埋めず、対応する因果的下位契約ができるまで `available=false`, `value=null`, `confidence=0` とする。

---

## 4. 特徴利用可能性契約

各特徴は最低限、次を持つ。

```text
feature_id
group
value
available
confidence
support_count
minimum_history_frames
derivation_status
evidence_source
reason_unavailable
```

### 4.1 欠測・証拠不足

- 利用不能値へのゼロ埋めは禁止する。
- 利用不能時は `value=null`。
- `confidence=0`。
- `reason_unavailable` を必須とする。
- 数値0は、計算結果として本当に0の場合だけ使用できる。

これにより「観測できない」を「変化がない」へ変換しない。

### 4.2 代理特徴

固定格子代理量は厳密量と同じ名称空間へ出せるが、必ず次を持つ。

- `derivation_status=adapted_fixed_grid_proxy`
- 1未満の `confidence_cap`
- 代理の意味範囲
- 禁止される強い解釈

例:

- 軸周辺分布のWasserstein距離は、完全な5次元同時Wasserstein距離ではない。
- 境界質量は統計的一般のtailではない。
- 閾値連結成分数は物理的な真のモード数ではない。
- 固定格子近傍密度は文字通りのk近傍密度ではない。

---

## 5. 校正契約

H11値を生成する場合、校正成果物を必須とする。

### 5.1 校正の生成

校正値は校正用データだけから生成する。

禁止:

- 現在の1要求内で平均・標準偏差を再計算
- validationでfit
- holdoutでfit
- 実行中のオンライン再fit
- 結果を見て校正値を変更

校正成果物は最低限、次を持つ。

- 校正版
- 特徴台帳ハッシュ
- 特徴順
- 中心値
- 尺度
- クリップ上下限
- fitデータ識別子
- fit軌道識別子のハッシュ
- fit時点境界
- 正規化方法
- 生成コードハッシュ

尺度0の一定特徴は、H11証拠として使用しない。

### 5.2 単一時点の全0.5化防止

Phase 1配布実装のように入力データ自身へ `fit_transform` すると、単一時点入力は全特徴が0となり、H11が一律0.5へ潰れる。

RC1では、実行時は凍結済み校正値による `transform` のみ許可する。

---

## 6. H11証拠契約

軸順は次に固定する。

1. `Stability`
2. `AdaptabilityStar`
3. `Exploration`
4. `Efficiency`
5. `Robustness`
6. `StructuralDiversity`
7. `TrajectoryDynamics`
8. `Predictability`
9. `Coherence`
10. `Recoverability`
11. `NoveltyQuality`

証拠構成は
`configs/fixed5axis_hdept_h11_evidence_map_rc1.json`
に固定する。

### 6.1 基礎成分

Phase 1のH11_STRUCTURED構造を保ち、正規化済み特徴から次を作る。

```text
基礎成分 = 利用可能な正特徴の平均 - 利用可能な負特徴の平均
```

空でない証拠群の被覆率が不足する場合、値を暗黙補完せず、成分または軸を `LIMITED` / `UNAVAILABLE` とする。

### 6.2 合成軸

```text
AdaptabilityStar
  = 0.50 Adaptability + 0.50 Plasticity

StructuralDiversity
  = 0.65 Diversity + 0.35 ModeSeparability

TrajectoryDynamics
  = 0.45 Persistence
  + 0.25 AxisTurnover
  + 0.15 CurvatureSensitivity
  + 0.15 OscillationSensitivity
```

他のH11軸は対応する基礎成分を使う。

軸値は凍結校正後のraw scoreへ `sigmoid(gamma * raw)` を適用し、RC1の `gamma=1.0` とする。

### 6.3 軸の証拠状態

各軸は次を持つ。

```text
value
transport_value
transport_value_is_neutral_placeholder
available
confidence
evidence_coverage
status
evidence_feature_ids
claim_limit
watchpoints
```

軸状態:

- `READY`
- `LIMITED`
- `UNAVAILABLE`

ただしTask 1・Task 2の全体状態上限は `LIMITED` とする。`READY` の全体判定にはTask 4の科学検証が必要である。

### 6.4 中立転送値

下流形式の都合で利用不能軸にも数値が必要な場合だけ、`transport_value=0.5` を使用できる。

ただし、

- `value=null`
- `available=false`
- `confidence=0`
- `transport_value_is_neutral_placeholder=true`

を必須とする。

この0.5を正常な観測証拠や通常圧生成に使うことは禁止する。

---

## 7. 軸ごとの主張限界

| H11軸 | RC1での最大解釈 |
|---|---|
| Stability | 観測された分布運動の小ささ。安全性ではない |
| AdaptabilityStar | 移動・再構成可能性の代理。適応成功ではない |
| Exploration | 分布拡張・軸参加・モード構造・運動の代理 |
| Efficiency | 幾何的な圧縮・構成効率代理。費用効率ではない |
| Robustness | 回復証拠が揃うまで限定または利用不能 |
| StructuralDiversity | 分布多様性＋閾値モード分離代理 |
| TrajectoryDynamics | 持続・交代・曲率・振動代理 |
| Predictability | 因果的予測契約ができるまで利用不能 |
| Coherence | 幾何的整合性代理 |
| Recoverability | 回復事象契約ができるまで利用不能 |
| NoveltyQuality | 構造的新規性代理。新規性の有用性は観測不能 |

特に `NoveltyQuality` は、固定5軸 `G_t/K_t` だけから「質」を確定しない。最大状態を `LIMITED` とする。

---

## 8. 出力契約

翻訳層の成果物は次とする。

```text
identity.json
features.json
m_observation.json
audit.json
provenance.json
manifest.json
```

成果物bundleのJSON schemaは
`schemas/fixed5axis_hdept_observation_bridge_rc1.schema.json`
に固定する。

### 8.1 全体状態

- `INVALID_INPUT`
- `INSUFFICIENT_HISTORY`
- `LIMITED`
- `READY`
- `HOLD_RECOMMENDED`

Task 1・Task 2で `READY` を出してはならない。

### 8.2 監査必須事項

監査には最低限、次を記録する。

- 使用した現在時点
- 使用履歴の開始・終了時点
- `G_t` ハッシュ
- 履歴鎖ハッシュ
- 特徴台帳ハッシュ
- H11証拠対応表ハッシュ
- 校正版
- 利用不能特徴と理由
- 代理特徴一覧
- クリップ発生
- 未来接尾部を読んでいないこと
- truthを使っていないこと
- 外部ログを数値証拠に使っていないこと
- `O_t` や圧を使っていないこと
- 正本への書戻しをしていないこと
- 中立転送値を証拠として使っていないこと

---

## 9. 旧上位層との将来接続

既存入口:

```python
compute(formal_packet)
```

は回帰比較のため残す。

新しい入口:

```python
compute_from_m(m_packet)
```

は接続タスク5で追加する。

新経路では旧 `gt_*` 列を経由しない。

```text
固定5軸 G_t/K_t
    ↓
固定5軸上位観測翻訳層
    ↓
H11 M_t + confidence + evidence_coverage
    ↓
compute_from_m()
```

`UNAVAILABLE` 軸の0.5転送値を通常圧へ使用してはならない。信頼度不足時は圧減衰・HOLD・NO_OPのいずれかを要求する。

---

## 10. 禁止事項

1. 旧コードを動かすためだけの `gt_*` 偽変換
2. 47特徴を固定5軸抽出器として既に検証済みと扱うこと
3. 未来接尾部や予測対象側成果物の参照
4. truth・外部事象・作用結果・`O_t`・圧の正式証拠利用
5. 利用不能値のゼロ埋め
6. 0.5転送値を観測証拠として扱うこと
7. 実行要求ごとの正規化fit
8. validation/holdoutを使った校正fit
9. 未知の版を黙って受理
10. 固定格子代理量への過剰な名称・意味付与
11. Task 1での上位圧生成
12. 正本・親成果物・校正成果物への書戻し
13. Task 4前の正式H11接続主張

---

## 11. Task 1完了条件

- 主契約が機械可読JSONとして存在する。
- 47特徴が重複なく台帳化される。
- 全特徴が厳密量・履歴量・代理量・予約量に分類される。
- 11軸の証拠参照が全て台帳へ解決する。
- 利用不能・信頼度・中立転送値の規則が固定される。
- 校正のfit/transform境界が固定される。
- 未来・truth・外部ログ・O_t・作用・圧の混入が禁止される。
- 旧上位層との接続入口方針が固定される。
- builder実装者が新たな入力境界判断をしなくてよい。
- 翻訳性能・安全性・閉ループ有効性はまだ主張しない。

---

## 12. 次タスク

接続タスク2では、この契約を変更せずに次を実装する。

- 正本入力読込み
- 因果的連続履歴選択
- 47特徴record生成
- 利用可能性・信頼度
- 凍結校正読込み
- H11生成
- 監査成果物
- 決定論的出力

予測残差・回復幾何の予約特徴を実装可能へ変更する場合は、別の因果的下位契約を先に固定し、ユーザー確認を取る。
