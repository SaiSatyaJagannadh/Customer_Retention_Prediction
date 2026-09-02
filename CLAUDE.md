# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Full training pipeline (load → validate → preprocess → features → XGBoost → MLflow)
python scripts/run_pipeline.py --input data/raw/Telco-Customer-Churn.csv --target Churn
# useful flags: --threshold 0.35  --test_size 0.2  --experiment "Telco Churn"  --mlflow_uri <uri>

# Write data/processed/telco_churn_processed.csv only (no training)
python scripts/prepare_processed_data.py

# Manual checks (plain scripts, not pytest — run one at a time)
python scripts/test_pipeline_phase1_data_features.py   # load → preprocess → features
python scripts/test_pipeline_phase2_modeling.py        # Optuna tuning + XGBoost on processed CSV
python scripts/test_fastapi.py                         # POSTs a sample to a running server

# Serve locally (API at /, /predict; Gradio UI at /ui)
python -m uvicorn src.app.main:app --host 0.0.0.0 --port 8000

# Docker (note: lowercase `dockerfile`)
docker build -t telco-churn-app . && docker run -p 8000:8000 telco-churn-app

mlflow ui --backend-store-uri file:./mlruns
```

`data/`, `mlruns/`, and `artifacts/` are gitignored — a fresh clone has no dataset and no
tracking store. Only `src/serving/model/` (two bundled MLflow runs) is committed.

## Architecture

Two pipelines that must stay in lockstep on feature encoding:

**Training** — `scripts/run_pipeline.py` orchestrates everything inside one `mlflow.start_run()`:
`load_data` → `validate_telco_data` (Great Expectations, logged as `data_quality_pass`, raises on
failure) → `preprocess_data` (drops customerID, coerces TotalCharges, fills numeric NaN with 0) →
`build_features` → stratified split → XGBoost → metrics (precision/recall/f1/roc_auc/train_time/
pred_time) → `mlflow.sklearn.log_model`. Hyperparameters are hardcoded at `scripts/run_pipeline.py:145`
(`n_estimators=301`, `learning_rate=0.034`, `max_depth=7`); `scale_pos_weight` is computed from the
train split. Classification uses `--threshold` (0.35) on `predict_proba`, **not** `model.predict`.

**Serving** — `src/app/main.py` (FastAPI + Gradio) → `src/serving/inference.py`. `inference.py` loads
the model at *import time* from `MODEL_DIR = "/app/model"`, falling back to a glob over
`./mlruns/*/*/artifacts/model`. Importing anything from `src.app` therefore fails outside the
container unless `./mlruns` exists — train once first, or point `MODEL_DIR` at
`src/serving/model/<run_id>/artifacts/`.

`src/models/{train,evaluate,tune}.py` are standalone helpers, **not** wired into `run_pipeline.py`.
`src/app/app.py` is an older duplicate of `main.py` (same endpoints, `sys.path` hack instead of the
`src.` prefix); `main.py` is the one the Dockerfile serves — change both or delete `app.py`.

### Train/serve feature parity (the fragile part)

`build_features` derives encodings from the data: any 2-value object column → 0/1 (`Yes`→1,
`Male`→1, else alphabetical), everything else → `pd.get_dummies(..., drop_first=True)`.
`_serve_transform` in `inference.py` reimplements this with a hardcoded `BINARY_MAP` and the same
`get_dummies` call, then `reindex(columns=FEATURE_COLS, fill_value=0)` against
`feature_columns.txt`. Consequences:

- Any change to one encoder must be mirrored in the other, or predictions silently degrade.
- Missing/unknown categories become 0 rather than an error — a schema mistake looks like a valid
  prediction. The bundled model's 29 columns include `SeniorCitizen`, which the 18-field
  `CustomerData` schema doesn't collect, so it is always served as 0.
- `feature_columns.txt` is the contract; it ships next to the model, not in the code.

### Model artifacts and Docker

`dockerfile` hardcodes MLflow run `3b1a41221fc44548aed629fa42b762e0` and copies its
`artifacts/model`, `feature_columns.txt`, and `preprocessing.pkl` into the flat `/app/model` path
`inference.py` expects. Retraining does **not** update the served model: copy the new run into
`src/serving/model/` and bump the run ID in the Dockerfile. The other bundled run
(`2ac205f9…`) has no `preprocessing.pkl` and would not build cleanly.

`PYTHONPATH=/app/src` in the image is what makes `serving.*` importable; `src.app.main:app` works
because `WORKDIR` is `/app`.

### CI/CD

`.github/workflows/ci.yml` builds on push to `main` and pushes `anasriad8/telco-fastapi:latest`
(needs `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`). It does **not** deploy; the ECS Fargate service
behind the ALB is updated manually (force new deployment). ALB health check hits `GET /` on 8000.

## Known rough edges

- `scripts/run_pipeline.py:13` has a stray `from posthog import project_root`; `project_root` is
  reassigned locally a few lines later. `posthog` is pinned in requirements only to satisfy it.
- `requirements.txt` pins `great_expectations==1.5.8`, but `src/utils/validate_data.py` uses the
  legacy `ge.dataset.PandasDataset` API. Verify validation actually runs before trusting it.
- `scripts/test_pipeline_phase1_data_features.py` has an absolute `DATA_PATH` from another machine.
- `/predict` catches every exception and returns `{"error": ...}` with HTTP 200.
