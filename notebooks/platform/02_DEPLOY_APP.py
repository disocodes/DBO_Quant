# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Deploy the OpenBB API App
# MAGIC Deploy or redeploy the DBO_Quant Databricks App directly from the existing cloned workspace directory. This notebook does not use a Git URL, Git branch, or Git-backed App source.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Install the Databricks SDK
# MAGIC Install the SDK version used for Databricks Apps resource and deployment APIs.

# COMMAND ----------
# MAGIC %pip install -q --upgrade "databricks-sdk>=0.74,<1"

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Restart Python
# MAGIC Restart Python so the upgraded SDK is loaded before App API calls.

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Discover DBO_Quant and the Workspace App Directory
# MAGIC Resolve the canonical Unity Catalog namespace and locate `databricks_app/` inside this cloned DBO_Quant workspace folder.

# COMMAND ----------
from pathlib import Path
import sys

repo_root=Path.cwd()
for candidate in [repo_root,*repo_root.parents]:
    if (candidate/'src'/'quant_platform').exists() and (candidate/'databricks_app').exists():
        repo_root=candidate
        break
else:
    raise RuntimeError('Could not locate the cloned DBO_Quant workspace root containing src/quant_platform and databricks_app/.')

sys.path.insert(0,str(repo_root/'src'))
from quant_platform.location import discover_with_spark
from databricks.sdk import WorkspaceClient

location=discover_with_spark(spark)
CATALOG,SCHEMA=location.catalog,location.schema
DETECTED_WORKSPACE_ROOT=str(repo_root).rstrip('/')

for name,default in [
    ('app_name','dbo-quant-api'),
    ('repo_workspace_root',DETECTED_WORKSPACE_ROOT),
    ('sql_warehouse_id',''),
]:
    dbutils.widgets.text(name,default)

APP_NAME=dbutils.widgets.get('app_name').strip() or 'dbo-quant-api'
WORKSPACE_ROOT=dbutils.widgets.get('repo_workspace_root').strip().rstrip('/') or DETECTED_WORKSPACE_ROOT
WAREHOUSE_ID=dbutils.widgets.get('sql_warehouse_id').strip()

if not WORKSPACE_ROOT.startswith('/Workspace/'):
    raise ValueError(
        f'repo_workspace_root must be an absolute Databricks workspace path beginning with /Workspace/. Detected: {WORKSPACE_ROOT!r}'
    )

SOURCE_CODE_PATH=f'{WORKSPACE_ROOT}/databricks_app'

print('Canonical DBO_Quant namespace:',location.namespace)
print('Workspace repository root:',WORKSPACE_ROOT)
print('App deployment source:',SOURCE_CODE_PATH)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Validate the Existing App and SQL Warehouse Resource
# MAGIC Confirm the App exists and ensure it has a resource named `sql_warehouse`. Providing `sql_warehouse_id` replaces or creates that resource with `CAN_USE`; otherwise the existing resource is reused.

# COMMAND ----------
w=WorkspaceClient()
try:
    app=w.apps.get(name=APP_NAME)
except Exception as exc:
    raise RuntimeError(f"Databricks App {APP_NAME!r} must already exist before deployment.") from exc

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
        "The App has no resource named 'sql_warehouse'. Enter sql_warehouse_id or add the SQL Warehouse resource to the App before deployment."
    )
else:
    configured=warehouse_resource.get('sql_warehouse') or {}
    print('Using existing App resource sql_warehouse:',configured.get('id','<configured>'))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Deploy the Workspace Snapshot
# MAGIC Deploy a snapshot of the cloned workspace `databricks_app/` directory. The request intentionally contains no `git_source`, Git URL, or branch, so this deployment switches/redeploys the App from workspace files only.

# COMMAND ----------
body={
    'source_code_path':SOURCE_CODE_PATH,
    'mode':'SNAPSHOT',
    'env_vars':[
        {'name':'DATABRICKS_WAREHOUSE_ID','value_from':'sql_warehouse'},
        {'name':'FINANCE_CATALOG','value':CATALOG},
        {'name':'FINANCE_SCHEMA','value':SCHEMA},
    ],
}

print('App:',APP_NAME)
print('Deployment mode: SNAPSHOT')
print('Deployment source:',SOURCE_CODE_PATH)
print('Git source: NONE')

response=w.api_client.do(
    'POST',
    f'/api/2.0/apps/{APP_NAME}/deployments',
    body=body,
)
print('Deployment response:',response)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Publish the Backend URL
# MAGIC Read the App after requesting deployment and print the URL used by OpenBB Workspace.

# COMMAND ----------
app=w.apps.get(name=APP_NAME)
print('APP DEPLOYMENT REQUESTED')
print('Workspace source:',SOURCE_CODE_PATH)
print('OpenBB backend URL:',str(app.url).rstrip('/') + '/api' if app.url else '<App URL becomes available after deployment>')
print('After RUNNING, test:',str(app.url).rstrip('/') + '/api/widgets.json' if app.url else '<APP_URL>/api/widgets.json')
