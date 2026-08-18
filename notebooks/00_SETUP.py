# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Setup
# MAGIC Run this notebook on first installation and again only when applying repository updates/migrations.
# MAGIC
# MAGIC **First run:** choose an existing Unity Catalog **catalog**. DBO_Quant creates the schema and tables it owns if they do not exist.
# MAGIC
# MAGIC **Rerun:** if DBO_Quant is already installed, this notebook detects the existing deployment and reuses the same catalog/schema automatically. Existing tables and research data are preserved.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Install Runtime Dependencies
# MAGIC Install the pinned OpenBB, Databricks, data-processing, and visualization packages required by setup and the platform notebooks.

# COMMAND ----------
%pip install -q "openbb==4.7.2" "openbb-yfinance==1.6.3" "openbb-platform-api==1.3.6" "databricks-sdk>=0.50,<1" "databricks-sql-connector>=4,<5" "databricks-feature-engineering>=0.13.0" "pandas>=2.2,<3" "numpy>=1.26" "plotly>=6,<7"

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Restart Python
# MAGIC Restart the notebook Python process so the newly installed packages are available to subsequent cells.

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Load the DBO_Quant Project
# MAGIC Build the OpenBB extensions, locate the repository root, and import the project registry and canonical namespace-discovery helpers.

# COMMAND ----------
from pathlib import Path
from datetime import datetime, timezone
import subprocess, sys

subprocess.run(["openbb-build"], check=True)
repo_root = Path.cwd()
for candidate in [repo_root, *repo_root.parents]:
    if (candidate / "src" / "quant_platform").exists():
        repo_root = candidate
        break
sys.path.insert(0, str(repo_root / "src"))

from quant_platform import REGISTRY
from quant_platform.location import (
    MARKER_TABLE,
    PROJECT_ID,
    DEFAULT_SCHEMA,
    discover_with_spark,
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Detect an Existing Deployment
# MAGIC Search for the DBO_Quant marker table before presenting configuration defaults. Existing deployments are reused rather than silently duplicated.

# COMMAND ----------
# Detect an existing DBO_Quant deployment before choosing defaults.
existing = None
try:
    existing = discover_with_spark(spark)
except RuntimeError as exc:
    message = str(exc)
    if "No DBO_Quant deployment marker" not in message:
        # Multiple deployments are deliberately not guessed.
        raise

if existing:
    default_catalog = existing.catalog
    default_schema = existing.schema
    print(f"EXISTING DBO_QUANT DEPLOYMENT DETECTED: {existing.namespace}")
    print("Setup will reuse this namespace and preserve existing data.")
else:
    default_catalog = spark.sql("SELECT current_catalog() c").first()["c"]
    default_schema = DEFAULT_SCHEMA
    print("FIRST DBO_QUANT SETUP")
    print("Select an existing Unity Catalog catalog below. DBO_Quant will create its schema/tables there.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Select and Validate the Unity Catalog Namespace
# MAGIC Configure the target catalog/schema, prevent accidental retargeting on reruns, and create the DBO_Quant schema inside the selected existing catalog.

# COMMAND ----------
dbutils.widgets.text("catalog", default_catalog, "Unity Catalog catalog for DBO_Quant")
dbutils.widgets.text("schema", default_schema, "DBO_Quant schema")
CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()

if not CATALOG or not SCHEMA:
    raise ValueError("catalog and schema are required")

if existing and (CATALOG != existing.catalog or SCHEMA != existing.schema):
    raise RuntimeError(
        f"DBO_Quant is already installed at {existing.namespace}. "
        "Setup will not silently create or retarget a second deployment. "
        "Use the detected catalog/schema or deliberately create a separate deployment outside this setup flow."
    )

# The catalog is an administrative Unity Catalog object and must already exist.
# DBO_Quant owns the schema and tables below it.
spark.sql(f"DESCRIBE CATALOG `{CATALOG}`")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Apply Database Schema and Register the Project
# MAGIC Execute the repository SQL definitions/migrations with idempotent semantics, then create the canonical DBO_Quant deployment marker only when it does not already exist.

# COMMAND ----------
# Apply schema definitions/migrations. The SQL uses IF NOT EXISTS for managed objects,
# so rerunning setup does not delete or recreate existing research tables/data.
for sql_path in sorted((repo_root / "sql").glob("*.sql")):
    print("Applying", sql_path.name)
    sql_text = sql_path.read_text().replace("{{CATALOG}}", CATALOG).replace("{{SCHEMA}}", SCHEMA)
    for stmt in [s.strip() for s in sql_text.split(";") if s.strip()]:
        executable = "\n".join(
            line for line in stmt.splitlines() if not line.strip().startswith("--")
        ).strip()
        if executable:
            spark.sql(executable)

# Register the canonical location only on first installation. Preserve the original
# initialized_at value on ordinary reruns.
marker = f"`{CATALOG}`.`{SCHEMA}`.`{MARKER_TABLE}`"
marker_count = spark.sql(
    f"SELECT COUNT(*) AS n FROM {marker} WHERE project_id = '{PROJECT_ID}'"
).first()["n"]

if marker_count == 0:
    initialized_at = datetime.now(timezone.utc).replace(tzinfo=None)
    spark.createDataFrame(
        [(PROJECT_ID, CATALOG, SCHEMA, initialized_at, 1)],
        ["project_id", "catalog_name", "schema_name", "initialized_at", "config_version"],
    ).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.{MARKER_TABLE}")
    print(f"Registered canonical DBO_Quant namespace: {CATALOG}.{SCHEMA}")
else:
    print(f"Canonical DBO_Quant namespace already registered: {CATALOG}.{SCHEMA}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 7. Verify the Installation
# MAGIC Confirm the required tables are readable, show the registered strategy catalogue, and print the next notebook in the workflow.

# COMMAND ----------
required = [
    MARKER_TABLE,
    "prices_daily",
    "strategy_runs",
    "strategy_daily",
    "strategy_metrics",
    "portfolio_comparison_runs",
    "monte_carlo_runs",
    "optimization_runs",
    "optimization_backtest_metrics",
    "optimization_rebalance_runs",
    "optimization_rebalance_events",
    "optimization_rebalance_daily",
    "model_predictions",
]
rows = []
for name in required:
    spark.table(f"{CATALOG}.{SCHEMA}.{name}").limit(1).collect()
    rows.append((name, "READY"))

display(spark.createDataFrame(rows, ["component", "status"]))
print("Available built-in strategies:", REGISTRY.names())
print(f"\nSETUP COMPLETE: {CATALOG}.{SCHEMA}")
print("Existing data was preserved." if existing else "First installation complete.")
print("NEXT → open notebooks/01_INGEST_DATA.py")
