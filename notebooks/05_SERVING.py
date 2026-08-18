# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Databricks Serving
# MAGIC This step is **optional for basic research**. Use it when you have a real Unity Catalog model to expose through Model Serving. Feature Serving remains opt-in because it provisions billable online infrastructure.

# COMMAND ----------
from pathlib import Path
import sys
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/"serving").exists(): repo_root=c; break
sys.path.insert(0,str(repo_root))
current_catalog=spark.sql("SELECT current_catalog() c").first()["c"]
for n,d in [("catalog",current_catalog),("schema","openbb_quant"),("create_model_endpoint","false"),("uc_model_name",""),("model_version","1"),("model_endpoint_name","dbo-quant-model")]: dbutils.widgets.text(n,d)
CATALOG=dbutils.widgets.get("catalog"); SCHEMA=dbutils.widgets.get("schema")

# COMMAND ----------
print("Feature table expected at:",f"{CATALOG}.{SCHEMA}.equity_features_latest")
print("Existing model-serving endpoints can be viewed in Databricks → Serving.")
if dbutils.widgets.get("create_model_endpoint").lower()=="true":
    model=dbutils.widgets.get("uc_model_name").strip()
    if not model: raise ValueError("Set uc_model_name to an existing catalog.schema.model")
    from serving.model_serving_setup import create_model_serving_endpoint
    endpoint=create_model_serving_endpoint(dbutils.widgets.get("model_endpoint_name"),model,dbutils.widgets.get("model_version"))
    print(endpoint)
else:
    print("No endpoint created. This is the safe default.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Feature Serving
# MAGIC Use `serving/feature_serving_setup.py` only when you specifically need low-latency online feature lookup. It creates/reuses an Online Feature Store, publishes the feature table, creates a FeatureSpec, and creates the endpoint.
# MAGIC
# MAGIC **You do not need Serving to run backtests, comparisons, Monte Carlo, or the OpenBB API App.**

# COMMAND ----------
print("SERVING STEP COMPLETE")
print("NEXT → notebooks/06_DEPLOY_APP.py")