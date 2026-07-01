# PseudoReality v2-RC1 Freeze

## 1. v2-RC1 の位置づけ

PseudoReality v2-RC1 は、PseudoReality v2 の世界モデル全体が完成したことを意味しない。

PseudoReality v2-RC1 は、DEPT2/H-DEPT closed-loop validation 用の「非対称動的ゲーム疑似現実系」として、最低限の実行・trace 出力・profile 差分・probe matrix・監査境界が揃った到達点を凍結するものである。

この freeze は、現時点で実行可能かつ監査可能な到達点を docs 上で固定するためのものであり、以下を意味しない。

- v2-RC1 は performance validation ではない。
- v2-RC1 は v2 world の優位性主張ではない。
- v2-RC1 は H-DEPT 診断指標の正式採用ではない。
- v2-RC1 は v1 world を置き換えない。
- v2-RC1 は closed-loop validation 用の追加疑似現実系である。

## 2. v2-RC1 として凍結するもの

v2-RC1 では、以下の接続・profile・matrix・trace・検証状態を凍結する。

### world_engine

- `pseudo_reality_v1` / `asymmetric_game_v2` の切替。

### world class

- `AsymmetricGamePseudoRealitySystem`。

### profiles

- `pseudo_reality_v2_shrinking_equilibrium`
- `pseudo_reality_v2_trust_collapse`
- `pseudo_reality_v2_public_stability_hidden_decay`

### matrices

- `matrix_v2_smoke`
- `matrix_v2_probe`

### traces

- `entity_trace`
- `relation_trace`
- `v2_hidden_trace`
- `v2_game_trace`
- `v2_resource_trace`
- `v2_information_trace`
- `v2_action_effect_trace`

### validation status

- `compileall` PASS。
- existing smoke PASS。
- `matrix_v2_smoke` PASS。
- `matrix_v2_probe` PASS。
- boundary/write/forbidden write 0。
- NaN / inf なし。
- 主要数値列は 0.0〜1.0 範囲内。

## 3. v2-RC1 として凍結しないもの

v2-RC1 では、以下は凍結しない。

- v2 追加 trace の `G_t` / `O_t` / `K_t` 接続。
- v2 trace の H-DEPT 正式診断指標化。
- v2 profile の長期妥当性。
- v2 long-run validation。
- v2 stress / ablation validation。
- v2 metrics の正式採用。
- 現実系対応。
- 安全性証明。
- 性能優位性。

## 4. v2-RC1 の実装範囲

v2-RC1 の実装範囲は、closed-loop validation 用の追加疑似現実系として、既存 runner から v2 world を選択し、ActionFrame 入力に対して v2 world 内部状態を更新し、監査用 trace を出力できる範囲に限定する。

この範囲には、`world_engine` による `pseudo_reality_v1` / `asymmetric_game_v2` の切替、`AsymmetricGamePseudoRealitySystem` の最小接続、v2 用 profiles、v2 smoke/probe matrices、v2 追加 trace 出力が含まれる。

この範囲には、v2 trace の H-DEPT 正式診断指標化、`G_t` / `O_t` / `K_t` への直接接続、現実系対応、安全性証明、性能優位性主張は含まれない。

## 5. v2-RC1 の profile 範囲

### `pseudo_reality_v2_shrinking_equilibrium`

縮小均衡を見る profile。表面上は一定の安定や短期利得が残りつつ、内部劣化・長期健全性低下が進むかを見る。

### `pseudo_reality_v2_trust_collapse`

信頼低下・情報歪み・調整遅れによる崩壊を見る profile。悪意ある抽出だけでなく、誤読と遅延で協力が崩れる構造を見る。

### `pseudo_reality_v2_public_stability_hidden_decay`

表面安定と内部劣化の分離を見る profile。`volatility` / `uncertainty` が安定していても `hidden_damage` / `fatigue` / `latent_pressure` が悪化するかを見る。

## 6. v2-RC1 の trace 範囲

### `v2_hidden_trace`

hidden state の監査 trace。`latent_pressure` / `fatigue` / `private_resource` / `defensiveness` / `opportunism` / `cooperation_intent` / `information_quality` / `hidden_damage` を読む。

### `v2_game_trace`

主体ごとの局所反応傾向・短期利得・長期健全性 proxy を読む trace。

### `v2_resource_trace`

`shared_resource` / `commons_health` / `resource_pressure` / `resource_inequality` を読む trace。

### `v2_information_trace`

`information_delay` / `distortion` / `hidden_state_visibility` / `misread` / `coordination_lag` を読む trace。

### `v2_action_effect_trace`

