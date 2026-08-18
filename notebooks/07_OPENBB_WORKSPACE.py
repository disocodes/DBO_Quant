# Databricks notebook source
# MAGIC %md
# MAGIC # 07 — Connect OpenBB Workspace
# MAGIC **Prerequisite:** 06_DEPLOY_APP and a running Databricks App.
# MAGIC
# MAGIC This notebook does not configure OpenBB for you; it gives you the exact values to enter and verifies that the quant tables contain data.

# COMMAND ----------
current_catalog=spark.sql("SELECT current_catalog() c").first()["c"]
for n,d in [("catalog",current_catalog),("schema","openbb_quant"),("app_url","https://<your-app-url>")]: dbutils.widgets.text(n,d)
CATALOG=dbutils.widgets.get("catalog"); SCHEMA=dbutils.widgets.get("schema"); APP_URL=dbutils.widgets.get("app_url").rstrip("/")

# COMMAND ----------
checks=[]
for t in ["prices_daily","strategy_runs","portfolio_comparison_runs","monte_carlo_runs","optimization_runs","model_predictions"]:
    try: count=spark.table(f"{CATALOG}.{SCHEMA}.{t}").count()
    except Exception: count=-1
    checks.append((t,count))
display(spark.createDataFrame(checks,["table","row_count"]))

# COMMAND ----------
print("OPENBB WORKSPACE BACKEND URL")
print(APP_URL + "/api")
print("\nDiscovery endpoint")
print(APP_URL + "/api/widgets.json")
print("\nAuthentication")
print("Authorization: Bearer <current Databricks OAuth access token>")

# COMMAND ----------
# MAGIC %md
# MAGIC ## In OpenBB Workspace
# MAGIC 1. Add a **Custom Backend**.
# MAGIC 2. Backend URL: `https://<your-app-url>/api`
# MAGIC 3. Add request header: `Authorization: Bearer <Databricks OAuth token>`.
# MAGIC 4. Save the backend and refresh the widget catalogue.
# MAGIC 5. Start with price/fundamental ODP widgets, then DBO_Quant backtest, comparison, Monte Carlo and optimization result widgets.
# MAGIC
# MAGIC ## Daily use from here
# MAGIC - New market data → `01_INGEST_DATA.py`
# MAGIC - New strategy test → `02_BACKTEST.py`
# MAGIC - Compare runs → `03_COMPARE_PORTFOLIOS.py`
# MAGIC - Forward simulation → `04_MONTE_CARLO.py`
# MAGIC - Model endpoint changes → `05_SERVING.py`
# MAGIC - App configuration changes → `06_DEPLOY_APP.py`
# MAGIC
# MAGIC You do **not** rerun setup for normal research work.

# COMMAND ----------
print("DBO_QUANT WORKFLOW COMPLETE")