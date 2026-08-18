# Portfolio Optimization

This folder contains the shared Mean-CVaR portfolio-optimization integration used by both Databricks and remote/on-prem execution.

## Purpose

Portfolio optimization receives an asset universe and portfolio context and calculates candidate allocations for a Mean-CVaR objective.

It complements, rather than replaces, the other research components:

```text
historical strategy or portfolio allocation
          ↓
portfolio optimization
          ↓
selected_optimal allocation
          ↓
Monte Carlo validation
```

## Shared configuration

Both execution routes use:

```text
optimization/portfolio_optimization/portfolio_config.toml
```

Default solver:

```toml
[execution]
solver = "cpu"
```

Supported modes:

- `cpu` — CVXPY + CLARABEL with CPU return/scenario processing;
- `gpu` — CVXPY + NVIDIA cuOpt with GPU return/scenario processing.

GPU mode requires a compatible NVIDIA runtime and the corresponding cuOpt/cuML packages. GPU execution does not silently fall back to CPU.

## Databricks execution

Run:

```text
notebooks/portfolio/04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py
```

The notebook:

1. installs the pinned upstream Portfolio Optimization package revision required by the workflow;
2. discovers the canonical DBO_Quant Unity Catalog namespace;
3. resolves the portfolio or strategy allocation to optimize;
4. loads the required price history;
5. runs Mean-CVaR optimization;
6. optionally runs dynamic rebalancing;
7. persists the results to Unity Catalog;
8. publishes `optimization_run_id` as a Databricks task value when running inside a Job.

### Manual source

Without Job parameters, the notebook uses the portfolio/symbol configuration in `portfolio_config.toml`.

### Strategy-run source

The notebook also accepts:

```text
source_type = strategy_run
source_id   = <run_id>
```

In this mode, the strategy's latest effective allocation becomes the reference portfolio and the active strategy symbols become the optimization universe.

This is the source mode used by the automated strategy workflow.

## Remote or on-prem execution

Run:

```text
optimization/portfolio_optimization/PORTFOLIO_OPTIMIZATION.ipynb
```

The external notebook uses a Databricks SQL Warehouse to read DBO_Quant inputs and persist results.

Authentication supports:

- an existing Databricks profile; or
- OAuth U2M browser authentication using the workspace URL and SQL Warehouse HTTP path.

The canonical DBO_Quant catalog/schema is discovered after authentication unless an explicit override is supplied.

### CPU environment

Install the upstream Portfolio Optimization package and its notebook dependencies in a Python environment with CVXPY/CLARABEL available.

### GPU environment

Install the CUDA extra matching the target host together with the notebook dependencies and confirm cuOpt/cuML compatibility before execution.

## Outputs

CPU and GPU execution write the same result model:

```text
optimization_runs
    run metadata

efficient_frontier
    Mean-CVaR frontier points

optimal_allocations
    frontier allocations and selected_optimal weights

optimization_matrix_entries
    covariance matrix entries

optimization_backtest_metrics
    historical optimizer backtest metrics

optimization_rebalance_runs
optimization_rebalance_events
optimization_rebalance_daily
    optional dynamic-rebalancing results
```

A successful optimization returns an `optimization_run_id`. Rebalancing also returns a `rebalance_run_id` when enabled.

## Review results

Use:

```text
notebooks/portfolio/03_OPTIMIZATION_RESULTS.py
```

for Databricks-side review.

To validate the selected allocation with Monte Carlo, run:

```text
notebooks/portfolio/02_MONTE_CARLO.py
source_type = optimization_run
source_id   = <optimization_run_id>
```

## OpenBB outputs

After the Databricks App is deployed, OpenBB Workspace can display:

- Mean-CVaR efficient frontier;
- optimized allocation chart;
- optimization run metadata;
- historical optimization backtest metrics;
- optional rebalancing events;
- optional rebalancing portfolio-value curve.