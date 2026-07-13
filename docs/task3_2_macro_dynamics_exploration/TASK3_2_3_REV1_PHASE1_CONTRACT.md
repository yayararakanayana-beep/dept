# Task 3.2-3 Rev1 Phase 1 固定契約
## 局所・履歴予測の情報境界、未知条件、評価、再現性

## 1. タスク識別

- 区分: 既存Task 3.2-3のRev1
- 現段階: Phase 1 契約固定
- repository: `yayararakanayana-beep/dept`
- base branch: `main`
- working branch: `agent/task3-2-3-rev1-phase1-contract`
- 既存PR: なし。Phase 1用の新規PRを作る。

旧Task 3.2-3のselection lockとholdout結果は、旧基準の証拠として変更しない。Rev1は別契約、別コーパス、別selection identityを使用する。

## 2. 正確な目的

Task 3 Rev1の固定質問は次とする。

> 未知の外乱予定と変動する背景条件の下で、同じ現在利用可能情報だけを持つ基準に対して、局所履歴が未来の局所リスクに関する不確実性をどの程度減らすか。

Task 3の固定役割は`局所・履歴早期警戒`である。

将来の実装が出力してよい情報は次に限定する。

1. 局所リスク接近確率
2. 局所リスク開始までの時間
3. 局所リスク深度
4. 悪化・回復・中立の方向
5. 持続・回復困難性候補
6. 予測不確実性

Phase 1の実装対象は次だけである。

- 固定config
- 独立validator
- 正常系・異常系test
- 契約専用CI
- 本文書
- `AGENTS.md`境界追記

Phase 1では次を実施しない。

- 新コーパス生成
- 特徴量実装
- 予測モデル実装・学習・選択
- validationまたはholdout状態の読込
- Task 4のマクロ特徴導入
- Task 4.1正解によるfit・調整・選択
- 正式G_t、関係場、ゲーム構造、不可逆性、作用選択への接続

## 3. 正本

設定値と動作の正本を次に固定する。

| 対象 | 正本 |
|---|---|
| 情報段階、予測対象、コーパス条件、評価閾値、selection identity | `configs/task3_2_3_rev1_contract.json` |
| 契約・manifest・selection identity検証動作 | `scripts/task3_2_3_rev1_contract.py` |
| 研究境界と実装手順 | 本文書 |
| 旧比較基準 | `configs/task3_2_3_simple_early_warning.json` |

正式値をPythonへ重複記述しない。Pythonに固定してよいのは、未来情報禁止、Task 4/4.1混入禁止、Phase 1の非実装境界など、設定変更できない安全条件だけである。

## 4. 順序付き実施手順

### Phase 1で実施する順序

1. Phase 0監査結果からTask 3の役割を`局所・履歴早期警戒`へ固定する。
2. 情報段階I0〜I4と比較対をconfigへ一度だけ定義する。
3. 予測対象とTask 4.1正解の利用境界を定義する。
4. 未知schedule・背景変動・hard positive/negative・回復結果をコーパス必須条件として定義する。
5. horizon別評価、警報種別、履歴成功条件を定義する。
6. metricsと実行IDを含まないstable selection identityを定義する。
7. validatorを実装する。
8. 正常系と、各近道を拒否する異常系testを実装する。
9. validatorとtestだけを動かす契約専用CIを追加する。
10. Phase 1完了後も、新コーパス生成やモデル実装へ自動的に進まない。

### Phase 2以降へ渡す順序

1. Phase 1契約を変更せずにpilotコーパス設計を作る。
2. pilot manifestを独立validatorで検証する。
3. モデルを見る前に、結果分布、event prevalence、軌道間分散からformal軌道数を固定する。
4. formal splitとselection identity契約を固定する。
5. その後にだけTask 3 Rev1のモデル比較へ進む。

## 5. 重要要件契約

### 5.1 Task 3の役割分離

- **要件:** Task 3は局所・履歴早期警戒だけを担当する。
- **必須実装:** configの`fixed_role`を固定し、Task 4、Task 4.1、G_t、関係場、ゲーム構造、不可逆性、作用選択を禁止役割へ入れる。
- **禁止する近道:** Task 4の出力を履歴特徴と呼び替える、Task 4.1の反実仮想結果を教師または選択指標へ入れる、ゲーム構造ラベルを局所リスクラベルとして扱う。
- **検証:** validatorが禁止役割の欠落を拒否し、異常系testがTask 4.1正解のmodel selection指定を失敗させる。

### 5.2 情報量別比較

- **要件:** 履歴以外の情報量を揃えた比較によって履歴の寄与を測る。
- **必須実装:** 次の固定名称を使用する。

| ID | 固定名称 | 情報 |
|---|---|---|
| I0 | 内部現在 | 内部現在情報 |
| I1 | 内部現在＋内部履歴 | I0＋内部履歴 |
| I2 | 内部現在＋現在観測外力 | I0＋現在外力 |
| I3 | 内部現在＋内部履歴＋現在観測外力 | I2＋内部履歴 |
| I4 | 内部現在＋内部履歴＋観測外力履歴 | I3＋過去外力履歴 |

