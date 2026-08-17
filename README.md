# Databricks + OpenBB Quant Research Platform — Final Bundle

This bundle implements the final architecture agreed in the conversation. Start with **`Databricks_OpenBB_Quant_Platform_Final.ipynb`**.

## Final architecture

```text
                         OPENBB WORKSPACE
                        (financial research UI)
                                │
                                ▼
                    Minimal Databricks App
             OpenBB ODP API + custom /api/quant routes
                    via openbb-platform-api
                                │
             ┌──────────────────┼──────────────────┐
             │                  │                  │
             ▼                  ▼                  ▼
        OpenBB ODP         Delta / SQL       Databricks Serving
     permanent provider    Unity Catalog      ├─ Model Serving
     abstraction + API          │              └─ Feature Serving
             │                  │
             ▼             Databricks Jobs
      Financial providers  ├─ arbitrary backtests
                           ├─ Monte Carlo
                           └─ portfolio comparisons
                                ▲
                                │
                    NVIDIA portfolio-optimization
                       on your external GPU PC
```

### Component responsibilities

- **OpenBB ODP — permanent:** standardized financial-provider access and native ODP API routes. ODP is used both during Databricks ingestion and in the Workspace backend.
- **Unity Catalog / Delta — system of record:** prices, point-in-time factors, strategy runs, holdings, metrics, portfolio comparisons, Monte Carlo output, model predictions and optimizer output.
- **Databricks Jobs — heavy quant compute:** backtests, sweeps, Monte Carlo and other long-running simulations.
- **Databricks Model Serving — inference:** registered expected-return, volatility, regime, sentiment, risk and other models.
- **Databricks Feature Serving — low-latency feature lookup:** latest factor/feature values once the feature table is published to an online feature store.
- **Databricks App — thin API gateway only:** starts from the OpenBB ODP FastAPI app, adds the `/api/quant/*` routes, and is launched by `openbb-platform-api`. It is not a second UI.
- **OpenBB Workspace — only analyst UI:** consumes native ODP endpoints plus your custom quant endpoints.
- **NVIDIA portfolio optimization — external optimizer:** runs on your separate GPU computer and pushes efficient-frontier/allocation/matrix results back to Databricks.

## Start here

1. Import `Databricks_OpenBB_Quant_Platform_Final.ipynb` into Databricks.
2. Attach compute with Unity Catalog access and outbound PyPI/provider access.
3. Set the notebook widgets. The defaults use your current catalog, schema `openbb_quant`, provider `yfinance`, and universe `SPY,QQQ,IEF,GLD`.
4. Run the notebook from top to bottom.
5. The first run creates the Delta schema, ingests price history through ODP, derives latest features, runs several different strategies, persists a portfolio comparison, and runs/persists a Monte Carlo simulation.
6. After the notebook succeeds, deploy `databricks_app/` as the OpenBB backend, create the three supplied Jobs, then connect `https://<app-url>/api` to OpenBB Workspace using the OAuth steps in `databricks_app/AUTHENTICATION.md`.

The notebook deliberately **does not automatically create Serving endpoints or Apps**. Those can incur compute cost and require workspace-specific permissions/resources. The Serving cells are opt-in.

## Arbitrary backtesting design

The platform does not make SMA crossover the architecture. A strategy is a function that produces target weights:

```python
def my_strategy(prices, params):
    # calculate any technical, factor, model or allocation logic
    return target_weights_dataframe
```

The common engine then handles:

- rebalance frequency
- one-observation implementation lag
- long-only / gross-leverage constraints
- fees and slippage
- holdings and turnover
- benchmark comparison
- CAGR, volatility, Sharpe, Sortino, drawdown, Calmar, VaR/CVaR, alpha/beta
- common persistence to Delta

Built-in examples include equal/buy-and-hold, moving-average trend, time-series momentum, cross-sectional momentum, mean reversion, inverse volatility and dual momentum. The setup notebook adds a custom momentum/low-volatility strategy to demonstrate extension.

`jobs/backtest_worker.py` also includes adapters for **point-in-time factor ranking** (`factor_top_n`) and **model-prediction ranking** (`model_top_n`).

## Point-in-time correctness

`factor_snapshots` includes both `as_of_date` and `available_at`. A historical strategy must use the value that was actually available by the rebalance date. Do not backfill current/revised fundamentals across past dates. The model-prediction table uses `prediction_timestamp` for the same reason.

The engine shifts target weights one observation before applying returns, but point-in-time correctness of the input factor/model dataset remains the responsibility of the ingestion/research pipeline.

## Monte Carlo

The included simulator supports:

