# DBO_Quant

DBO_Quant is a Databricks quantitative-research platform using **OpenBB ODP** for financial data access, **Delta/Unity Catalog** for storage, **Databricks Jobs/Serving** for production compute, and **OpenBB Workspace** as the research UI.

## Start here

Clone this repository into a Databricks Git folder and run the notebooks **in number order**.

| Step | Notebook | Purpose | Run frequency |
|---|---|---|---|
| 0 | `notebooks/00_SETUP.py` | Install dependencies and create/verify all Delta tables | Once per environment |
| 1 | `notebooks/01_INGEST_DATA.py` | Load market data through OpenBB ODP | Whenever data needs refreshing |
| 2 | `notebooks/02_BACKTEST.py` | Run and save one arbitrary strategy | As often as needed |
| 3 | `notebooks/03_COMPARE_PORTFOLIOS.py` | Compare two or more saved backtests | As often as needed |
| 4 | `notebooks/04_MONTE_CARLO.py` | Run and save forward portfolio simulations | As often as needed |
| 5 | `notebooks/05_SERVING.py` | Optional Model/Feature Serving setup | Only when needed |
| 6 | `notebooks/06_DEPLOY_APP.py` | Deploy/configure the OpenBB API App | Initial deployment / changes |
| 7 | `notebooks/07_OPENBB_WORKSPACE.py` | Connect OpenBB Workspace and verify the final system | After App deployment |

**Every notebook ends by telling you exactly which notebook to open next.**

## First run

1. Open `notebooks/00_SETUP.py` and run all cells.
2. When it prints `SETUP COMPLETE`, open `notebooks/01_INGEST_DATA.py`.
3. Start with provider `yfinance` and the default ETF universe so no API keys are needed.
4. When ingestion completes, run `notebooks/02_BACKTEST.py`.
5. Run `02_BACKTEST.py` several times with different strategies. Copy the resulting `run_id` values.
6. Paste two or more run IDs into `notebooks/03_COMPARE_PORTFOLIOS.py`.
7. Run `notebooks/04_MONTE_CARLO.py` for forward simulations.
8. `05_SERVING.py` is optional. You do not need Serving for ordinary research/backtesting.
9. Use `06_DEPLOY_APP.py` when you are ready to expose the data/results to OpenBB Workspace.
10. Finish with `07_OPENBB_WORKSPACE.py`.

## Normal daily use

You normally **do not rerun setup**.

- Refresh prices → `01_INGEST_DATA.py`
- Test a strategy → `02_BACKTEST.py`
- Compare saved runs → `03_COMPARE_PORTFOLIOS.py`
- Run Monte Carlo → `04_MONTE_CARLO.py`
- Change model/feature endpoints → `05_SERVING.py`
- Change/redeploy API App → `06_DEPLOY_APP.py`

## Repository layout

```text
DBO_Quant/
├── notebooks/              # USER WORKFLOW — start here
│   ├── 00_SETUP.py
│   ├── 01_INGEST_DATA.py
│   ├── 02_BACKTEST.py
│   ├── 03_COMPARE_PORTFOLIOS.py
│   ├── 04_MONTE_CARLO.py
│   ├── 05_SERVING.py
│   ├── 06_DEPLOY_APP.py
│   └── 07_OPENBB_WORKSPACE.py
├── src/quant_platform/     # reusable quant engine; normally do not edit while operating
├── sql/                    # canonical Delta/Unity Catalog schema
├── jobs/                   # production Lakeflow Job workers
├── serving/                # Model/Feature Serving helpers
├── databricks_app/         # minimal OpenBB/Databricks API backend
├── nvidia_bridge/          # NVIDIA portfolio-optimization ingestion
└── tests/                  # quant-engine tests
```

## Architecture

```text
Financial providers
       │
       ▼
   OpenBB ODP
       │
       ▼
Delta / Unity Catalog
       │
 ┌─────┼──────────────┐
 ▼     ▼              ▼
Quant  Monte Carlo   NVIDIA optimizer results
engine
       │
       ▼
Databricks App / openbb-platform-api
       │
       ▼
OpenBB Workspace
```

OpenBB ODP is a permanent component. Databricks Model Serving and Feature Serving are first-class capabilities but are provisioned only when a model or low-latency online feature workload actually needs them.

## Built-in strategies

The engine uses target portfolio weights rather than an SMA-specific architecture. Included examples are:

- fixed allocation / buy-and-hold
- moving-average trend
- time-series momentum
- cross-sectional momentum
- mean reversion
- inverse volatility
- dual momentum

Custom strategies only need to produce a date × asset target-weight DataFrame and can use the same execution, transaction-cost and performance pipeline.

## Production automation

The numbered notebooks are the easiest way to learn and operate the platform manually. After the workflow is working, use the existing `jobs/` workers for scheduled/triggered production backtests, Monte Carlo and comparisons. They write to the same canonical tables used by the notebooks and OpenBB App.

## NVIDIA optimizer

The `nvidia_bridge/` directory remains independent. Run NVIDIA Portfolio Optimization on your GPU computer and push frontier/allocation/matrix results into the DBO_Quant optimization tables. OpenBB reads those results through the same API as everything else.

## Important

Do not start inside `src/`, `jobs/`, `serving/` or `databricks_app/` on your first run. They are implementation folders. **Start with `notebooks/00_SETUP.py`.**