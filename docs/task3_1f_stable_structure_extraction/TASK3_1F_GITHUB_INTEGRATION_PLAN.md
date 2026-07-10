# Task 3.1f GitHub統合計画

## 1. 目的

Task 3.1f-2からTask 3.1f-5までの途中作業を、最終的に**Task 3.1fとして1本のPull Requestで`main`へマージできる状態**へ集約する。

Task 3.1f-1の固定契約はすでに`main`へマージ済みである。以後の実装・検証・結果監査は、Task 3.1f専用の統合ブランチへ積み上げる。

## 2. 統合ブランチ

正式な統合ブランチ：

```text
task3-1f-stable-structure-extraction
```

このブランチは、Task 3.1f-1が反映済みの`main`から作成する。

## 3. サブタスクの扱い

### Task 3.1f-2

最小構造抽出基盤、独立検証器、正常系・破壊系テスト、smoke実行を実装する。

### Task 3.1f-3

固定済みの構造数・初期値条件を一括実行できるようにする。Codexを使用する場合も、成果は統合ブランチへ取り込む。

### Task 3.1f-4

GitHub Actionsによる正式fit／validation走査、selection lock、holdout分離、正式成果物保存を実装・実行する。

### Task 3.1f-5

正式成果物を監査し、結果、制限、Task 3.1gへ渡す構造を確定する。

## 4. ブランチとPull Requestの規則

### 4.1 ChatGPTが直接実装する場合

原則として、Task 3.1f統合ブランチへ直接コミットする。

大きな変更で安全上分離が必要な場合は、短命な作業ブランチを作成してよい。ただし、そのPRのbaseは`main`ではなく、必ずTask 3.1f統合ブランチとする。

### 4.2 Codexを使用する場合

Codexには単作業ごとの短命な作業ブランチを使わせる。

例：

```text
task3-1f2-minimal-extraction
task3-1f3-fixed-grid-runner
task3-1f4-formal-workflow
```

各PRは次を満たす。

- base：`task3-1f-stable-structure-extraction`
- head：各単作業ブランチ
- `main`へ直接マージしない
- 固定契約を変更しない
- 実装・テスト・成果物契約が確認できた後に統合ブランチへマージする

## 5. 最終Pull Request

Task 3.1f-2からTask 3.1f-5が完了し、正式検証と結果監査が終わった後に、次の最終PRを作成する。

### PRタイトル

```text
[Task 3.1f] Complete stable-structure extraction from the full-distribution corpus
```

### base／head

- base：`main`
- head：`task3-1f-stable-structure-extraction`

### 最終PRに含めるもの

- 固定契約に沿った構造抽出実装
- 入力固定処理
- fit／validation分離
- selection lockと独立監査
- holdout一度限り評価
- 重み付きKL非負行列分解
- 主成分分析・平均分布基準・Frobenius感度参照
- 初期値・データ摂動・world seed安定性監査
- 正常系テスト
- 破壊系テスト
- GitHub Actions正式検証
- 正式成果物情報
- Task 3.1f結果報告
- Task 3.1gへの引き渡し情報

## 6. 最終マージ条件

以下をすべて満たすまで、Task 3.1f最終PRを`main`へマージしない。

1. Task 3.1f-2からTask 3.1f-5が完了している。
2. 固定契約との差分がない、または承認済み変更として記録されている。
3. smokeが成功している。
4. 正常系・必須破壊系テストが成功している。
5. GitHub Actions正式実行が完了している。
6. selection lockが独立検証されている。
7. holdout結果が保存・独立再計算されている。
8. 正式成果物のdigestとrun IDがPRへ記録されている。
9. Task 3.1gへ渡す構造と、渡さない構造の理由が記録されている。
10. placeholder、固定pass、自己証明、黙示的fallbackが残っていない。

科学的結果が`failed`であっても、契約どおり正しく実行・検証されていればTask 3.1fの実装タスクとしてはマージ可能である。その場合は、仮説不支持として明示し、成功結果へ偽装しない。

## 7. 途中の`main`マージ禁止

Task 3.1f-2、3.1f-3、3.1f-4、3.1f-5を個別完了PRとして`main`へ直接マージしない。

例外は、Task 3.1fと無関係な緊急修正、またはユーザーが明示的に個別`main`マージを指示した場合だけとする。

## 8. 現在地

- Task 3.1f-1：`main`へマージ済み
- Task 3.1f統合ブランチ：作成済み
- 次工程：Task 3.1f-2を統合ブランチ上で実装
- 最終到達点：Task 3.1f最終PRを`main`へマージ
