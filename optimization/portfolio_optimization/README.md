# Portfolio optimization

This folder contains DBO_Quant's optional Mean-CVaR portfolio-optimization workflow.

## Purpose

Portfolio optimization answers:

> Given a portfolio universe and risk objective, what allocation should be considered?

It does not replace backtesting or Monte Carlo. A typical decision flow is:

```text
current portfolio or strategy allocation
          ↓
portfolio optimization
          ↓
selected_optimal allocation
          ↓
Monte Carlo forward-risk validation
```

## Shared configuration

Both Databricks and external runs read:

```text
optimization/portfolio_optimization/portfolio_config.toml
```

The committed default is CPU:

```toml
[execution]
solver = "cpu"
```

Supported solver modes:

- `cpu` — CVXPY + CLARABEL. CPU return/scenario computation; no GPU required.
- `gpu` — CVXPY + NVIDIA cuOpt. Requires a compatible NVIDIA GPU/cuOpt environment.

The underlying NVIDIA Portfolio Optimization project supports both CVXPY and cuOpt APIs; DBO_Quant keeps that backend detail inside this implementation layer rather than in operator notebook names.

## Databricks route

Run:

```text
notebooks/portfolio/04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py
```

The notebook uses Spark/Unity Catalog directly, discovers the canonical DBO_Quant namespace, reads prices/holdings, runs the selected solver, and persists results.

CPU mode can run on ordinary Databricks CPU compute. GPU mode requires compatible GPU compute and the required NVIDIA/cuOpt packages.

## Remote/on-prem route

Run:

```text
optimization/portfolio_optimization/PORTFOLIO_OPTIMIZATION.ipynb
```

The external route connects to Databricks through a SQL Warehouse. Authentication supports an existing Databricks profile or OAuth U2M browser sign-in.

CPU mode can run on a normal workstation/server with the NVIDIA Portfolio Optimization Python environment and CVXPY/CLARABEL available. GPU mode additionally requires a compatible NVIDIA/cuOpt environment.

## Outputs

Both routes write the same DBO_Quant result model:

- `optimization_runs`;
- `efficient_frontier`;
- `optimal_allocations`;
- `optimization_matrix_entries`;
- `optimization_backtest_metrics`;
- optional `optimization_rebalance_*` tables.

Each successful run returns an `optimization_run_id` and, when rebalancing is enabled, a `rebalance_run_id`.

Review results with:

```text
notebooks/portfolio/03_OPTIMIZATION_RESULTS.py
```

Validate the selected allocation with:

```text
notebooks/portfolio/02_MONTE_CARLO.py
source_type = optimization_run
source_id   = <optimization_run_id>
```

OpenBB Workspace can display the efficient frontier, optimized allocation chart, optimizer metrics, and rebalancing value curve after the Databricks App is deployed.
