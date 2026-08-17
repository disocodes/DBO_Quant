# Databricks notebook source
# MAGIC %md
# MAGIC # Quant Platform — Monte Carlo Worker
# MAGIC Portfolio Visualizer-style forward simulation, intended to run as a Databricks Job.

# COMMAND ----------
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from pyspark.sql import functions as F

try:
    _here = Path(__file__).resolve()
    sys.path.insert(0, str(_here.parents[1] / "src"))
except Exception:
    pass

from quant_platform import simulate_portfolio

# COMMAND ----------
PARAMS = {
    "catalog": "main",
    "schema": "openbb_quant",
    "portfolio_id": "",
    "symbols": "SPY,IEF,GLD",
    "weights": "0.6,0.3,0.1",
    "history_start": "2010-01-01",
    "horizon_days": "2520",
    "n_simulations": "10000",
    "method": "historical_bootstrap",
    "initial_value": "100000",
    "seed": "42",
    "block_size": "5",
    "sample_path_count": "50",
    "rebalance_every_days": "21",
}
for k, default in PARAMS.items():
    try:
        dbutils.widgets.text(k, default)
        PARAMS[k] = dbutils.widgets.get(k)
    except Exception:
        PARAMS[k] = os.getenv(k.upper(), default)

catalog = PARAMS["catalog"]
schema = PARAMS["schema"]
portfolio_id = PARAMS["portfolio_id"] or None
symbols = [s.strip().upper() for s in PARAMS["symbols"].split(",") if s.strip()]
weights = [float(x) for x in PARAMS["weights"].split(",") if x.strip()]
if len(symbols) != len(weights):
    raise ValueError("symbols and weights must have the same length")
history_start = PARAMS["history_start"]
horizon_days = int(PARAMS["horizon_days"])
n_simulations = int(PARAMS["n_simulations"])
method = PARAMS["method"]
initial_value = float(PARAMS["initial_value"])
seed = int(PARAMS["seed"])
block_size = int(PARAMS["block_size"])
sample_path_count = int(PARAMS["sample_path_count"])
rebalance_every_days = int(PARAMS["rebalance_every_days"])

# If portfolio_id is supplied, the latest weighted holdings are authoritative and
# override the symbols/weights passed in the request. This makes saved portfolios
# first-class Monte Carlo inputs rather than merely metadata.
portfolio_as_of_date = None
if portfolio_id:
    holdings_sdf = (spark.table(f"{catalog}.{schema}.portfolio_holdings")
                    .where(F.col("portfolio_id") == portfolio_id)
                    .where(F.col("weight").isNotNull()))
    latest = holdings_sdf.agg(F.max("as_of_date").alias("as_of_date")).first()["as_of_date"]
    if latest is None:
        raise ValueError(f"No weighted holdings found for portfolio_id={portfolio_id!r}")
    holdings_pdf = (holdings_sdf.where(F.col("as_of_date") == latest)
                    .select("symbol", "weight").toPandas())
    symbols = [str(x).upper() for x in holdings_pdf["symbol"].tolist()]
    weights = [float(x) for x in holdings_pdf["weight"].tolist()]
    portfolio_as_of_date = str(latest)

# COMMAND ----------
prices_pdf = (
    spark.table(f"{catalog}.{schema}.prices_daily")
    .where(F.col("symbol").isin(symbols))
    .where(F.col("date") >= F.lit(history_start))
    .select("date", "symbol", F.coalesce("adjusted_close", "close").alias("price"))
    .toPandas()
)
if prices_pdf.empty:
    raise ValueError("No historical prices found for Monte Carlo input")
prices = prices_pdf.pivot_table(index="date", columns="symbol", values="price", aggfunc="last").sort_index()[symbols].ffill().dropna()
asset_returns = prices.pct_change(fill_method=None).dropna()

result = simulate_portfolio(
    asset_returns,
    pd.Series(weights, index=symbols),
    initial_value=initial_value,
    horizon_days=horizon_days,
    n_simulations=n_simulations,
    method=method,
    seed=seed,
    block_size=block_size,
    sample_path_count=sample_path_count,
    rebalance_every_days=rebalance_every_days,
)

# COMMAND ----------
now = datetime.now(timezone.utc).replace(tzinfo=None)
run = pd.DataFrame([{
    "mc_run_id": result.run_id,
    "portfolio_id": portfolio_id or "",
    "method": method,
    "initial_value": initial_value,
    "horizon_days": horizon_days,
    "n_simulations": n_simulations,
    "rebalance_every_days": rebalance_every_days,
    "seed": seed,
    "parameters_json": json.dumps({
        "symbols": symbols, "weights": weights, "history_start": history_start,
        "block_size": block_size, "sample_path_count": sample_path_count,
        "rebalance_every_days": rebalance_every_days, "portfolio_as_of_date": portfolio_as_of_date
    }),
    "status": "COMPLETED",
    "source_engine": "quant_platform.monte_carlo",
    "created_at": now,
    "completed_at": now,
    "summary_json": json.dumps(result.summary),
}])
spark.createDataFrame(run).write.mode("append").saveAsTable(f"{catalog}.{schema}.monte_carlo_runs")

pct = result.percentiles.reset_index().rename(columns={"p1": "p01", "p5": "p05"})
pct.insert(0, "mc_run_id", result.run_id)
# Ensure schema names are exactly p01, p05, ...
rename_map = {"p1":"p01", "p5":"p05"}
pct = pct.rename(columns=rename_map)
cols = ["mc_run_id", "day", "p01", "p05", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]
spark.createDataFrame(pct[cols]).write.mode("append").saveAsTable(f"{catalog}.{schema}.monte_carlo_percentiles")

paths = result.sample_paths.reset_index().melt(id_vars="day", var_name="path_id", value_name="value")
paths.insert(0, "mc_run_id", result.run_id)
spark.createDataFrame(paths[["mc_run_id", "day", "path_id", "value"]]).write.mode("append").saveAsTable(f"{catalog}.{schema}.monte_carlo_sample_paths")

print(json.dumps({"mc_run_id": result.run_id, **result.summary}, indent=2))
