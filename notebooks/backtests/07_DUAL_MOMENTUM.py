# Databricks notebook source
# MAGIC %md
# MAGIC # Backtest — Dual Momentum
# MAGIC Configure the dual-momentum lookback and selection count, execute the strategy through the shared DBO_Quant engine, and persist the resulting run.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Load the Research Engine and Configure Inputs
# MAGIC Import the common strategy runner and configure the universe, benchmark, momentum lookback, number of selected assets, rebalancing frequency, capital, and trading costs.

# COMMAND ----------
from pathlib import Path
import sys
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform.research import run_research_strategy
current_catalog=spark.sql('SELECT current_catalog() c').first()['c']
for n,d in [('catalog',current_catalog),('schema','openbb_quant'),('symbols','SPY,QQQ,IEF,GLD'),('benchmark','SPY'),('lookback','252'),('top_n','1'),('rebalance','monthly'),('initial_capital','100000'),('fee_bps','5'),('slippage_bps','2')]: dbutils.widgets.text(n,d)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Run and Persist the Backtest
# MAGIC Build the dual-momentum parameters, execute the strategy, display recent performance and metrics, and print the persisted `run_id` for downstream analysis.

# COMMAND ----------
symbols=[x.strip().upper() for x in dbutils.widgets.get('symbols').split(',') if x.strip()]
params={'lookback':int(dbutils.widgets.get('lookback')),'top_n':int(dbutils.widgets.get('top_n'))}
result=run_research_strategy(spark,catalog=dbutils.widgets.get('catalog'),schema=dbutils.widgets.get('schema'),symbols=symbols,benchmark=dbutils.widgets.get('benchmark').upper(),strategy_name='dual_momentum',strategy='dual_momentum',params=params,rebalance=dbutils.widgets.get('rebalance'),initial_capital=float(dbutils.widgets.get('initial_capital')),fee_bps=float(dbutils.widgets.get('fee_bps')),slippage_bps=float(dbutils.widgets.get('slippage_bps')),notebook_path='notebooks/backtests/07_DUAL_MOMENTUM.py')
display(result.daily.tail(30).reset_index()); display(__import__('pandas').DataFrame([result.metrics]).T.reset_index().rename(columns={'index':'metric',0:'value'}))
print('\nBACKTEST SAVED:',result.run_id)
print('NEXT → run another strategy notebook, or notebooks/portfolio/01_COMPARE_RUNS.py')