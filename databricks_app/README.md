# Minimal OpenBB / Databricks App

This is deliberately **not another UI**. Startup runs `openbb-build`, loads the permanent OpenBB ODP FastAPI application, adds `/api/quant/*` routes that read Unity Catalog and trigger Databricks Jobs, and launches the result through `openbb-platform-api`. Widget definitions are generated from the combined OpenAPI schema; there is no hand-maintained `widgets.json`.

## Why the `/api` prefix matters

Databricks external token authentication for Apps is designed for API endpoints under `/api/...`. This App therefore provides:

- `/api/widgets.json` — dynamically generated Workspace widget discovery
- `/api/apps.json` — empty optional App-layout list
- `/api/v1/...` — native OpenBB ODP REST routes
- `/api/quant/...` — Databricks quant research routes

Connect OpenBB Workspace to **`https://<your-app-url>/api`**, not the bare App URL. See `AUTHENTICATION.md`.
The `/api/widgets.json` response rewrites generated endpoint values to backend-relative paths (`v1/...`, `quant/...`) so the `/api` prefix is applied exactly once by the connection URL.

## Databricks App resources

1. Add a SQL warehouse resource with key `sql_warehouse` and `CAN USE`.
2. Add the backtest Lakeflow Job with key `backtest_job` and `CAN MANAGE RUN`.
3. Add the Monte Carlo Lakeflow Job with key `monte_carlo_job` and `CAN MANAGE RUN`.
4. Add the comparison Lakeflow Job with key `comparison_job` and `CAN MANAGE RUN`.
5. Give the App service principal `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the quant tables it reads. If you later add API write routes, grant `MODIFY` only to the specific tables that need it.
6. Change `FINANCE_CATALOG` in `app.yaml`.
7. For paid/keyed ODP providers, add Databricks Secret resources and expose them under the corresponding environment variable names (for example `FMP_API_KEY`).
8. Configure App network egress to the provider domains you actually use.

`app.yaml` uses App resource `valueFrom` references for the warehouse and all three Jobs, so those resource IDs are not hard-coded into source.

## OpenBB Workspace

Use backend URL `https://<your-app-url>/api` and an `Authorization: Bearer <OAuth token>` custom header for the initial connection. The hosted OpenBB UI origin `https://pro.openbb.co` is allowed by default through CORS; configure `OPENBB_ALLOWED_ORIGINS` for other origins.
