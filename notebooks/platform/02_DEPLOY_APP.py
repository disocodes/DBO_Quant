# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Deploy the OpenBB API App
# MAGIC The Databricks App is the thin API layer between OpenBB Workspace and DBO_Quant. It is not another UI.
# MAGIC
# MAGIC First deployment requires the completed DBO_Quant tables, one SQL Warehouse, and the `databricks_app/` source folder.

# COMMAND ----------
current_catalog=spark.sql('SELECT current_catalog() c').first()['c']
for n,d in [('catalog',current_catalog),('schema','openbb_quant'),('sql_warehouse_id',''),('app_name','dbo-quant-api')]: dbutils.widgets.text(n,d)
CATALOG=dbutils.widgets.get('catalog').strip(); SCHEMA=dbutils.widgets.get('schema').strip(); WAREHOUSE=dbutils.widgets.get('sql_warehouse_id').strip(); APP_NAME=dbutils.widgets.get('app_name').strip()
if not WAREHOUSE: raise ValueError('Enter the SQL Warehouse ID.')

# COMMAND ----------
print('APP CONFIGURATION')
print('App name:',APP_NAME)
print('Catalog:',CATALOG)
print('Schema:',SCHEMA)
print('SQL Warehouse ID:',WAREHOUSE)
print('Source folder: databricks_app/')
print('Entrypoint: databricks_app/app_entry.py')

# COMMAND ----------
# MAGIC %md
# MAGIC ## Deploy in Databricks
# MAGIC 1. Open **Apps** in Databricks.
# MAGIC 2. Create the App.
# MAGIC 3. Add a SQL warehouse resource with key **`sql_warehouse`** and permission **Can use**.
# MAGIC 4. In `databricks_app/app.yaml`, replace `REPLACE_WITH_YOUR_CATALOG` with the catalog printed above.
# MAGIC 5. Deploy `databricks_app/`.
# MAGIC 6. Grant the App service principal `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the DBO_Quant schema/tables.
# MAGIC 7. Wait for **RUNNING** and copy the App URL.
# MAGIC
# MAGIC Lakeflow Job IDs remain optional. They are needed only when OpenBB forms should trigger new compute, not for viewing saved research/NVIDIA results.

# COMMAND ----------
print('After deployment test: <APP_URL>/api/widgets.json')
print('NEXT → notebooks/platform/03_OPENBB_WORKSPACE.py')