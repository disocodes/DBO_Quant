# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Connect OpenBB Workspace
# MAGIC Prerequisite: a running DBO_Quant Databricks App from `02_DEPLOY_APP.py` or `04_DEPLOY_APP_AUTOMATED.py`.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Discover the Project and Enter the App URL
# MAGIC Resolve the canonical DBO_Quant namespace and configure the running Databricks App URL that OpenBB Workspace will use as its custom backend.

# COMMAND ----------
from pathlib import Path
import sys
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform.location import discover_with_spark

location=discover_with_spark(spark)
CATALOG,SCHEMA=location.catalog,location.schema
print('DBO_Quant namespace:',location.namespace)

dbutils.widgets.text('app_url','https://<your-app-url>')
APP_URL=dbutils.widgets.get('app_url').rstrip('/')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Verify Persisted Research Data
# MAGIC Check the core DBO_Quant result tables and display their row counts so missing research outputs can be identified before configuring OpenBB.

# COMMAND ----------
checks=[]
for t in ['prices_daily','strategy_runs','portfolio_comparison_runs','monte_carlo_runs','monte_carlo_sample_paths','optimization_runs','optimization_backtest_metrics','optimization_rebalance_runs','model_predictions']:
    try: count=spark.table(f'{CATALOG}.{SCHEMA}.{t}').count()
    except Exception: count=-1
    checks.append((t,count))
display(spark.createDataFrame(checks,['table','row_count']))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Generate the OpenBB Backend Settings
# MAGIC Print the API base URL, widget-discovery endpoint, and authorization-header format needed for the initial OpenBB Workspace connection.

# COMMAND ----------
print('OPENBB WORKSPACE BACKEND URL')
print(APP_URL + '/api')
print('\nDiscovery endpoint')
print(APP_URL + '/api/widgets.json')
print('\nAuthentication header for initial testing')
print('Authorization: Bearer <current Databricks OAuth access token>')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Configure OpenBB Workspace
# MAGIC 1. Add a **Custom Backend**.
# MAGIC 2. Set the backend URL to `https://<your-app-url>/api`.
# MAGIC 3. Add the Databricks OAuth authorization header required by your deployment.
# MAGIC 4. Save and refresh the widget catalogue.
# MAGIC
# MAGIC ### Persisted visualizations
# MAGIC DBO_Quant exposes chart widgets for:
# MAGIC - strategy equity/benchmark/drawdown;
# MAGIC - portfolio comparison curves;
# MAGIC - Monte Carlo percentile fan chart;
# MAGIC - Monte Carlo sample paths;
# MAGIC - Mean-CVaR efficient frontier;
# MAGIC - optimized allocation bars;
# MAGIC - portfolio rebalancing value curve.
# MAGIC
# MAGIC Table widgets expose saved portfolios, holdings, run metadata, metrics, optimization results, and rebalancing events.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Complete the Platform Connection
# MAGIC Confirm the connection workflow is complete and show where normal research and final cleanup continue.

# COMMAND ----------
print('DBO_QUANT PLATFORM CONNECTION COMPLETE')
print('Normal research continues in notebooks/backtests/, notebooks/portfolio/, and notebooks/workflows/.')
print('Final teardown, when required: notebooks/99_CLEANUP.py')