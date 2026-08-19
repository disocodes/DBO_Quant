# Platform Notebooks

This folder contains DBO_Quant presentation and optional serving deployment notebooks.

The **primary analyst environment is now Databricks-native**:

```text
Unity Catalog / Delta
       ├────────→ AI/BI Dashboard
       └────────→ DBO_Quant Research App
```

OpenBB Workspace remains an optional compatibility path. Serving remains separate and optional.

## Notebook map

```text
01_SERVING.py
    optional Model Serving / Feature Serving setup

02_DEPLOY_APP.py
    optional OpenBB backend manual deployment

03_OPENBB_WORKSPACE.py
    optional OpenBB backend / Workspace validation

04_DEPLOY_APP_AUTOMATED.py
    optional OpenBB backend Job-driven redeployment

05_DEPLOY_DATABRICKS_RESEARCH.py
    PRIMARY: create/update AI/BI research dashboard + native Research App
```

## `05_DEPLOY_DATABRICKS_RESEARCH.py` — primary UI deployment

Use this notebook to deploy DBO_Quant as a Databricks-native research environment.

It:

- discovers the canonical DBO_Quant Unity Catalog namespace;
- uses the **existing cloned workspace repository** as the only application source;
- creates/updates the versioned presentation views in `sql/research_dashboard_views.sql`;
- builds the dashboard definition from `dashboards/research_dashboard.py`;
- runs every AI/BI dataset query before dashboard creation/update;
- creates or updates the `DBO_Quant Research` AI/BI dashboard while preserving its dashboard ID on updates;
- optionally publishes the dashboard against the selected SQL Warehouse without embedding the notebook user's credentials;
- creates/reuses the `dbo-quant-research` Databricks App;
- grants its service principal read access to the DBO_Quant schema;
- attaches the SQL Warehouse with `CAN_USE`;
- optionally attaches configured Lakeflow Jobs with `CAN_MANAGE_RUN`;
- deploys `<repo_workspace_root>/research_app` as a workspace snapshot.

The dashboard pages are:

```text
Overview
Strategy Lab
Portfolio Lab
Risk & Monte Carlo
Models & Signals
```

The Research App provides those same research domains with richer run selection and a **Run Research** surface for backtest, Monte Carlo, comparison, and optimization Jobs. Job controls are enabled only for Job IDs configured during deployment.

The App is read-only against Unity Catalog. Research writes continue to happen through the existing notebooks/workers and Lakeflow Jobs.

### Required deployment inputs

At minimum set:

```text
sql_warehouse_id
```

The notebook auto-detects the cloned repository root when run from inside DBO_Quant. Override `repo_workspace_root` only when required; it must be an absolute `/Workspace/...` path.

Optional Job resource inputs:

```text
backtest_job_id
monte_carlo_job_id
comparison_job_id
optimization_job_id
```

When omitted, dashboard deployment and read-only App analysis still work; the corresponding run buttons are disabled.

### Source rule

The Research App deployment source is always:

```text
<repo_workspace_root>/research_app
```

No Git URL, branch, `git_source`, or secondary repository clone is supplied to the App deployment API.

## Databricks-native automated workflow

Use:

```text
notebooks/workflows/01_CONFIGURE_DATABRICKS_RESEARCH_FLOW.py
```

Default flow:

```text
refresh data
   ↓
selected strategy
   ↓
Monte Carlo baseline
   ↓
portfolio optimization — CPU default
   ↓
Monte Carlo optimized allocation
   ↓
Unity Catalog
```

The AI/BI dashboard and running Research App read new persisted results directly, so `include_research_ui_deploy` is disabled by default. Enable it only when dashboard/App code itself needs deployment.

## `01_SERVING.py`

Use this notebook only when DBO_Quant needs low-latency model inference or online feature lookup.

Serving is not required for strategy backtests, comparisons, Monte Carlo, portfolio optimization, rebalancing, Lakeflow Jobs, AI/BI dashboards, the Research App, or OpenBB display of persisted results.

## Optional OpenBB compatibility path

The OpenBB backend under `databricks_app/` and notebooks 02–04 remain supported but are no longer the primary presentation layer.

### `02_DEPLOY_APP.py`

Manual OpenBB backend deployment. It discovers the canonical namespace, configures the App SQL Warehouse resource, grants the App service principal `USE CATALOG`, `USE SCHEMA`, and schema-level `SELECT`, and snapshots:

```text
<repo_workspace_root>/databricks_app
```

No Git URL or independent App checkout is used.

### `03_OPENBB_WORKSPACE.py`

OpenBB-specific validation. It separates:

1. widget discovery;
2. non-SQL App health;
3. SQL Warehouse connectivity;
4. Unity Catalog strategy-table access;
5. form-widget metadata validation.

Use this only when OpenBB Workspace is being used as an additional client.

### `04_DEPLOY_APP_AUTOMATED.py`

Optional final Lakeflow task for redeploying the OpenBB backend from the same cloned workspace repository. Ordinary data-only runs do not require an OpenBB App redeploy.

The original OpenBB-compatible automated workflow remains available at:

```text
notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py
```

## Cleanup

Use:

```text
notebooks/99_CLEANUP.py
```

and explicitly provide the App names, Job IDs, Serving endpoint names, or Online Feature Store name that should be removed. AI/BI dashboard deletion is intentionally not implicit; manage the dashboard separately so cleanup cannot silently destroy a shared research presentation.
