# quant_platform

`src/quant_platform/` contains the shared DBO_Quant research engine used by strategy notebooks, Monte Carlo analysis, comparisons, and persistence helpers.

Operator notebooks should call this package rather than reimplementing execution logic.

## Strategy interface

A strategy produces target portfolio weights:

```python
def strategy(prices, params):
    return target_weights_dataframe
```

The returned DataFrame uses:

- dates as the index;
- asset symbols as columns;
- target portfolio weights as values.

## Core modules

```text
engine.py
    strategy execution, rebalancing, implementation lag,
    transaction costs, weight drift, leverage and cash handling

metrics.py
    performance and risk metrics

monte_carlo.py
    forward portfolio simulation

comparison.py
    common comparison utilities

research.py
    Databricks research entry point and result persistence

location.py
    canonical DBO_Quant Unity Catalog discovery
```

## Backtest execution

The shared engine applies a consistent execution model across all strategy notebooks.

It handles:

- target weights;
- rebalance schedules;
- one-observation implementation lag;
- effective-weight drift between rebalances;
- transaction costs and slippage;
- long-only or long/short exposure;
- gross leverage limits;
- residual cash;
- benchmark comparison;
- holdings and daily-result generation.

The engine returns a common result structure used by every strategy notebook.

## Metrics

The metrics layer supports portfolio measures including:

- annualized return;
- annualized volatility;
- Sharpe ratio;
- Sortino ratio;
- maximum drawdown;
- Calmar ratio;
- historical VaR and CVaR;
- beta and alpha;
- ending value;
- turnover and trading costs.

## Monte Carlo

`monte_carlo.py` simulates future portfolio-value paths for a supplied allocation.

Supported methods include:

- historical block bootstrap;
- multivariate normal simulation.

The simulator supports portfolio-weight drift and configurable periodic rebalancing and produces:

- percentile curves;
- sampled paths;
- terminal values;
- summary risk statistics.

The operator notebook is:

```text
notebooks/portfolio/02_MONTE_CARLO.py
```

## Persistence

`research.py` is the common Databricks strategy entry point.

It discovers the canonical DBO_Quant namespace, loads price data, invokes the engine, and persists:

```text
strategy_runs
strategy_daily
strategy_holdings
strategy_metrics
```

When executed inside a Databricks Job task, it also publishes `strategy_run_id` for downstream tasks.

## Canonical namespace

`location.py` discovers the DBO_Quant deployment created by:

```text
notebooks/00_SETUP.py
```

Research code should use this canonical location instead of independently choosing a catalog/schema.

## Adding strategies

Use:

```text
notebooks/backtests/90_CUSTOM_STRATEGY_TEMPLATE.py
```

as the operator-facing starting point for a custom strategy.

Ordinary strategy development should add or modify strategy logic without changing the common engine unless the execution model itself must change.