# Task 3.1f-1 検証契約

## 0. 原則

Task 3.1fの検証は、実装者が自分で書いた合格値を出力する自己証明ではなく、保存済み入力・基底・活性度から独立検証器が結果を再計算する方式とする。

必須原則：

- 生成と検証を別モジュールにする。
- fit/validation選択工程とholdout工程を分離する。
- holdoutを選択前に読めない実行構造にする。
- 指標値を保存済み行列から独立再計算する。
- 正常系だけでなく破壊系を必須とする。
- 固定`true`、固定0、空配列、既定値による合格を禁止する。
- 収束失敗や不適格rankを隠さない。

---

## 1. 実行段階

## 1.1 Stage A：入力固定

Task 3.1e正式成果物を読み、以下を検証する。

- artifact SHA-256
- 必須ファイルの存在
- `mass_matrix.npy` の形状・型・有限性・非負性・行総和
- metadata／discovery／massの行対応
- fit 1,082行
- validation 256行
- holdout 244行
- split値が `fit`, `validation`, `holdout` のみ
- `analysis_weight` が有限・正値
- split内平均weightが1
- snapshot IDの一意性
- matrix row indexの一意性と連続性
- matched pairの完全対応

Stage Aは次を作る。

- `input_manifest.json`
- `fit_bundle.npz`
- `validation_bundle.npz`
- `holdout_bundle.npz`
- 各bundleのrow map CSV

bundleにはモデル入力に必要な質量、重み、row index、snapshot IDのみを含める。評価用metadataは別ファイルへ保持する。

fit/validation bundle作成後の選択工程では、holdout bundleのパスを引数に渡してはならない。

## 1.2 Stage B：fit/validation sweep

入力：

- fit bundle
- validation bundle
- frozen contract

holdout bundleを入力に含めない。

実行内容：

- 固定rank grid
- 固定初期値
- 主KL-NMF
- weighted PCA reference
- mean-distribution baseline
- run単位の再構成指標
- run間構造対応付け
- rank単位の安定性・重複・未使用監査
- admissible判定
- one-standard-error rule
- provisional rank選択
- representative run選択
- grouped 80%摂動
- world seed感度

Stage Bの最後に `selection_candidate.json` を作る。Stage B自身は `selection_lock.json` を作らない。

Stage Bでholdout由来の行数、指標、構造、活性度、画像、統計量を出力した場合、検証失敗とする。

## 1.3 Stage C：selection candidate独立検証・lock作成

独立検証器が以下を再計算する。

- contract hash
- input hash
- rank grid実行漏れ
- 各rankのrun数
- 収束run数
- 構造基底正規化
- validation再構成指標
- run間Hungarian対応
- stability score
- redundancy rate
- inactive rate
- admissible判定
- one-standard-error rule
- selected rank
- representative run medoid
- candidate内各ファイルhash

再計算結果と `selection_candidate.json` が一致し、独立検証が合格した場合だけ、独立検証器が `selection_lock.json` を作る。一致しない場合はholdoutへ進まない。

## 1.4 Stage D：holdout一度限り評価

Stage C合格後にだけ実行する。

入力：

- 有効なselection lock
- lockされた代表基底
- holdout bundle
- frozen contract

許可される処理：

- holdout活性度推定
- lock済みNMFの再構成
- rank-matched PCA参照
- mean-distribution baseline
- holdout層別指標
- external/base変形保持指標
- confirmed／conditional／failed判定

禁止：

- 新しい基底学習
- rank変更
- 初期値変更
- 正則化変更
- 前処理変更
- fit／validationの再実行
- holdoutを用いた閾値調整

## 1.5 Stage E：最終独立検証

保存済み成果物だけを読み、次を再計算する。

- holdout再構成
- holdout指標
- baseline改善率
- validation比率
- final outcome
- 構造・活性度・row mapの対応
- artifact manifestのhash

すべて一致した場合のみ正式成果物をPASSとする。

---

## 2. 正常系検証

最低限、次を自動テストする。

### 2.1 入力

- 正式Task 3.1e成果物を読み込める。
- fit／validation／holdout行数が契約値と一致する。
- 行を並べ替えてもrow mapで正しく対応できる。
- 全行が確率分布として有効。
- analysis weightが正しく適用される。

### 2.2 非負行列分解

- 固定seedで再実行すると同じ初期条件を使う。
- 基底と活性度が非負・有限。
- 基底行総和が1。
- 基底正規化前後で再構成が変わらない。
- validation変換時に基底が更新されない。
- holdout変換時に基底が更新されない。

### 2.3 重み

KL主手法について、行倍率方式が明示的な重み付きKLと小規模例で一致することを確認する。

Frobenius感度参照について、`sqrt(weight)` 行倍率が重み付き二乗誤差と一致することを確認する。

### 2.4 構造対応

- 構造順を入れ替えた同一基底同士を完全対応できる。
- 既知の近似構造で期待するHungarian対応になる。
- 構造番号そのものを比較していない。
- normalized JS similarityが0から1の範囲。

### 2.5 rank判定

- 収束率5/6以上を正しく判定。
- stability、redundancy、inactiveの各gateを正しく適用。
- admissible rankだけをone-standard-error ruleへ渡す。
- 最小rank優先が働く。
- admissible rankがない場合はholdout lockを作らない。

### 2.6 holdout lock

