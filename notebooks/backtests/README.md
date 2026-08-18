# Strategy Backtests

This folder contains one Databricks notebook per strategy. Each notebook defines strategy logic and parameters and delegates execution to the shared engine in `src/quant_platform/`.

## Prerequisites

Run:

```text
notebooks/00_SETUP.py
notebooks/01_INGEST_DATA.py
```

before running a strategy notebook.

## Built-in strategies

```text
01_FIXED_ALLOCATION.py
02_INVERSE_VOLATILITY.py
03_MOVING_AVERAGE_TREND.py
04_TIME_SERIES_MOMENTUM.py
05_CROSS_SECTIONAL_MOMENTUM.py
06_MEAN_REVERSION.py
07_DUAL_MOMENTUM.py
08_BUY_AND_HOLD.py
90_CUSTOM_STRATEGY_TEMPLATE.py
```

## How a strategy run works

```text
strategy notebook
      ↓
target weights
      ↓
shared research engine
      ↓
implementation lag
rebalancing
transaction costs
weight drift
benchmark comparison
metrics
      ↓
Unity Catalog
```

A successful run persists:

- a `run_id` in `strategy_runs`;
- daily equity, return, benchmark, drawdown, and turnover data in `strategy_daily`;
- effective and target holdings in `strategy_holdings`;
- performance and risk metrics in `strategy_metrics`.

When the notebook runs as a Databricks Job task, the shared persistence layer also publishes the run identifier as the task value `strategy_run_id`.

## Run a built-in strategy

Open the required strategy notebook, configure its widgets, and run all cells.

After completion, use the resulting `run_id` with:

```text
notebooks/portfolio/01_COMPARE_RUNS.py
```

to compare multiple strategies, or:

```text
notebooks/portfolio/02_MONTE_CARLO.py
source_type = strategy_run
source_id   = <run_id>
```

to run forward-risk simulation on the strategy's latest effective allocation.

## Create a custom strategy

Copy:

```text
90_CUSTOM_STRATEGY_TEMPLATE.py
```

Rename the copy and implement:

```python
def strategy(prices, params):
    return target_weights_dataframe
```

The returned DataFrame must use:

- dates as the index;
- symbols as columns;
- target portfolio weights as values.

Keep strategy-specific logic in the notebook. Execution rules and persistence remain in the common engine.

## Automate a strategy

Use:

```text
notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py
```

Set `strategy_notebook` to the relative path of any built-in or custom strategy notebook. Strategy widget values can be supplied through `strategy_parameters_json`.

The default automated workflow runs:

```text
market-data refresh
      ↓
selected strategy
      ↓
Monte Carlo baseline
      ↓
portfolio optimization
      ↓
Monte Carlo on optimized allocation
```

## OpenBB outputs

After the Databricks App is deployed, OpenBB Workspace can display:

- strategy run metadata;
- performance and risk metrics;
- strategy equity curve;
- benchmark curve;
- drawdown curve;
- persisted strategy-comparison curves.