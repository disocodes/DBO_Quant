# Databricks notebook source
# MAGIC %md
# MAGIC # Portfolio Analysis — NVIDIA GPU Results
# MAGIC Review an `optimization_run_id` produced by either the Databricks GPU route or the remote/on-prem GPU route. No GPU is required for this review notebook.

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

dbutils.widgets.text('optimization_run_id','')
dbutils.widgets.text('rebalance_run_id','')
RUN_ID=dbutils.widgets.get('optimization_run_id').strip(); REBALANCE_ID=dbutils.widgets.get('rebalance_run_id').strip()
if not RUN_ID: raise ValueError('Enter an optimization_run_id produced by a DBO_Quant NVIDIA GPU workflow')

# COMMAND ----------
run=spark.table(f'{CATALOG}.{SCHEMA}.optimization_runs').where(f"optimization_run_id = '{RUN_ID}'")
if run.count()==0: raise RuntimeError('optimization_run_id not found')
print('OPTIMIZATION RUN'); display(run)
print('EFFICIENT FRONTIER'); display(spark.table(f'{CATALOG}.{SCHEMA}.efficient_frontier').where(f"optimization_run_id = '{RUN_ID}'").orderBy('point_id'))
print('ALLOCATIONS'); display(spark.table(f'{CATALOG}.{SCHEMA}.optimal_allocations').where(f"optimization_run_id = '{RUN_ID}'").orderBy('portfolio_label','symbol'))
print('BACKTEST METRICS'); display(spark.table(f'{CATALOG}.{SCHEMA}.optimization_backtest_metrics').where(f"optimization_run_id = '{RUN_ID}'").orderBy('portfolio_name','metric_name'))

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
    print('No rebalancing output for this optimization run. This is valid when rebalancing was disabled.')

# COMMAND ----------
print('NVIDIA RESULT REVIEW COMPLETE')
print('NEXT → 02_MONTE_CARLO.py with source_type=optimization_run and source_id=',RUN_ID)
print('OPENBB → Mean-CVaR Frontier / Optimized Allocation / Rebalancing Value using these run IDs')