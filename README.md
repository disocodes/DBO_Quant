# DBO_Quant

DBO_Quant is a Databricks-based quantitative research platform that combines OpenBB market data, Unity Catalog/Delta persistence, reusable strategy backtesting, Monte Carlo simulation, portfolio optimization, Databricks Jobs, and OpenBB Workspace.

## System workflow

```text
00_SETUP
   ↓
01_INGEST_DATA
   ↓
strategy research
   ↓
strategy_run_id
   ↓
Monte Carlo baseline
   ↓
portfolio optimization
   ↓
optimization_run_id
   ↓
Monte Carlo on optimized allocation
   ↓
Unity Catalog / Delta
   ↓
Databricks App
   ↓
OpenBB Workspace
```

The components have separate responsibilities:

- **Backtesting** evaluates a strategy against historical market data.
- **Monte Carlo** simulates possible future portfolio paths for an existing allocation.
- **Portfolio optimization** calculates candidate allocations for a Mean-CVaR objective.
- **Rebalancing** repeatedly re-optimizes an allocation through time when enabled.
- **Unity Catalog/Delta** is the persistent system of record.
- **OpenBB Workspace** is the analyst-facing interface for persisted results and charts.

## 1. Initial setup

Run the following Databricks notebooks in order:

```text
notebooks/00_SETUP.py
notebooks/01_INGEST_DATA.py
```

`00_SETUP.py` requires an existing Unity Catalog catalog. It creates the DBO_Quant schema and managed tables inside that catalog, records the canonical deployment location, and safely reuses the same namespace on reruns.

`01_INGEST_DATA.py` discovers the canonical namespace and loads OpenBB market data into `prices_daily`. The notebook installs its required OpenBB packages in its own Databricks session before importing OpenBB.

## 2. Strategy research

Strategy notebooks are located in:

```text
notebooks/backtests/
```

Each strategy notebook defines strategy-specific logic and parameters. The shared engine in `src/quant_platform/` handles execution rules, implementation lag, rebalancing, transaction costs, weight drift, performance metrics, holdings, benchmark comparison, and persistence.

A successful strategy run creates a `run_id` and writes its results to Unity Catalog.

To create a custom strategy, copy:

```text
notebooks/backtests/90_CUSTOM_STRATEGY_TEMPLATE.py
```

and implement the standard strategy interface:

```python
def strategy(prices, params):
    return target_weights_dataframe
```

The returned DataFrame uses dates as the index, asset symbols as columns, and target portfolio weights as values.

## 3. Automated strategy workflows

Use:

```text
notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py
```

This notebook creates or updates a Databricks Lakeflow Job around any built-in or custom strategy notebook.

The default automated flow is:

```text
refresh market data
      ↓
selected strategy
      ↓
Monte Carlo — strategy allocation
      ↓
portfolio optimization
      ↓
Monte Carlo — optimized allocation
      ↓
persisted results
      ↓
optional Databricks App redeployment
```

The optimizer receives the selected strategy's latest effective allocation and active asset universe. The strategy and optimization run identifiers are passed between Job tasks with Databricks task values.

Default workflow settings:

```text
refresh market data      enabled
strategy Monte Carlo     enabled
portfolio optimization   enabled
optimized Monte Carlo    enabled
optimizer solver         CPU
App redeployment         disabled
schedule                 manual Run now
```

A Quartz cron expression can be supplied when scheduled execution is required.

## 4. Saved portfolios

Use:

```text
notebooks/portfolio/00_SAVE_PORTFOLIO.py
```

A saved portfolio receives a persistent `portfolio_id` and dated holdings snapshots. Reuse the same `portfolio_id` when updating an existing portfolio.

Saved portfolios can be used directly by Monte Carlo or portfolio optimization.

## 5. Portfolio analysis

Portfolio notebooks are located in:

```text
notebooks/portfolio/
```

Main workflow:

