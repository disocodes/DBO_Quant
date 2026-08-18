# Databricks notebook source
# MAGIC %md
# MAGIC # Portfolio Analysis — Compare Saved Backtests
# MAGIC Run two or more strategy notebooks first, then paste their `run_id` values below.

# COMMAND ----------
from pathlib import Path
from datetime import datetime, timezone
import sys, json, uuid
import pandas as pd

repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform.location import discover_with_spark

location=discover_with_spark(spark)
CATALOG,SCHEMA=location.catalog,location.schema
print('DBO_Quant namespace:',location.namespace)

dbutils.widgets.text('run_ids','')
dbutils.widgets.text('comparison_name','Research comparison')
RUN_IDS=[x.strip() for x in dbutils.widgets.get('run_ids').split(',') if x.strip()]
if len(RUN_IDS)<2: raise ValueError('Provide at least two run IDs produced by notebooks/backtests/*.py')

# COMMAND ----------
where='run_id IN ({})'.format(','.join([f"'{x}'" for x in RUN_IDS]))
runs=spark.table(f'{CATALOG}.{SCHEMA}.strategy_runs').where(where).toPandas()
daily=spark.table(f'{CATALOG}.{SCHEMA}.strategy_daily').where(where).toPandas()
metrics=spark.table(f'{CATALOG}.{SCHEMA}.strategy_metrics').where(where).toPandas()
if len(runs)<2: raise RuntimeError('Could not find at least two requested run IDs')
labels={r.run_id:f'{r.strategy_name} [{r.run_id[:8]}]' for _,r in runs.iterrows()}
display(metrics.pivot_table(index='metric_name',columns='run_id',values='metric_value',aggfunc='last').rename(columns=labels).reset_index())
display(daily.pivot_table(index='date',columns='run_id',values='wealth',aggfunc='last').rename(columns=labels).tail(60).reset_index())

# COMMAND ----------
comparison_id=str(uuid.uuid4()); now=datetime.now(timezone.utc).replace(tzinfo=None); name=dbutils.widgets.get('comparison_name'); start=pd.to_datetime(daily.date).min().date(); end=pd.to_datetime(daily.date).max().date(); benchmark=str(runs.benchmark_symbol.dropna().iloc[0]) if runs.benchmark_symbol.notna().any() else ''
spark.createDataFrame(pd.DataFrame([{'comparison_id':comparison_id,'comparison_name':name,'benchmark_symbol':benchmark,'start_date':start,'end_date':end,'created_at':now,'metadata_json':json.dumps({'run_ids':RUN_IDS})}])).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.portfolio_comparison_runs')
members=[]; metric_rows=[]; daily_rows=[]
for i,rid in enumerate(RUN_IDS):
    label=labels.get(rid,rid); members.append({'comparison_id':comparison_id,'member_name':label,'member_type':'strategy_run','member_id':rid,'display_order':i})
    for _,r in metrics[metrics.run_id==rid].iterrows(): metric_rows.append({'comparison_id':comparison_id,'member_name':label,'metric_name':r.metric_name,'metric_value':None if pd.isna(r.metric_value) else float(r.metric_value),'metric_text':''})
    for _,r in daily[daily.run_id==rid].iterrows(): daily_rows.append({'comparison_id':comparison_id,'date':pd.to_datetime(r.date).date(),'member_name':label,'wealth':float(r.wealth),'daily_return':float(r.net_return),'drawdown':float(r.drawdown)})
spark.createDataFrame(pd.DataFrame(members)).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.portfolio_comparison_members')
spark.createDataFrame(pd.DataFrame(metric_rows)).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.portfolio_comparison_metrics')
spark.createDataFrame(pd.DataFrame(daily_rows)).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.portfolio_comparison_daily')
print('COMPARISON SAVED:',comparison_id)
print('OPENBB → Portfolio Comparison / Portfolio Comparison Curves')
print('NEXT → 02_MONTE_CARLO.py to forward-test one of the strategy allocations.')