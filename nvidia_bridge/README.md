# External Optimization Write-Back Bridge

This folder contains the internal Databricks SQL write-back adapter used by the remote/on-prem portfolio-optimization workflow.

Operators normally use the portfolio-optimization notebook rather than calling this package directly.

## Entry point

Run:

```text
optimization/portfolio_optimization/PORTFOLIO_OPTIMIZATION.ipynb
```

The external workflow uses this bridge after optimization completes.

## Data flow

```text
PORTFOLIO_OPTIMIZATION.ipynb
        ↓
CPU or GPU optimization
        ↓
Databricks SQL Warehouse
        ↓
external write-back bridge
        ↓
canonical DBO_Quant Unity Catalog tables
```

## Responsibilities

The bridge writes external optimization results into the same DBO_Quant schema used by Databricks-native optimization.

Supported result types include:

- optimization run metadata;
- Mean-CVaR efficient-frontier points;
- frontier allocations;
- selected portfolio allocations;
- covariance or correlation matrix entries;
- optimization backtest metrics;
- rebalancing run metadata;
- rebalancing events;
- rebalancing portfolio-value series.

CPU and GPU external runs use the same persistence model.

## Databricks connection

The external workflow connects through a Databricks SQL Warehouse.

Authentication supports:

- an existing Databricks profile; or
- OAuth U2M browser sign-in using a Databricks workspace URL and SQL Warehouse HTTP path.

After authentication, the workflow discovers the canonical DBO_Quant catalog/schema created by `notebooks/00_SETUP.py` unless an explicit location override is provided.

Do not store Databricks access tokens in source files.

## Result review

A successful external optimization returns an `optimization_run_id`.

Review it in Databricks with:

```text
notebooks/portfolio/03_OPTIMIZATION_RESULTS.py
```

or through OpenBB Workspace after the Databricks App is deployed.

To perform forward-risk validation of the selected allocation, use:

```text
notebooks/portfolio/02_MONTE_CARLO.py
source_type = optimization_run
source_id   = <optimization_run_id>
```

## Direct use

Direct use of the bridge is only required when integrating another external optimization process with the DBO_Quant persistence schema.