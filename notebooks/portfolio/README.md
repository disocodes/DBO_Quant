# Portfolio Analysis

This folder contains the portfolio-level research notebooks used after market data and strategy results are available in Unity Catalog.

## Prerequisites

Run:

```text
notebooks/00_SETUP.py
notebooks/01_INGEST_DATA.py
```

before using these notebooks.

## Notebook map

```text
00_SAVE_PORTFOLIO.py
    save or update portfolio holdings

01_COMPARE_RUNS.py
    compare two or more strategy backtests

02_MONTE_CARLO.py
    simulate forward portfolio outcomes

03_OPTIMIZATION_RESULTS.py
    inspect persisted optimization results

04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py
    run Mean-CVaR portfolio optimization in Databricks
```

## Saved portfolio workflow

```text
00_SAVE_PORTFOLIO.py
      ↓
portfolio_id
      ├──────────────→ 02_MONTE_CARLO.py
      │                 source_type=saved_portfolio
      │
      └──────────────→ 04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py
                              ↓
                       optimization_run_id
                              ├────────→ 03_OPTIMIZATION_RESULTS.py
                              └────────→ 02_MONTE_CARLO.py
                                         source_type=optimization_run
```

`00_SAVE_PORTFOLIO.py` creates or updates dated holdings under a persistent `portfolio_id`.

## Strategy-result workflow

```text
notebooks/backtests/*.py
      ↓
run_id
      ├────────→ 01_COMPARE_RUNS.py
      ├────────→ 02_MONTE_CARLO.py
      │           source_type=strategy_run
      └────────→ 04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py
                  source_type=strategy_run
```

## Monte Carlo

`02_MONTE_CARLO.py` evaluates an allocation under forward simulation. It does not calculate optimal weights.

Supported sources:

- `saved_portfolio` — latest holdings for a `portfolio_id`;
- `strategy_run` — latest effective allocation from a strategy `run_id`;
- `optimization_run` — `selected_optimal` allocation from an optimization run;
- `adhoc` — manually supplied symbols and weights.

The notebook persists:

- run metadata;
- percentile curves;
- sampled simulation paths;
- terminal-value statistics;
- probability-of-loss summary data.

## Portfolio optimization

Run:

```text
04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py
```

for Databricks-native Mean-CVaR optimization.

Shared configuration is stored in:

```text
optimization/portfolio_optimization/portfolio_config.toml
```

Default execution mode:

```toml
[execution]
solver = "cpu"
```

Supported modes:

- `cpu` — CVXPY + CLARABEL;
- `gpu` — CVXPY + NVIDIA cuOpt.

Both modes persist the same tables and return an `optimization_run_id`.

Review persisted results with:

```text
03_OPTIMIZATION_RESULTS.py
```

## Remote or on-prem optimization

Use:

```text
optimization/portfolio_optimization/PORTFOLIO_OPTIMIZATION.ipynb
```

The external route uses the same portfolio configuration and writes the same optimization result model as the Databricks route.

## Recommended analysis sequence

```text
current portfolio or strategy allocation
          ↓
Monte Carlo baseline
          ↓
portfolio optimization
          ↓
selected_optimal allocation
          ↓
Monte Carlo validation
          ↓
OpenBB review
```

## OpenBB outputs

The Databricks App exposes:

- saved holdings;
- strategy-comparison metrics and curves;
- Monte Carlo fan charts;
- Monte Carlo sample paths;
- Mean-CVaR efficient frontier;
- optimized allocation chart;
- optimization backtest metrics;
- rebalancing runs, events, and portfolio-value curve.