```text
00_SAVE_PORTFOLIO.py          save/update holdings
01_COMPARE_RUNS.py            compare strategy backtests
02_MONTE_CARLO.py             simulate portfolio outcomes
03_OPTIMIZATION_RESULTS.py    inspect persisted optimization results
04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py
                              run Mean-CVaR optimization in Databricks
```

### Monte Carlo sources

`02_MONTE_CARLO.py` supports:

- `saved_portfolio` — latest holdings for a `portfolio_id`;
- `strategy_run` — latest effective allocation from a strategy `run_id`;
- `optimization_run` — `selected_optimal` allocation from an `optimization_run_id`;
- `adhoc` — manually supplied symbols and weights.

Monte Carlo persists percentile curves, sample paths, terminal-value statistics, and summary risk measures.

## 6. Portfolio optimization

Databricks execution:

```text
notebooks/portfolio/04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py
```

Remote or on-prem execution:

```text
optimization/portfolio_optimization/PORTFOLIO_OPTIMIZATION.ipynb
```

Shared configuration:

```text
optimization/portfolio_optimization/portfolio_config.toml
```

Default solver:

```toml
[execution]
solver = "cpu"
```

Supported modes:

- `cpu` — CVXPY + CLARABEL with CPU scenario generation;
- `gpu` — CVXPY + NVIDIA cuOpt with GPU scenario generation.

CPU and GPU runs persist the same result schema and use the same result-review notebook.

Optimization outputs include:

- optimization run metadata;
- Mean-CVaR efficient-frontier points;
- frontier allocations;
- the `selected_optimal` allocation;
- covariance matrix entries;
- historical optimizer backtest metrics;
- optional rebalancing results.

## 7. OpenBB Workspace

The Databricks App under `databricks_app/` is the API backend used by OpenBB Workspace.

Platform notebooks are located in:

```text
notebooks/platform/
```

Use:

```text
02_DEPLOY_APP.py             guided App deployment preparation
03_OPENBB_WORKSPACE.py       verify the backend and OpenBB connection
04_DEPLOY_APP_AUTOMATED.py   optional Job-driven App redeployment
```

Persisted OpenBB visualizations include:

- strategy equity, benchmark, and drawdown curves;
- portfolio-comparison curves;
- Monte Carlo percentile fan charts;
- Monte Carlo sample paths;
- Mean-CVaR efficient frontier;
- optimized allocation chart;
- portfolio rebalancing value curve;
- associated holdings, runs, metrics, and events.

## 8. Optional serving

Model Serving and Feature Serving are optional and are not required for ordinary strategy research, Monte Carlo, portfolio optimization, Jobs, or OpenBB display of persisted results.

Use:

```text
notebooks/platform/01_SERVING.py
```

only when low-latency model inference or online feature lookup is required.

## 9. Cleanup

Use:

```text
notebooks/99_CLEANUP.py
```

The cleanup notebook discovers the canonical DBO_Quant namespace and requires an exact confirmation phrase before destructive operations.

It can remove:

- the DBO_Quant schema and contained tables;
- explicitly named Databricks Apps;
- explicitly supplied Job IDs;
- explicitly named Serving endpoints;
- an explicitly named Online Feature Store.

It does not automatically delete the parent Unity Catalog catalog, SQL Warehouses, Git folders, shared compute, or unrelated workspace resources.

## Repository layout

```text
DBO_Quant/
├── notebooks/
│   ├── 00_SETUP.py
│   ├── 01_INGEST_DATA.py
│   ├── 99_CLEANUP.py
│   ├── backtests/
│   ├── portfolio/
│   ├── workflows/
│   └── platform/
├── src/quant_platform/                  shared research engine
├── optimization/portfolio_optimization/ portfolio optimization integration
├── nvidia_bridge/                       external optimization write-back adapter
├── databricks_app/                      OpenBB API backend
├── jobs/                                optional API-triggered workers
├── serving/                             optional model/feature serving helpers
├── sql/                                 Unity Catalog schema and migrations
└── tests/
```

For subsystem-specific instructions, use the README in the corresponding directory.