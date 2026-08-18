# Databricks notebook source
# MAGIC %md
# MAGIC # Custom Strategy Template
# MAGIC Copy this notebook, rename it, and edit the strategy logic and parameter widgets. The strategy function must return a **date × asset DataFrame of target weights**; the shared DBO_Quant engine handles execution mechanics, costs, metrics, and persistence.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Load the Research Engine and Configure Inputs
# MAGIC Import the common research helpers and define example widgets for the asset universe, benchmark, custom strategy parameters, rebalancing, capital, and trading costs.

# COMMAND ----------
from pathlib import Path
import sys
import numpy as np
import pandas as pd
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform.research import run_research_strategy
from quant_platform.engine import scores_to_weights
current_catalog=spark.sql('SELECT current_catalog() c').first()['c']
for n,d in [('catalog',current_catalog),('schema','openbb_quant'),('symbols','SPY,QQQ,IEF,GLD'),('benchmark','SPY'),('momentum_lookback','126'),('volatility_lookback','63'),('top_n','2'),('rebalance','monthly'),('initial_capital','100000'),('fee_bps','5'),('slippage_bps','2')]: dbutils.widgets.text(n,d)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Define the Custom Strategy
# MAGIC Implement the strategy-specific signal and convert it to target portfolio weights. Replace this example function when creating a new strategy notebook.

# COMMAND ----------
def my_strategy(prices: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Example: rank assets by positive momentum divided by volatility."""
    momentum = prices.pct_change(int(params['momentum_lookback']), fill_method=None)
    volatility = prices.pct_change(fill_method=None).rolling(int(params['volatility_lookback'])).std()
    score = (momentum / volatility.replace(0, np.nan)).where(momentum > 0)
    return scores_to_weights(score, top_n=int(params['top_n']))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Run and Persist the Custom Backtest
# MAGIC Parse the custom parameters, execute the strategy through the shared engine, display recent performance and metrics, and print the persisted `run_id`.

# COMMAND ----------
symbols=[x.strip().upper() for x in dbutils.widgets.get('symbols').split(',') if x.strip()]
params={'momentum_lookback':int(dbutils.widgets.get('momentum_lookback')),'volatility_lookback':int(dbutils.widgets.get('volatility_lookback')),'top_n':int(dbutils.widgets.get('top_n'))}
result=run_research_strategy(spark,catalog=dbutils.widgets.get('catalog'),schema=dbutils.widgets.get('schema'),symbols=symbols,benchmark=dbutils.widgets.get('benchmark').upper(),strategy_name='my_custom_strategy',strategy=my_strategy,params=params,rebalance=dbutils.widgets.get('rebalance'),initial_capital=float(dbutils.widgets.get('initial_capital')),fee_bps=float(dbutils.widgets.get('fee_bps')),slippage_bps=float(dbutils.widgets.get('slippage_bps')),notebook_path='notebooks/backtests/90_CUSTOM_STRATEGY_TEMPLATE.py')
display(result.daily.tail(30).reset_index()); display(pd.DataFrame([result.metrics]).T.reset_index().rename(columns={'index':'metric',0:'value'}))
print('\nCUSTOM BACKTEST SAVED:',result.run_id)
print('NEXT → notebooks/portfolio/01_COMPARE_RUNS.py')