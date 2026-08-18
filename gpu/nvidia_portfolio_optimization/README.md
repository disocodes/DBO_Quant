# NVIDIA GPU portfolio workflow

This workflow has **two supported execution routes**:

1. **Databricks GPU compute** — run `notebooks/portfolio/04_NVIDIA_GPU_DATABRICKS.py` on GPU-enabled Databricks Runtime ML compute.
2. **Remote/on-prem GPU** — run `gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb` in NVIDIA's Portfolio Optimization environment.

Both routes use the same DBO_Quant data model, the same NVIDIA `portfolio_optimization` APIs, the same `.env` configuration, and write to the same Unity Catalog result tables.

## Shared configuration

Copy the repository template once:

```bash
cp .env.example .env
```

Then edit the GPU section:

```dotenv
DATABRICKS_PROFILE=
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/...
DBO_CATALOG=your_catalog
DBO_SCHEMA=openbb_quant
DBO_PORTFOLIO_ID=
DBO_SYMBOLS=SPY,QQQ,IEF,GLD
DBO_RISK_AVERSION=1.0
DBO_CONFIDENCE=0.95
DBO_NUM_SCENARIOS=10000
DBO_FRONTIER_POINTS=25
DBO_RUN_REBALANCING=false
DBO_TRANSACTION_COST_FACTOR=0.0
DBO_LOOK_BACK_WINDOW=126
DBO_LOOK_FORWARD_WINDOW=21
DBO_PUSH_RESULTS=true
```

`.env` is ignored by Git. Environment variables override values in the file. Do not store PATs, OAuth tokens, or provider secrets in the committed `.env.example`.

## Route A — Databricks GPU

Use GPU-enabled Databricks compute with **Databricks Runtime ML** and Dedicated access mode when accessing Unity Catalog.

Open:

```text
notebooks/portfolio/04_NVIDIA_GPU_DATABRICKS.py
```

The notebook checks `nvidia-smi` and validates that NVIDIA cuOpt is actually available before running.

The NVIDIA project currently supports Python 3.11–3.13 and provides a `cuda12` dependency set containing cuOpt/cuML 26.6. Databricks Runtime 18 LTS ML currently uses CUDA 12.9, so the CUDA 12 NVIDIA dependency set is the appropriate starting point for that runtime. Install NVIDIA's package/runtime on the GPU compute before executing the workflow, following the upstream NVIDIA installation requirements.

The Databricks route still uses the configured SQL Warehouse for the DBO_Quant bridge. This keeps read/write behavior identical to the remote route and avoids maintaining two persistence implementations.

## Route B — remote/on-prem GPU

Clone NVIDIA's project on the GPU host:

```bash
git clone https://github.com/NVIDIA-AI-Blueprints/portfolio-optimization.git
cd portfolio-optimization

# Match the CUDA runtime on the host.
uv sync --extra cuda12 --group notebooks
# or, where appropriate:
# uv sync --extra cuda13 --group notebooks

uv run python -m ipykernel install --user --name=portfolio-opt --display-name "Portfolio Optimization"
uv run jupyter lab
```

Also clone `DBO_Quant` on the same machine and install the Databricks clients if needed:

```bash
uv pip install databricks-sdk databricks-sql-connector
```

Authenticate using Databricks unified authentication, for example a configured profile or service principal.

Open:

```text
gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
```

## What either route does

The workflow can:

- read DBO_Quant prices through the configured SQL Warehouse
- optionally load the latest holdings for a saved `portfolio_id`
- run NVIDIA Mean-CVaR optimization with cuOpt
- generate an efficient frontier
- backtest the optimized allocation against equal weight and the saved current portfolio
- optionally run monthly dynamic rebalancing
- push frontier points, allocations, covariance data, backtest metrics and rebalancing output back to Unity Catalog

Rebalancing is disabled by default because it performs repeated optimization and is substantially more GPU-intensive than a single optimization/frontier run.

## After either route finishes

The workflow prints:

```text
optimization_run_id = ...
rebalance_run_id = ...
```

Back in Databricks, open:

```text
notebooks/portfolio/03_NVIDIA_RESULTS.py
```

Paste the run ID to review the frontier, allocations, backtest metrics and rebalancing results. The same records are exposed through the OpenBB Workspace backend.

## NVIDIA source workflow

The integration follows NVIDIA's current `cvar_basic.ipynb`, `efficient_frontier.ipynb`, `rebalancing_strategies.ipynb`, and `portfolio_optimization` package APIs. NVIDIA remains the source of truth for cuOpt/CUDA compatibility and installation.
