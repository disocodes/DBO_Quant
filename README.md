# DBO_Quant

DBO_Quant is a Databricks quantitative-research platform using OpenBB ODP for financial data access, Delta/Unity Catalog for storage, a reusable target-weight backtest engine, Databricks Serving for model/feature inference, and OpenBB Workspace as the research UI.

## First run

Clone this repository into a Databricks Git folder, then run:

```text
notebooks/00_SETUP.py
        ↓
notebooks/01_INGEST_DATA.py
```

`00_SETUP.py` installs the Databricks-side dependencies and applies every SQL migration in `sql/`. `01_INGEST_DATA.py` loads price history through OpenBB ODP into the canonical `prices_daily` table.

After those two steps, choose the workflow you need. Setup does not need to be rerun for ordinary research.

## Strategy backtesting

Each strategy has its own notebook under `notebooks/backtests/`.

```text
notebooks/backtests/
├── 01_FIXED_ALLOCATION.py
├── 02_INVERSE_VOLATILITY.py
├── 03_MOVING_AVERAGE_TREND.py
├── 04_TIME_SERIES_MOMENTUM.py
├── 05_CROSS_SECTIONAL_MOMENTUM.py
├── 06_MEAN_REVERSION.py
├── 07_DUAL_MOMENTUM.py
├── 08_BUY_AND_HOLD.py
└── 90_CUSTOM_STRATEGY_TEMPLATE.py
```

A strategy notebook contains only its research logic and parameters. All notebooks use the same engine for implementation lag, rebalancing, transaction costs, weight drift, performance metrics, holdings and persistence.

Every completed backtest produces a `run_id` and writes to the common strategy result tables.

### Add a new strategy

1. Copy `notebooks/backtests/90_CUSTOM_STRATEGY_TEMPLATE.py`.
2. Rename the copy, for example `20_VALUE_MOMENTUM.py`.
3. Edit the strategy function and parameter widgets.
4. Keep this contract:

```python
def strategy(prices, params):
    return target_weights_dataframe
```

The returned DataFrame must use dates as the index and asset symbols as columns. Values are target portfolio weights.

Do not modify the backtest engine for normal strategy development.

## Portfolio analysis

Use the notebooks under `notebooks/portfolio/` after data ingestion.

```text
notebooks/portfolio/
├── 01_COMPARE_RUNS.py
├── 02_MONTE_CARLO.py
└── 03_NVIDIA_RESULTS.py
```

- `01_COMPARE_RUNS.py` compares two or more saved backtest `run_id` values.
- `02_MONTE_CARLO.py` runs forward simulations for explicit portfolio weights and is independent of strategy backtesting.
- `03_NVIDIA_RESULTS.py` reviews optimization, backtest and rebalancing output pushed from the optional NVIDIA GPU workflow.

## Optional NVIDIA GPU portfolio optimization

GPU optimization is a separate workflow. Databricks remains the system of record; the GPU computer is a compute worker.

```text
Databricks prices / saved portfolio
              │
              ▼
Remote or on-prem NVIDIA GPU
NVIDIA portfolio-optimization + cuOpt
              │
        ┌─────┼─────────┐
        ▼     ▼         ▼
   optimization   backtest   rebalancing
        │             │          │
        └─────────────┴──────────┘
                      │
                      ▼
              write results back
                to Databricks
                      │
                      ▼
            OpenBB Workspace
```

The derived notebook is:

```text
gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
```

Run it on a remote or on-prem Linux machine with a compatible NVIDIA GPU and NVIDIA's `portfolio-optimization` environment. The notebook can:

- read DBO_Quant price history directly through a Databricks SQL Warehouse
- optionally load the latest holdings for a saved `portfolio_id`
- run NVIDIA Mean-CVaR optimization with cuOpt
- generate an efficient frontier
- backtest the optimized allocation against equal weight and the current saved portfolio
- optionally run dynamic monthly rebalancing
- push frontier points, allocations, covariance data, backtest metrics and rebalancing output back to Databricks

Rebalancing is disabled by default because it is more GPU-intensive. The GPU workflow requires cuOpt and does not silently substitute a CPU solver.

See `gpu/nvidia_portfolio_optimization/README.md` for one-time GPU environment setup.

After the GPU notebook finishes, copy its `optimization_run_id` into:

```text
notebooks/portfolio/03_NVIDIA_RESULTS.py
```

The same persisted outputs are exposed to OpenBB Workspace through the DBO_Quant App.

## Platform deployment

Infrastructure notebooks are separate from normal research:

```text
notebooks/platform/
├── 01_SERVING.py
├── 02_DEPLOY_APP.py
└── 03_OPENBB_WORKSPACE.py
```

- `01_SERVING.py` is optional and is used only for Databricks Model Serving or Feature Serving.
- `02_DEPLOY_APP.py` guides deployment of the minimal `openbb-platform-api` Databricks App.
- `03_OPENBB_WORKSPACE.py` verifies tables and provides the final OpenBB Workspace backend settings.

The first App deployment requires only a SQL Warehouse resource. Lakeflow Jobs can be added later if OpenBB forms should trigger new backtests, Monte Carlo runs or comparisons.

## Normal workflow

```text
Refresh financial data
    notebooks/01_INGEST_DATA.py

Run a strategy
    notebooks/backtests/<STRATEGY>.py

Compare saved strategies
    notebooks/portfolio/01_COMPARE_RUNS.py

Run Monte Carlo
    notebooks/portfolio/02_MONTE_CARLO.py

Optional GPU optimization/rebalancing
    gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
    ↓
    notebooks/portfolio/03_NVIDIA_RESULTS.py

Deploy or update research API
    notebooks/platform/02_DEPLOY_APP.py

Connect/check OpenBB Workspace
    notebooks/platform/03_OPENBB_WORKSPACE.py
```

## Repository layout

```text
DBO_Quant/
├── notebooks/
│   ├── 00_SETUP.py
│   ├── 01_INGEST_DATA.py
│   ├── backtests/          # one notebook per strategy
│   ├── portfolio/          # comparison, Monte Carlo, NVIDIA result review
│   └── platform/           # Serving, App, OpenBB connection
├── src/quant_platform/     # common backtest/Monte Carlo/research engine
├── sql/                    # Unity Catalog schema and migrations
├── jobs/                   # optional production Lakeflow workers
├── serving/                # Model/Feature Serving helpers
├── databricks_app/         # minimal OpenBB API backend
├── gpu/                    # standalone GPU workflows
├── nvidia_bridge/          # Databricks write-back adapters for NVIDIA output
└── tests/
```

## Core architecture

```text
Financial providers
      │
      ▼
 OpenBB ODP
      │
      ▼
Delta / Unity Catalog
      │
 ┌────┼───────────────┬──────────────────┐
 ▼    ▼               ▼                  ▼
Quant Monte Carlo  Databricks Serving  NVIDIA GPU
engine                                  optional
 └────┴───────────────┴──────────────────┘
                  │
                  ▼
     Databricks App + openbb-platform-api
                  │
                  ▼
          OpenBB Workspace
```

OpenBB ODP is a permanent component. Unity Catalog/Delta is the system of record. The Databricks App is an API gateway, not another UI.