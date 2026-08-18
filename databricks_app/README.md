# DBO_Quant API App

This folder is the thin API backend for OpenBB Workspace. It is not a research notebook environment and does not provide a second dashboard.

## Purpose

The App reads persisted DBO_Quant results from Unity Catalog through a Databricks SQL Warehouse and exposes them as OpenBB-compatible API routes and dynamically generated widgets.

## Deployment options

Guided/manual preparation:

```text
notebooks/platform/02_DEPLOY_APP.py
```

Optional automated redeployment:

```text
notebooks/platform/04_DEPLOY_APP_AUTOMATED.py
```

The automated strategy flow can include the latter as its final task by setting `include_app_deploy=true`. It is disabled by default.

## First deployment prerequisites

1. `notebooks/00_SETUP.py` has completed successfully.
2. Research data/results exist in the canonical DBO_Quant namespace.
3. A Databricks SQL Warehouse is available.
4. A Databricks App is created for this backend.
5. The App has a SQL Warehouse resource with key `sql_warehouse` and `CAN USE` permission.
6. `FINANCE_CATALOG` and `FINANCE_SCHEMA` match the canonical DBO_Quant namespace.
7. The App service principal has `USE CATALOG`, `USE SCHEMA`, and `SELECT` permissions for the DBO_Quant schema.

The launcher uses `app_entry.py`, which imports the core API and registers portfolio-analysis routes before OpenBB widget discovery.

## OpenBB visualization routes

The App exposes chart-ready persisted outputs including:

- backtest equity, benchmark, and drawdown curves;
- portfolio-comparison curves;
- Monte Carlo fan chart;
- Monte Carlo sample paths;
- Mean-CVaR efficient frontier;
- optimized allocation bar chart;
- portfolio rebalancing value curve.

It also exposes saved portfolio holdings, run metadata, optimizer metrics, rebalancing events, features, predictions, and other table-style results.

## Endpoints

```text
/api/widgets.json        OpenBB widget discovery
/api/v1/...              native OpenBB ODP routes
/api/quant/...           DBO_Quant research routes
```

Connect OpenBB Workspace to:

```text
https://<databricks-app-url>/api
```

Continue with:

```text
notebooks/platform/03_OPENBB_WORKSPACE.py
```

## Jobs

Lakeflow Jobs are not required merely to view persisted results. `notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py` creates a reproducible research Job that can refresh data, run a selected strategy, pass its `strategy_run_id` to Monte Carlo, run CPU-default portfolio optimization, and optionally redeploy this App.

## Cleanup

Use `notebooks/99_CLEANUP.py` and provide the App name explicitly if the App itself should be deleted.
