# DBO_Quant

DBO_Quant is a Databricks quantitative-research platform using OpenBB ODP for financial data access, Delta/Unity Catalog for storage, a reusable target-weight backtest engine, optional NVIDIA GPU portfolio optimization, Databricks Serving, and OpenBB Workspace as the research UI.

## First run

Clone this repository into a Databricks Git folder, then run:

```text
notebooks/00_SETUP.py
        ↓
notebooks/01_INGEST_DATA.py
```

`00_SETUP.py` installs the Databricks-side dependencies and applies every SQL migration in `sql/`. `01_INGEST_DATA.py` loads price history through OpenBB ODP into `prices_daily`.

After these two steps, choose the research workflow you need. Setup does not need to be rerun for ordinary research.

## Shared configuration

Copy the committed template to a local `.env` file:

```bash
cp .env.example .env
```

`.env` is ignored by Git. The NVIDIA GPU workflow reads its settings from this file (or equivalent environment variables), including:

```dotenv
DATABRICKS_PROFILE=
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/...
DBO_CATALOG=your_catalog
DBO_SCHEMA=openbb_quant
DBO_PORTFOLIO_ID=
DBO_SYMBOLS=SPY,QQQ,IEF,GLD
DBO_RISK_AVERSION=1.0
DBO_CONFIDENCE=0.95
DBO_NUM_SCENARIOS=10000
DBO_FRONTIER_POINTS=25
DBO_RUN_REBALANCING=false
DBO_TRANSACTION_COST_FACTOR=0.0
DBO_LOOK_BACK_WINDOW=126
DBO_LOOK_FORWARD_WINDOW=21
DBO_PUSH_RESULTS=true
```

Do not commit credentials or tokens in `.env`.

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

A strategy notebook contains only its research logic and parameters. All strategy notebooks use the same engine for implementation lag, rebalancing, transaction costs, weight drift, performance metrics, holdings and persistence.

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

The returned DataFrame uses dates as the index and asset symbols as columns. Values are target portfolio weights. Do not modify the common engine for ordinary strategy development.

## Portfolio analysis

```text
notebooks/portfolio/
├── 00_SAVE_PORTFOLIO.py
├── 01_COMPARE_RUNS.py
├── 02_MONTE_CARLO.py
├── 03_NVIDIA_RESULTS.py
└── 04_NVIDIA_GPU_DATABRICKS.py
```

- `00_SAVE_PORTFOLIO.py` creates or updates a saved `portfolio_id`.
- `01_COMPARE_RUNS.py` compares saved strategy `run_id` values.
- `02_MONTE_CARLO.py` can use a saved `portfolio_id` or ad-hoc weights.
- `03_NVIDIA_RESULTS.py` reviews optimizer/backtest/rebalancing output already persisted in Databricks.
- `04_NVIDIA_GPU_DATABRICKS.py` runs the NVIDIA workflow directly on compatible Databricks GPU compute.

A saved `portfolio_id` is the preferred identity for a real portfolio across Databricks, NVIDIA optimization and OpenBB.

## Optional NVIDIA GPU portfolio optimization

There are **two equal execution routes**. Both use the same `.env`, the same NVIDIA `portfolio_optimization` APIs, and write the same canonical result tables.

```text
                    DBO_Quant / Unity Catalog
                              │
                   prices + saved portfolio
                              │
                 ┌────────────┴────────────┐
                 │                         │
                 ▼                         ▼
       Databricks GPU compute       Remote/on-prem GPU
       Runtime ML + cuOpt           NVIDIA environment
                 │                         │
                 └────────────┬────────────┘
                              ▼
             optimization / frontier / backtest
                 optional dynamic rebalancing
                              │
                              ▼
                    Unity Catalog results
                              │
                              ▼
                       OpenBB Workspace
```

### Route A — Databricks GPU

Attach `notebooks/portfolio/04_NVIDIA_GPU_DATABRICKS.py` to compatible GPU-enabled Databricks Runtime ML compute. The notebook validates `nvidia-smi` and cuOpt before running.

For Unity Catalog access on Databricks Runtime ML, use Dedicated access mode. The NVIDIA package/runtime must also be compatible with the CUDA/Python versions on the selected runtime.

The Databricks route still uses the configured SQL Warehouse for the DBO_Quant read/write bridge, so persistence is identical to the external route.

### Route B — remote/on-prem GPU

Run:

```text
gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
```

inside NVIDIA's `portfolio-optimization` environment on a compatible GPU host. Authenticate to Databricks using unified authentication/profile/service-principal credentials.

### What either route can do

- load DBO_Quant prices
- load latest holdings for a saved `portfolio_id`, or use an ad-hoc symbol universe
- run NVIDIA Mean-CVaR optimization with cuOpt
- generate an efficient frontier
- backtest the optimized allocation against equal weight and the saved current portfolio
- optionally run dynamic monthly rebalancing
- persist frontier points, allocations, covariance data, backtest metrics and rebalancing output back to Databricks

Rebalancing is disabled by default because it performs repeated optimization and is more GPU-intensive.

After either route finishes, copy the printed `optimization_run_id` into:

```text
notebooks/portfolio/03_NVIDIA_RESULTS.py
```

The same results are exposed to OpenBB Workspace through the DBO_Quant App.

See `gpu/nvidia_portfolio_optimization/README.md` for GPU setup details.

## Platform deployment

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

Save/update a real portfolio
    notebooks/portfolio/00_SAVE_PORTFOLIO.py

Compare saved strategies
    notebooks/portfolio/01_COMPARE_RUNS.py

Run Monte Carlo
    notebooks/portfolio/02_MONTE_CARLO.py

Optional NVIDIA GPU optimization/rebalancing
    ├─ Databricks GPU:
    │    notebooks/portfolio/04_NVIDIA_GPU_DATABRICKS.py
    │
    └─ Remote/on-prem GPU:
         gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb
                ↓
         notebooks/portfolio/03_NVIDIA_RESULTS.py

Deploy/update API
    notebooks/platform/02_DEPLOY_APP.py

Connect/check OpenBB Workspace
    notebooks/platform/03_OPENBB_WORKSPACE.py
```

## Repository layout

```text
DBO_Quant/
├── .env.example
├── notebooks/
│   ├── 00_SETUP.py
│   ├── 01_INGEST_DATA.py
│   ├── backtests/
│   ├── portfolio/
│   └── platform/
├── src/quant_platform/
├── sql/
├── jobs/
├── serving/
├── databricks_app/
├── gpu/
├── nvidia_bridge/
└── tests/
```

OpenBB ODP is permanent. Unity Catalog/Delta is the system of record. The Databricks App is an API gateway, not another UI.
