# NVIDIA GPU portfolio workflow

Two execution routes are supported.

## Shared portfolio configuration

Both routes read non-secret research settings from:

```text
gpu/nvidia_portfolio_optimization/portfolio_config.toml
```

That file contains the saved `portfolio_id` or symbol universe plus optimizer, frontier and rebalancing settings. It is safe to keep in source control because it contains no credentials.

## Route A — Databricks GPU

Run:

```text
notebooks/portfolio/04_NVIDIA_GPU_DATABRICKS.py
```

on GPU-enabled Databricks Runtime ML compute.

This route requires **no `.env` file**, workspace URL, Databricks profile, OAuth login, or SQL Warehouse HTTP path. It uses the notebook's Databricks identity and native Spark/Unity Catalog access to read inputs and persist results.

For Unity Catalog access with Databricks Runtime ML, use Dedicated access mode. The notebook validates `nvidia-smi` and cuOpt before running.

## Route B — remote/on-prem GPU

Run:

```text
gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
```

in NVIDIA's Portfolio Optimization environment.

The external route needs a SQL Warehouse connection because it is outside Databricks. Authentication is resolved in this order:

1. A configured `DATABRICKS_PROFILE`, if present.
2. Otherwise workspace URL + SQL Warehouse HTTP path, followed by Databricks OAuth U2M interactive browser sign-in.

`.env` is optional. It can store the connection hints below so you are not prompted every run:

```dotenv
DATABRICKS_PROFILE=
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/...
DBO_CATALOG=your_catalog
DBO_SCHEMA=openbb_quant
```

If these values are missing, the external notebook prompts for the workspace URL, HTTP path and catalog. With no profile configured it then uses OAuth U2M, which performs real-time browser sign-in and consent. Do not put PATs or OAuth access tokens in `.env`.

## NVIDIA environment

Clone NVIDIA's project on the GPU host and install the CUDA extra that matches the runtime. For a CUDA 12 environment:

```bash
git clone https://github.com/NVIDIA-AI-Blueprints/portfolio-optimization.git
cd portfolio-optimization
uv sync --extra cuda12 --group notebooks
uv run python -m ipykernel install --user --name=portfolio-opt --display-name "Portfolio Optimization"
```

The DBO_Quant external route also needs `databricks-sdk` and `databricks-sql-connector` in that environment.

## Outputs

Either route can run Mean-CVaR optimization, efficient frontier generation, historical backtesting and optional monthly rebalancing. Results are written to the same Unity Catalog tables and exposed to OpenBB Workspace.

After a run, open:

```text
notebooks/portfolio/03_NVIDIA_RESULTS.py
```

and use the returned `optimization_run_id` and optional `rebalance_run_id`.
