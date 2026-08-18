# Portfolio analysis notebooks

Run `notebooks/00_SETUP.py` once and keep `notebooks/01_INGEST_DATA.py` current before using this folder.

## Purpose

This folder covers portfolio-level research after market data exists in Unity Catalog.

```text
Real portfolio
00_SAVE_PORTFOLIO.py
      ↓
 portfolio_id
      │
      ├─→ 02_MONTE_CARLO.py
      │
      └─→ optional NVIDIA optimization
             ├─ Databricks GPU: 04_NVIDIA_GPU_DATABRICKS.py
             └─ external GPU: ../../gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
                         ↓
                 03_NVIDIA_RESULTS.py
                         ↓
                 02_MONTE_CARLO.py
                 source_type=optimization_run

Strategy research
../backtests/*.py
      ↓
    run_id
      ├─→ 01_COMPARE_RUNS.py
      └─→ 02_MONTE_CARLO.py
           source_type=strategy_run
```

## Notebook roles

### `00_SAVE_PORTFOLIO.py`

Creates or updates a real portfolio using a persistent `portfolio_id` and dated holdings snapshots.

### `01_COMPARE_RUNS.py`

Compares two or more historical strategy `run_id` values. Use it for backtest-to-backtest performance and wealth-curve comparison.

### `02_MONTE_CARLO.py`

Forward-risk validation for an existing allocation. It can load weights from:

- a saved `portfolio_id`;
- a strategy `run_id`;
- an NVIDIA/optimizer `optimization_run_id`;
- an ad-hoc allocation.

It persists percentile distributions and sample paths. Monte Carlo does not optimize weights.

### `03_NVIDIA_RESULTS.py`

Reviews already-persisted NVIDIA optimization, allocation, backtest-metric, and rebalancing results.

### `04_NVIDIA_GPU_DATABRICKS.py`

Runs the NVIDIA workflow on compatible Databricks GPU compute using native Spark/Unity Catalog access.

## Recommended portfolio decision flow

```text
Saved current portfolio
      ↓
Monte Carlo baseline
      ↓
optional NVIDIA optimization
      ↓
selected_optimal allocation
      ↓
Monte Carlo validation
      ↓
compare downside/upside distributions
```

This keeps the responsibilities separate: optimization chooses candidate weights; Monte Carlo evaluates forward uncertainty around those weights.

## OpenBB outputs

The Databricks App exposes:

- saved portfolio holdings;
- strategy comparison curves;
- Monte Carlo fan charts;
- Monte Carlo sample paths;
- Mean-CVaR efficient frontier;
- optimized allocation chart;
- optimizer backtest metrics;
- rebalancing events and portfolio-value curve.