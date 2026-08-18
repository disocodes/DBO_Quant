# Databricks notebook source
# MAGIC %md
# MAGIC # Backtest — Fixed Allocation
# MAGIC Configure a constant target allocation, run the shared DBO_Quant backtest engine, and persist the resulting strategy run.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Load the Research Engine and Configure Inputs
# MAGIC Locate the repository, import the common strategy runner, and define widgets for the asset universe, benchmark, fixed weights, rebalancing, capital, and trading costs.

# COMMAND ----------
from pathlib import Path
import sys, json
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform.research import run_research_strategy
current_catalog=spark.sql('SELECT current_catalog() c').first()['c']
for n,d in [('catalog',current_catalog),('schema','openbb_quant'),('symbols','SPY,QQQ,IEF,GLD'),('benchmark','SPY'),('weights_json','{"SPY":0.25,"QQQ":0.25,"IEF":0.25,"GLD":0.25}'),('rebalance','monthly'),('initial_capital','100000'),('fee_bps','5'),('slippage_bps','2')]: dbutils.widgets.text(n,d)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Run and Persist the Backtest
# MAGIC Parse the configured fixed weights, execute the common backtest engine, display recent daily results and metrics, and print the persisted `run_id` for downstream analysis.

# COMMAND ----------
symbols=[x.strip().upper() for x in dbutils.widgets.get('symbols').split(',') if x.strip()]
params={'weights':json.loads(dbutils.widgets.get('weights_json'))}
result=run_research_strategy(spark,catalog=dbutils.widgets.get('catalog'),schema=dbutils.widgets.get('schema'),symbols=symbols,benchmark=dbutils.widgets.get('benchmark').upper(),strategy_name='fixed_allocation',strategy='fixed_allocation',params=params,rebalance=dbutils.widgets.get('rebalance'),initial_capital=float(dbutils.widgets.get('initial_capital')),fee_bps=float(dbutils.widgets.get('fee_bps')),slippage_bps=float(dbutils.widgets.get('slippage_bps')),notebook_path='notebooks/backtests/01_FIXED_ALLOCATION.py')
display(result.daily.tail(30).reset_index()); display(__import__('pandas').DataFrame([result.metrics]).T.reset_index().rename(columns={'index':'metric',0:'value'}))
print('\nBACKTEST SAVED:',result.run_id)
print('NEXT → run another notebook in notebooks/backtests/, or notebooks/portfolio/01_COMPARE_RUNS.py')