# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Connect OpenBB Workspace
# MAGIC Prerequisite: a running DBO_Quant Databricks App from `02_DEPLOY_APP.py`.

# COMMAND ----------
current_catalog=spark.sql('SELECT current_catalog() c').first()['c']
for n,d in [('catalog',current_catalog),('schema','openbb_quant'),('app_url','https://<your-app-url>')]: dbutils.widgets.text(n,d)
CATALOG=dbutils.widgets.get('catalog'); SCHEMA=dbutils.widgets.get('schema'); APP_URL=dbutils.widgets.get('app_url').rstrip('/')

# COMMAND ----------
checks=[]
for t in ['prices_daily','strategy_runs','portfolio_comparison_runs','monte_carlo_runs','optimization_runs','optimization_backtest_metrics','optimization_rebalance_runs','model_predictions']:
    try: count=spark.table(f'{CATALOG}.{SCHEMA}.{t}').count()
    except Exception: count=-1
    checks.append((t,count))
display(spark.createDataFrame(checks,['table','row_count']))

# COMMAND ----------
print('OPENBB WORKSPACE BACKEND URL')
print(APP_URL + '/api')
print('\nDiscovery endpoint')
print(APP_URL + '/api/widgets.json')
print('\nAuthentication header')
print('Authorization: Bearer <current Databricks OAuth access token>')

# COMMAND ----------
# MAGIC %md
# MAGIC ## In OpenBB Workspace
# MAGIC 1. Add a Custom Backend.
# MAGIC 2. Backend URL: `https://<your-app-url>/api`.
# MAGIC 3. Add `Authorization: Bearer <Databricks OAuth token>`.
# MAGIC 4. Save and refresh the widget catalogue.
# MAGIC 5. DBO_Quant widgets include strategy runs/curves, comparisons, Monte Carlo, efficient frontiers, allocations, NVIDIA optimizer backtest metrics, and NVIDIA rebalancing outputs.
# MAGIC
# MAGIC ## Normal research workflow
# MAGIC - Refresh data → `notebooks/01_INGEST_DATA.py`
# MAGIC - Run a strategy → choose a notebook under `notebooks/backtests/`
# MAGIC - Compare saved runs → `notebooks/portfolio/01_COMPARE_RUNS.py`
# MAGIC - Monte Carlo → `notebooks/portfolio/02_MONTE_CARLO.py`
# MAGIC - NVIDIA GPU optimization → `gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb`
# MAGIC - Review NVIDIA output → `notebooks/portfolio/03_NVIDIA_RESULTS.py`

# COMMAND ----------
print('DBO_QUANT PLATFORM CONNECTION COMPLETE')