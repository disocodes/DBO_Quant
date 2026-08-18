# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Setup
# MAGIC Run this notebook **once** after cloning the repo. It installs dependencies, creates/updates the selected Unity Catalog schema, records that namespace as the canonical DBO_Quant deployment, and verifies the quant engine. When it finishes, continue to **01_INGEST_DATA**.

# COMMAND ----------
%pip install -q "openbb==4.7.2" "openbb-yfinance==1.6.3" "openbb-platform-api==1.3.6" "databricks-sdk>=0.50,<1" "databricks-sql-connector>=4,<5" "databricks-feature-engineering>=0.13.0" "pandas>=2.2,<3" "numpy>=1.26" "plotly>=6,<7"

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
from pathlib import Path
from datetime import datetime, timezone
import subprocess, sys
subprocess.run(["openbb-build"], check=True)
repo_root = Path.cwd()
for candidate in [repo_root, *repo_root.parents]:
    if (candidate / "src" / "quant_platform").exists():
        repo_root = candidate; break
sys.path.insert(0, str(repo_root / "src"))
from quant_platform import REGISTRY
from quant_platform.location import MARKER_TABLE, PROJECT_ID

# COMMAND ----------
current_catalog = spark.sql("SELECT current_catalog() c").first()["c"]
dbutils.widgets.text("catalog", current_catalog, "Unity Catalog catalog for DBO_Quant")
dbutils.widgets.text("schema", "openbb_quant", "DBO_Quant schema")
CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
if not CATALOG or not SCHEMA:
    raise ValueError("catalog and schema are required")
spark.sql(f"DESCRIBE CATALOG `{CATALOG}`")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`")

for sql_path in sorted((repo_root / "sql").glob("*.sql")):
    print("Applying", sql_path.name)
    sql_text = sql_path.read_text().replace("{{CATALOG}}", CATALOG).replace("{{SCHEMA}}", SCHEMA)
    for stmt in [s.strip() for s in sql_text.split(";") if s.strip()]:
        executable = "\n".join(line for line in stmt.splitlines() if not line.strip().startswith("--")).strip()
        if executable:
            spark.sql(executable)

marker = f"`{CATALOG}`.`{SCHEMA}`.`{MARKER_TABLE}`"
spark.sql(f"DELETE FROM {marker} WHERE project_id = '{PROJECT_ID}'")
initialized_at = datetime.now(timezone.utc).replace(tzinfo=None)
spark.createDataFrame([
    (PROJECT_ID, CATALOG, SCHEMA, initialized_at, 1)
], ["project_id", "catalog_name", "schema_name", "initialized_at", "config_version"]).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.{MARKER_TABLE}")

# COMMAND ----------
required = [
    MARKER_TABLE,
    "prices_daily", "strategy_runs", "strategy_daily", "strategy_metrics",
    "portfolio_comparison_runs", "monte_carlo_runs", "optimization_runs",
    "optimization_backtest_metrics", "optimization_rebalance_runs",
    "optimization_rebalance_events", "optimization_rebalance_daily", "model_predictions",
]
rows=[]
for name in required:
    spark.table(f"{CATALOG}.{SCHEMA}.{name}").limit(1).collect()
    rows.append((name,"READY"))
display(spark.createDataFrame(rows,["component","status"]))
print("Available built-in strategies:", REGISTRY.names())
print(f"\nSETUP COMPLETE: {CATALOG}.{SCHEMA}")
print("This namespace is now discoverable by DBO_Quant workflows.")
print("NEXT → open notebooks/01_INGEST_DATA.py")