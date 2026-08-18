# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Automated App Deployment
# MAGIC Optional final task for an automated research workflow.
# MAGIC
# MAGIC This performs a real Databricks App deployment from Git. The App must already exist and its required resources (for example the SQL Warehouse resource) must already be configured.

# COMMAND ----------
# MAGIC %pip install -q --upgrade "databricks-sdk>=0.74,<1"

# COMMAND ----------
dbutils.library.restartPython()

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
    ('git_url','https://github.com/disocodes/DBO_Quant.git'),
    ('git_branch','main'),
    ('app_source_path','databricks_app'),
]: dbutils.widgets.text(name,default)
APP_NAME=dbutils.widgets.get('app_name').strip()
GIT_URL=dbutils.widgets.get('git_url').strip()
GIT_BRANCH=dbutils.widgets.get('git_branch').strip()
APP_SOURCE=dbutils.widgets.get('app_source_path').strip().strip('/')

# COMMAND ----------
w=WorkspaceClient()
try:
    app=w.apps.get(name=APP_NAME)
except Exception as exc:
    raise RuntimeError(
        f"Databricks App {APP_NAME!r} must already exist and have its resources configured before automated deployment."
    ) from exc

body={
    'git_source': {
        'branch': GIT_BRANCH,
        'source_code_path': APP_SOURCE,
    },
    'mode': 'SNAPSHOT',
    'env_vars': [
        {'name':'FINANCE_CATALOG','value':CATALOG},
        {'name':'FINANCE_SCHEMA','value':SCHEMA},
    ],
}

# The App's configured Git repository is used for the deployment. The URL is printed
# as an operator check because the deployment endpoint resolves the repository from
# the App configuration and the git_source ref above.
print('App:',APP_NAME)
print('Expected Git repository:',GIT_URL)
print('Branch:',GIT_BRANCH)
print('Source path:',APP_SOURCE)
print('DBO_Quant namespace:',location.namespace)

response=w.api_client.do(
    'POST',
    f'/api/2.0/apps/{APP_NAME}/deployments',
    body=body,
)
print('Deployment response:',response)

# COMMAND ----------
app=w.apps.get(name=APP_NAME)
print('APP DEPLOYMENT REQUESTED')
print('OpenBB backend URL:',str(app.url).rstrip('/') + '/api' if app.url else '<App URL becomes available after deployment>')
try:
    dbutils.jobs.taskValues.set(key='app_url', value=str(app.url or ''))
except Exception:
    pass
