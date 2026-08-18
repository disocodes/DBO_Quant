# Databricks notebook source
# MAGIC %md
# MAGIC # NVIDIA GPU Portfolio Optimization — Databricks Route
# MAGIC Run this notebook on GPU-enabled Databricks Runtime ML compute.
# MAGIC
# MAGIC **No `.env`, workspace URL, OAuth login, Databricks profile, SQL Warehouse path, catalog name, or schema name is required here.**
# MAGIC The setup notebook registers the canonical DBO_Quant Unity Catalog namespace, and this notebook discovers it automatically.
# MAGIC Portfolio/optimizer settings come from `gpu/nvidia_portfolio_optimization/portfolio_config.toml`.

# COMMAND ----------
# MAGIC %sh
# MAGIC nvidia-smi

# COMMAND ----------
from pathlib import Path
import sys
repo_root=Path.cwd()
for candidate in [repo_root,*repo_root.parents]:
    if (candidate/'gpu'/'nvidia_portfolio_optimization').exists(): repo_root=candidate; break
sys.path.insert(0,str(repo_root))

from gpu.nvidia_portfolio_optimization.config import load_portfolio_config
from gpu.nvidia_portfolio_optimization.runner import execute_gpu_analysis
from gpu.nvidia_portfolio_optimization.databricks_native import discover_location_spark, load_inputs_spark, persist_result_spark
from gpu.nvidia_portfolio_optimization.workflow import require_nvidia_runtime

require_nvidia_runtime()
CFG=load_portfolio_config(repo_root)
CATALOG,SCHEMA=discover_location_spark(spark)
print('DBO_Quant namespace:',f'{CATALOG}.{SCHEMA}')
print('Portfolio config:',CFG)

# COMMAND ----------
prices,current_weights=load_inputs_spark(
    spark,catalog=CATALOG,schema=SCHEMA,
    portfolio_id=CFG['portfolio_id'],symbols=CFG['symbols'])

result=execute_gpu_analysis(
    prices=prices,
    current_weights=current_weights,
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
        portfolio_id=CFG['portfolio_id'],
        transaction_cost_factor=CFG['transaction_cost_factor'],
        look_back_window=CFG['look_back_window'],
        look_forward_window=CFG['look_forward_window'])
else:
    optimization_run_id=rebalance_run_id=None
print('optimization_run_id =',optimization_run_id)
print('rebalance_run_id =',rebalance_run_id)
print('NEXT → notebooks/portfolio/03_NVIDIA_RESULTS.py')
