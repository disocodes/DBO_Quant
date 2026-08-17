# Start Here

For the GitHub repository, the recommended entry point is **`Databricks_OpenBB_Quant_Platform_Final.py`**. It is a Databricks **source notebook** and uses the checked-in `src/quant_platform/` package and `sql/quant_platform_schema.sql` directly.

`Databricks_OpenBB_Quant_Platform_Final.ipynb` is a small convenience launcher that `%run`s the source notebook when both are kept in the same Databricks Git folder.

1. Add/clone this GitHub repository into a Databricks Git folder.
2. Open `Databricks_OpenBB_Quant_Platform_Final.py` as a Databricks notebook.
3. Attach Unity-Catalog-enabled compute.
4. Choose an **existing catalog** in the notebook widget; leave schema as `openbb_quant` unless you want another name.
5. Leave provider `yfinance` for the first run unless your OpenBB provider secrets are already configured.
6. Run all cells.
7. Confirm the final validation table has rows in prices, features, strategy runs, comparison runs and Monte Carlo runs.
8. Then import/use all three `jobs/*.py` source notebooks as Lakeflow Job notebook tasks and add them plus a SQL warehouse as Databricks App resources using the keys documented in the README.
9. Deploy `databricks_app/` and connect `https://<app-url>/api` to OpenBB Workspace using a current Databricks OAuth Bearer header; see `databricks_app/AUTHENTICATION.md`.
10. On your GPU computer, use `nvidia_bridge/` after running NVIDIA's portfolio-optimization notebook.

The setup notebook does **not** automatically create billable Serving infrastructure. Model Serving and Feature Serving remain explicit opt-in steps.
