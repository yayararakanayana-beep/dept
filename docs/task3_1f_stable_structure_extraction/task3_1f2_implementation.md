# Task 3.1f-2 最小構造抽出基盤

## 1. 位置づけ

Task 3.1f-1で固定した契約に従い、正式一括走査へ進む前の最小実装を追加する。

本タスクでは、構造数の正式選択、`selection_lock.json`、holdout評価は行わない。これらはTask 3.1f-3／3.1f-4で行う。

## 2. 実装した範囲

- Task 3.1e成果物の完全性検査
- fit／validation／holdout bundleの物理分離
- row mapとsnapshot hashによる対応固定
- 重み付き一般化KL非負行列分解
- 基底の総和1正規化と活性度への倍率移動
- 固定基底に対するvalidation活性度推定
- 重み付き主成分分析参照
- 重み付き平均分布基準
- 確率単体へのユークリッド射影
- Jensen–Shannon距離による構造比較
- Hungarian法による構造対応付け
- 重み付き／重みなし再構成指標
- 通常分布、外部要因作用後分布、step、活性要因数、vector origin別集計
- 保存済み基底・活性度からの独立再計算
- 型・形状・hashを含む成果物一覧

## 3. smoke条件

smokeは正式な科学的選択ではなく、同じ計算経路が実装どおり動くかを確認する。

- 構造数：固定gridの最初の値`5`
- 初期値：決定論的基準run 1本＋固定ランダムseed 6本
- 主手法：正式契約と同じKL-NMF
- 許容値：正式契約と同じ`1e-5`
- 反復上限：smoke専用`50`
- 正式契約の反復上限：`2,000`のまま変更なし
- holdout：モデル選択処理から完全に除外
- selection lock：作成しない

smokeの未収束は正式な収束判定に使用しない。収束状態は各runへ実測値として保存する。

## 4. holdout境界

入力固定処理はholdout bundleを作るが、最小抽出実行のCLIは次の4入力しか受け取らない。

- fit bundle
- fit row map
- validation bundle
- validation row map

holdout pathを渡す引数自体を設けない。smoke成果物にholdout由来の指標、活性度、選択情報が存在した場合、独立検証を失敗させる。

## 5. 独立検証

生成器と別の検証モジュールが、保存済み成果物から次を再計算する。

- model file hash
- 基底形状・非負性・行総和
- 活性度形状・非負性
- fit／validation再構成
- 重み付き／重みなし指標
- 全構造対応表
- contract snapshot
- holdout未使用

品質検査はboolean単独ではなく、測定値、閾値、件数、証拠pathを保存する。

## 6. Task 3.1f-3への引き継ぎ

次工程では本実装を拡張して、固定rank grid全体と正式2,000反復を一括実行する。

追加対象：

- 全rank×全初期値の正式runner
- rank単位安定性集計
- 重複・未使用構造判定
- one-standard-error rule
- 代表run選択
- grouped 80%摂動
- world seed感度

Task 3.1f-2のsmoke結果を科学的な構造数選択へ流用してはならない。
