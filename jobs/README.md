# Databricks Job workers

These workers are optional production execution paths. Interactive research starts with the notebooks under `notebooks/`; create Jobs when calculations should be launched repeatedly, scheduled, or triggered from the OpenBB-facing App.

For a complete scheduled strategy workflow rather than individual workers, use:

```text
notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py
```

## Workers

### `backtest_worker.py`
Runs arbitrary target-weight strategy backtests using the shared DBO_Quant engine. Built-in strategies come from `src/quant_platform/`; additional adapters can consume point-in-time factor snapshots or model predictions.

### `monte_carlo_worker.py`
Runs historical-block-bootstrap or multivariate-normal portfolio simulations with configurable horizon, simulation count, rebalancing interval, block size, and persisted sample paths.

### `comparison_worker.py`
Builds a persisted common-period comparison from two or more existing strategy `run_id` values.

## Deployment

Create one Lakeflow Job/Notebook task for each worker needed by the API. The workers use `dbutils.widgets` for job parameters, so configure job-level parameters or notebook-task base parameters.

When OpenBB forms should trigger calculations, grant the Databricks App the required Job permission and configure:

```text
BACKTEST_JOB_ID
MONTE_CARLO_JOB_ID
COMPARISON_JOB_ID
```

The App submits the Job and returns the Databricks run ID. Heavy research computation remains outside the App request process.

## End-to-end strategy automation

`notebooks/workflows/00_CONFIGURE_STRATEGY_FLOW.py` creates a separate multi-task research Job that can refresh data, execute any selected strategy notebook, pass its generated `strategy_run_id` into Monte Carlo, run CPU-default portfolio optimization, and optionally redeploy the OpenBB backend.

## When these individual workers are not needed

You do not need these worker Jobs to run interactive strategy notebooks, run the portfolio Monte Carlo notebook, run portfolio optimization, use the multi-task strategy automation flow, or review already-persisted results in OpenBB.

## Cleanup

If Jobs were created specifically for DBO_Quant, their IDs can be supplied to `notebooks/99_CLEANUP.py` for explicit deletion.
