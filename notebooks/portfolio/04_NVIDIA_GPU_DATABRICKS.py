# Databricks notebook source
# MAGIC %md
# MAGIC # NVIDIA GPU Portfolio Optimization — Databricks Route
# MAGIC Run this notebook only on **Databricks GPU compute using Databricks Runtime ML**.
# MAGIC
# MAGIC This is the Databricks execution route for the same NVIDIA workflow used by the remote/on-prem notebook. Both routes read the same `.env` configuration and write the same result tables.
# MAGIC
# MAGIC **Prerequisites**
# MAGIC - GPU-enabled Databricks compute
# MAGIC - Databricks Runtime ML (Dedicated access mode for Unity Catalog)
# MAGIC - NVIDIA `portfolio-optimization` package plus the CUDA 12 cuOpt/cuML dependencies installed on this compute
# MAGIC - `.env` configured from `.env.example`

# COMMAND ----------
# MAGIC %sh
# MAGIC nvidia-smi

# COMMAND ----------
from pathlib import Path
import sys

repo_root = Path.cwd()
for candidate in [repo_root, *repo_root.parents]:
    if (candidate / "gpu" / "nvidia_portfolio_optimization").exists():
        repo_root = candidate
        break
sys.path.insert(0, str(repo_root))

from gpu.nvidia_portfolio_optimization.config import load_gpu_config
from gpu.nvidia_portfolio_optimization.runner import run_gpu_workflow
from gpu.nvidia_portfolio_optimization.workflow import require_nvidia_runtime

print("DBO_Quant root:", repo_root)

# COMMAND ----------
# Validate that cuOpt is actually available on this GPU runtime.
solver = require_nvidia_runtime()
print("NVIDIA runtime ready:", solver)

# COMMAND ----------
CONFIG = load_gpu_config(repo_root)
print("GPU workflow configuration")
for key, value in CONFIG.items():
    if key != "profile":
        print(f"{key}: {value}")

# COMMAND ----------
result = run_gpu_workflow(**CONFIG)

display(result["optimal_weights"].sort_values(ascending=False).to_frame())
display(result["frontier"].head(25))
display(result["frontier_figure"])
display(result["backtest_results"])

if result["rebalance_results"] is not None:
    display(result["rebalance_results"])

print("optimization_run_id =", result["optimization_run_id"])
print("rebalance_run_id =", result["rebalance_run_id"])

# COMMAND ----------
# MAGIC %md
# MAGIC ## Next
# MAGIC Open `notebooks/portfolio/03_NVIDIA_RESULTS.py` and paste the `optimization_run_id` above. The results are also available through the OpenBB Workspace backend after the App is deployed.
