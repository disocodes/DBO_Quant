# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Deploy the OpenBB API App
# MAGIC The Databricks App is the thin API layer between OpenBB Workspace and DBO_Quant. It is not another UI.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Discover the Project and Configure App Resources
# MAGIC Resolve the canonical DBO_Quant namespace and enter the SQL Warehouse ID and Databricks App name required by the API backend.

# COMMAND ----------
from pathlib import Path
import sys
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform.location import discover_with_spark

location=discover_with_spark(spark)
CATALOG,SCHEMA=location.catalog,location.schema
print('Canonical DBO_Quant namespace:',location.namespace)

dbutils.widgets.text('sql_warehouse_id','')
dbutils.widgets.text('app_name','dbo-quant-api')
WAREHOUSE=dbutils.widgets.get('sql_warehouse_id').strip(); APP_NAME=dbutils.widgets.get('app_name').strip()
if not WAREHOUSE: raise ValueError('Enter the SQL Warehouse ID.')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Review the Required App Configuration
# MAGIC Print the exact App name, Unity Catalog namespace, SQL Warehouse resource, source folder, and Python entrypoint that should be configured in Databricks Apps.

# COMMAND ----------
print('APP CONFIGURATION')
print('App name:',APP_NAME)
print('Catalog:',CATALOG)
print('Schema:',SCHEMA)
print('SQL Warehouse ID:',WAREHOUSE)
print('Workspace source: <repo_workspace_root>/databricks_app')
print('Entrypoint: app_entry.py')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Deploy the App in Databricks
# MAGIC 1. Open **Apps** in Databricks and create the App.
# MAGIC 2. Add a SQL Warehouse resource with key **`sql_warehouse`** and permission **Can use**.
# MAGIC 3. In `databricks_app/app.yaml`, set `FINANCE_CATALOG` and `FINANCE_SCHEMA` to the values printed above.
# MAGIC 4. Deploy `databricks_app/` from the existing cloned DBO_Quant workspace Git folder. A separate GitHub source is not required for the App.
# MAGIC 5. Grant the App service principal `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the DBO_Quant schema.
# MAGIC 6. Wait for **RUNNING** and copy the App URL.
# MAGIC
# MAGIC Lakeflow Job IDs are optional and are required only when OpenBB forms should launch new calculations.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Verify the Deployment Target
# MAGIC After deployment, test the widget-discovery endpoint and continue to the OpenBB Workspace connection notebook.

# COMMAND ----------
print('After deployment test: <APP_URL>/api/widgets.json')
print('Expected OpenBB charts include backtests, comparisons, Monte Carlo fan/sample paths, CVaR frontier, allocation, and rebalancing value.')
print('NEXT → notebooks/platform/03_OPENBB_WORKSPACE.py')