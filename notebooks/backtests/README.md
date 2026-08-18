# Backtest strategy notebooks

This folder contains one research notebook per strategy. Run `notebooks/00_SETUP.py` once and keep market data current with `notebooks/01_INGEST_DATA.py`.

## Purpose

Backtesting answers:

> How would this strategy have behaved over historical market data under the common DBO_Quant execution assumptions?

Every notebook delegates execution to the shared engine in `src/quant_platform/`. The notebook defines only strategy logic and parameters; the engine handles implementation lag, rebalancing, transaction costs, weight drift, benchmark comparison, metrics, holdings, and persistence.

## Run a built-in strategy

Open any numbered notebook and run all cells. A successful run prints a `run_id` and saves its equity curve, holdings, and metrics to Unity Catalog.

Next actions:

```text
single run
   ├─→ notebooks/portfolio/01_COMPARE_RUNS.py
   └─→ notebooks/portfolio/02_MONTE_CARLO.py
        source_type = strategy_run
        source_id   = <run_id>
```

## Add a custom strategy

1. Copy `90_CUSTOM_STRATEGY_TEMPLATE.py`.
2. Rename it, for example `20_VALUE_MOMENTUM.py`.
3. Edit the strategy function and parameter widgets.
4. Keep the function contract:

```python
def strategy(prices, params):
    return target_weights_dataframe
```

The returned DataFrame must use dates as the index and symbols as columns. Values are target portfolio weights.

Do not modify the common backtest engine for ordinary strategy development.

## OpenBB outputs

After the Databricks App is deployed, OpenBB Workspace can display:

- strategy run metadata;
- performance/risk metrics;
- strategy equity curve;
- benchmark equity curve;
- drawdown curve;
- persisted comparison curves created from multiple runs.