# DBO_Quant Databricks App

This folder contains the API backend used by OpenBB Workspace.

The App does not run research notebooks directly. It reads persisted DBO_Quant results from Unity Catalog through a Databricks SQL Warehouse and exposes those results as OpenBB-compatible API routes and widgets.

## Architecture

```text
Unity Catalog / Delta
        ↓
Databricks SQL Warehouse
        ↓
DBO_Quant Databricks App
        ↓
OpenBB Workspace
```

## Main files

```text
app.py
    core API routes and Job-trigger endpoints

app_entry.py
    application entrypoint and portfolio-analysis routes

app.yaml
    Databricks App command and resource configuration

requirements.txt
    App Python dependencies

AUTHENTICATION.md
    authentication and permission guidance
```

## Prerequisites

Before deploying the App:

1. run `notebooks/00_SETUP.py`;
2. ensure DBO_Quant research tables exist in the canonical Unity Catalog namespace;
3. make a Databricks SQL Warehouse available;
4. create a Databricks App for this backend;
5. attach a SQL Warehouse resource with key `sql_warehouse`;
6. grant the App service principal `CAN USE` on the Warehouse;
7. grant the App service principal `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the DBO_Quant namespace;
8. configure `FINANCE_CATALOG` and `FINANCE_SCHEMA` with the canonical DBO_Quant location.

## Deployment

### Guided deployment preparation

Use:

```text
notebooks/platform/02_DEPLOY_APP.py
```

This notebook discovers the canonical DBO_Quant namespace and prints the configuration required by the App.

### Automated redeployment

Use:

```text
notebooks/platform/04_DEPLOY_APP_AUTOMATED.py
```

This notebook is intended for an existing App whose Git source, Warehouse resource, and permissions are already configured.

It can be added as the final task of:

```text
notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py
```

by setting `include_app_deploy=true`.

## OpenBB endpoints

```text
/api/widgets.json
    OpenBB widget discovery

/api/v1/...
    native OpenBB ODP routes

/api/quant/...
    DBO_Quant research routes
```

Connect OpenBB Workspace to:

```text
https://<databricks-app-url>/api
```

Use `notebooks/platform/03_OPENBB_WORKSPACE.py` to verify the expected connection settings.

## Research outputs exposed to OpenBB

The App exposes persisted data for:

- strategy runs and metrics;
- strategy equity, benchmark, and drawdown curves;
- saved portfolios and holdings;
- strategy-comparison metrics and curves;
- Monte Carlo runs;
- Monte Carlo fan charts;
- Monte Carlo sample paths;
- portfolio-optimization runs;
- Mean-CVaR efficient frontier;
- optimized allocation chart;
- optimization backtest metrics;
- rebalancing runs, events, and portfolio-value curves;
- persisted features and model predictions.

## Job-trigger endpoints

The App can optionally trigger dedicated Databricks Jobs for backtesting, Monte Carlo, and portfolio comparisons.

Configure the following environment variables only when those API-triggered workers are deployed:

```text
BACKTEST_JOB_ID
MONTE_CARLO_JOB_ID
COMPARISON_JOB_ID
```

The multi-task automated strategy workflow under `notebooks/workflows/` is separate from these individual API-triggered workers.

## Authentication

See:

```text
databricks_app/AUTHENTICATION.md
```

for App authentication and permissions.

## Cleanup

To remove an App created for DBO_Quant, run:

```text
notebooks/99_CLEANUP.py
```

and provide the App name explicitly.