- lock前にholdout評価が実行できない。
- lockのhashを変更するとholdout評価が拒否される。
- lockされたrank以外のモデルが拒否される。
- holdout評価後もselection lockが変化しない。

### 2.7 結果

- 保存済みW・Hから独立に全再構成指標を再計算できる。
- weighted／unweighted集計が区別される。
- base／external、step、active factor count別の集計が存在する。
- matched pair変形指標を再計算できる。
- artifact manifestに全成果物のSHA-256、size、shape、dtype、row countが入る。

---

## 3. 破壊系検証

最低限、以下を個別に破壊し、独立検証器が失敗することを確認する。

## 3.1 入力破壊

1. mass行を1行削除する。
2. metadata行を1行削除する。
3. matrix row indexを重複させる。
4. snapshot IDを入れ替える。
5. splitをfitからholdoutへ書き換える。
6. NaNを1セルへ挿入する。
7. Infを1セルへ挿入する。
8. 負質量を挿入する。
9. 行総和を0.9へ変更する。
10. analysis weightを0、負値、NaNのいずれかへ変更する。

## 3.2 漏洩破壊

11. Stage B出力へholdout行数を追加する。
12. fit bundleへholdout行を混入する。
13. validation bundleへholdout行を混入する。
14. selection lock作成前にholdout metricを作成する。
15. holdout metricをrank選択表へ追加する。
16. holdout結果を見てselected rankを変更する。

## 3.3 モデル破壊

17. 基底を全0にする。
18. 活性度を全0にする。
19. 基底へ負値を入れる。
20. 基底行総和を1以外へ変更する。
21. WとHのrankを不一致にする。
22. 同じ構造を複製し、重複率を上げる。
23. 1構造を全runで別構造へ置換する。
24. runを1本しか実行していないのに安定性合格値を書く。
25. 収束していないrunを収束済みと書く。

## 3.4 指標破壊

26. reconstruction metricを全0にする。
27. stability scoreを固定1にする。
28. redundancy rateを固定0にする。
29. inactive rateを固定0にする。
30. PCAの負値を隠して分布距離だけを記録する。
31. NMFの生行総和誤差を削除する。
32. weightedとunweightedの値を同一列へ上書きする。
33. matched pairを別seedまたは別stepへつなぐ。

## 3.5 lock・manifest破壊

34. selection lock内のrankを書き換える。
35. basis SHA-256を書き換える。
36. contract SHA-256を書き換える。
37. artifact manifestのfile hashを固定値へ変える。
38. 出力ファイルを1つ削除する。
39. output schema列を1つ削除する。
40. final outcomeを固定`confirmed`へ変える。

破壊テストは、単に例外が出るだけでなく、どの契約違反として拒否されたかを記録する。

---

## 4. 停止条件

以下の場合、既定値で続行せず停止する。

- Task 3.1e artifact digestが契約と異なる。
- 必須入力が欠けている。
- 分割行数が異なる。
- 行対応を一意に解決できない。
- 確率分布条件を満たさない。
- frozen rank gridを全て実行できない。
- ランダムseed runが不足する。
- ライブラリが指定solver／lossを実装できない。
- validation前に基底を固定できない。
- holdoutを選択前に読んだ可能性がある。
- selection lockを独立再現できない。
- admissible rankが0。
- selected model fileのhashが不一致。
- 独立指標再計算が保存値と一致しない。
- 結果を合格にするため契約変更が必要になる。

停止時は、成功したように見える空成果物を作らない。

---

## 5. 数値一致許容値

同じ保存済み行列からの独立再計算について：

- shape、count、ID、rank、seed：完全一致
- SHA-256：完全一致
- 基底行総和：絶対誤差 `<= 1e-10`
- 再構成行列再計算：`rtol <= 1e-10`, `atol <= 1e-12`
- 保存指標再計算：`rtol <= 1e-9`, `atol <= 1e-12`
- Hungarian対応費用：`rtol <= 1e-9`, `atol <= 1e-12`

別ハードウェア・別BLASによるモデル再学習結果のbit一致は要求しない。その代わり、保存済みモデルからの再計算一致と、固定seed、library version、environment manifestを要求する。

---

## 6. GitHub Actions正式構造

正式検証は少なくとも次のjobへ分離する。

### job 1：input-freeze

- Task 3.1e artifact取得
- input validation
- fit／validation／holdout bundle作成
- bundle artifact upload

### job 2：fit-validate

- fit／validation bundleだけをdownload
- rank sweep
- independent selection audit
- selection lock作成
- selection artifact upload

holdout bundleをdownloadしてはならない。

### job 3：holdout-evaluate

- validated selection artifactをdownload
- holdout bundleをdownload
- 一度限り評価
- final independent validation
- formal artifact upload

### job 4：mutation-tests

- 縮小fixtureを使用
- 必須破壊系を実行
- 1つでも期待どおり失敗しなければworkflow失敗

正式runのjob ID、commit SHA、input artifact digest、contract digestを最終run manifestへ記録する。

---

## 7. 完了判定

Task 3.1f-1自体の完了条件は次のとおり。

- scope freezeが存在する。
- 比較設計が数値まで固定されている。
- validation／holdout分離が固定されている。
- output schemaが固定されている。
- machine-readable contractが存在する。
- 変更には明示的確認が必要と記録されている。
- 実装者が設計判断を追加で行う余地が残っていない。

Task 3.1f-1ではコード実装や正式NMF実行を完了条件に含めない。それらはTask 3.1f-2以降で行う。
