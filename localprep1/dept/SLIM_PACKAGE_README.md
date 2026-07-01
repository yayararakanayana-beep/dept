# Task22C Rev1 LocalPrep-1 Slim GitHub Upload

これはCodex/GitHub投入用に軽量化したパッケージです。

元のfull packageから以下を除外しています。

```text
results/
validation_runs/
manifests/
過去検証CSV
ActionModule内部docs
__pycache__
*.pyc
```

実行に必要なコード、configs、scripts、requirements.txt は残しています。

## GitHub/Codexでの配置

このzipをアップロードしたあと、Codexに以下を依頼してください。

```text
diffを読まずにzipを解凍し、zip内の dept/ を localprep1/dept/ に配置して、
cd localprep1/dept で以下を実行してください。

python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_q9_full_integration_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_basic.json
```
