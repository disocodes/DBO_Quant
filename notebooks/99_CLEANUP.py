# Databricks notebook source
# MAGIC %md
# MAGIC # 99 — Cleanup DBO_Quant
# MAGIC Permanently remove DBO_Quant-owned resources from this Databricks workspace.
# MAGIC
# MAGIC **This notebook is destructive and cannot be undone.**
# MAGIC
# MAGIC By default it removes only the canonical DBO_Quant Unity Catalog schema and everything inside it. It does **not** delete the parent catalog, SQL Warehouse, cluster, Git folder, or unrelated resources.
# MAGIC
# MAGIC Optional sections can also delete a named Databricks App, Databricks Jobs, and Serving endpoints when you explicitly provide their identifiers.

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
NAMESPACE=location.namespace
print('Detected DBO_Quant deployment:',NAMESPACE)

# COMMAND ----------
# Show exactly what will be removed from Unity Catalog.
objects=spark.sql(f"SHOW TABLES IN `{CATALOG}`.`{SCHEMA}`")
display(objects)

print('The parent catalog will NOT be deleted:',CATALOG)
print('Only this schema is targeted:',NAMESPACE)

# COMMAND ----------
dbutils.widgets.text('confirmation','',f'Type DROP {NAMESPACE}')
dbutils.widgets.dropdown('delete_schema','true',['true','false'],'Drop DBO_Quant schema and all tables')
dbutils.widgets.text('app_name','','Optional Databricks App name')
dbutils.widgets.text('job_ids','','Optional comma-separated Databricks Job IDs')
dbutils.widgets.text('serving_endpoints','','Optional comma-separated Serving endpoint names')

EXPECTED=f'DROP {NAMESPACE}'
CONFIRM=dbutils.widgets.get('confirmation').strip()
if CONFIRM!=EXPECTED:
    raise RuntimeError(f'Cleanup blocked. Type exactly: {EXPECTED}')

# COMMAND ----------
w=WorkspaceClient()
cleanup_log=[]

# Optional workspace resources. Nothing is guessed or discovered by name.
app_name=dbutils.widgets.get('app_name').strip()
if app_name:
    try:
        w.apps.delete(name=app_name)
        cleanup_log.append(('Databricks App',app_name,'DELETE REQUESTED'))
    except Exception as exc:
        cleanup_log.append(('Databricks App',app_name,f'ERROR: {exc}'))

job_ids=[x.strip() for x in dbutils.widgets.get('job_ids').split(',') if x.strip()]
for job_id in job_ids:
    try:
        w.jobs.delete(job_id=int(job_id))
        cleanup_log.append(('Databricks Job',job_id,'DELETE REQUESTED'))
    except Exception as exc:
        cleanup_log.append(('Databricks Job',job_id,f'ERROR: {exc}'))

endpoints=[x.strip() for x in dbutils.widgets.get('serving_endpoints').split(',') if x.strip()]
for endpoint in endpoints:
    try:
        w.serving_endpoints.delete(name=endpoint)
        cleanup_log.append(('Serving endpoint',endpoint,'DELETE REQUESTED'))
    except Exception as exc:
        cleanup_log.append(('Serving endpoint',endpoint,f'ERROR: {exc}'))

# COMMAND ----------
if dbutils.widgets.get('delete_schema').lower()=='true':
    spark.sql(f'DROP SCHEMA `{CATALOG}`.`{SCHEMA}` CASCADE')
    cleanup_log.append(('Unity Catalog schema',NAMESPACE,'DELETED WITH CASCADE'))
else:
    cleanup_log.append(('Unity Catalog schema',NAMESPACE,'SKIPPED'))

# COMMAND ----------
if cleanup_log:
    display(spark.createDataFrame(cleanup_log,['resource_type','resource','status']))

print('\nCLEANUP COMPLETE')
print('Not deleted automatically:')
print('- parent Unity Catalog catalog:',CATALOG)
print('- SQL Warehouses')
print('- interactive/job clusters not explicitly identified above')
print('- repository/Git folder')
print('- remote/on-prem GPU environments')
print('- OpenBB Workspace configuration outside Databricks')
