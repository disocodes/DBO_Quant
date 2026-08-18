# External optimization write-back bridge

This is an internal implementation folder used by the remote/on-prem portfolio-optimization route. Operators normally start from the neutral portfolio-optimization notebook rather than invoking this bridge directly.

## External workflow

```text
optimization/portfolio_optimization/PORTFOLIO_OPTIMIZATION.ipynb
        ↓
CPU or GPU optimization backend
        ↓
Databricks SQL Warehouse
        ↓
write-back bridge
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

The external workflow discovers the canonical DBO_Quant namespace after authenticating to Databricks. Both CPU and GPU routes write the same schema.

## Authentication

Use either:

- an existing Databricks profile; or
- OAuth U2M interactive browser sign-in using the workspace URL and SQL Warehouse HTTP path.

Do not hard-code Databricks access tokens in source files.

## Normal entry point

Run:

```text
optimization/portfolio_optimization/PORTFOLIO_OPTIMIZATION.ipynb
```

Then review the returned `optimization_run_id` with:

```text
notebooks/portfolio/03_OPTIMIZATION_RESULTS.py
```

or OpenBB Workspace.
