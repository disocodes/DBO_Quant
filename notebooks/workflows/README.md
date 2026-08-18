# Automated workflows

Use this folder to turn reproducible DBO_Quant notebook research into Databricks Lakeflow Jobs.

## `00_CONFIGURE_STRATEGY_FLOW.py`

Creates a multi-task Job around any selected strategy notebook, including a custom strategy copied from `notebooks/backtests/90_CUSTOM_STRATEGY_TEMPLATE.py`.

Default flow:

```text
01_INGEST_DATA
      ↓
selected strategy notebook
      ↓
strategy_run_id task value
      ↓
02_MONTE_CARLO
source_type=strategy_run
      ↓
04_PORTFOLIO_OPTIMIZATION_DATABRICKS
CPU solver by default
      ↓
persisted Unity Catalog results
      ↓
optional 04_DEPLOY_APP_AUTOMATED
      ↓
OpenBB Workspace
```

### Required configuration

Set `repo_workspace_root` to the absolute Databricks workspace path of the DBO_Quant Git folder. `strategy_notebook` is relative to that root. Any strategy widget values can be passed with `strategy_parameters_json`.

Example:

```json
{
  "symbols": "SPY,QQQ,IEF,GLD",
  "lookback": "63",
  "rebalance": "monthly"
}
```

### Scheduling

Leave `cron_expression` blank for a manually triggered Job. To automate runs, provide a Databricks Quartz cron expression and a `timezone_id`.

### Portfolio optimization

The Job uses `optimization/portfolio_optimization/portfolio_config.toml`. The committed default is CPU:

```toml
[execution]
solver = "cpu"
```

Change it to `gpu` only when the optimization task is configured on compatible GPU compute.

### App deployment

`include_app_deploy=false` is the safe default. Set it to `true` only after the Databricks App exists and its SQL Warehouse/Git resources are configured. The final task then requests a new deployment from the repository.

### OpenBB

The Job does not create a second dashboard. Each research task persists results to Unity Catalog; the DBO_Quant Databricks App exposes those results to OpenBB Workspace.
