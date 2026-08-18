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
Monte Carlo — strategy allocation baseline
      ↓
Portfolio Optimization
input = same strategy_run_id
solver = CPU by default
      ↓
optimization_run_id task value
      ↓
Monte Carlo — optimized allocation
      ↓
persisted Unity Catalog results
      ↓
optional automated App deployment
      ↓
OpenBB Workspace
```

This produces an apples-to-apples research sequence: the optimizer receives the selected strategy's latest effective allocation/universe, and Monte Carlo evaluates both the strategy allocation and the resulting optimized allocation.

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

The strategy notebook can be any built-in notebook or a copied custom strategy template, provided it uses the shared DBO_Quant research engine and therefore publishes `strategy_run_id`.

### Scheduling

Leave `cron_expression` blank for a manually triggered Job. To automate runs, provide a Databricks Quartz cron expression and a `timezone_id`.

### Portfolio optimization

The Job uses `optimization/portfolio_optimization/portfolio_config.toml`. The committed default is CPU:

```toml
[execution]
solver = "cpu"
```

CPU mode uses CVXPY + CLARABEL. Change the setting to `gpu` only when the optimization task is configured on compatible GPU compute with cuOpt/cuML available.

### App deployment

`include_app_deploy=false` is the safe default. Set it to `true` only after the Databricks App exists and its SQL Warehouse/Git resources are configured. The final task then requests a new deployment from the repository.

### OpenBB

The Job does not create a second dashboard. Each research task persists results to Unity Catalog. The DBO_Quant App exposes the strategy curves, both Monte Carlo runs, optimization frontier/allocation, and optional rebalancing output to OpenBB Workspace.
