# Deployment Checklist

This is the shortest production-oriented path from the ZIP to a working Databricks + OpenBB Workspace quant platform.

## Phase 1 — Run the platform setup notebook

1. Import `Databricks_OpenBB_Quant_Platform_Final.ipynb` into Databricks.
2. Attach Unity-Catalog-enabled Python compute (or serverless notebook compute that supports the installed dependencies).
3. Choose an **existing catalog** you can use. The default schema is `openbb_quant`.
4. For the first smoke test, leave the ODP provider as `yfinance` unless you already configured provider secrets.
5. Run the notebook from top to bottom.
6. Verify the final table-count cell shows data for prices, latest features, strategy runs, portfolio comparison runs, and Monte Carlo runs.

The notebook deliberately does not create billable Serving infrastructure unless you explicitly enable the relevant provisioning widgets.

## Phase 2 — Create the three Lakeflow Jobs

Import each file below into Databricks as a **source notebook** (do not configure it as a Python-script task):

- `jobs/backtest_worker.py`
- `jobs/monte_carlo_worker.py`
- `jobs/comparison_worker.py`

Create one Lakeflow Job with one Notebook task for each worker. Job parameters are intentionally read through `dbutils.widgets`.

Attach the wheel `dist/openbb_databricks_quant_platform-0.1.0-py3-none-any.whl` as a task library/dependency, or make the repository `src/` package available on the task Python path.

Recommended job resource keys later in the App:

- backtest Job → `backtest_job`
- Monte Carlo Job → `monte_carlo_job`
- comparison Job → `comparison_job`

The workers write result data to Unity Catalog, so their run identity must have the required `USE CATALOG`, `USE SCHEMA`, `SELECT`, and `MODIFY` privileges.

## Phase 3 — Make Databricks Serving first-class

### Model Serving

1. Train/register your real model in Unity Catalog/MLflow.
2. Use `serving/model_serving_setup.py` or the guarded setup-notebook cell to create an endpoint.
3. Appropriate use cases include expected-return forecasts, volatility models, regime classifiers, credit/risk models, NLP/sentiment, and other inference workloads.
4. Persist research predictions that need historical comparison/backtesting into `model_predictions` with the original prediction timestamp.

### Feature Serving

1. The setup notebook creates `equity_features_latest` with a primary key and Change Data Feed.
2. Use `serving/feature_serving_setup.py::prepare_online_feature_store()` to create/reuse an Online Feature Store and publish the feature table.
3. Use `create_feature_serving()` to create a FeatureSpec and Feature Serving endpoint.
4. Keep historical point-in-time features in `factor_snapshots`; Feature Serving is for low-latency current feature access, not a replacement for historical research tables.

Serving resources are billable and workspace-specific, so they are opt-in by design.

## Phase 4 — Deploy the minimal Databricks App

Deploy the `databricks_app/` directory as a Databricks App. It is only an API gateway/orchestrator; there is no second dashboard.

Before deployment:

1. Edit `databricks_app/app.yaml` and set `FINANCE_CATALOG` to your catalog.
2. Add a SQL Warehouse App resource with key `sql_warehouse` and **CAN USE**.
3. Add the three Lakeflow Jobs with keys `backtest_job`, `monte_carlo_job`, `comparison_job` and **CAN MANAGE RUN**.
4. Grant the App service principal `USE CATALOG`, `USE SCHEMA`, and `SELECT` for the quant tables it reads.
5. Add ODP provider API keys as Databricks Secret App resources and map them to the supported environment variables when required.
6. Configure Databricks App network egress to the external provider domains you use.

Startup runs `openbb-build`, loads the permanent ODP FastAPI app, adds `/api/quant/*`, and launches the combined API through `openbb-platform-api`.

## Phase 5 — Connect OpenBB Workspace

Use this backend URL:

```text
https://<your-databricks-app-url>/api
```

For initial testing add:

```text
Authorization: Bearer <current Databricks OAuth access token>
```

The backend exposes:

- native ODP endpoints under `/api/v1/...`
- generated Workspace discovery at `/api/widgets.json`
- custom quant routes under `/api/quant/...`

A manually pasted OAuth access token is suitable for testing, not unattended permanent production connectivity. For production use an approved OAuth/M2M-aware gateway/service or an appropriate private/enterprise deployment authentication design.

## Phase 6 — Run NVIDIA Portfolio Optimization on your GPU computer

Run the NVIDIA `portfolio-optimization` blueprint separately. Then use:

```text
nvidia_bridge/nvidia_push_adapter.py
```

to push efficient-frontier points, optimal allocations, and matrices into the Databricks optimization tables using Databricks unified authentication.

OpenBB Workspace then displays those external results from the same `/api/quant/optimization/*` backend routes as Databricks-produced research.

## Phase 7 — Expand the research universe

After the smoke test:

- replace/free-tier market data with your licensed ODP providers;
- ingest fundamentals, estimates, macro, fixed income, FX, options, news/transcripts as required;
- populate `factor_snapshots` with true point-in-time `available_at` timestamps;
- add custom weight-generating strategies or factor/model ranking configurations;
- register real models and Serving endpoints;
- add saved portfolio workflows and additional Monte Carlo assumptions (cash flows, inflation, taxes, regime models) if required.
