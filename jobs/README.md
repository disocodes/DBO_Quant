# Databricks Job workers

Import these three `.py` files into the Databricks Workspace as **source notebooks**, then create one Lakeflow Job with a Notebook task for each. This matters because the workers use `dbutils.widgets` to read job/task parameters:

- `backtest_worker.py`: arbitrary weight-strategy backtests. Built-ins come from `src/quant_platform`; special adapters `factor_top_n` and `model_top_n` consume point-in-time factor or model prediction tables. The job contract exposes starting capital, fees/slippage, risk-free rate, long-only vs long/short, gross-leverage limits and strategy-specific JSON parameters.
- `monte_carlo_worker.py`: historical block bootstrap or multivariate-normal simulations, including configurable block size and persisted sample-path count.
- `comparison_worker.py`: builds a common-period persisted comparison from two or more existing strategy run IDs.

Configure the jobs to accept job parameters. Add them to the Databricks App as managed resources:

- `backtest_job` → `CAN MANAGE RUN`
- `monte_carlo_job` → `CAN MANAGE RUN`
- `comparison_job` → `CAN MANAGE RUN`

`app.yaml` resolves their numeric IDs through `valueFrom`. The App submits work and returns the Databricks run ID; heavy computation is not executed inside the App request process.

## Job parameter behavior

Define the worker parameters as job-level parameters (or notebook-task base parameters). Databricks pushes job parameters into notebook tasks; an API `run_now` override takes precedence. The App uses that mechanism so the same worker can run many strategy, portfolio, date-range, leverage, fee, and model configurations without creating a new Job definition.
