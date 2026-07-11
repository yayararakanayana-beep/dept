# Task 3.1f-3 検証結果

## 1. GitHub Actions

- Workflow：`Task 3.1f-3 Stage B/C`
- Run ID：`29135918146`
- 検証head：`1c0a76c499cfa04c20a178e90c0d80ede0ab394e`
- 結論：成功
- モジュールコンパイル：成功
- Task 3.1f-2回帰テスト：成功
- Task 3.1f-3正常系・破壊系テスト：成功
- Stage B／C smoke実行：成功
- 保存済み成果物の独立監査：成功

テストはTask 3.1f-2の17件とTask 3.1f-3の13件、合計30件を実行した。

## 2. 独立監査

独立監査は19項目すべて合格した。

主な再計算量：

- 再構成指標：14,960件
- 外部要因作用後／通常分布の対応変形指標：5,440件
- run間構造対応：273件
- 再構成指標の最大差：`9.974659986866641e-17`
- 対応変形指標の最大差：`4.440892098500626e-16`
- 構造対応の最大差：`2.351169259284802e-11`

確認済み：

- 固定構造数・seedの実行範囲
- モデルhash・形状・基底総和
- seed間の成果物使い回しなし
- 収束証拠
- 構造数別集計
- one-standard-error rule
- selection candidate
- 5部分集合のsalt・group・行集合の独立再構成
- 5部分集合の実モデルと学習行数
- world seed 0／1の実モデルと学習行数
- Frobenius感度の実モデルと学習行数
- holdout未使用
- selection lockの独立生成

## 3. smoke結果

smokeでは固定gridの先頭2構造数、5と8を実行した。

- 構造数5：適格
- 構造数8：smoke反復範囲ではランダムrunが収束せず不適格
- smoke選択構造数：5
- 代表run：`nmf_kl_rank05_seed31012`
- 5部分集合の構造生存率：1.0
- world seed 0の中央値類似度：`0.868493`
- world seed 1の中央値類似度：`0.835166`
- 選択5構造：すべてsmoke上では`stable_structure`

これは縮小データによる実行経路検証であり、正式なTask 3.1f科学結果ではない。

## 4. GitHub Actions成果物

- Artifact ID：`8243572725`
- Artifact名：`task3-1f3-stage-bc-smoke`
- サイズ：455,619 bytes
- Digest：`sha256:83dbc221ad9b70529f3a4777e47a534eae26e7753a97ac2b2868edaf5d0dcece`
- 保存期限：2026-07-25

成果物には以下を含む。

- 学習用／検証用evidence bundle
- 14本のKL-NMFモデル
- 重み付き主成分分析参照
- 平均分布基準
- 対応変形指標
- 構造対応
- 構造数別集計
- 5部分集合の再学習モデル
- world seed 0／1再学習モデル
- Frobenius感度モデル
- selection candidate
- 独立selection audit
- selection lock
- 品質検査
- 破壊系検査記録
- 全成果物manifest

## 5. 破壊系

少なくとも次を個別に破壊し、独立監査が拒否することを確認した。

- seed run欠落
- 収束値の偽造
- 基底hash改変
- 安定構造率の固定値化
- 対応変形指標の固定0化
- producer作成selection lock
- holdout由来ファイル混入
- grouped subsetのgroup保持偽装

## 6. 科学的境界

- holdoutは使用していない。
- 正式7構造数・49runはまだ実行していない。
- smoke選択構造数5を正式結果として扱わない。
- Task 3.1gへ渡す正式構造はまだ決定していない。
- 次工程はTask 3.1f-4の正式Stage B／C実行とholdout評価である。
