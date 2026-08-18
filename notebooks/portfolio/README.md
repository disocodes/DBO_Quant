# Portfolio analysis notebooks

Run `notebooks/00_SETUP.py` once and keep `notebooks/01_INGEST_DATA.py` current before using this folder.

## Flow

```text
Saved portfolio
00_SAVE_PORTFOLIO.py
      ↓
 portfolio_id
      ├─→ 02_MONTE_CARLO.py
      │
      └─→ 04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py
                ↓
        optimization_run_id
                ├─→ 03_OPTIMIZATION_RESULTS.py
                └─→ 02_MONTE_CARLO.py
                     source_type=optimization_run

Strategy notebook
../backtests/*.py
      ↓
    run_id
      ├─→ 01_COMPARE_RUNS.py
      └─→ 02_MONTE_CARLO.py
           source_type=strategy_run
```

## Notebook roles

### `00_SAVE_PORTFOLIO.py`
Creates or updates a portfolio using a persistent `portfolio_id` and dated holdings snapshots.

### `01_COMPARE_RUNS.py`
Compares two or more historical strategy runs and persists a common comparison.

### `02_MONTE_CARLO.py`
Forward-risk validation for an existing allocation. Sources are saved portfolios, strategy runs, optimization runs, or ad-hoc weights. It persists percentile curves and sample paths; it does not optimize weights.

### `03_OPTIMIZATION_RESULTS.py`
Reviews any persisted portfolio-optimization result. CPU and GPU runs use the same tables and IDs, so the operator does not need separate result notebooks.

### `04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py`
Runs Mean-CVaR portfolio optimization inside Databricks. Solver selection comes from:

```text
optimization/portfolio_optimization/portfolio_config.toml
```

The committed default is `solver = "cpu"`, using CVXPY + CLARABEL. Set `solver = "gpu"` to use CVXPY + NVIDIA cuOpt on compatible GPU compute.

## Remote/on-prem optimization

Use:

```text
optimization/portfolio_optimization/PORTFOLIO_OPTIMIZATION.ipynb
```

It uses the same configuration and writes the same result tables as the Databricks route.

## Recommended decision flow

```text
Current portfolio or strategy allocation
          ↓
Monte Carlo baseline
          ↓
optional portfolio optimization
          ↓
selected_optimal allocation
          ↓
Monte Carlo validation
          ↓
OpenBB comparison and review
```

## OpenBB outputs

The Databricks App exposes saved holdings, strategy comparison curves, Monte Carlo fan/sample-path charts, the Mean-CVaR efficient frontier, optimized allocation chart, optimizer metrics, and rebalancing outputs.
