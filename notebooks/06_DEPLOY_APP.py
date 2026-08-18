# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Deploy the OpenBB API App
# MAGIC The Databricks App is the thin API layer between OpenBB Workspace and DBO_Quant. It is **not another UI**.
# MAGIC
# MAGIC First deployment requires only:
# MAGIC - the completed DBO_Quant setup/data tables
# MAGIC - one Databricks SQL Warehouse
# MAGIC - the `databricks_app/` source folder

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
print("Source folder: databricks_app/")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Deploy in Databricks
# MAGIC 1. Open **Apps** in your Databricks workspace.
# MAGIC 2. Create an App named `dbo-quant-api` (or your chosen name).
# MAGIC 3. Add a **SQL warehouse** resource with resource key **`sql_warehouse`** and permission **Can use**.
# MAGIC 4. Open `databricks_app/app.yaml` in the Git folder and replace `REPLACE_WITH_YOUR_CATALOG` with the catalog printed by this notebook.
# MAGIC 5. Deploy the repository folder **`databricks_app/`**.
# MAGIC 6. Grant the App service principal `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the DBO_Quant schema/tables.
# MAGIC 7. Wait until the App is **RUNNING**, then copy its App URL.
# MAGIC
# MAGIC ### What about the three Jobs?
# MAGIC They are **not required for the first App deployment** anymore. The App can immediately serve ODP endpoints and read saved backtest/comparison/Monte Carlo results. Add Lakeflow Job IDs later if you want OpenBB forms to trigger new calculations remotely.

# COMMAND ----------
print("FIRST DEPLOYMENT CHECK")
print("After the App is RUNNING, test:")
print("  <APP_URL>/api/widgets.json")
print("Then continue to notebooks/07_OPENBB_WORKSPACE.py")