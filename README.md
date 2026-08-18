# DBO_Quant

DBO_Quant is a Databricks quantitative-research platform built around OpenBB ODP, Unity Catalog/Delta, reusable strategy backtesting, Monte Carlo risk simulation, portfolio optimization, Databricks Jobs, and OpenBB Workspace.

## End-to-end workflow

```text
00_SETUP
   ↓
01_INGEST_DATA
   ↓
selected strategy notebook
   ↓
strategy run_id
   ↓
Monte Carlo — strategy allocation baseline
   ↓
portfolio optimization on the same strategy allocation/universe
   ├─ CPU: CVXPY + CLARABEL (default)
   └─ GPU: CVXPY + NVIDIA cuOpt
   ↓
optimization run_id
   ↓
Monte Carlo — optimized allocation
   ↓
persisted Unity Catalog results
   ↓
Databricks App
   ↓
OpenBB Workspace
```

The research components have distinct roles:

- **Backtest** — evaluates how a strategy behaved historically.
- **Monte Carlo** — evaluates the distribution of future outcomes for an existing allocation.
- **Portfolio optimization** — proposes an allocation for a Mean-CVaR objective.
- **Rebalancing** — repeatedly re-optimizes an allocation through time.
- **OpenBB Workspace** — displays persisted research results and curves.

## 1. First run

Run:

```text
notebooks/00_SETUP.py
notebooks/01_INGEST_DATA.py
```

`00_SETUP.py` uses an existing Unity Catalog catalog, creates the DBO_Quant schema/tables when missing, records the canonical namespace, and safely reuses it on reruns.

`01_INGEST_DATA.py` discovers that namespace and writes OpenBB market data to `prices_daily`. On Databricks serverless it installs its own pinned OpenBB ingestion dependencies before importing OpenBB, so it does not depend on another notebook session.

## 2. Strategy research

Built-in strategy notebooks are under:

```text
notebooks/backtests/
```

Each notebook contains strategy-specific logic and parameters while the common engine handles implementation lag, rebalancing, transaction costs, weight drift, metrics, holdings, and persistence.

To add a strategy, copy:

```text
notebooks/backtests/90_CUSTOM_STRATEGY_TEMPLATE.py
```

and keep the contract:

```python
def strategy(prices, params):
    return target_weights_dataframe
```

A completed strategy run persists a `run_id`. When executed as a Databricks Job task, the same ID is also published as the task value `strategy_run_id` for downstream workflow tasks.

## 3. Automated strategy flows

Use:

```text
notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py
```

The notebook creates a reusable Lakeflow Job around any selected strategy notebook, including custom strategies copied from the template.

Default job flow:

```text
refresh market data
      ↓
selected strategy
      ↓
Monte Carlo baseline using strategy_run_id
      ↓
portfolio optimization using the same strategy_run_id
      ↓
Monte Carlo using optimization_run_id
      ↓
persist results for OpenBB
```

This means the optimizer does not silently switch to an unrelated symbol basket: in the automated flow it uses the selected strategy's latest effective allocation as the reference portfolio and its active symbols as the optimization universe.

The committed defaults are:

- refresh market data: enabled;
- Monte Carlo: enabled before and after optimization;
- portfolio optimization: enabled;
- portfolio optimizer: **CPU**;
- Databricks App redeployment: disabled;
- schedule: manual `Run now` unless a Quartz cron expression is supplied.

To include automatic App redeployment at the end, set `include_app_deploy=true`. The final task uses `notebooks/platform/04_DEPLOY_APP_AUTOMATED.py` and deploys the existing Databricks App from the repository. The App and its required resources must already exist.

## 4. Saved portfolios

Use:

```text
notebooks/portfolio/00_SAVE_PORTFOLIO.py
```

A saved portfolio receives a persistent `portfolio_id` and dated holdings snapshots. Reuse the same `portfolio_id` when updating the portfolio.

## 5. Portfolio optimization

Portfolio optimization is solver-neutral at the operator level.

Databricks route:

```text
notebooks/portfolio/04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py
```

Remote/on-prem route:

```text
optimization/portfolio_optimization/PORTFOLIO_OPTIMIZATION.ipynb
```

Shared non-secret settings:

```text
optimization/portfolio_optimization/portfolio_config.toml
```

The committed solver setting is:

```toml
[execution]
solver = "cpu"
```

Solver modes:

- `cpu` — CVXPY + CLARABEL with CPU return/scenario computation; no GPU required.
- `gpu` — CVXPY + NVIDIA cuOpt with GPU return/scenario computation; requires a compatible NVIDIA/cuOpt environment.

The Databricks notebook can use the portfolio/symbols in `portfolio_config.toml`, or accept a `strategy_run` source so the optimization universe/reference allocation comes directly from a completed strategy run.

Both execution routes persist the same result tables and IDs. Review either type of run with:

```text
notebooks/portfolio/03_OPTIMIZATION_RESULTS.py
```

A successful run can persist an efficient frontier, selected allocation, covariance matrix, optimizer backtest metrics, and optional rebalancing output.

## 6. Monte Carlo forward-risk validation

Use:

```text
notebooks/portfolio/02_MONTE_CARLO.py
```

Supported allocation sources:

- `saved_portfolio` — latest holdings for a `portfolio_id`;
- `strategy_run` — latest effective allocation from a strategy `run_id`;
- `optimization_run` — `selected_optimal` allocation from an optimization run;
- `adhoc` — manually supplied weights.

Monte Carlo persists percentile curves, sample paths, terminal-value statistics, and probability of loss under the selected simulation assumptions.

## 7. OpenBB Workspace

Platform notebooks:

```text
notebooks/platform/01_SERVING.py
notebooks/platform/02_DEPLOY_APP.py
notebooks/platform/03_OPENBB_WORKSPACE.py
notebooks/platform/04_DEPLOY_APP_AUTOMATED.py
```

The Databricks App is the API backend; OpenBB Workspace remains the analyst-facing UI.

Persisted OpenBB visualizations include:

- strategy equity, benchmark, and drawdown curves;
- portfolio-comparison curves;
- Monte Carlo percentile fan chart;
- Monte Carlo sample paths;
- Mean-CVaR efficient frontier;
- optimized allocation bar chart;
- rebalancing portfolio-value curve;
- associated run, holdings, metrics, and event tables.

The default automated flow produces both a strategy-allocation Monte Carlo run and an optimized-allocation Monte Carlo run, so both can be inspected alongside the optimization frontier in OpenBB.

## 8. Optional Serving

`notebooks/platform/01_SERVING.py` is only for Model Serving or Feature Serving. Backtests, Monte Carlo, portfolio optimization, automated Jobs, and OpenBB result viewing do not require Serving.

## 9. Cleanup

Use:

```text
notebooks/99_CLEANUP.py
```

The notebook discovers the canonical DBO_Quant namespace and requires an exact confirmation phrase before destructive operations. It can drop the DBO_Quant schema with `CASCADE` and optionally delete explicitly named Apps, Jobs, Serving endpoints, and an Online Feature Store. Shared parent catalogs, SQL Warehouses, Git folders, and unrelated compute are not deleted automatically.

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
├── src/quant_platform/
├── optimization/portfolio_optimization/
├── nvidia_bridge/              internal external-writeback adapter
├── sql/
├── jobs/
├── serving/
├── databricks_app/
└── tests/
```

Unity Catalog/Delta is the system of record. OpenBB ODP is the market-data abstraction. OpenBB Workspace is the analyst-facing interface.