- historical block bootstrap
- multivariate-normal simulation
- configurable horizon, initial value, simulation count and seed
- percentile fan data (P01/P05/P10/P25/P50/P75/P90/P95/P99)
- a compact sample of paths instead of storing every full path
- probability of loss and terminal-value summary

The notebook runs a moderate demo. `jobs/monte_carlo_worker.py` is intended for larger production runs.

## Portfolio comparison

A comparison has its own canonical tables for members, daily wealth/returns/drawdowns and metrics. Members can represent strategy runs, saved portfolios or optimizer/model portfolios after conversion to the common series format. This is the basis for Portfolio Visualizer-style comparison screens in OpenBB Workspace.

`jobs/comparison_worker.py` creates new common-period comparisons from two or more persisted strategy runs; Workspace can submit it through the comparison form endpoint.

## Databricks Serving

### Model Serving

`serving/model_serving_setup.py` deploys an **existing Unity Catalog model**. The notebook has an equivalent guarded cell. Register your real model first, then opt in. Do not use the App process as the model runtime.

### Feature Serving

The notebook installs `databricks-feature-engineering>=0.13.0` and creates `equity_features_latest` as a primary-keyed Delta/Unity Catalog feature table with Change Data Feed enabled. Online serving remains explicit because it provisions billable infrastructure. Use `serving/feature_serving_setup.py` to create/reuse an Online Feature Store, publish the feature table, create a `FeatureSpec`, and then create the Feature Serving endpoint.

## OpenBB ODP provider keys

The notebook looks for these secret names in a Databricks Secret Scope called `openbb` by default:

- `fmp-api-key`
- `fred-api-key`
- `intrinio-api-key`
- `tiingo-token`
- `benzinga-api-key`

Only create the secrets for providers you use. `yfinance` can be used for the initial demonstration without a key. Provider entitlement/licensing is separate from OpenBB itself.

For the Databricks App's native ODP routes, add the relevant secret resources to the App and expose them as environment variables such as `FMP_API_KEY`. Also configure Databricks App network egress so the App can reach the external data-provider domains you intend to query.

## Minimal OpenBB backend (`databricks_app/`)

The App starts with:

```python
from openbb_core.api.rest_api import app
```

and adds the quant API routes to that same FastAPI instance. It is launched after rebuilding the installed ODP extensions:

```bash
openbb-build && openbb-api --app app.py ...
```

`openbb-platform-api` generates Workspace widget/backend configuration from the combined OpenAPI schema, so this bundle intentionally contains **no hand-maintained `widgets.json`**.

Key custom routes include:

- `/api/quant/backtests/runs` — includes the documented Workspace form hook to submit `/api/quant/jobs/backtest`
- `/api/quant/backtests/metrics`
- `/api/quant/backtests/equity-curve`
- `/api/quant/portfolio/comparison-runs` — includes the Workspace form hook to submit `/api/quant/jobs/portfolio-comparison`
- `/api/quant/portfolio/comparison`
- `/api/quant/portfolio/comparison-curve`
- `/api/quant/monte-carlo/runs` — includes the documented Workspace form hook to submit `/api/quant/jobs/monte-carlo`
- `/api/quant/monte-carlo/fan-chart`
- `/api/quant/optimization/runs`
- `/api/quant/optimization/efficient-frontier`
- `/api/quant/optimization/allocations`
- `/api/quant/features/latest`
- `/api/quant/models/predictions`
- `/api/quant/jobs/backtest`
- `/api/quant/jobs/monte-carlo`
- `/api/quant/jobs/portfolio-comparison`

All native OpenBB ODP routes remain present as well.

### Workspace connection and Databricks App OAuth

Databricks token authentication for externally called App APIs is supported on `/api/...` routes. This bundle therefore exposes the auto-generated OpenBB widget discovery at **`/api/widgets.json`**, an empty optional App-layout response at **`/api/apps.json`**, native ODP routes at **`/api/v1/...`**, and custom research routes at **`/api/quant/...`**.

In OpenBB Workspace, connect the backend using:

```text
https://<your-databricks-app-url>/api
```

The generated widget configuration deliberately strips the leading Databricks `/api/` prefix from endpoint values (`v1/...`, `quant/...`). OpenBB documents widget `endpoint` values as backend-relative API paths; this lets the backend URL carry the Databricks-required `/api` prefix exactly once.

and add a request header:

```text
Authorization: Bearer <current Databricks OAuth access token>
```

