# Platform Notebooks

This folder contains the optional Databricks infrastructure notebooks used to expose persisted DBO_Quant research through OpenBB Workspace and, when required, Databricks Serving.

## Platform flow

```text
Unity Catalog research results
        ↓
Databricks App
        ↓
OpenBB Workspace
```

Serving is separate and optional.

## Notebook map

```text
01_SERVING.py
    optional Model Serving / Feature Serving setup

02_DEPLOY_APP.py
    guided App deployment preparation

03_OPENBB_WORKSPACE.py
    verify persisted data and OpenBB backend connection

04_DEPLOY_APP_AUTOMATED.py
    optional Job-driven App redeployment
```

## `01_SERVING.py`

Use this notebook only when DBO_Quant needs low-latency model inference or online feature lookup.

Serving is not required for:

- strategy backtests;
- strategy comparisons;
- Monte Carlo simulation;
- portfolio optimization;
- rebalancing research;
- Lakeflow strategy Jobs;
- OpenBB display of already-persisted research results.

## `02_DEPLOY_APP.py`

Use this notebook when preparing or verifying a Databricks App deployment manually.

It discovers the canonical DBO_Quant namespace and provides the values required by the App configuration.

The App must have access to a Databricks SQL Warehouse and permission to read the DBO_Quant Unity Catalog schema.

## `03_OPENBB_WORKSPACE.py`

Use this notebook after the Databricks App is running.

It:

- discovers the canonical DBO_Quant namespace;
- checks the main persisted result tables;
- prints the App backend URL expected by OpenBB Workspace;
- documents the OpenBB custom-backend connection values.

OpenBB can display persisted strategy, comparison, Monte Carlo, portfolio-optimization, holdings, metrics, and rebalancing results.

## `04_DEPLOY_APP_AUTOMATED.py`

This notebook is intended as an optional final Lakeflow Job task.

It requests a Databricks App deployment from the configured Git repository and supplies the discovered DBO_Quant catalog and schema as App environment values.

Prerequisites:

- the Databricks App already exists;
- its Git source is configured for this repository;
- its SQL Warehouse resource is configured;
- the App service principal has the required Unity Catalog permissions;
- the Job identity has App deployment permission.

The automated strategy workflow keeps this task disabled by default.

## Automated research workflow

Use:

```text
notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py
```

for the full multi-task research workflow. When App redeployment is enabled, `04_DEPLOY_APP_AUTOMATED.py` is appended as the final task.

## Cleanup

Use:

```text
notebooks/99_CLEANUP.py
```

and explicitly provide the App name, Job IDs, Serving endpoint names, or Online Feature Store name that should be removed.