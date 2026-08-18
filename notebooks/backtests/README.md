# Backtest strategy notebooks

This folder contains one research notebook per strategy. Run `notebooks/00_SETUP.py` once and keep market data current with `notebooks/01_INGEST_DATA.py`.

## Purpose

Backtesting answers:

> How would this strategy have behaved over historical market data under the common DBO_Quant execution assumptions?

Every notebook delegates execution to the shared engine in `src/quant_platform/`. The notebook defines strategy logic and parameters; the engine handles implementation lag, rebalancing, transaction costs, weight drift, benchmark comparison, metrics, holdings, and persistence.

## Run a built-in strategy

Open any numbered notebook and run all cells. A successful run prints a `run_id` and persists its equity curve, holdings, and metrics to Unity Catalog.

Next actions:

```text
single run
   ├─→ notebooks/portfolio/01_COMPARE_RUNS.py
   └─→ notebooks/portfolio/02_MONTE_CARLO.py
        source_type = strategy_run
        source_id   = <run_id>
```

When a strategy runs inside a Lakeflow Job, the common persistence layer also publishes `strategy_run_id` as a task value so downstream Monte Carlo can consume it automatically.

## Add a custom strategy

1. Copy `90_CUSTOM_STRATEGY_TEMPLATE.py`.
2. Rename it, for example `20_VALUE_MOMENTUM.py`.
3. Edit the strategy function and parameter widgets.
4. Keep the function contract:

```python
def strategy(prices, params):
    return target_weights_dataframe
```

The returned DataFrame uses dates as the index and symbols as columns. Values are target portfolio weights. Do not modify the common engine for ordinary strategy development.

## Automate a strategy

Use:

```text
notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py
```

Set `strategy_notebook` to any built-in strategy or your copied custom notebook. Strategy widget values can be supplied with `strategy_parameters_json`. The generated Job can refresh market data, run the strategy, run Monte Carlo on its exact `strategy_run_id`, optionally run portfolio optimization, and optionally redeploy the OpenBB backend.

## OpenBB outputs

After the Databricks App is deployed, OpenBB Workspace can display strategy run metadata, performance/risk metrics, equity and benchmark curves, drawdown, and persisted comparison curves.
