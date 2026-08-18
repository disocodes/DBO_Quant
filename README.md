# DBO_Quant

DBO_Quant is a Databricks quantitative-research platform built around OpenBB ODP, Unity Catalog/Delta, a reusable portfolio backtest engine, Monte Carlo risk simulation, optional NVIDIA GPU portfolio optimization, and OpenBB Workspace.

## Workflow

```text
00_SETUP
   ↓
01_INGEST_DATA
   ↓
┌──────────────────────────────┬──────────────────────────────┐
│ Strategy research            │ Real portfolio research      │
│ notebooks/backtests/*.py     │ portfolio/00_SAVE_PORTFOLIO  │
│        ↓                     │              ↓               │
│ strategy run_id              │         portfolio_id         │
│        ↓                     │              │               │
│ portfolio/01_COMPARE_RUNS    │              │               │
└───────────────┬──────────────┴──────────────┼───────────────┘
                │                             │
                │                    optional NVIDIA GPU
                │                    optimization/rebalancing
                │                             │
                │                     optimization_run_id
                │                             │
                └──────────────┬──────────────┘
                               ↓
                 portfolio/02_MONTE_CARLO
                 forward-risk validation
                               ↓
                     persisted results
                               ↓
                  Databricks App / OpenBB
```

Monte Carlo and NVIDIA optimization are complementary:

- **Backtest:** how a strategy behaved historically.
- **NVIDIA optimization:** which allocation to consider for a chosen risk objective.
- **Monte Carlo:** what range of future outcomes an existing allocation could experience.
- **NVIDIA rebalancing:** how an optimized portfolio changes through repeated optimization.

## 1. First run

Run these Databricks notebooks in order:

```text
notebooks/00_SETUP.py
notebooks/01_INGEST_DATA.py
```

`00_SETUP.py`:

- uses an existing Unity Catalog catalog;
- creates the DBO_Quant schema and tables when missing;
- records the canonical DBO_Quant namespace;
- safely reuses that namespace on later reruns;
- applies SQL migrations with `IF NOT EXISTS` semantics.

`01_INGEST_DATA.py` discovers the canonical namespace and writes OpenBB ODP market data to `prices_daily`.

## 2. Strategy research

Each strategy is a separate notebook in `notebooks/backtests/`.

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

Every strategy notebook uses the same execution engine for implementation lag, rebalancing, transaction costs, weight drift, metrics, holdings, and persistence.

To add a strategy, copy `90_CUSTOM_STRATEGY_TEMPLATE.py` and implement:

```python
def strategy(prices, params):
    return target_weights_dataframe
```

A completed backtest returns a `run_id`. Use `notebooks/portfolio/01_COMPARE_RUNS.py` to compare multiple runs.

## 3. Saved portfolios

Use:

```text
notebooks/portfolio/00_SAVE_PORTFOLIO.py
```

A saved portfolio receives a persistent `portfolio_id` and dated holdings snapshots. Use the same `portfolio_id` when updating its allocation later.

## 4. NVIDIA GPU optimization

NVIDIA optimization is optional and has two execution routes.

### Databricks GPU

```text
notebooks/portfolio/04_NVIDIA_GPU_DATABRICKS.py
```

This route uses native Spark/Unity Catalog access. No `.env`, workspace URL, SQL Warehouse path, or OAuth login is required inside Databricks.

### Remote or on-prem GPU

```text
gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
```

The external route uses a Databricks SQL Warehouse. It can authenticate with an existing Databricks profile or OAuth U2M browser sign-in.

Both routes read non-secret portfolio/optimizer settings from:

```text
gpu/nvidia_portfolio_optimization/portfolio_config.toml
```

The workflow can generate Mean-CVaR optimization, efficient-frontier allocations, historical optimizer metrics, covariance data, and optional dynamic rebalancing. Results receive an `optimization_run_id` and optional `rebalance_run_id`.

Review persisted GPU results in:

```text
notebooks/portfolio/03_NVIDIA_RESULTS.py
```

## 5. Monte Carlo forward-risk validation

Use:

```text
notebooks/portfolio/02_MONTE_CARLO.py
```

Choose one allocation source:

- `saved_portfolio` — latest holdings for a `portfolio_id`;
- `strategy_run` — latest effective allocation from a backtest `run_id`;
- `optimization_run` — `selected_optimal` allocation from an NVIDIA/optimizer run;
- `adhoc` — manually supplied symbols and weights.

Monte Carlo does not choose portfolio weights. It simulates thousands of possible future paths for the supplied allocation and persists percentile curves, sample paths, terminal-value statistics, and probability of loss under the selected simulation assumptions.

This makes the preferred optimization-validation sequence:

```text
Current portfolio
      ↓
NVIDIA optimization
      ↓
selected_optimal allocation
      ↓
Monte Carlo
      ↓
forward-risk distribution
```

You can run Monte Carlo again against the original portfolio or a strategy allocation for comparison.

## 6. OpenBB Workspace

Infrastructure notebooks are under `notebooks/platform/`:

```text
01_SERVING.py          optional Model/Feature Serving
02_DEPLOY_APP.py       deploy/update DBO_Quant API App
03_OPENBB_WORKSPACE.py connect and verify OpenBB Workspace
```

The Databricks App is a thin API backend; OpenBB Workspace remains the research UI.

Persisted visualizations exposed to OpenBB include:

- strategy equity curve, benchmark, and drawdown;
- portfolio-comparison curves;
- Monte Carlo percentile fan chart;
- Monte Carlo sample-path chart;
- NVIDIA Mean-CVaR efficient frontier;
- optimized allocation bar chart;
- NVIDIA rebalancing portfolio-value curve;
- associated run, holdings, metrics, and event tables.

## 7. Optional Serving

`notebooks/platform/01_SERVING.py` is optional. Use it only when a real Unity Catalog model or online feature workflow needs low-latency Model Serving or Feature Serving.

Backtests, Monte Carlo, comparisons, NVIDIA analysis, and OpenBB result viewing do not require Serving.

## 8. Cleanup

To permanently remove DBO_Quant-owned resources, run:

```text
notebooks/99_CLEANUP.py
```

The notebook discovers the canonical namespace and requires an exact confirmation phrase before deletion.

By default it removes the DBO_Quant schema and all contained tables with `CASCADE`. It does not delete the parent Unity Catalog catalog, SQL Warehouses, clusters, Git folders, or external GPU environments. Named Databricks Apps, Jobs, and Serving endpoints can be deleted explicitly through optional cleanup fields.

## Repository layout

```text
DBO_Quant/
├── notebooks/
│   ├── 00_SETUP.py
│   ├── 01_INGEST_DATA.py
│   ├── 99_CLEANUP.py
│   ├── backtests/
│   ├── portfolio/
│   └── platform/
├── src/quant_platform/          shared engines and location discovery
├── sql/                         Unity Catalog schema and migrations
├── jobs/                        optional Lakeflow Job workers
├── serving/                     Model/Feature Serving helpers
├── databricks_app/              OpenBB API backend
├── gpu/nvidia_portfolio_optimization/
├── nvidia_bridge/               external GPU SQL write-back
└── tests/
```

Unity Catalog/Delta is the system of record. OpenBB ODP is the market-data abstraction. OpenBB Workspace is the analyst-facing UI.