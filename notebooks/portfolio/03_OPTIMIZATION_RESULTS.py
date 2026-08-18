# Databricks notebook source
# MAGIC %md
# MAGIC # Portfolio Optimization — Results
# MAGIC Review any persisted portfolio-optimization run, regardless of whether it used CPU or GPU. This notebook reads stored results only; it does not execute an optimizer.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Discover the Project and Select a Run
# MAGIC Resolve the canonical DBO_Quant namespace and configure the `optimization_run_id` plus an optional `rebalance_run_id` to inspect.

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
for n,d in [('optimization_run_id',''),('rebalance_run_id','')]: dbutils.widgets.text(n,d)
RUN_ID=dbutils.widgets.get('optimization_run_id').strip(); REBALANCE_ID=dbutils.widgets.get('rebalance_run_id').strip()
if not RUN_ID: raise ValueError('Enter an optimization_run_id produced by a Databricks or external portfolio-optimization run.')
print('DBO_Quant namespace:',location.namespace)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Review Optimization Outputs
# MAGIC Validate the requested run and display its metadata, efficient frontier, selected/frontier allocations, and persisted optimizer backtest metrics.

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
# MAGIC %md
# MAGIC ## 3. Review Rebalancing Outputs
# MAGIC Display any rebalancing runs associated with the optimization, automatically select the latest run when none is supplied, and show its events and portfolio-value series.

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
    print('No rebalancing output for this optimization run.')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Continue to Risk Validation or OpenBB
# MAGIC Use the reviewed `optimization_run_id` as the allocation source for Monte Carlo, or inspect the same persisted outputs through OpenBB Workspace.

# COMMAND ----------
print('OPTIMIZATION RESULT REVIEW COMPLETE')
print('NEXT → notebooks/portfolio/02_MONTE_CARLO.py with source_type=optimization_run for forward-risk validation, or OpenBB Workspace for persisted charts.')
