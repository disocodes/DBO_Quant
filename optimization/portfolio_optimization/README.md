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

- `cpu` — CVXPY + CLARABEL with CPU returns/scenario generation; no GPU required.
- `gpu` — CVXPY + NVIDIA cuOpt with GPU returns/scenario generation; requires compatible NVIDIA GPU/cuOpt/cuML packages.

The upstream Portfolio Optimization project supports both CVXPY and cuOpt APIs. DBO_Quant keeps those backend details inside this implementation layer rather than encoding a vendor or device in operator notebook names.

## Databricks route

Run:

```text
notebooks/portfolio/04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py
```

The notebook uses Spark/Unity Catalog directly, discovers the canonical DBO_Quant namespace, and persists results to the same tables for CPU and GPU runs.

A fresh CPU/serverless session installs the verified upstream package revision used by this repository before running:

```text
efa60ce29b7351cfda8fd4c9afb94b9d7fce482c
```

Manual input defaults to `portfolio_config.toml`. The notebook can also be called with:

```text
source_type = strategy_run
source_id   = <run_id>
```

In that mode, the latest effective strategy allocation becomes the reference portfolio and its active symbols become the optimization universe. This is the mode used by the automated strategy workflow.

GPU mode requires compatible GPU compute plus the matching cuOpt/cuML CUDA packages; it does not silently fall back to CPU.

## Remote/on-prem route

Run:

```text
optimization/portfolio_optimization/PORTFOLIO_OPTIMIZATION.ipynb
```

The external route connects to Databricks through a SQL Warehouse. Authentication supports an existing Databricks profile or OAuth U2M browser sign-in.

For a reproducible CPU environment:

```bash
git clone https://github.com/NVIDIA-AI-Blueprints/portfolio-optimization.git
cd portfolio-optimization
git checkout efa60ce29b7351cfda8fd4c9afb94b9d7fce482c
uv sync --group notebooks
```

Install `databricks-sdk` and `databricks-sql-connector` in the same environment for DBO_Quant read/write access.

For GPU execution, install the CUDA extra that matches the host, for example `--extra cuda12`, together with the notebook group. Confirm the actual CUDA/cuOpt compatibility of the target host before running.

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
