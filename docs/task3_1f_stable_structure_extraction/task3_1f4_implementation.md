# Task 3.1f-4 実装記録

## 1. 位置づけ

Task 3.1f-4は、Task 3.1f-3で選択・独立固定した安定構造候補を、未使用のholdoutで一度だけ評価し、その結果を別の独立検証器で再計算する工程である。

本タスクは構造への意味付けや意味軸としての採用判断を行わない。それらはTask 3.1g以降で扱う。

## 2. 実装範囲

新たに実装したのは次の範囲だけである。

- 有効な`selection_lock.json`を先に検証するholdout評価器
- 固定済み基底に対するholdout活性度推定
- 選択モデル、平均分布基準、選択rankのPCA参照のholdout指標
- external/base対応分布の変形保持指標
- `confirmed`／`conditional`／`failed`の判定候補
- 保存済み成果物から活性度・指標・判定を再計算する最終独立検証器
- holdout用縮小fixtureと主要改ざんテスト
- GitHub Actionsの`formal-holdout-evaluate` job

既存のStage B/C、構造数選択、感度監査、selection lock作成処理は変更していない。

## 3. 自己証明の防止

holdout評価器は最終判定を確定せず、`holdout_outcome_candidate.json`だけを作る。

独立検証器が次を再計算して一致した場合だけ、正式な`holdout_outcome.json`を作る。

- 固定基底に対するholdout活性度
- NMF・平均分布基準・PCAのholdout指標
- external/base変形保持指標
- validationとの性能比
- 最終判定
- 選択lock、入力、基底、活性度のhash

科学的判定が`failed`でも、独立再計算が一致していれば監査自体はPASSとする。

## 4. holdout境界

正式workflowは次の順序で実行する。

```text
formal-input-freeze
→ formal-fit-validate
→ formal-holdout-evaluate
```

`formal-fit-validate`はfit／validation Artifactだけを取得する。

`formal-holdout-evaluate`は、独立監査済みselection Artifactと分離保存されたholdout Artifactを初めて同時に取得する。評価器はselection lockを検証した後にholdout bundleを開く。

以下は行わない。

- 基底の再学習
- rank変更
- seed変更
- 閾値変更
- holdout結果を使った再選択
- producerによる最終合格の自己申告

## 5. 主要成果物

- `selected_model/holdout_activations.npy`
- `selected_model/pca_holdout_scores.npy`
- `holdout_metrics.csv`
- `pca_holdout_metrics.csv`
- `holdout_pair_deformation_metrics.csv`
- `holdout_outcome_candidate.json`
- `holdout_execution_manifest.json`
- `quality_checks.json`
- `final_audit.json`
- `holdout_outcome.json`
- `artifact_manifest.json`
- `results.md`

## 6. 縮小検証

縮小データでは、Task 3.1f-3のselection lockを作成してからholdout評価を実行する。

正常系に加え、最低限次を検出する。

- selection lock欠落
- lockされたrankの改変
- holdout活性度の改変
- holdout指標の改変
- outcomeの固定・改変
- holdout row mapの入れ替え

## 7. 正式実行との境界

本PRではコードとsmokeを実装する。正式Task 3.1e Artifactを使った49run、holdout 244行の評価、正式なselected rankとholdout outcomeの確定は、PRマージ後の手動GitHub Actions実行で行う。

したがって、本PR自体は正式holdout結果を主張しない。
