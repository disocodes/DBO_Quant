# Databricks notebook source
# MAGIC %md
# MAGIC # 99 — Cleanup DBO_Quant
# MAGIC Permanently remove DBO_Quant-owned resources from this Databricks workspace.
# MAGIC
# MAGIC **This notebook is destructive and cannot be undone.**
# MAGIC
# MAGIC By default it removes only the canonical DBO_Quant Unity Catalog schema and everything inside it. It does **not** delete the parent catalog, SQL Warehouse, cluster, Git folder, or unrelated resources.
# MAGIC
# MAGIC Optional fields can also delete a named Databricks App, Databricks Jobs, Serving endpoints, and a Databricks Online Feature Store when you explicitly provide their identifiers.

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
objects=spark.sql(f"SHOW TABLES IN `{CATALOG}`.`{SCHEMA}`")
display(objects)
print('The parent catalog will NOT be deleted:',CATALOG)
print('Only this schema is targeted by the default cleanup:',NAMESPACE)

# COMMAND ----------
dbutils.widgets.text('confirmation','',f'Type DROP {NAMESPACE}')
dbutils.widgets.dropdown('delete_schema','true',['true','false'],'Drop DBO_Quant schema and all tables')
dbutils.widgets.text('app_name','','Optional Databricks App name')
dbutils.widgets.text('job_ids','','Optional comma-separated Databricks Job IDs')
dbutils.widgets.text('serving_endpoints','','Optional comma-separated Serving endpoint names')
dbutils.widgets.text('online_feature_store','','Optional Databricks Online Feature Store name')

EXPECTED=f'DROP {NAMESPACE}'
CONFIRM=dbutils.widgets.get('confirmation').strip()
if CONFIRM!=EXPECTED:
    raise RuntimeError(f'Cleanup blocked. Type exactly: {EXPECTED}')

# COMMAND ----------
w=WorkspaceClient()
cleanup_log=[]

# Delete serving endpoints before any online feature store they may depend on.
endpoints=[x.strip() for x in dbutils.widgets.get('serving_endpoints').split(',') if x.strip()]
for endpoint in endpoints:
    try:
        w.serving_endpoints.delete(name=endpoint)
        cleanup_log.append(('Serving endpoint',endpoint,'DELETE REQUESTED'))
    except Exception as exc:
        cleanup_log.append(('Serving endpoint',endpoint,f'ERROR: {exc}'))

online_store=dbutils.widgets.get('online_feature_store').strip()
if online_store:
    try:
        from databricks.feature_engineering import FeatureEngineeringClient
        FeatureEngineeringClient().delete_online_store(name=online_store)
        cleanup_log.append(('Online Feature Store',online_store,'DELETE REQUESTED'))
    except Exception as exc:
        cleanup_log.append(('Online Feature Store',online_store,f'ERROR: {exc}'))

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
print('- clusters or compute not explicitly owned by DBO_Quant')
print('- repository/Git folder')
print('- remote/on-prem portfolio-optimization environments')
print('- OpenBB Workspace configuration outside Databricks')
