# NVIDIA external write-back bridge

This implementation folder is used only by the remote/on-prem NVIDIA GPU route.

The Databricks GPU route does not use this bridge; it reads and writes Unity Catalog directly with Spark.

## External workflow

```text
DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
        ↓
Databricks SQL Warehouse
        ↓
nvidia_bridge
        ↓
canonical DBO_Quant Unity Catalog tables
```

The bridge persists:

- optimization run metadata;
- efficient-frontier points;
- frontier and selected allocations;
- covariance/correlation matrix entries;
- optimizer backtest metrics;
- rebalancing runs, events, and portfolio-value series.

The external workflow discovers the canonical DBO_Quant namespace after authenticating to Databricks.

## Authentication

Use either:

- an existing Databricks profile; or
- OAuth U2M interactive browser sign-in using the workspace URL and SQL Warehouse HTTP path.

Do not hard-code Databricks access tokens in source files.

## Normal entry point

Do not invoke the bridge directly for ordinary use. Start with:

```text
gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
```

Then review the returned `optimization_run_id` with `notebooks/portfolio/03_NVIDIA_RESULTS.py` or OpenBB Workspace.