For initial testing, generate the token with Databricks CLI/SDK OAuth. OAuth access tokens are short-lived; do **not** treat a pasted token as a production unattended-auth solution. For a permanently connected hosted Workspace, use an OAuth-aware gateway/service that can refresh M2M tokens, or your organization’s approved OpenBB Enterprise/private deployment authentication pattern. The quant/data architecture does not change.

The App also enables CORS for `https://pro.openbb.co` by default. Add other Workspace origins with the comma-separated `OPENBB_ALLOWED_ORIGINS` environment variable.

### App resources

Before deploying the App, add these Databricks App resources:

- SQL warehouse → resource key `sql_warehouse` → **Can use**
- Backtest Lakeflow Job → resource key `backtest_job` → **Can manage run**
- Monte Carlo Lakeflow Job → resource key `monte_carlo_job` → **Can manage run**
- Portfolio comparison Lakeflow Job → resource key `comparison_job` → **Can manage run**
- Provider API-key secrets as needed → **Can read**, mapped to the corresponding environment variables

`app.yaml` uses `valueFrom` for the warehouse and Job resources, so their IDs are not hard-coded. Grant the App service principal `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the quant tables it reads (or add individual UC table resources). The workers themselves need write privileges on the result tables.

## NVIDIA bridge (`nvidia_bridge/`)

Run NVIDIA's `portfolio-optimization` project independently on your GPU PC. After `create_efficient_frontier` (or the current equivalent in your notebook) returns its result DataFrame:

```python
from nvidia_push_adapter import DatabricksOptimizationBridge

bridge = DatabricksOptimizationBridge(
    http_path="/sql/1.0/warehouses/<warehouse-id>",
    catalog="<catalog>",
    schema="openbb_quant",
)

run_id = bridge.push_efficient_frontier(
    results_df,
    source_engine="NVIDIA-AI-Blueprints/portfolio-optimization",
    weight_columns=[...],   # supply if asset weights are columns in your result
)
```

The adapter maps common frontier fields such as return, CVaR, objective, risk aversion, variance, volatility, Sharpe, solver and regime. It can also push labelled matrices (for example covariance) with `push_matrix()`.

Use Databricks unified authentication (`databricks auth login`, a Databricks profile, or a service principal) on the external computer. Do not paste a personal token into the bridge source.

## Bundle contents

```text
Databricks_OpenBB_Quant_Platform_Final.ipynb   <- run this first
Databricks_OpenBB_Quant_Platform_Final.py      <- Databricks source equivalent
README.md
START_HERE.md
DEPLOYMENT_CHECKLIST.md
STRATEGY_GUIDE.md
SERVING_GUIDE.md
pyproject.toml

src/quant_platform/
  engine.py
  metrics.py
  monte_carlo.py
  comparison.py

jobs/
  backtest_worker.py
  monte_carlo_worker.py
  comparison_worker.py

serving/
  model_serving_setup.py
  feature_serving_setup.py

databricks_app/
  app.py
  app.yaml
  requirements.txt
  workspace_apps.json
  AUTHENTICATION.md

nvidia_bridge/
  nvidia_push_adapter.py
  example_after_nvidia_notebook.py
  requirements.txt

sql/
  quant_platform_schema.sql

tests/
  test_quant_platform.py

dist/
  openbb_databricks_quant_platform-0.1.0-py3-none-any.whl
```

## Validation performed before packaging

- Jupyter notebook JSON/schema validation
- Python syntax compilation for the App, Serving helpers and NVIDIA bridge
- unit tests against synthetic data for strategy registry, lagged-weight backtesting, portfolio comparison and Monte Carlo
- local package wheel build

## Current upstream references used for this build

- OpenBB ODP / `openbb-api`: https://docs.openbb.co/odp/python/extensions/interface/openbb-api
- OpenBB package: https://pypi.org/project/openbb/
- Databricks Apps: https://docs.databricks.com/aws/en/dev-tools/databricks-apps/
- Databricks Model Serving: https://docs.databricks.com/aws/en/machine-learning/model-serving/
- Databricks Feature Serving: https://docs.databricks.com/aws/en/machine-learning/feature-store/feature-function-serving
- Unity Catalog feature tables: https://docs.databricks.com/aws/en/machine-learning/feature-store/uc/feature-tables-uc
- NVIDIA portfolio optimization: https://github.com/NVIDIA-AI-Blueprints/portfolio-optimization

### Monte Carlo rebalancing

Monte Carlo simulations preserve asset-level weight drift. Set `rebalance_every_days=1` for daily, about `21` for monthly, `63` for quarterly, `252` for annual, or `0` for true buy-and-hold paths. Supplying `portfolio_id` to the production worker makes its latest saved holdings the authoritative weights.
