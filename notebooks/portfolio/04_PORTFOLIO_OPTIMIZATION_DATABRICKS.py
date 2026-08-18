# Databricks notebook source
# MAGIC %md
# MAGIC # Portfolio Optimization — Databricks
# MAGIC Run Mean-CVaR portfolio optimization inside Databricks using either CPU or GPU.
# MAGIC
# MAGIC Solver selection comes from `optimization/portfolio_optimization/portfolio_config.toml`. `cpu` is the default and uses CVXPY + CLARABEL; `gpu` uses CVXPY + NVIDIA cuOpt.
# MAGIC
# MAGIC By default the portfolio/universe comes from `portfolio_config.toml`. For automated strategy flows, set `source_type=strategy_run` and pass the strategy `run_id`; the optimizer then uses that run's latest effective allocation as its reference portfolio and universe.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Install the Portfolio Optimization Runtime
# MAGIC Install the pinned upstream portfolio-optimization package used by DBO_Quant. This base package supports the CPU path; GPU execution additionally requires compatible cuOpt/cuML CUDA packages.

# COMMAND ----------
# MAGIC %pip install -q "git+https://github.com/NVIDIA-AI-Blueprints/portfolio-optimization.git@efa60ce29b7351cfda8fd4c9afb94b9d7fce482c"

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Restart Python
# MAGIC Restart the Python process so the installed optimization package is available before project imports run.

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Load Configuration and Select the Optimization Source
# MAGIC Locate the DBO_Quant repository, load shared optimizer settings, choose either configured portfolio inputs or a strategy-run allocation, validate the selected solver, and discover the canonical Unity Catalog namespace.

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
# MAGIC %md
# MAGIC ## 4. Load Inputs and Run Portfolio Optimization
# MAGIC Load the price history and reference weights for the selected source, execute Mean-CVaR optimization with the configured CPU/GPU solver, and display the optimized allocation, frontier, backtest metrics, and optional rebalancing output.

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
# MAGIC %md
# MAGIC ## 5. Persist Results and Publish Workflow IDs
# MAGIC Write the optimization outputs to the canonical DBO_Quant tables, publish `optimization_run_id` and `rebalance_run_id` as task values when running inside a Job, and print the next analysis step.

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