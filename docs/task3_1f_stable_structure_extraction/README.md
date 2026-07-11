# Task 3.1f 固定契約一覧

## 現在地

- Task 3.1e：完了・`main`へマージ済み
- Task 3.1f：範囲固定済み
- Task 3.1f-1：比較設計・検証契約・出力仕様を確定
- Task 3.1f-2：最小構造抽出基盤・独立検証・smokeを実装
- Task 3.1f-3：固定rank・初期値条件のStage B/C fit-validation batch、選択候補、独立selection audit、smoke lockを実装
- 次工程：Task 3.1f-4 GitHub Actions上の正式fit／validation実行とholdout評価

## 契約文書

1. `TASK3_1F_SCOPE_FREEZE.md`
   - 目的、変更管理、成功定義、対象外範囲
2. `../../configs/task3_1f_structure_extraction_contract.json`
   - 数値、seed、構造数、solver、閾値、holdout判定の機械可読契約
3. `task3_1f1_comparison_design.md`
   - 数理方法、重み付け、対応付け、構造数選択
4. `task3_1f1_validation_contract.md`
   - 実行段階、正常系、破壊系、停止条件、GitHub Actions分離
5. `task3_1f1_output_schema.md`
   - 成果物、列、配列形状、hash、保存量管理
6. `task3_1f2_implementation.md`
   - 最小実装の範囲、smoke条件、holdout境界
7. `task3_1f2_results.md`
   - ローカル・GitHub Actions検証結果
8. `task3_1f3_implementation.md`
   - Stage B/C batch・selection candidate・独立validator実装
9. `task3_1f3_results.md`
   - Task 3.1f-3 smoke検証結果、未解決項目、holdout未アクセス記録

## 優先順位

文書間の食い違いを見つけた場合は、まず結果の意味、holdout独立性、過去結果との比較可能性に影響するかを確認する。

- 影響する場合：作業を止め、ユーザー確認を得る。
- 影響しない実装詳細の場合：元の目的を保つ最小修正を行い、変更を記録する。

参照の優先順位は次とする。

1. `TASK3_1F_SCOPE_FREEZE.md` の変更管理・範囲・禁止事項
2. machine-readable JSONの正確な数値・seed・solver・閾値
3. 比較設計の数理手順
4. 検証契約
5. 出力仕様

優先順位は、実質的な矛盾を黙って上書きするためには使用しない。

## 固定した主経路

```text
Task 3.1e正式質量分布
→ fitだけで重み付きKL-NMFを学習
→ validationだけで構造数候補を作成
→ 独立監査に合格した場合だけselection lockを作成
→ holdoutを一度だけ評価
→ 安定構造だけをTask 3.1gへ渡す
```

Task 3.1f-2では、このうち入力固定、fit／validation最小抽出、参照手法、独立再計算まで実装した。Task 3.1f-3では、Stage B/Cの固定grid batch、selection candidate、独立selection audit、smoke selection lockまでを実装した。holdout評価と最終科学判定はまだ行っていない。

## 運用分担

- ChatGPT：設計、仕様整理、実装、監査、修正
- GitHub Actions：正式rank走査、長時間検証、holdout分離、成果物保存

各サブタスクは個別PRとして`main`へマージしてよい。Task 3.1f全体の完了後、GitHub上で全到達点とTask 3.1gへの引き継ぎをまとめる。

## 結果の意味に影響する変更時の報告

- 変更が必要な理由
- 衝突した固定要件
- 最小変更案
- 結果の比較可能性への影響
- holdout契約をやり直す必要性
