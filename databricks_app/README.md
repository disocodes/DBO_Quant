# DBO_Quant API App

This folder is the **thin API backend** for OpenBB Workspace. It is not a dashboard and is not where you run research notebooks.

For the guided deployment workflow, use **`notebooks/06_DEPLOY_APP.py`**.

## First deployment

You need only:

1. DBO_Quant tables created by `notebooks/00_SETUP.py`.
2. A Databricks SQL Warehouse.
3. A Databricks App using this folder as its source.
4. A SQL Warehouse App resource with key `sql_warehouse` and **Can use** permission.
5. `FINANCE_CATALOG` in `app.yaml` changed from `REPLACE_WITH_YOUR_CATALOG` to the catalog used during setup.
6. App service-principal permissions: `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the DBO_Quant tables.

The App can then serve existing market data and saved research results without any Lakeflow Jobs.

## Optional production Jobs

Later, if you want OpenBB Workspace forms to launch new calculations, create Jobs from `jobs/backtest_worker.py`, `jobs/monte_carlo_worker.py`, and `jobs/comparison_worker.py`, then populate the corresponding App environment variables.

## Endpoints

- `/api/widgets.json` — OpenBB Workspace widget discovery
- `/api/v1/...` — native OpenBB ODP endpoints
- `/api/quant/...` — DBO_Quant backtest, comparison, Monte Carlo, optimization, feature and model-result endpoints

Connect OpenBB Workspace to:

```text
https://<your-app-url>/api
```

For initial authenticated testing, add:

```text
Authorization: Bearer <Databricks OAuth token>
```

Continue with `notebooks/07_OPENBB_WORKSPACE.py` after the App is running.