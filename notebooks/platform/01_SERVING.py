# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Databricks Serving
# MAGIC Optional. Use this only when DBO_Quant needs a Unity Catalog model exposed through Model Serving or low-latency online features through Feature Serving.

# COMMAND ----------
from pathlib import Path
import sys
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'serving').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root))
current_catalog=spark.sql('SELECT current_catalog() c').first()['c']
for n,d in [('catalog',current_catalog),('schema','openbb_quant'),('create_model_endpoint','false'),('uc_model_name',''),('model_version','1'),('model_endpoint_name','dbo-quant-model')]: dbutils.widgets.text(n,d)
CATALOG=dbutils.widgets.get('catalog'); SCHEMA=dbutils.widgets.get('schema')

# COMMAND ----------
print('Feature table:',f'{CATALOG}.{SCHEMA}.equity_features_latest')
if dbutils.widgets.get('create_model_endpoint').lower()=='true':
    model=dbutils.widgets.get('uc_model_name').strip()
    if not model: raise ValueError('Set uc_model_name to an existing catalog.schema.model')
    from serving.model_serving_setup import create_model_serving_endpoint
    print(create_model_serving_endpoint(dbutils.widgets.get('model_endpoint_name'),model,dbutils.widgets.get('model_version')))
else:
    print('No Model Serving endpoint created. This is the safe default.')

# COMMAND ----------
# MAGIC %md
# MAGIC ## Feature Serving
# MAGIC Use `serving/feature_serving_setup.py` only when low-latency online feature lookup is required. Ordinary backtests, Monte Carlo, NVIDIA optimization-result review, and the OpenBB App do not require Feature Serving.

# COMMAND ----------
print('SERVING STEP COMPLETE')
print('NEXT → notebooks/platform/02_DEPLOY_APP.py')