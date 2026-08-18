# Databricks notebook source
# MAGIC %md
# MAGIC # Portfolio Analysis — NVIDIA GPU Results
# MAGIC Paste the `optimization_run_id` printed by the remote GPU notebook. This notebook only reads persisted results; the GPU is not required here.

# COMMAND ----------
current_catalog=spark.sql('SELECT current_catalog() c').first()['c']
for n,d in [('catalog',current_catalog),('schema','openbb_quant'),('optimization_run_id',''),('rebalance_run_id','')]: dbutils.widgets.text(n,d)
CATALOG=dbutils.widgets.get('catalog').strip(); SCHEMA=dbutils.widgets.get('schema').strip(); RUN_ID=dbutils.widgets.get('optimization_run_id').strip(); REBALANCE_ID=dbutils.widgets.get('rebalance_run_id').strip()
if not RUN_ID: raise ValueError('Paste optimization_run_id from gpu/nvidia_portfolio_optimization/DBO_NVIDIA_PORTFOLIO_OPTIMIZATION.ipynb')

# COMMAND ----------
run=spark.table(f'{CATALOG}.{SCHEMA}.optimization_runs').where(f"optimization_run_id = '{RUN_ID}'")
if run.count()==0: raise RuntimeError('optimization_run_id not found')
print('OPTIMIZATION RUN'); display(run)

print('EFFICIENT FRONTIER')
display(spark.table(f'{CATALOG}.{SCHEMA}.efficient_frontier').where(f"optimization_run_id = '{RUN_ID}'").orderBy('point_id'))

print('ALLOCATIONS')
display(spark.table(f'{CATALOG}.{SCHEMA}.optimal_allocations').where(f"optimization_run_id = '{RUN_ID}'").orderBy('portfolio_label','symbol'))

print('BACKTEST METRICS')
display(spark.table(f'{CATALOG}.{SCHEMA}.optimization_backtest_metrics').where(f"optimization_run_id = '{RUN_ID}'").orderBy('portfolio_name','metric_name'))

# COMMAND ----------
rebalance_runs=spark.table(f'{CATALOG}.{SCHEMA}.optimization_rebalance_runs').where(f"optimization_run_id = '{RUN_ID}'").orderBy('created_at',ascending=False)
display(rebalance_runs)
if not REBALANCE_ID and rebalance_runs.count()>0:
    REBALANCE_ID=rebalance_runs.first()['rebalance_run_id']
    print('Using latest rebalance_run_id:',REBALANCE_ID)

if REBALANCE_ID:
    print('REBALANCE EVENTS')
    display(spark.table(f'{CATALOG}.{SCHEMA}.optimization_rebalance_events').where(f"rebalance_run_id = '{REBALANCE_ID}'").orderBy('event_index'))
    print('REBALANCED PORTFOLIO VALUE')
    display(spark.table(f'{CATALOG}.{SCHEMA}.optimization_rebalance_daily').where(f"rebalance_run_id = '{REBALANCE_ID}'").orderBy('date'))
else:
    print('No rebalancing output for this optimization run. That is valid when RUN_REBALANCING=False on the GPU notebook.')

# COMMAND ----------
print('NVIDIA RESULT REVIEW COMPLETE')
print('NEXT → notebooks/platform/02_DEPLOY_APP.py if the App is not deployed, otherwise OpenBB Workspace can read these results directly.')