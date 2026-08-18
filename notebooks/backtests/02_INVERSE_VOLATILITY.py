# Databricks notebook source
# MAGIC %md
# MAGIC # Backtest — Inverse Volatility
# MAGIC Change the lookback or universe, run all cells, and keep the generated `run_id` for comparison.

# COMMAND ----------
from pathlib import Path
import sys
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform.research import run_research_strategy
current_catalog=spark.sql('SELECT current_catalog() c').first()['c']
for n,d in [('catalog',current_catalog),('schema','openbb_quant'),('symbols','SPY,QQQ,IEF,GLD'),('benchmark','SPY'),('lookback','63'),('rebalance','monthly'),('initial_capital','100000'),('fee_bps','5'),('slippage_bps','2')]: dbutils.widgets.text(n,d)

# COMMAND ----------
symbols=[x.strip().upper() for x in dbutils.widgets.get('symbols').split(',') if x.strip()]
params={'lookback':int(dbutils.widgets.get('lookback'))}
result=run_research_strategy(spark,catalog=dbutils.widgets.get('catalog'),schema=dbutils.widgets.get('schema'),symbols=symbols,benchmark=dbutils.widgets.get('benchmark').upper(),strategy_name='inverse_volatility',strategy='inverse_volatility',params=params,rebalance=dbutils.widgets.get('rebalance'),initial_capital=float(dbutils.widgets.get('initial_capital')),fee_bps=float(dbutils.widgets.get('fee_bps')),slippage_bps=float(dbutils.widgets.get('slippage_bps')),notebook_path='notebooks/backtests/02_INVERSE_VOLATILITY.py')
display(result.daily.tail(30).reset_index()); display(__import__('pandas').DataFrame([result.metrics]).T.reset_index().rename(columns={'index':'metric',0:'value'}))
print('\nBACKTEST SAVED:',result.run_id)
print('NEXT → run another strategy notebook, or notebooks/portfolio/01_COMPARE_RUNS.py')