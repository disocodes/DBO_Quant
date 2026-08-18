# Platform notebooks

These notebooks configure optional infrastructure around the research workflows. They are not part of every backtest or portfolio run.

## Flow

```text
Research results already persisted in Unity Catalog
                 ↓
02_DEPLOY_APP.py
                 ↓
Databricks App / openbb-platform-api
                 ↓
03_OPENBB_WORKSPACE.py
                 ↓
OpenBB Workspace
```

`01_SERVING.py` is independent and optional.

## `01_SERVING.py`

Use only when a registered model or online feature workflow needs Databricks Model Serving or Feature Serving.

You do not need Serving for:

- strategy backtests;
- portfolio comparisons;
- Monte Carlo simulation;
- NVIDIA optimization/rebalancing;
- OpenBB display of already-persisted results.

## `02_DEPLOY_APP.py`

Deploys or updates the thin DBO_Quant API backend used by OpenBB Workspace. The notebook discovers the canonical DBO_Quant namespace and provides the values needed by `databricks_app/app.yaml`.

The App requires a SQL Warehouse resource for querying persisted Unity Catalog results.

## `03_OPENBB_WORKSPACE.py`

Verifies the result tables and provides the backend URL/settings for OpenBB Workspace.

OpenBB receives dynamically generated widgets for backtests, portfolio comparisons, Monte Carlo, optimizer results, and other DBO_Quant API routes.

## Cleanup

Platform resources are not deleted implicitly. Use `notebooks/99_CLEANUP.py` and explicitly provide any App name, Job IDs, or Serving endpoint names you want removed.