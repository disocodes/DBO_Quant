# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Automated App Deployment
# MAGIC Optional final task for an automated research workflow.
# MAGIC
# MAGIC This deploys the Databricks App from the existing DBO_Quant workspace Git folder. It also validates the required SQL Warehouse App resource before requesting deployment.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Install the Databricks SDK
# MAGIC Install a current Databricks SDK version that supports the Apps deployment APIs used by this notebook.

# COMMAND ----------
# MAGIC %pip install -q --upgrade "databricks-sdk>=0.74,<1"

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Restart Python
# MAGIC Restart the Python process so the upgraded Databricks SDK is available before imports run.

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Discover the Project and Configure the Workspace Source
# MAGIC Resolve the canonical DBO_Quant namespace and configure the existing App name, workspace source folder, and SQL Warehouse used by the App backend.

# COMMAND ----------
from pathlib import Path
import sys
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform.location import discover_with_spark
from databricks.sdk import WorkspaceClient

location=discover_with_spark(spark)
CATALOG,SCHEMA=location.catalog,location.schema
for name,default in [
    ('app_name','dbo-quant-api'),
    ('repo_workspace_root',''),
    ('app_source_path','databricks_app'),
    ('sql_warehouse_id',''),
]: dbutils.widgets.text(name,default)

APP_NAME=dbutils.widgets.get('app_name').strip()
WORKSPACE_ROOT=dbutils.widgets.get('repo_workspace_root').strip().rstrip('/')
APP_SOURCE=dbutils.widgets.get('app_source_path').strip().strip('/')
WAREHOUSE_ID=dbutils.widgets.get('sql_warehouse_id').strip()

if not WORKSPACE_ROOT:
    raise ValueError('repo_workspace_root is required. Use the absolute Databricks workspace path of the cloned DBO_Quant Git folder.')
if not WORKSPACE_ROOT.startswith('/Workspace/'):
    raise ValueError('repo_workspace_root must be an absolute Databricks workspace path beginning with /Workspace/.')
if not APP_SOURCE:
    raise ValueError('app_source_path is required')

SOURCE_CODE_PATH=f'{WORKSPACE_ROOT}/{APP_SOURCE}'

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Validate the App and SQL Warehouse Resource
# MAGIC Confirm the named Databricks App exists. If `sql_warehouse_id` is supplied, ensure the App has a resource named `sql_warehouse` with `CAN_USE`. If the resource already exists, reuse it.

# COMMAND ----------
w=WorkspaceClient()
try:
    app=w.apps.get(name=APP_NAME)
except Exception as exc:
    raise RuntimeError(f"Databricks App {APP_NAME!r} must already exist before automated deployment.") from exc

resources=[]
for resource in (app.resources or []):
    resources.append(resource.as_dict() if hasattr(resource,'as_dict') else resource)

warehouse_resource=next((r for r in resources if r.get('name')=='sql_warehouse'),None)

if WAREHOUSE_ID:
    desired={
        'name':'sql_warehouse',
        'description':'DBO_Quant SQL Warehouse',
        'sql_warehouse':{
            'id':WAREHOUSE_ID,
            'permission':'CAN_USE',
        },
    }
    resources=[r for r in resources if r.get('name')!='sql_warehouse']+[desired]
    w.api_client.do(
        'PATCH',
        f'/api/2.0/apps/{APP_NAME}',
        body={'resources':resources},
    )
    app=w.apps.get(name=APP_NAME)
    warehouse_resource=desired
    print('Configured App resource sql_warehouse:',WAREHOUSE_ID,'(CAN_USE)')
elif not warehouse_resource:
    raise RuntimeError(
        "The App has no resource named 'sql_warehouse'. Enter sql_warehouse_id in this notebook or add a SQL Warehouse resource to the App with resource key 'sql_warehouse' and CAN_USE permission."
    )
else:
    configured=warehouse_resource.get('sql_warehouse') or {}
    print('Using existing App resource sql_warehouse:',configured.get('id','<configured>'))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Request the Workspace-Sourced Deployment
# MAGIC Snapshot the already-cloned `databricks_app/` workspace folder and supply the canonical catalog/schema as runtime environment variables.

# COMMAND ----------
body={
    'source_code_path': SOURCE_CODE_PATH,
    'mode': 'SNAPSHOT',
    'env_vars': [
        {'name':'FINANCE_CATALOG','value':CATALOG},
        {'name':'FINANCE_SCHEMA','value':SCHEMA},
    ],
}

print('App:',APP_NAME)
print('Workspace source:',SOURCE_CODE_PATH)
print('DBO_Quant namespace:',location.namespace)

response=w.api_client.do(
    'POST',
    f'/api/2.0/apps/{APP_NAME}/deployments',
    body=body,
)
print('Deployment response:',response)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Publish the App URL for Downstream Use
# MAGIC Read the App after the deployment request, print its OpenBB backend URL when available, and publish the URL as a Databricks task value for downstream workflow tasks.

# COMMAND ----------
app=w.apps.get(name=APP_NAME)
print('APP DEPLOYMENT REQUESTED')
print('Deployment source:',SOURCE_CODE_PATH)
print('OpenBB backend URL:',str(app.url).rstrip('/') + '/api' if app.url else '<App URL becomes available after deployment>')
try:
    dbutils.jobs.taskValues.set(key='app_url', value=str(app.url or ''))
except Exception:
    pass
