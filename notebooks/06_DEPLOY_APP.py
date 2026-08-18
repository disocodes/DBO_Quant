# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Deploy the OpenBB API App
# MAGIC The Databricks App is the thin API layer between OpenBB Workspace and DBO_Quant. It is **not another UI**.
# MAGIC
# MAGIC Before this step, create or choose a Databricks SQL Warehouse. The App needs it to read result tables.

# COMMAND ----------
current_catalog=spark.sql("SELECT current_catalog() c").first()["c"]
for n,d in [("catalog",current_catalog),("schema","openbb_quant"),("sql_warehouse_id",""),("app_name","dbo-quant-api")]: dbutils.widgets.text(n,d)
CATALOG=dbutils.widgets.get("catalog").strip(); SCHEMA=dbutils.widgets.get("schema").strip(); WAREHOUSE=dbutils.widgets.get("sql_warehouse_id").strip(); APP_NAME=dbutils.widgets.get("app_name").strip()
if not WAREHOUSE: raise ValueError("Enter the SQL Warehouse ID. Open SQL Warehouses in Databricks and copy the warehouse ID.")

# COMMAND ----------
print("APP CONFIGURATION")
print("App name:",APP_NAME)
print("Catalog:",CATALOG)
print("Schema:",SCHEMA)
print("SQL Warehouse ID:",WAREHOUSE)
print("\nUse the repository folder `databricks_app/` as the App source.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Create the App in the Databricks UI
# MAGIC 1. Open **Compute → Apps** (or **Apps** in your workspace navigation).
# MAGIC 2. Create an App named with the value above (default `dbo-quant-api`).
# MAGIC 3. Add a **SQL warehouse resource** with resource key **`sql_warehouse`** and permission **Can use**.
# MAGIC 4. Set `FINANCE_CATALOG` in `databricks_app/app.yaml` to the catalog printed above if it is still a placeholder.
# MAGIC 5. Deploy the repository folder **`databricks_app/`**.
# MAGIC 6. Grant the App service principal `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the DBO_Quant schema/tables.
# MAGIC
# MAGIC The three Lakeflow Job resources in the current App configuration are for production-triggered backtest/Monte Carlo/comparison forms. If you are not creating those Jobs yet, remove those three job resource entries from `app.yaml` before the first deployment, or add the Jobs following `jobs/README.md`.

# COMMAND ----------
print("When deployment reports RUNNING, copy the App URL.")
print("Health check: open <APP_URL>/api/widgets.json using valid Databricks authentication.")
print("NEXT → notebooks/07_OPENBB_WORKSPACE.py")