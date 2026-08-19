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
    direct App deploy/redeploy from the cloned workspace directory

03_OPENBB_WORKSPACE.py
    verify persisted data, SQL connectivity, widget forms, and OpenBB backend connection

04_DEPLOY_APP_AUTOMATED.py
    optional Job-driven App redeployment from the cloned workspace directory
```

## `01_SERVING.py`

Use this notebook only when DBO_Quant needs low-latency model inference or online feature lookup.

Serving is not required for strategy backtests, strategy comparisons, Monte Carlo simulation, portfolio optimization, rebalancing research, Lakeflow strategy Jobs, or OpenBB display of already-persisted research results.

## `02_DEPLOY_APP.py`

Use this notebook for a manual App deploy or redeploy.

It:

- discovers the canonical DBO_Quant Unity Catalog namespace;
- locates the current cloned DBO_Quant workspace root;
- validates or configures the App's `sql_warehouse` resource;
- reads the App's dedicated service-principal client ID;
- grants that principal `USE CATALOG`, `USE SCHEMA`, and schema-level `SELECT` on the dedicated DBO_Quant namespace;
- deploys `<repo_workspace_root>/databricks_app` with `mode=SNAPSHOT`;
- sends no Git URL, Git branch, or `git_source` in the deployment request;
- prints the OpenBB backend URL.

The Databricks App must already exist. The notebook identity must be able to manage the relevant Unity Catalog privileges in order to apply the App grants. The App service principal needs `CAN USE` on the SQL Warehouse plus `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the DBO_Quant namespace.

This notebook is the preferred manual redeploy path. Do not rely on an old Git-backed deployment source remembered by the Databricks Apps UI.

## `03_OPENBB_WORKSPACE.py`

Use this notebook after the Databricks App is running.

It discovers the canonical DBO_Quant namespace, checks the main persisted result tables, generates an App-scoped OAuth token, and tests four distinct layers:

1. OpenBB `/api/widgets.json` discovery;
2. App `/api/quant/health` without SQL;
3. `/api/quant/sql-health`, which executes a minimal SQL query through the App's configured warehouse without reading a DBO_Quant table;
4. `/api/quant/backtests/runs`, which verifies the App service principal can read persisted strategy results from Unity Catalog.

This separation makes a SQL timeout actionable: if `sql-health` fails, investigate the warehouse resource, `CAN_USE`, warehouse availability/cold start, or SQL connector authentication. If `sql-health` succeeds but `backtests/runs` fails, investigate Unity Catalog grants and the target table.

The notebook also inspects the three form-enabled widgets — **Strategy Runs**, **Portfolio Comparison Runs**, and **Monte Carlo Runs**. The backend retains OpenBB's generated nested `type=form` input while removing the build-only top-level `form_endpoint` directive from the final discovery payload because Workspace rejects that top-level field.

## `04_DEPLOY_APP_AUTOMATED.py`

This notebook is intended as an optional final Lakeflow Job task.

It performs the same workspace-snapshot deployment and App service-principal Unity Catalog grant setup as `02_DEPLOY_APP.py`. The notebook auto-detects the cloned DBO_Quant workspace root when run directly and also accepts `repo_workspace_root` from the automated workflow.

The deployment source is always:

```text
<repo_workspace_root>/databricks_app
```

Example:

```text
/Workspace/Users/user@example.com/DBO_Quant/databricks_app
```

The deployment API body uses:

```text
source_code_path = <repo_workspace_root>/databricks_app
mode = SNAPSHOT
```

No Git URL, Git branch, or `git_source` is supplied.

App redeployment is not required for ordinary data-only research runs because the already-running App reads new persisted results from Unity Catalog.

## Automated research workflow

Use:

```text
notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py
```

for the full multi-task research workflow. When App redeployment is enabled, `04_DEPLOY_APP_AUTOMATED.py` is appended as the final task and receives the same `repo_workspace_root` used by the research notebooks.

## Cleanup

Use:

```text
notebooks/99_CLEANUP.py
```

and explicitly provide the App name, Job IDs, Serving endpoint names, or Online Feature Store name that should be removed.
