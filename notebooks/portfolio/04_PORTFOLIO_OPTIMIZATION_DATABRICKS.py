# Databricks notebook source
# MAGIC %md
# MAGIC # Portfolio Optimization — Databricks
# MAGIC Run Mean-CVaR portfolio optimization inside Databricks using either CPU or GPU.
# MAGIC
# MAGIC Solver selection comes from `optimization/portfolio_optimization/portfolio_config.toml`.
# MAGIC `cpu` is the default and uses CVXPY + CLARABEL. `gpu` uses CVXPY + NVIDIA cuOpt.
# MAGIC The canonical DBO_Quant Unity Catalog namespace is discovered automatically.
# MAGIC
# MAGIC By default the portfolio/universe comes from `portfolio_config.toml`. For automated strategy flows, set `source_type=strategy_run` and pass the strategy `run_id`; the optimizer then uses that run's latest effective allocation as its reference portfolio and universe.
# MAGIC
# MAGIC The base Portfolio Optimization package is pinned below so a fresh serverless CPU session is reproducible. GPU mode additionally requires the matching cuOpt/cuML CUDA packages in the selected Databricks environment.

# COMMAND ----------
# MAGIC %pip install -q "git+https://github.com/NVIDIA-AI-Blueprints/portfolio-optimization.git@efa60ce29b7351cfda8fd4c9afb94b9d7fce482c"

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
from pathlib import Path
import sys
repo_root=Path.cwd()
for candidate in [repo_root,*repo_root.parents]:
    if (candidate/'optimization'/'portfolio_optimization').exists(): repo_root=candidate; break
sys.path.insert(0,str(repo_root))

from optimization.portfolio_optimization.config import load_portfolio_config
from optimization.portfolio_optimization.runner import execute_optimization_analysis
from optimization.portfolio_optimization.databricks_native import discover_location_spark, load_inputs_spark, persist_result_spark
from optimization.portfolio_optimization.workflow import require_optimization_runtime

CFG=load_portfolio_config(repo_root)
dbutils.widgets.dropdown('source_type','config',['config','strategy_run'],'Optimization input')
dbutils.widgets.text('source_id','','strategy run_id when source_type=strategy_run')
SOURCE_TYPE=dbutils.widgets.get('source_type').strip()
SOURCE_ID=dbutils.widgets.get('source_id').strip()
if SOURCE_TYPE=='strategy_run' and not SOURCE_ID:
    raise ValueError('source_id is required when source_type=strategy_run')

require_optimization_runtime(CFG['solver'])
CATALOG,SCHEMA=discover_location_spark(spark)
print('DBO_Quant namespace:',f'{CATALOG}.{SCHEMA}')
print('Optimization solver:',CFG['solver'].upper())
print('Input source:',SOURCE_TYPE,SOURCE_ID or '')
print('Portfolio config:',CFG)

# COMMAND ----------
prices,current_weights=load_inputs_spark(
    spark,
    catalog=CATALOG,
    schema=SCHEMA,
    strategy_run_id=SOURCE_ID if SOURCE_TYPE=='strategy_run' else '',
    portfolio_id=CFG['portfolio_id'] if SOURCE_TYPE=='config' else '',
    symbols=CFG['symbols'] if SOURCE_TYPE=='config' else None,
)

result=execute_optimization_analysis(
    prices=prices,
    current_weights=current_weights,
    solver=CFG['solver'],
    risk_aversion=CFG['risk_aversion'],
    confidence=CFG['confidence'],
    num_scenarios=CFG['num_scenarios'],
    frontier_points=CFG['frontier_points'],
    run_rebalancing=CFG['run_rebalancing'],
    transaction_cost_factor=CFG['transaction_cost_factor'],
    look_back_window=CFG['look_back_window'],
    look_forward_window=CFG['look_forward_window'])

display(result['optimal_weights'].sort_values(ascending=False).to_frame())
display(result['frontier'].head(CFG['frontier_points']))
display(result['frontier_figure'])
display(result['backtest_results'])
if result['rebalance_results'] is not None: display(result['rebalance_results'])

# COMMAND ----------
if CFG['push_results']:
    optimization_run_id,rebalance_run_id=persist_result_spark(
        spark,catalog=CATALOG,schema=SCHEMA,result=result,
        portfolio_id=CFG['portfolio_id'] if SOURCE_TYPE=='config' else '',
        source_type=SOURCE_TYPE,
        source_id=SOURCE_ID,
        transaction_cost_factor=CFG['transaction_cost_factor'],
        look_back_window=CFG['look_back_window'],
        look_forward_window=CFG['look_forward_window'])
else:
    optimization_run_id=rebalance_run_id=None
print('optimization_run_id =',optimization_run_id)
print('rebalance_run_id =',rebalance_run_id)
try:
    dbutils.jobs.taskValues.set(key='optimization_run_id', value=optimization_run_id or '')
    dbutils.jobs.taskValues.set(key='rebalance_run_id', value=rebalance_run_id or '')
except Exception:
    pass
print('NEXT → notebooks/portfolio/03_OPTIMIZATION_RESULTS.py or 02_MONTE_CARLO.py with source_type=optimization_run')
