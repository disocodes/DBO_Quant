# Platform notebooks

These notebooks configure optional infrastructure around the research workflows.

## Flow

```text
persisted Unity Catalog results
        ↓
Databricks App
        ↓
OpenBB Workspace
```

## `01_SERVING.py`
Use only when a registered model or online feature workflow needs Model Serving or Feature Serving. Ordinary backtests, Monte Carlo, portfolio optimization, automated Jobs, and OpenBB result viewing do not require it.

## `02_DEPLOY_APP.py`
Guided/manual App deployment preparation. It discovers the canonical DBO_Quant namespace and shows the required App/SQL Warehouse configuration.

## `03_OPENBB_WORKSPACE.py`
Verifies persisted tables and provides the OpenBB backend URL/settings. OpenBB exposes strategy curves, comparisons, Monte Carlo charts, portfolio-optimization charts, holdings, metrics, and rebalancing outputs.

## `04_DEPLOY_APP_AUTOMATED.py`
Optional real deployment task for Lakeflow Jobs. It requests a Databricks App deployment from the Git repository and overrides `FINANCE_CATALOG` / `FINANCE_SCHEMA` with the discovered DBO_Quant namespace.

Prerequisites:

- the Databricks App already exists;
- its Git repository is configured for this repository;
- required App resources, including the SQL Warehouse resource, already exist;
- the caller has App deployment permission.

The automated strategy-flow notebook keeps this task disabled by default. Enable it only when you want a successful research Job to finish by redeploying the OpenBB backend.

## Automation

Use `notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py` to create an end-to-end Lakeflow Job. The optional final task is `04_DEPLOY_APP_AUTOMATED.py`.

## Cleanup

Use `notebooks/99_CLEANUP.py` and explicitly provide any App name, Job IDs, Serving endpoint names, or Online Feature Store name that should be removed.
