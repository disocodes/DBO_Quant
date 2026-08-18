# NVIDIA write-back bridge

This is an implementation folder used by the standalone workflow in `gpu/nvidia_portfolio_optimization/`.

Normal operation starts with:

```text
gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
```

The bridge writes NVIDIA optimizer output through a Databricks SQL Warehouse into the canonical DBO_Quant tables:

- optimization runs and efficient-frontier points
- frontier and selected portfolio allocations
- covariance/correlation matrices
- optimizer backtest metrics
- rebalancing runs, events and cumulative portfolio values

NVIDIA's current efficient-frontier workflow returns asset allocations in a dictionary-valued `weights` column. The GPU runner expands those dictionaries and uses `push_allocation()` for each frontier point.

Use Databricks unified authentication on the GPU host through a profile or service principal. Do not hard-code tokens in source files.
