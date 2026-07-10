# Task 3.1f 固定契約一覧

## 現在地

- Task 3.1e：完了・`main`へマージ済み
- Task 3.1f：範囲固定済み
- Task 3.1f-1：比較設計・検証契約・出力仕様を確定
- 次工程：Task 3.1f-2 最小構造抽出基盤の実装

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

## 優先順位

内容が矛盾して見える場合、勝手に解釈して進めず停止する。

優先順位は次とする。

1. `TASK3_1F_SCOPE_FREEZE.md` の変更管理・範囲・禁止事項
2. machine-readable JSONの正確な数値・seed・solver・閾値
3. 比較設計の数理手順
4. 検証契約
5. 出力仕様

文書間に実質的な矛盾がある場合は、優先順位で黙って上書きせず、ユーザー確認を求める。

## 固定した主経路

```text
Task 3.1e正式質量分布
→ fitだけで重み付きKL-NMFを学習
→ validationだけで構造数を固定
→ selection lockを独立監査
→ holdoutを一度だけ評価
→ 安定構造だけをTask 3.1gへ渡す
```

## 運用分担

- ChatGPT：設計、Task 3.1f-2の通常実装、監査、修正
- Codex：固定済み条件の重い単作業だけ
- GitHub Actions：正式rank走査、長時間検証、holdout分離、成果物保存

## 変更時の必須報告

- 変更が必要な理由
- 衝突した固定要件
- 最小変更案
- 結果の比較可能性への影響
- holdout契約をやり直す必要性
