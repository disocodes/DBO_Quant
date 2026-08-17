# NVIDIA portfolio-optimization → Databricks bridge

This folder is for the **separate GPU notebook on your computer** using NVIDIA's `portfolio-optimization` blueprint.

The bridge does not modify NVIDIA's optimizer. After the NVIDIA notebook returns its efficient-frontier result DataFrame, call `DatabricksOptimizationBridge.push_efficient_frontier(...)`. It writes the canonical `optimization_runs`, `efficient_frontier`, optional `optimal_allocations`, and ingestion-log tables through your Databricks SQL Warehouse.

The adapter intentionally maps common NVIDIA result fields (`return`, `CVaR`, `obj`, `risk_aversion`, `variance`, `volatility`, `sharpe`, `solver`, `regime`, solve time) instead of depending on one exact notebook revision. If your result includes asset weights as columns, pass those column names explicitly via `weight_columns=[...]`. If the notebook returns the selected weight vector separately, call `push_allocation(...)` with the same `optimization_run_id`. Covariance/correlation/other labelled matrices use `push_matrix(...)`.

## Authentication

Use Databricks unified authentication on your computer (`databricks auth login`, a configured profile, or a service principal). Do not put a personal access token in this file.
