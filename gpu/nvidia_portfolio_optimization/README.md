# NVIDIA GPU portfolio workflow

This folder is optional. Use it when an NVIDIA GPU with cuOpt is available on an on-prem or remote Linux machine.

## What it does

The derived notebook reads prices and, optionally, a saved portfolio directly from DBO_Quant in Databricks. It then uses NVIDIA's official `NVIDIA-AI-Blueprints/portfolio-optimization` package to run Mean-CVaR optimization, a 25-point efficient frontier, historical backtesting, and optional monthly rebalancing. Results are written back to the DBO_Quant optimization tables and become available through the OpenBB App.

## One-time GPU environment setup

```bash
git clone https://github.com/NVIDIA-AI-Blueprints/portfolio-optimization.git
cd portfolio-optimization

# Match the CUDA runtime on the GPU host.
uv sync --extra cuda12 --group notebooks
# or: uv sync --extra cuda13 --group notebooks

uv run python -m ipykernel install --user --name=portfolio-opt --display-name "Portfolio Optimization"
uv run jupyter lab
```

Also clone `DBO_Quant` on the same machine, or otherwise make this repository available to Jupyter. The notebook needs the DBO_Quant `gpu/` and `nvidia_bridge/` modules.

Install the Databricks client packages into the NVIDIA environment if they are not already present:

```bash
uv pip install databricks-sdk databricks-sql-connector
```

Authenticate the GPU machine with Databricks unified authentication, for example with a Databricks CLI profile or service principal. Do not hard-code access tokens into the notebook.

## Run

Open `DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb` using the **Portfolio Optimization** kernel.

Fill in:

- Databricks SQL Warehouse `HTTP_PATH`
- `CATALOG` and `SCHEMA`
- either `PORTFOLIO_ID` or `SYMBOLS`
- optional Databricks `PROFILE`
- optimizer and rebalancing settings

Run cells in order. Rebalancing is disabled by default because it is substantially more GPU-intensive than a single optimization/frontier run.

At the end the notebook prints `optimization_run_id` and, when enabled, `rebalance_run_id`.

## Back in Databricks

Open `notebooks/portfolio/03_NVIDIA_RESULTS.py`, paste the run ID, and verify the frontier, allocations, backtest metrics and rebalancing output. The same records are exposed to OpenBB Workspace by the Databricks App.

## NVIDIA source workflow

This integration follows the current NVIDIA examples for `cvar_basic.ipynb`, `efficient_frontier.ipynb`, and `rebalancing_strategies.ipynb`. NVIDIA remains the source of truth for cuOpt/CUDA installation and the optimizer APIs.