ActionFrame の直接効果と副作用を読む trace。

これらの v2 追加 trace は、現時点では audit / diagnostic 用である。これらの v2 追加 trace を `G_t` / `O_t` / `K_t` に直接混ぜない。これらの v2 追加 trace を H-DEPT 正式診断指標として扱わない。

## 7. v2-RC1 の matrix 範囲

### `matrix_v2_smoke`

v2 world が既存 runner に接続され、最小実行できることを確認する smoke matrix。

### `matrix_v2_probe`

3 profiles × 3 action profiles = 9 runs。v2 追加 trace と profile 差分を読むための probe matrix。

## 8. main 統合確認結果

| Check | Status | Evidence | Notes |
| --- | --- | --- | --- |
| compileall | completed | `compileall` PASS | main 統合確認で確認済み。 |
| existing smoke | completed | overall_pass true | 既存 smoke が通過している。 |
| matrix_v2_smoke | completed | overall_pass true | v2 world の最小接続 smoke が通過している。 |
| matrix_v2_probe | completed | overall_pass true | 3 profiles × 3 action profiles の probe matrix が通過している。 |
| boundary_violation_total | completed | `0` | closed-loop 境界違反なし。 |
| dry_run_write_violation_count | completed | `0` | no-write / dry-run 境界違反なし。 |
| forbidden_write_count | completed | `0` | forbidden write なし。 |
| v2 追加 CSV 出力 | completed | CSV output observed | v2 追加 trace CSV 出力を確認済み。 |
| NaN / inf | completed | none observed | v2 追加 CSV に NaN / inf なし。 |
| major numeric range | completed | `0.0`〜`1.0` | 主要数値列は範囲内。 |

## 9. profile behavior report の扱い

profile behavior report は、v2 profile ごとの trace 傾向を観測するためのレポートである。

これは performance validation ではない。これは v2 world の優位性主張ではない。これは H-DEPT 診断指標の正式採用ではない。

profile behavior report は、v2-RC1 に進むための補助証拠である。ただし、long-run validation や stress / ablation validation の代替ではない。

## 10. closed-loop boundary rule

v2-RC1 では、以下の closed-loop boundary rule を維持する。

- v2 world は ActionFrame だけを受け取る。
- v2 world は ParameterBox を直接読まない。
- v2 world は上位圧を直接読まない。
- v2 world は `G_t` / `O_t` / `K_t` を直接読まない。
- v2 world は探索 sidecar を直接読まない。
- v2 world から DEPT2 内部へ直接書き戻さない。
- 世界状態は v2 world 内部が正本。
- `G_t` / `O_t` / `K_t` は世界 trace から派生するだけ。

## 11. 現時点で言ってよいこと

- v2-RC1 は、closed-loop validation 用の追加疑似現実系として実行可能である。
- v2-RC1 は、v1 world を置き換えずに併存できる。
- v2-RC1 は、複数 profile と追加 trace を持つ。
- v2-RC1 は、`matrix_v2_smoke` と `matrix_v2_probe` を通過している。
- v2-RC1 は、boundary/write/forbidden write 0 を確認済みである。

## 12. 現時点で言ってはいけないこと

- v2-RC1 は性能優位性を示した。
- v2-RC1 は現実系に対応済みである。
- v2-RC1 は安全性を証明した。
- v2-RC1 は H-DEPT 診断指標を正式採用した。
- v2-RC1 は v1 world を置き換える。
- v2-RC1 は長期妥当性を確認済みである。

## 13. v2-RC1 後に残す課題

- v2 long-run validation。
- `matrix_v2_probe_long`。
- v2 stress / ablation validation。
- profile-specific ablation。
- action side-effect deeper audit。
- v2 追加 trace を `G_t` / `O_t` / `K_t` へ接続するかどうかの設計。
- v2 metrics 正式化の可否。
- v2-RC1 report。

## 14. 次フェーズ候補

推奨順序は以下の通り。

### Task A: v2-RC1 main integration verification

main 統合後の v2-RC1 到達点を再確認し、docs freeze と実行状態の対応を確認する。

### Task B: v2-RC1 report

v2-RC1 の凍結範囲、確認結果、未凍結範囲、次フェーズ課題を report として整理する。

### Task C: matrix_v2_probe_long design

`matrix_v2_probe` を長期観測用に拡張する設計を作る。

### Task D: v2 long-run validation

長期実行で profile ごとの挙動、trace の安定性、境界維持、数値範囲を確認する。

### Task E: v2 stress / ablation design

stress / ablation validation の対象、観測軸、禁止する結論、境界条件を設計する。
