# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Automated App Deployment
# MAGIC Optional final task for an automated research workflow.
# MAGIC
# MAGIC This deploys the Databricks App from the existing cloned DBO_Quant workspace directory. It does not use a Git URL, Git branch, or Git-backed App source.

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
# MAGIC ## 3. Discover the Project and Workspace App Source
# MAGIC Resolve the canonical DBO_Quant namespace and automatically locate `databricks_app/` in the current cloned workspace repository. `repo_workspace_root` can still override the detected path when the notebook is invoked by a workflow.

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
# MAGIC ## 5. Grant the App Service Principal Read Access
# MAGIC A SQL Warehouse resource grants compute access but not Unity Catalog table access. Grant the App service principal read access to the dedicated DBO_Quant schema before the deployment is requested.

# COMMAND ----------
APP_SERVICE_PRINCIPAL=str(getattr(app,'service_principal_client_id',None) or '').strip()
if not APP_SERVICE_PRINCIPAL:
    raise RuntimeError(
        f"Databricks App {APP_NAME!r} does not expose service_principal_client_id; cannot configure Unity Catalog grants automatically."
    )


def _sql_identifier(value:str)->str:
    return '`'+value.replace('`','``')+'`'

principal_sql=_sql_identifier(APP_SERVICE_PRINCIPAL)
catalog_sql=_sql_identifier(CATALOG)
schema_sql=f'{catalog_sql}.{_sql_identifier(SCHEMA)}'

try:
    spark.sql(f'GRANT USE CATALOG ON CATALOG {catalog_sql} TO {principal_sql}')
    spark.sql(f'GRANT USE SCHEMA ON SCHEMA {schema_sql} TO {principal_sql}')
    spark.sql(f'GRANT SELECT ON SCHEMA {schema_sql} TO {principal_sql}')
except Exception as exc:
    raise RuntimeError(
        'Could not grant the Databricks App service principal read access to the DBO_Quant schema. '
        'The workflow identity must own/manage the catalog/schema or an administrator must grant USE CATALOG, USE SCHEMA, and SELECT.'
    ) from exc

print('App service principal:',APP_SERVICE_PRINCIPAL)
print('Granted USE CATALOG:',CATALOG)
print('Granted USE SCHEMA + SELECT:',location.namespace)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Request the Workspace-Sourced Deployment
# MAGIC Snapshot the cloned `databricks_app/` workspace directory and supply the SQL Warehouse resource binding plus the canonical catalog/schema as runtime environment variables. The request intentionally contains no `git_source`.

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
print('Workspace source:',SOURCE_CODE_PATH)
print('Git source: NONE')
print('DBO_Quant namespace:',location.namespace)
print('Runtime SQL warehouse binding: sql_warehouse -> DATABRICKS_WAREHOUSE_ID')

response=w.api_client.do(
    'POST',
    f'/api/2.0/apps/{APP_NAME}/deployments',
    body=body,
)
print('Deployment response:',response)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 7. Publish the App URL for Downstream Use
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
