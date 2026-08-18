# Databricks notebook source
# MAGIC %md
# MAGIC # Portfolio Analysis — Monte Carlo
# MAGIC Run after `01_INGEST_DATA.py`. This notebook is independent of backtesting and simulates the explicit portfolio weights you enter.

# COMMAND ----------
from pathlib import Path
from datetime import datetime, timezone
import sys, json
import pandas as pd
from pyspark.sql import functions as F
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform import simulate_portfolio
current_catalog=spark.sql('SELECT current_catalog() c').first()['c']
for n,d in [('catalog',current_catalog),('schema','openbb_quant'),('symbols','SPY,QQQ,IEF,GLD'),('weights_json','{"SPY":0.4,"QQQ":0.2,"IEF":0.25,"GLD":0.15}'),('initial_value','100000'),('horizon_days','1260'),('n_simulations','5000'),('method','historical_bootstrap'),('rebalance_every_days','21')]: dbutils.widgets.text(n,d)
CATALOG=dbutils.widgets.get('catalog'); SCHEMA=dbutils.widgets.get('schema'); SYMBOLS=[x.strip().upper() for x in dbutils.widgets.get('symbols').split(',') if x.strip()]; WEIGHTS=pd.Series(json.loads(dbutils.widgets.get('weights_json')),dtype=float).reindex(SYMBOLS)
if WEIGHTS.isna().any(): raise ValueError('weights_json must contain every symbol')

# COMMAND ----------
prices=spark.table(f'{CATALOG}.{SCHEMA}.prices_daily').where(F.col('symbol').isin(SYMBOLS)).select('date','symbol',F.coalesce('adjusted_close','close').alias('price')).toPandas()
if prices.empty: raise RuntimeError('No prices found. Run notebooks/01_INGEST_DATA.py first.')
wide=prices.pivot_table(index='date',columns='symbol',values='price',aggfunc='last').sort_index().reindex(columns=SYMBOLS).ffill(); returns=wide.pct_change(fill_method=None).dropna(how='any')
mc=simulate_portfolio(returns,WEIGHTS,initial_value=float(dbutils.widgets.get('initial_value')),horizon_days=int(dbutils.widgets.get('horizon_days')),n_simulations=int(dbutils.widgets.get('n_simulations')),method=dbutils.widgets.get('method'),rebalance_every_days=int(dbutils.widgets.get('rebalance_every_days')))
print(mc.summary); display(mc.percentiles.iloc[::max(1,len(mc.percentiles)//30)].reset_index())

# COMMAND ----------
now=datetime.now(timezone.utc).replace(tzinfo=None); summary=mc.summary
spark.createDataFrame(pd.DataFrame([{'mc_run_id':mc.run_id,'portfolio_id':'','method':dbutils.widgets.get('method'),'initial_value':float(summary['initial_value']),'horizon_days':int(summary['horizon_days']),'n_simulations':int(summary['n_simulations']),'rebalance_every_days':int(summary['rebalance_every_days']),'seed':42,'parameters_json':json.dumps({'symbols':SYMBOLS,'weights':WEIGHTS.to_dict()}),'status':'COMPLETED','source_engine':'quant_platform.monte_carlo','created_at':now,'completed_at':now,'summary_json':json.dumps(summary)}])).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.monte_carlo_runs')
pct=mc.percentiles.reset_index().rename(columns={'p1':'p01','p5':'p05'}); pct.insert(0,'mc_run_id',mc.run_id); spark.createDataFrame(pct[['mc_run_id','day','p01','p05','p10','p25','p50','p75','p90','p95','p99']]).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.monte_carlo_percentiles')
print('MONTE CARLO SAVED:',mc.run_id)
print('NEXT → optional GPU workflow under gpu/nvidia_portfolio_optimization/, or notebooks/platform/02_DEPLOY_APP.py')