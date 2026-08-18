# Automated Strategy Workflows

This folder contains Databricks notebooks that create and manage reproducible Lakeflow Jobs for DBO_Quant research.

## Main notebook

```text
notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py
```

The notebook creates or updates one exact-name Lakeflow Job around a selected strategy notebook.

It supports:

- any built-in strategy notebook;
- any custom strategy copied from `notebooks/backtests/90_CUSTOM_STRATEGY_TEMPLATE.py`;
- manual `Run now` execution;
- scheduled execution with a Quartz cron expression;
- downstream task handoff through Databricks task values;
- optional Databricks App redeployment.

## Default workflow

```text
01_INGEST_DATA
      ↓
selected strategy notebook
      ↓
strategy_run_id
      ↓
02_MONTE_CARLO
source_type=strategy_run
      ↓
04_PORTFOLIO_OPTIMIZATION_DATABRICKS
source_type=strategy_run
solver=cpu by default
      ↓
optimization_run_id
      ↓
02_MONTE_CARLO
source_type=optimization_run
      ↓
persisted Unity Catalog results
      ↓
optional App redeployment
```

The optimization task uses the selected strategy's latest effective allocation as its reference allocation and the strategy's active assets as its optimization universe.

## Required configuration

### `repo_workspace_root`

Absolute Databricks workspace path of the DBO_Quant Git folder.

Example:

```text
/Workspace/Users/user@example.com/DBO_Quant
```

### `strategy_notebook`

Repository-relative path to the strategy notebook.

Example:

```text
notebooks/backtests/02_INVERSE_VOLATILITY.py
```

### `strategy_parameters_json`

JSON object containing widget values that should be supplied to the strategy task.

Example:

```json
{
  "symbols": "SPY,QQQ,IEF,GLD",
  "lookback": "63",
  "rebalance": "monthly"
}
```

Only parameters supported by the selected notebook should be supplied.

## Default switches

```text
include_ingest        true
include_monte_carlo   true
include_optimization  true
include_app_deploy    false
```

With these defaults, one Job run produces:

1. refreshed market data;
2. one strategy backtest;
3. one Monte Carlo run for the strategy allocation;
4. one portfolio-optimization run;
5. one Monte Carlo run for the optimized allocation.

## Scheduling

Leave `cron_expression` empty for a manually triggered Job.

For scheduled execution, provide:

- a Databricks Quartz cron expression;
- the required `timezone_id`.

The default timezone is `Australia/Perth`.

## Job updates

If exactly one Job already exists with the configured `job_name`, the notebook updates that Job definition.

If no matching Job exists, a new Job is created.

If multiple Jobs share the exact name, the notebook stops rather than choosing one automatically.

## Portfolio optimization

The optimization task reads:

```text
optimization/portfolio_optimization/portfolio_config.toml
```

The committed default is:

```toml
[execution]
solver = "cpu"
```

CPU mode uses CVXPY + CLARABEL. GPU mode requires compatible GPU compute and the required NVIDIA cuOpt/cuML packages.

## App redeployment

App redeployment is disabled by default.

Set:

```text
include_app_deploy = true
```

only after the Databricks App already exists and its required Git, SQL Warehouse, permissions, and App resources are configured.

The final task uses:

```text
notebooks/platform/04_DEPLOY_APP_AUTOMATED.py
```

## OpenBB results

Research tasks persist their outputs to Unity Catalog. The Databricks App then exposes those results to OpenBB Workspace.

A complete default workflow can produce OpenBB-ready:

- strategy equity and drawdown curves;
- strategy metrics;
- Monte Carlo baseline fan chart and sample paths;
- efficient frontier and optimized allocation;
- optimization metrics;
- Monte Carlo fan chart and sample paths for the optimized allocation.