比較対は`I1-I0`、`I3-I2`、`I4-I3`で固定する。

- **禁止する近道:** 履歴モデルだけへ現在外力を追加する、異なる時点集合で比較する、scenarioや絶対stepを時刻情報として使う。
- **検証:** validatorが比較対の実際の差分と宣言差分の完全一致を確認し、余分な情報群を混ぜたtestを失敗させる。

### 5.3 未来情報とschedule指紋の遮断

- **要件:** 入力は時点`t`までに観測済みの情報だけとする。
- **必須実装:** scenario、trajectory、seed、split、絶対step、generator event名、未来外力、未来状態、正解、最終結果を禁止入力へ含める。
- **禁止する近道:** `step`から既知の外乱開始時刻を推定する、`regime:started`のようなgenerator名を数値化する、同一seed通常軌道の特徴を入力へ結合する。
- **検証:** validatorが必須禁止項目の欠落を拒否し、未来外力を許可した異常系testを失敗させる。

### 5.4 未知条件コーパス

- **要件:** seedだけでなく、schedule、背景状態、world parameter profileを未知にする。
- **必須実装:** `schedule_template_id`、`background_regime_id`、`world_parameter_profile_id`の各値をfit/validation/holdout間で非重複にする。開始、期間、強度、組合せ、形状、残留負荷、再悪化を変える。
- **禁止する近道:** 同じscheduleをseedだけ変えてholdoutへ置く、複合IDだけ変えて内部scheduleを再利用する、軌道窓を独立標本として数える。
- **検証:** manifest validatorが各OOD軸を独立に追跡し、同じ値が複数splitへ現れた時点で拒否する。再利用scheduleの異常系testを置く。

### 5.5 危険・回復の多様性

- **要件:** 現在値だけでは区別しにくい危険、安全、回復、再悪化を含める。
- **必須実装:** configに定義した8結果群、5 hard negative群、5 hard positive群、4背景変動をpilot設計の必須条件とする。
- **禁止する近道:** scenario名を結果へコピーする、名前だけ回復で実測は全て持続悪化の軌道を回復例として数える、不足結果を固定ラベルで補う。
- **検証:** pilot manifest validatorが各splitの結果群実数を数え、不足時に拒否する。回復結果を削った異常系testを置く。実測結果の妥当性検査はPhase 2で別途必要とし、producerの自己申告だけではformal corpusを承認しない。

### 5.6 評価と成功判定

- **要件:** 異なるhorizonと異なる標本集合を一つの加重点数で混ぜない。
- **必須実装:** H=4、8、16を別々に評価し、同一horizon・同一eligible window上で情報段階を比較する。Pareto比較後、事前登録した優先順で選ぶ。
- **禁止する近道:** `lead/horizon`を上限1へ切ってhorizon間で比較する、eventual-positive軌道の早すぎる警報を成功だけとして数える、safe false alarmとpremature alarmを合算して原因を隠す。
- **検証:** validatorがcross-horizon加重点数を拒否する。将来のevaluatorはsafe false alarm、premature alarm、alarm burden、missを別出力にしなければならない。

### 5.7 履歴の有望性判定

- **要件:** 二次的な校正改善だけで核心的早期警戒改善を主張しない。
- **必須実装:** A判定には、検出率、絶対先行時間、time-to-event誤差、方向精度の少なくとも1つがconfig閾値を超え、paired uncertainty、誤警報、Brier、未知schedule層のguardrailを通ることを要求する。
- **禁止する近道:** 絶対目標到達を現在基準に対する改善として数える、MAEまたはBrierだけの改善をAとする、全schedule平均で一部層の悪化を隠す。
- **検証:** Phase 1では閾値範囲とgrade文をvalidatorが検査する。数値判定関数と境界testはモデル実装と同じPhaseで追加し、追加されるまでA判定を出してはならない。

### 5.8 selection identityの再現性

- **要件:** 同一の事前仕様と入力から同じselection identityが得られる。
- **必須実装:** identityへ入れるのはconfigに列挙した仕様・content hashだけとする。metrics、timestamp、workflow/artifact ID、絶対pathは別Artifactへ分離する。canonical JSONのSHA-256を使う。
- **禁止する近道:** 生の浮動小数点metricsをidentityへ含める、時刻やrun IDをhashへ入れる、禁止fieldを黙って削除してhashを作る。
- **検証:** builderは不足、禁止、未宣言fieldをすべて拒否する。mapping順序だけ変えた同一payloadが同じhashになる正常系testと、metrics/run IDを入れた異常系testを置く。

### 5.9 holdout隔離

- **要件:** Rev1 holdoutは独立検証済みselection identityの後にだけ開く。
- **必須実装:** Phase 1ではvalidation/holdout状態を一切読まない。後続Phaseで2回の同一pre-holdout再実行identity一致と独立検証をgateにする。
- **禁止する近道:** holdout metadataから結果分布を確認する、holdoutを使ってformal軌道数や閾値を決める、runごとに変わるlockを文書だけ同一とする。
- **検証:** Phase 1 workflowにデータ生成・読込stageを置かない。後続実装ではlock前読込を実際に例外化する負のtestを必須とする。

