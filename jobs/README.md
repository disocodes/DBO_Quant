# Databricks Job Workers

This folder contains optional production workers that execute individual DBO_Quant calculations as Databricks Jobs.

Use these workers when an API or external process should trigger a specific calculation. For the complete scheduled strategy pipeline, use the multi-task workflow under `notebooks/workflows/` instead.

## Worker map

```text
backtest_worker.py
    execute a strategy backtest

monte_carlo_worker.py
    execute a Monte Carlo simulation

comparison_worker.py
    compare existing strategy runs
```

## `backtest_worker.py`

Runs a target-weight strategy through the shared DBO_Quant backtest engine.

It supports the same execution model used by the interactive strategy notebooks, including transaction costs, rebalancing, implementation lag, metrics, and persistence.

## `monte_carlo_worker.py`

Runs portfolio simulations using the shared Monte Carlo engine.

Supported simulation methods include:

- historical block bootstrap;
- multivariate normal simulation.

The worker can persist:

- Monte Carlo run metadata;
- percentile curves;
- sample paths;
- summary statistics.

## `comparison_worker.py`

Builds a persisted comparison from two or more existing strategy `run_id` values over their common analysis period.

It writes comparison metadata, metrics, members, and daily comparison curves.

## Job parameters

The workers use Databricks notebook/job parameters through `dbutils.widgets`.

Configure the required parameters in the Job definition or supply them when triggering the Job.

## OpenBB-triggered workers

The Databricks App can trigger these dedicated Jobs through API endpoints.

When enabled, configure:

```text
BACKTEST_JOB_ID
MONTE_CARLO_JOB_ID
COMPARISON_JOB_ID
```

and grant the App identity permission to run the corresponding Jobs.

The App submits the Job and returns the Databricks run identifier while computation remains outside the App request process.

## End-to-end strategy workflow

For a complete strategy pipeline, use:

```text
notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py
```

That workflow can run:

```text
market-data refresh
      ↓
selected strategy
      ↓
Monte Carlo baseline
      ↓
portfolio optimization
      ↓
Monte Carlo on optimized allocation
      ↓
optional App redeployment
```

The multi-task workflow does not require these individual worker files.

## Cleanup

If dedicated worker Jobs were created for DBO_Quant, supply their Job IDs to:

```text
notebooks/99_CLEANUP.py
```

for explicit deletion.