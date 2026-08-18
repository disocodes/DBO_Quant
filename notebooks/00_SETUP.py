# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Setup
# MAGIC Run this notebook **once** after cloning the repo. It installs dependencies, creates the Unity Catalog schema/tables, and verifies the quant engine. When it finishes, continue to **01_INGEST_DATA**.

# COMMAND ----------
%pip install -q "openbb==4.7.2" "openbb-yfinance==1.6.3" "openbb-platform-api==1.3.6" "databricks-sdk>=0.50,<1" "databricks-sql-connector>=4,<5" "databricks-feature-engineering>=0.13.0" "pandas>=2.2,<3" "numpy>=1.26" "plotly>=6,<7"

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
from pathlib import Path
import subprocess, sys
subprocess.run(["openbb-build"], check=True)
repo_root = Path.cwd()
for candidate in [repo_root, *repo_root.parents]:
    if (candidate / "src" / "quant_platform").exists():
        repo_root = candidate; break
sys.path.insert(0, str(repo_root / "src"))
from quant_platform import REGISTRY

# COMMAND ----------
current_catalog = spark.sql("SELECT current_catalog() c").first()["c"]
dbutils.widgets.text("catalog", current_catalog, "Existing Unity Catalog catalog")
dbutils.widgets.text("schema", "openbb_quant", "DBO_Quant schema")
CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
if not CATALOG or not SCHEMA:
    raise ValueError("catalog and schema are required")
spark.sql(f"DESCRIBE CATALOG `{CATALOG}`")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`")
sql_text = (repo_root / "sql" / "quant_platform_schema.sql").read_text().replace("{{CATALOG}}", CATALOG).replace("{{SCHEMA}}", SCHEMA)
for stmt in [s.strip() for s in sql_text.split(";") if s.strip()]:
    executable = "\n".join(line for line in stmt.splitlines() if not line.strip().startswith("--")).strip()
    if executable:
        spark.sql(executable)

# COMMAND ----------
required = ["prices_daily","strategy_runs","strategy_daily","strategy_metrics","portfolio_comparison_runs","monte_carlo_runs","optimization_runs","model_predictions"]
rows=[]
for name in required:
    spark.table(f"{CATALOG}.{SCHEMA}.{name}").limit(1).collect()
    rows.append((name,"READY"))
display(spark.createDataFrame(rows,["component","status"]))
print("Available built-in strategies:", REGISTRY.names())
print(f"\nSETUP COMPLETE: {CATALOG}.{SCHEMA}")
print("NEXT → open notebooks/01_INGEST_DATA.py")