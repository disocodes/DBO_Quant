# NVIDIA GPU portfolio optimization

This folder implements the optional NVIDIA portfolio-optimization workflow used by DBO_Quant.

## Purpose

The NVIDIA workflow answers:

> Given a portfolio universe and a Mean-CVaR objective, what allocation should be considered, and how would repeated optimization/rebalancing behave?

It does not replace Monte Carlo. After optimization, use `notebooks/portfolio/02_MONTE_CARLO.py` with `source_type=optimization_run` to evaluate the optimized allocation under forward simulation.

## Shared research configuration

Both execution routes use:

```text
gpu/nvidia_portfolio_optimization/portfolio_config.toml
```

This file contains non-secret portfolio and optimizer settings such as:

- saved `portfolio_id` or symbol universe;
- risk aversion;
- confidence level;
- number of scenarios;
- efficient-frontier points;
- optional rebalancing settings.

## Route A — Databricks GPU

Run:

```text
notebooks/portfolio/04_NVIDIA_GPU_DATABRICKS.py
```

on compatible GPU-enabled Databricks Runtime ML compute.

This route:

- requires no `.env` file;
- requires no workspace URL or SQL Warehouse path;
- uses the notebook identity and Spark/Unity Catalog directly;
- discovers the canonical DBO_Quant namespace created by `00_SETUP.py`;
- writes optimization results directly back to Unity Catalog.

The notebook validates the NVIDIA runtime and cuOpt before analysis.

## Route B — remote/on-prem GPU

Run:

```text
gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
```

inside NVIDIA's Portfolio Optimization environment.

The external route connects to Databricks through a SQL Warehouse. Authentication supports:

1. an existing Databricks profile; or
2. workspace URL + SQL Warehouse HTTP path followed by OAuth U2M browser sign-in.

A local `.env` file is optional and may hold only connection hints. Do not place PATs or OAuth tokens in source control.

After authentication, the external workflow discovers the canonical DBO_Quant namespace instead of requiring the catalog/schema to be repeated manually.

## NVIDIA environment

Install NVIDIA's current `portfolio-optimization` project and a CUDA extra compatible with the target GPU runtime. For a CUDA 12 environment, the typical setup is:

```bash
git clone https://github.com/NVIDIA-AI-Blueprints/portfolio-optimization.git
cd portfolio-optimization
uv sync --extra cuda12 --group notebooks
uv run python -m ipykernel install --user --name=portfolio-opt --display-name "Portfolio Optimization"
```

The external DBO_Quant route also requires `databricks-sdk` and `databricks-sql-connector` in the environment.

## Outputs

A successful optimization can persist:

- optimization run metadata;
- Mean-CVaR efficient-frontier points;
- frontier allocations;
- `selected_optimal` allocation;
- covariance matrix entries;
- historical optimizer backtest metrics;
- optional rebalancing runs, events, and portfolio-value series.

The run returns an `optimization_run_id` and, when rebalancing is enabled, a `rebalance_run_id`.

## Next steps

Review the optimizer result:

```text
notebooks/portfolio/03_NVIDIA_RESULTS.py
```

Then validate the selected allocation with Monte Carlo:

```text
notebooks/portfolio/02_MONTE_CARLO.py
source_type = optimization_run
source_id   = <optimization_run_id>
```

After the Databricks App is deployed, OpenBB Workspace can display the Mean-CVaR frontier, optimized allocation chart, optimizer metrics, and rebalancing value curve.