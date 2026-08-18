# Databricks notebook source
# MAGIC %md
# MAGIC # Backtest — Buy and Hold
# MAGIC Weights are set once, then allowed to drift with market returns. No periodic rebalancing is performed.

# COMMAND ----------
from pathlib import Path
import sys, json
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform.research import run_research_strategy
current_catalog=spark.sql('SELECT current_catalog() c').first()['c']
for n,d in [('catalog',current_catalog),('schema','openbb_quant'),('symbols','SPY,QQQ,IEF,GLD'),('benchmark','SPY'),('weights_json','{"SPY":0.25,"QQQ":0.25,"IEF":0.25,"GLD":0.25}'),('initial_capital','100000'),('fee_bps','5'),('slippage_bps','2')]: dbutils.widgets.text(n,d)

# COMMAND ----------
symbols=[x.strip().upper() for x in dbutils.widgets.get('symbols').split(',') if x.strip()]
params={'weights':json.loads(dbutils.widgets.get('weights_json'))}
result=run_research_strategy(spark,catalog=dbutils.widgets.get('catalog'),schema=dbutils.widgets.get('schema'),symbols=symbols,benchmark=dbutils.widgets.get('benchmark').upper(),strategy_name='buy_and_hold',strategy='buy_and_hold',params=params,rebalance='buy_and_hold',initial_capital=float(dbutils.widgets.get('initial_capital')),fee_bps=float(dbutils.widgets.get('fee_bps')),slippage_bps=float(dbutils.widgets.get('slippage_bps')),notebook_path='notebooks/backtests/08_BUY_AND_HOLD.py')
display(result.daily.tail(30).reset_index()); display(__import__('pandas').DataFrame([result.metrics]).T.reset_index().rename(columns={'index':'metric',0:'value'}))
print('\nBACKTEST SAVED:',result.run_id)
print('NEXT → notebooks/portfolio/01_COMPARE_RUNS.py')