## 6. スモーク実行契約

Phase 1のformal logical pathは次の4段階だけである。

1. configを読み込む。
2. validatorが全契約節を検査する。
3. selection identityの正常系・異常系testを実行する。
4. pilot manifestの正常系・異常系testを実行する。

Phase 1 smokeも同じ4段階を実行する。省略できるformal branchはない。軌道数だけを減らす必要もなく、test fixtureがconfigのpilot最低数を満たす。

workflowへコーパス生成、model fit、validation、holdout、自己生成した`passed: true`の確認を追加してはならない。

## 7. テスト

### 正常系

- 固定config全体がvalidatorを通る。
- I0〜I4と3比較対が期待数で保存される。
- configのpilot最低数を満たすmanifestが通る。
- JSON object順序だけ異なる同一contractが同じhashになる。
- field順序だけ異なる同一selection payloadが同じhashになる。

### 異常系

- 未来外力禁止を削除すると失敗する。
- Task 4.1正解をmodel selectionへ変更すると失敗する。
- 履歴比較へ宣言外の情報を追加すると失敗する。
- horizon横断加重点数を許可すると失敗する。
- selection identityへvalidation metricsを入れると失敗する。
- selection identityへworkflow run IDを入れると失敗する。
- 未宣言default fieldを追加すると失敗する。
- schedule templateをfitとvalidationで再利用すると失敗する。
- holdoutから回復結果群を削除すると失敗する。
- Phase 1 validatorへformal manifest自己認証を要求すると失敗する。

## 8. 停止条件

次のいずれかが発生した場合、条件を弱めず停止して報告する。

- 正本ファイルがない。
- 既存Task 3.2凍結境界と矛盾する。
- schedule、背景、world profileのいずれかがsplit間で重複する。
- 必須の回復または危険結果を実測生成できない。
- fitまたはvalidationで正解が単一値になる。
- 禁止入力がなければ性能を出せない。
- pilot監査前にformal軌道数を決める必要が生じる。
- 同一pre-holdout再実行でselection identityが一致しない。
- selection identity検証前にholdoutを開く必要が生じる。

PseudoRealityが必要な結果を自然に生成しない場合は、world不足または条件不足と記録する。結果を作るためにworld dynamicsを変更してはならない。

## 9. 受入条件

Phase 1は次の全条件を満たした場合だけ完了する。

1. configがvalidatorを通る。
2. validatorがcontract hashを計算して返す。
3. すべての正常系testが値と動作を確認する。
4. すべての異常系testが期待した境界違反を拒否する。
5. selection identityがmetricsとruntime IDを拒否する。
6. manifest validatorが3つのOOD軸を個別に検査する。
7. manifest validatorが結果群の実数を数える。
8. workflowがcontract logical pathだけを実行する。
9. 新コーパス、モデル、validation、holdoutの実行がdiffに含まれない。
10. 旧Task 3 selection lockと結果を変更しない。

ファイル存在、command終了コード、producer自身が書いた`valid: true`だけでは受け入れない。

## 10. 完了報告要件

Phase 1完了時は次を報告する。

- 変更ファイル
- 実行command
- 正常系test
- 異常系test
- 未実装・未解決項目
- 新コーパス、モデル、validation、holdoutを実行していないこと
- placeholder、固定pass、自己認証経路が残っていないこと

## 11. 必須近道監査

| 重要出力 | 最も安い偽実装 | 防止方法 | 異常系test | 偽実装は通るか |
|---|---|---|---|---|
| 情報段階比較 | 履歴側だけへ外力を追加 | group差分完全一致 | 宣言外group追加 | 通らない |
| 未知条件 | seedだけ変えて同scheduleを再利用 | OOD軸別split追跡 | schedule再利用 | 通らない |
| 結果多様性 | scenario名を結果として記録 | manifest実数検査＋Phase 2実測監査停止条件 | 回復結果削除 | Phase 1 schemaだけなら偽labelは残り得るため、formal承認はPhase 2独立実測監査まで禁止 |
| horizon評価 | 加重点数でH4を優遇 | horizon別評価固定 | scalar許可 | 通らない |
| selection identity | metrics・run ID込みhash | required/forbidden/extra完全検査 | metrics/run ID追加 | 通らない |
| holdout隔離 | `passed: true`を書くだけ | Phase 1では読込stage自体を禁止 | formal自己認証要求 | 通らない |

結果多様性については、Phase 1だけではmanifest producerが偽の`outcome_family`を書く可能性を完全には排除できない。そのためPhase 1はpilot manifestの構造検査までとし、Phase 2でraw trajectoryから結果を独立再計算するvalidatorができるまでformal corpusを承認しない。

この停止条件により、最小の偽実装がPhase 1からformal model selectionへ進むことはできない。
